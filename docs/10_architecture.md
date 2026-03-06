# 10_architecture — TryOnLab

## 1) Архитектурные цели
- **Быстрый MVP без мусора в коде**: минимум сущностей, но всё управляемо (jobs, статусы, ретраи).
- **Провайдеры взаимозаменяемы**: Grok / OpenAI / любое третье.
- **Никаких “синхронных чудес”**: генерация всегда через **job** (создал → ждёшь → получил).
- **Изоляция ответственности**: бот = UX, API = управление задачами и доступ к данным, worker = выполнение тяжёлого.

---

## 2) Компоненты (runtime)
### Контейнеры (docker-compose)
- **api**: FastAPI (REST), управление jobs, валидации, выдача статусов/результатов
- **worker**: фоновые задачи (вызовы AI, загрузка/выгрузка медиа, ретраи)
- **bot**: aiogram, wizard, кнопки, polling статусов
- **postgres**: данные (users/jobs/settings/results)
- **redis**: очередь/статусы/локи/rate-limit
- **storage**: MinIO (S3) *или* локально для V1 (настройкой)

> В V1 допустимо объединить worker в api процессом, но **рекомендуется отдельный worker**, чтобы API не “умирал” под GPU/таймаутами.

---

## 3) Слои кода (внутри репозитория)

```
app/
  core/        # конфиг, логирование, константы
  db/          # модели, сессии, alembic
  api/         # FastAPI роутеры, схемы, зависимости, auth (если нужен)
  bot/         # aiogram wizard, keyboards, состояния, UX
  providers/   # Grok/OpenAI/... (единый интерфейс)
  services/    # бизнес-логика jobs, storage, prompts, media
```

