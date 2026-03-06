# 50_data_model — TryOnLab (Postgres + Redis + Storage)

## 1) Цели модели данных (V1)
- Хранить **минимум сущностей**, чтобы прототип работал стабильно.
- Поддержать:
  - панель (panel message id)
  - сохранение и реюз **user photo**
  - jobs для image/video, статусы, ошибки, ретраи
  - провайдер per-user и per-job
  - TTL/retention: авто-экспирация медиа и задач
- Быть расширяемой под V2:
  - интеграция SIS/SizeBot
  - job events/audit trail
  - поинты/платёжка
  - multi-view (front/side/back), garment params

---

## 2) Entity Map (V1)
### Основные таблицы
- `users` — пользователь Telegram
- `user_settings` — настройки пользователя (provider, active user photo и т.д.)
- `user_photos` — сохранённые фото пользователя (реюз для генераций)
- `jobs` — задачи генерации (image/video), входы/выходы/статусы

### Опционально (V2)
- `job_events` — события/прогресс, диагностика качества
- `user_credits` / `transactions` — поинты/платёжка
- `garments` — если выделять каталог отдельно (не нужно в V1)

---

## 3) ER-логика (словами)
- `users (1) -> (1) user_settings`
- `users (1) -> (N) user_photos`
- `users (1) -> (N) jobs`
- `jobs (N) -> (1) users`
- `jobs (N) -> (0/1) jobs.parent_job`  
  (video job ссылается на image job)

---

## 4) Таблицы (рекомендуемая схема)

> Примечание: типы и названия колонок приведены “как должно быть” для Alembic/SQLAlchemy. Можно использовать UUID/ULID для `jobs.id`.

### 4.1 `users`
**Назначение:** идентификация Telegram пользователя, панель, базовые метки.

Поля:
- `id` BIGSERIAL PK
- `tg_user_id` BIGINT NOT NULL UNIQUE
- `tg_chat_id` BIGINT NOT NULL  (в личке обычно равен tg_user_id, но лучше хранить отдельно)
- `panel_message_id` BIGINT NULL  (message id панели)
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `last_seen_at` TIMESTAMPTZ NULL

Индексы:
- `UNIQUE (tg_user_id)`
- `INDEX (last_seen_at)` (опционально)

---

### 4.2 `user_settings`
**Назначение:** быстрый доступ к настройкам UX и провайдера.

Поля:
- `user_id` BIGINT PK/FK -> users.id (1:1)
- `provider` TEXT NOT NULL DEFAULT 'grok'
- `language` TEXT NULL (ru/ua/en, опционально)
- `active_user_photo_id` BIGINT NULL FK -> user_photos.id
- `retention_days_user_photos` INT NULL  (если хотите user-photo TTL по умолчанию)
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Индексы:
- `INDEX (provider)`
- `INDEX (active_user_photo_id)`

Ограничения:
- `provider` ограничить enum/чек-констрейнтом по allowlist (можно на уровне приложения).

---

### 4.3 `user_photos`
**Назначение:** сохранённые фото пользователя для реюза.

Поля:
- `id` BIGSERIAL PK
- `user_id` BIGINT NOT NULL FK -> users.id
- `storage_key` TEXT NOT NULL  (S3/MinIO key или локальный путь)
- `sha256` TEXT NULL  (дедуп по желанию)
- `width` INT NULL
- `height` INT NULL
- `mime_type` TEXT NULL
- `file_size` BIGINT NULL
- `is_deleted` BOOLEAN NOT NULL DEFAULT false
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `deleted_at` TIMESTAMPTZ NULL

Индексы:
- `INDEX (user_id, created_at DESC)`
- `INDEX (user_id, is_deleted)`
- `UNIQUE (user_id, sha256)` (опционально, если хотите дедуп)

Ограничения/правила:
- В V1 допускается хранить максимум `MAX_USER_PHOTOS` (например 5) на уровне приложения.
- Активное фото хранится в `user_settings.active_user_photo_id`.

---

### 4.4 `jobs`
**Назначение:** единый журнал задач генерации.

Поля:
- `id` UUID/ULID PK
- `user_id` BIGINT NOT NULL FK -> users.id

**Тип и связи:**
- `type` TEXT NOT NULL  ('tryon_image' | 'tryon_video')
- `parent_job_id` UUID/ULID NULL FK -> jobs.id (для видео)

**Провайдер/модель:**
- `provider` TEXT NOT NULL
- `provider_model` TEXT NULL (например 'grok-imagine-image', 'sora-2', etc.)
- `prompt_version` TEXT NOT NULL DEFAULT 'v1.0'

**Входные параметры:**
- `fit_pref` TEXT NULL ('slim'|'regular'|'oversize')
- `height_cm` INT NULL
- `measurements_json` JSONB NULL  (например {"chest":106,"waist":86,...})
- `preset` INT NULL  (1..5 для видео)

**Входные медиа:**
- `product_media_key` TEXT NULL   (storage key)
- `user_photo_id` BIGINT NULL FK -> user_photos.id
- `user_media_key` TEXT NULL      (если не используем user_photos, либо временно)
- `inputs_json` JSONB NULL        (расширяемое поле: дополнительные ссылки/метаданные)

**Результаты:**
- `result_image_key` TEXT NULL
- `result_video_key` TEXT NULL
- `result_json` JSONB NULL  (URLs, размеры, hashes, provider raw metadata)

