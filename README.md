# TryOnLab

PR-00 (bootstrap) для проекта виртуальной примерки в Telegram: базовый каркас API, bot, docker-окружения и документации.

## Что входит в PR-00
- FastAPI каркас с endpoint `/health`.
- aiogram bot каркас с командами `/start` и `/help`.
- Docker Compose окружение: `api`, `bot`, `postgres`, `redis` (+ optional `minio` в комментариях).
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