### Зоны ответственности
- **core/**
  - `config.py`: ENV → настройки (pydantic settings)
  - `logging.py`: формат логов, корреляция по `job_id`
- **db/**
  - `models.py`: User, Job, JobResult, UserSettings
  - `session.py`: async SQLAlchemy session
  - `migrations/`: Alembic
- **api/**
  - `routers/jobs.py`: create/poll/retry/video
  - `routers/health.py`: readiness/liveness
  - `deps.py`: DI для db/redis/storage/providers
- **bot/**
  - `wizard.py`: сценарий V1
  - `keyboards.py`: inline кнопки (provider toggle, presets 1..5)
  - `states.py`: FSM состояния
- **providers/**
  - `base.py`: `ProviderBase`, ошибки, capability flags
  - `registry.py`: регистрация и выбор провайдера
  - `grok.py`: xAI image/video calls
  - `openai.py`: OpenAI image/video calls (sora-2 опционально)
- **services/**
  - `jobs.py`: создание job, постановка в очередь, обновления статуса
  - `storage.py`: загрузка/выдача media (S3/локально), TTL
  - `prompts.py`: шаблоны промптов + пресеты видео 1..5
  - `media.py`: минимальная предобработка (проверки фото, размер, конвертация)

---

## 4) Job-модель (основа проекта)

### Статусы job
- `created` → `queued` → `running` → `done`
- `failed` (с reason + code)
- `expired` (TTL/cleanup)

### Типы job
- `tryon_image`
- `tryon_video`

> Видео job всегда ссылается на исходное `image_result` или `job_id` изображения.

### Политика ретраев
- Ретрай = новая попытка генерации **в рамках того же job** (attempt++), либо создание нового job, если нужно сохранять историю.
- В V1 проще: attempt++ и перезаписать результат (историю хранить минимально: last_error + attempts).

---

## 5) Потоки данных (sequence)

### A) Генерация изображения (Try-on)
1) **Bot**
   - собирает входы (фото товара, фото человека, fit pref, (опц.) мерки)
   - вызывает `POST /jobs` (type=tryon_image)
2) **API**
   - сохраняет Job в Postgres
   - сохраняет медиа (storage) → получает `input_urls`
   - ставит задачу в Redis очередь
   - возвращает `job_id`
3) **Worker**
   - берёт job из очереди
   - выбирает провайдера (по job.user_setting или request)
   - собирает prompt pack
   - вызывает `Provider.generate_image(...)`
   - сохраняет результат (storage)
   - обновляет job в Postgres + ставит быстрый статус в Redis
4) **Bot**
   - poll `GET /jobs/{job_id}`
   - когда `done` → отправляет картинку пользователю

### B) Генерация видео (Preset 1..5)
1) Пользователь нажимает кнопку `🎬 1..5`
2) Bot вызывает `POST /jobs/{image_job_id}/video?preset=3`
3) API создаёт job типа `tryon_video`, связывает с `image_job_id`
4) Worker генерирует видео по preset-промпту
5) Bot получает `video_url` и отправляет пользователю

---

## 6) Провайдеры (плагинный дизайн)

### ProviderBase (контракт)
- `generate_image(inputs, prompt_pack) -> ProviderResult`
- `generate_video(image_result, video_prompt) -> ProviderResult`
- `capabilities: {video: bool, async_video: bool, image_edit: bool}`

### Registry
- `ProviderRegistry.get(name) -> ProviderBase`
- `ProviderRegistry.list() -> [names]`
- allowlist применяется на уровне конфига, чтобы мгновенно “вырубить” проблемного провайдера без релиза.

### Ошибки провайдеров (единая классификация)
- `AuthError` (неверный ключ)
- `RateLimitError` (лимиты)
- `BadRequestError` (неверные входы/промпт/формат)
- `TemporaryError` (таймауты, 5xx)
- `UnsupportedError` (нет видео, нет image_edit и т.д.)

> В API/worker ошибки маппятся в `job.failed` с `error_code`, `error_message` и `is_retryable`.

---

## 7) Хранилище медиа (storage)
### Варианты
- **MinIO/S3** (рекомендуется)
- **Local FS** (для локального теста)

### Что храним
- input: `product.jpg`, `person.jpg`
- derived: (опционально) `normalized_person.jpg` (если делаем ресайз/конвертацию)
- output: `result.jpg`
- output video: `result.mp4`

### Именование ключей (пример)
- `tryon/{job_id}/input/product.jpg`
- `tryon/{job_id}/input/person.jpg`
- `tryon/{job_id}/output/image.jpg`
- `tryon/{job_id}/output/video_preset_3.mp4`

### TTL и очистка
- `RETENTION_HOURS` (например 72)
- отдельный cleanup task (worker cron):
  - помечает job `expired`
  - удаляет медиа ключи
  - оставляет метаданные (для метрик качества)

---

## 8) База данных (high-level)

### Таблицы (минимум V1)
**users**
- `id` (int/bigint)
- `tg_user_id` (unique)
- `created_at`
- `last_seen_at`

**user_settings**
- `user_id` (FK)
- `provider` (grok/openai/…)
- `language` (опционально)

**jobs**
- `id` (uuid/ulid)
- `user_id` (FK)
- `type` (image/video)
- `status`
- `provider`
- `preset` (nullable)
- `attempts`
- `fit_pref` (nullable)
- `height_cm` (nullable)
- `measurements_json` (nullable)
- `input_media_json` (urls/keys)
- `result_media_json` (urls/keys)
- `error_code`, `error_message`
- `created_at`, `updated_at`, `expires_at`
- `parent_job_id` (nullable, для video от image)

> В V1 достаточно `jobs` + `users` + `user_settings`. Историю событий (`job_events`) можно добавить в V2.

---

## 9) Redis (ключи и назначение)
- `queue:jobs` — очередь задач (list/stream)
- `job:{job_id}:status` — быстрый статус/прогресс (TTL)
- `lock:job:{job_id}` — защита от двойного выполнения
- `rl:user:{tg_user_id}` — rate limit (например N запросов/час)

---

## 10) API дизайн (контракт)
### POST /jobs
**Назначение**: создать job на изображение  
**Body**:
- `provider` (опц.)
- `fit_pref`
- `height_cm` (опц.)
- `measurements` (опц.)
- `product_image` (file/url)
- `person_image` (file/url)

**Response**:
- `job_id`, `status=queued`

### GET /jobs/{job_id}
**Response**:
- `status`, `progress`
- `result_image_url` / `result_video_url`
- `error_code`, `error_message`

### POST /jobs/{job_id}/retry
**Назначение**: ретрай изображения  
**Response**: новый status / attempts

### POST /jobs/{job_id}/video?preset=1..5
**Назначение**: создать video job от image job  
**Response**: `video_job_id`

---

## 11) Конфигурация (ENV)
- `DATABASE_URL`
- `REDIS_URL`
- `STORAGE_BACKEND=s3|local`
- `STORAGE_S3_ENDPOINT`, `STORAGE_S3_BUCKET`, `STORAGE_S3_ACCESS_KEY`, `STORAGE_S3_SECRET_KEY`
- `RETENTION_HOURS`
- `AI_PROVIDER_DEFAULT`
- `AI_PROVIDER_ALLOWLIST`
- `XAI_API_KEY`
- `OPENAI_API_KEY`
- `HTTP_TIMEOUT_SECONDS`
- `MAX_RETRIES`

---

## 12) Observability (минимально, но полезно)
### Логи
- корреляция по `job_id`
- уровни: INFO для этапов, WARNING для retryable проблем, ERROR для fail

### Метрики (V1 light)
- `jobs_created_total{type,provider}`
- `jobs_done_total{type,provider}`
- `jobs_failed_total{type,provider,error_code}`
- `job_duration_seconds{type,provider}` (p50/p95)

Можно начать просто с логов + выгрузки в таблицу, а Prometheus подключить позже.

---

## 13) Границы V1 (чтобы Codex не расползся)
- Никаких “умных” автоматических масок/pose в V1.
- Никаких сложных UI-админок.
- Только 2 провайдера: grok и openai (с allowlist).
- Только 1 изображение на результат + ретраи.
- Видео только из итогового изображения по 5 пресетам.

---

## 14) Decision log (почему так)
- **Job-first**: иначе бот превращается в “зависает, таймаут, попробуйте снова”.
- **Provider plugins**: рынок моделей меняется быстрее, чем люди успевают прочитать README.
- **Separate worker**: API должен отвечать быстро, даже когда провайдер тормозит/лимитит.
- **TTL медиа**: тестовый проект не должен становиться архивом чужих фото.

---
