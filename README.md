# TryOnLab

PR-00 (bootstrap) для проекта виртуальной примерки в Telegram: базовый каркас API, bot, docker-окружения и документации.

## Что входит в PR-00
- FastAPI каркас с endpoint `/health`.
- aiogram bot каркас с командами `/start` и `/help`.
- Docker Compose окружение: `api`, `bot`, `postgres`, `redis` (+ optional `minio` profile).
- Базовая конфигурация через `.env`.
- Подготовленная структура каталогов под следующие PR-01..PR-08.

## Структура проекта
```text
tryonlab/
  app/
    api/
      main.py
      routers/
        health.py
    bot/
      main.py
    core/
      config.py
      logging.py
      constants.py
    db/
      base.py
      models.py
      session.py
    providers/
      __init__.py
    services/
      __init__.py
  docs/
  .env.example
  docker-compose.yml
  requirements.txt
  DOCS.md
```

## Quick Start
1. Скопировать env-файл:
   ```bash
   cp .env.example .env
   ```
2. Поднять сервисы:
   ```bash
   docker compose up -d --build
   ```
3. Начиная с PR-01, применить миграции:
   ```bash
   docker compose exec api alembic upgrade head
   ```
4. Проверить liveness/readiness API:
   ```bash
   curl http://localhost:8000/health
   ```
5. Посмотреть логи:
   ```bash
   docker compose logs -f api
   docker compose logs -f bot
   ```

## Storage
- По умолчанию используется локальное хранилище (`STORAGE_BACKEND=local`) в `STORAGE_LOCAL_DIR`.
- Для MinIO/S3 включите storage-профиль:
  ```bash
  docker compose --profile storage up -d --build
  ```
- Для S3/MinIO задайте переменные: `STORAGE_S3_ENDPOINT`, `STORAGE_S3_BUCKET`, `STORAGE_S3_ACCESS_KEY`, `STORAGE_S3_SECRET_KEY`.
- Manual check для S3 backend:
  1. Запустить MinIO profile и убедиться, что бакет `tryonlab` создан (`minio-mc`).
  2. Установить `STORAGE_BACKEND=s3` в `.env`.
  3. Выполнить локальные тесты `pytest -q` (покрывают local backend), затем вручную проверить put/get/delete через shell или интеграционный сценарий API/worker.

## ENV (минимум для PR-00)
- `APP_ENV`
- `LOG_LEVEL`
- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL`
- `REDIS_URL`

## Документация
- Общий индекс: [DOCS.md](DOCS.md)
- Базовый обзор: [docs/00_overview.md](docs/00_overview.md)
- Архитектура: [docs/10_architecture.md](docs/10_architecture.md)
- Поток бота: [docs/20_bot_flow.md](docs/20_bot_flow.md)

## Что будет в PR-01+
- Начиная с PR-01, перед первым запуском API нужно выполнить `alembic upgrade head` внутри контейнера `api`.
- Jobs API, очередь и worker — в следующих PR по плану.


## Jobs API (PR-03)
Для прототипа V1 API использует header-идентификацию:
- `X-TG-User-Id` (обязательный)
- `X-TG-Chat-Id` (опциональный, если нет — используется `X-TG-User-Id`)

Endpoints:
- `POST /jobs` — создать image job (входные файлы сохраняются в storage, job уходит в Redis очередь).
- `GET /jobs/{job_id}` — получить статус job (owner-check по `X-TG-User-Id`).
- `POST /jobs/{job_id}/retry` — ретрай для job.
- `POST /jobs/{job_id}/video?preset=1..5` — создать video job на основе готового image job.

Пример создания image job:
```bash
curl -X POST http://localhost:8000/jobs
  -H "X-TG-User-Id: 12345"
  -H "X-TG-Chat-Id: 12345"
  -F "product_image=@./examples/product.jpg"
  -F "person_image=@./examples/person.jpg"
  -F "fit_pref=regular"
  -F 'measurements_json={"chest":92,"waist":74}'
```

Пример polling статуса:
```bash
curl http://localhost:8000/jobs/<job_id>
  -H "X-TG-User-Id: 12345"
```


## Worker и очередь (PR-04)
- Worker запускается отдельным сервисом в compose: `python -m app.worker.main`.
- Общий запуск всех сервисов:
  ```bash
  docker compose up -d --build
  ```
- Логи worker:
  ```bash
  docker compose logs -f --tail=200 worker
  ```

Пример создания тестового job с dummy provider:
```bash
curl -X POST http://localhost:8000/jobs \
  -H "X-TG-User-Id: 12345" \
  -H "X-TG-Chat-Id: 12345" \
  -F "provider=dummy" \
  -F "product_image=@./examples/product.jpg" \
  -F "person_image=@./examples/person.jpg"
```

Микро-проверка очереди/статуса в Redis:
```bash
docker compose exec redis redis-cli LRANGE queue:jobs 0 -1
docker compose exec redis redis-cli GET job:<job_id>:status
```

## Providers (PR-06): Grok/xAI + OpenAI
- Включение провайдеров делается через `.env` и `AI_PROVIDER_ALLOWLIST`.
- Провайдер регистрируется только когда задан API key.

Минимум для Grok:
```env
XAI_API_KEY=
XAI_BASE_URL=https://api.x.ai/v1
XAI_IMAGE_MODEL=grok-imagine-image
XAI_VIDEO_MODEL=grok-imagine-video
```

Минимум для OpenAI:
```env
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_VIDEO_MODEL=sora-2
```

Пример create image job с Grok:
```bash
curl -X POST http://localhost:8000/jobs \
  -H "X-TG-User-Id: 12345" \
  -H "X-TG-Chat-Id: 12345" \
  -F "provider=grok" \
  -F "product_image=@./examples/product.jpg" \
  -F "person_image=@./examples/person.jpg" \
  -F "fit_pref=regular"
```

Пример create video job (preset=1) после `done` image job:
```bash
curl -X POST "http://localhost:8000/jobs/<image_job_id>/video?preset=1" \
  -H "X-TG-User-Id: 12345" \
  -H "X-TG-Chat-Id: 12345"
```

Логи worker:
```bash
docker compose logs -f --tail=200 worker
```

## Bot UX flow (PR-07)
Бот работает по паттерну **одной панели** (single panel message): все экраны рендерятся в том же сообщении через `edit_message_text` + inline keyboard. Входные фото (товар/человек) удаляются best-effort после успешного сохранения; результаты image/video отправляются отдельными сообщениями и не удаляются.

### Happy-path сценарий
1. `/start` — создаётся/переиспользуется panel message.
2. `🧥 Товар` — бот ждёт фото товара, после загрузки ставит ✅.
3. `👤 Моё фото -> ⬆️ Загрузить новое` — бот ждёт фото человека, сохраняет его, делает active, удаляет входное сообщение.
4. `🎯 Посадка` — выбор slim/regular/oversize.
5. `⚡ Генерировать` — создаётся image job, запускается polling, готовая картинка приходит отдельным сообщением.
6. `🔁 Retry` — повтор генерации image для last job.
7. `🎬 Видео -> preset 3` — создаётся video job, после `done` видео отправляется отдельным сообщением.

### Запуск и логи
```bash
docker compose up -d --build
docker compose logs -f --tail=200 api
docker compose logs -f --tail=200 worker
docker compose logs -f --tail=200 bot
```

Быстрая проверка очереди/статусов:
```bash
docker compose exec redis redis-cli LRANGE queue:jobs 0 -1
docker compose exec redis redis-cli GET job:<job_id>:status
```