**Статусы:**
- `status` TEXT NOT NULL  ('created'|'queued'|'running'|'done'|'failed'|'expired')
- `progress` INT NULL  (0..100, опционально)
- `attempts` INT NOT NULL DEFAULT 0
- `max_attempts` INT NOT NULL DEFAULT 2
- `is_retryable` BOOLEAN NOT NULL DEFAULT false

**Ошибки:**
- `error_code` TEXT NULL  (auth|rate_limit|bad_request|timeout|provider_5xx|unsupported)
- `error_message` TEXT NULL

**Время:**
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `started_at` TIMESTAMPTZ NULL
- `finished_at` TIMESTAMPTZ NULL
- `expires_at` TIMESTAMPTZ NULL  (created_at + RETENTION_HOURS)

Индексы:
- `INDEX (user_id, created_at DESC)`
- `INDEX (status, created_at DESC)`
- `INDEX (provider, created_at DESC)`
- `INDEX (parent_job_id)`
- `INDEX (expires_at)`
- `INDEX (user_photo_id)` (если активно используем)

Ограничения:
- `preset` должен быть NULL для image-job и NOT NULL для video-job (можно enforce в приложении или CHECK).
- `parent_job_id` обязателен для video-job (логика приложения).

---

## 5) JSON структуры (рекомендации)

### 5.1 `measurements_json`
Пример:
```json
{
  "height_cm": 182,
  "chest_cm": 106,
  "waist_cm": 86,
  "hips_cm": 102,
  "shoulders_cm": 50,
  "inseam_cm": 84
}
```

### 5.2 `result_json`
Пример:
```json
{
  "image": {"url":"https://...","width":1024,"height":1536,"mime":"image/jpeg"},
  "video": {"url":"https://...","duration_sec":4},
  "provider_raw": {"request_id":"...","seed":"..."}
}
```

---

## 6) Redis keys (V1)
Redis используется для:
- очереди задач
- быстрых статусов (чтобы не дёргать БД каждую секунду)
- локов (защита от двойного воркера)
- rate limit

### 6.1 Queue
- `queue:jobs` — список/стрим задач (формат зависит от выбранного брокера)

Payload (пример):
```json
{"job_id":"01J...","type":"tryon_image"}
```

### 6.2 Быстрый статус
- `job:{job_id}:status` → JSON + TTL  
Пример:
```json
{"status":"running","progress":35}
```

TTL: 1–24 часа (достаточно для polling).

### 6.3 Locks
- `lock:job:{job_id}` → значение=worker_id, TTL=60–300 сек  
Используется перед выполнением job.

### 6.4 Rate-limit
- `rl:user:{tg_user_id}` → счётчик с TTL (например 1 час/сутки)

---

## 7) Storage key conventions (S3/MinIO/local)
Единый формат ключей упрощает очистку и аудит.

### 7.1 Временные входы/выходы job (TTL)
- `tryon/jobs/{job_id}/input/product.jpg`
- `tryon/jobs/{job_id}/input/person.jpg` (если не user_photos)
- `tryon/jobs/{job_id}/output/image.jpg`
- `tryon/jobs/{job_id}/output/video_preset_{N}.mp4`

### 7.2 Долговременные user photos (до удаления пользователем)
- `tryon/users/{tg_user_id}/photos/{photo_id}.jpg`

---

## 8) Retention / Expiration (важно)
### 8.1 Job retention
- `jobs.expires_at = created_at + RETENTION_HOURS`
- Cleanup задача:
  - помечает job `expired`
  - удаляет storage keys для input/output (job scope)
  - оставляет метаданные (jobs строку) для метрик качества

### 8.2 User photo retention
По умолчанию:
- сохраняем до ручного удаления пользователем  
Опционально:
- `retention_days_user_photos` в `user_settings` (30/90 дней)
- периодический cleanup удаляет старые, если политика включена

---

## 9) Миграции (Alembic) — правила
1) Любое изменение схемы — через Alembic миграцию.
2) JSONB поля расширяемы: добавление новых ключей не требует миграции.
3) CHECK-констрейнты можно держать минимальными, часть правил enforce на уровне приложения.
4) Индексы добавлять только те, что нужны под реальные запросы (polling, списки, отчёты).

### Рекомендуемые миграции V1
- `001_create_users`
- `002_create_user_settings`
- `003_create_user_photos`
- `004_create_jobs`

---

## 10) Запросы (профиль нагрузки)
### 10.1 Чаще всего
- получить/обновить `panel_message_id`
- обновить `user_settings.provider` и `active_user_photo_id`
- создать job
- poll статуса job (лучше через Redis, но fallback — БД)

### 10.2 Списки
- последние N jobs пользователя (история результатов)
- список `user_photos` пользователя

Индексы выше под это рассчитаны.

---

## 11) Расширение под V2 (без боли)
### SIS/SizeBot
Добавляем в `jobs.inputs_json`:
- `sis_product_id`
- `size_profile_id`
- `garment_params` (мерки изделия, материал, stretch)

Если нужно нормализовать:
- заводим отдельную таблицу `garment_specs` и ссылку из jobs.

### Job events
Добавляем таблицу:
- `job_events(job_id, ts, level, event_type, payload_json)`
Это полезно для дебага “почему именно этот провайдер развалился”.

### Поинты
Добавляем:
- `user_wallets`
- `transactions`
- `pricing_rules`

---

## 12) Definition of Done (data model V1)
- Таблицы: `users`, `user_settings`, `user_photos`, `jobs`
- Индексы под polling и списки
- Redis keys: queue/status/locks/rate-limit
- Storage keys: job-scope + user-scope
- Cleanup стратегия: job TTL и user-photo delete

---
