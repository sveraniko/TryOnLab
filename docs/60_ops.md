# 60_ops — TryOnLab (Deploy, Runbook, Logs, Migrations)

## 0) Цель документа
Дать “операционную” инструкцию:
- как поднять проект локально и на сервере
- как обновлять код и миграции
- как дебажить проблемы провайдеров
- как чистить медиаданные (TTL)
- какие ENV обязательны

---

## 1) Среда исполнения (assumptions)
- Linux server (Ubuntu/Debian) + Docker + Docker Compose
- Postgres 16
- Redis 7+
- Storage: MinIO (S3) желательно, но локальный FS допустим в тесте
- Внешний доступ: Telegram (bot), провайдер API (xAI/OpenAI)

---

## 2) Конфигурация (ENV)
Файл `.env` (не коммитим). Пример `.env.example` держим в репо.

### 2.1 Обязательные
- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL` (asyncpg)
- `REDIS_URL`
- `AI_PROVIDER_DEFAULT=grok`
- `AI_PROVIDER_ALLOWLIST=grok,openai`
- `XAI_API_KEY` (если grok включен)
- `OPENAI_API_KEY` (если openai включен)

### 2.2 Storage (рекомендовано)
- `STORAGE_BACKEND=s3`
- `STORAGE_S3_ENDPOINT=http://minio:9000`
- `STORAGE_S3_BUCKET=tryonlab`
- `STORAGE_S3_ACCESS_KEY=...`
- `STORAGE_S3_SECRET_KEY=...`
- `STORAGE_S3_REGION=us-east-1` (или любой)

### 2.3 Retention / лимиты
- `RETENTION_HOURS=72` (job media TTL)
- `MAX_USER_PHOTOS=5`
- `HTTP_TIMEOUT_SECONDS=60`
- `MAX_RETRIES=2`
- `RATE_LIMIT_PER_HOUR=...` (опционально)

### 2.4 Опционально (модели)
- `OPENAI_IMAGE_MODEL=...`
- `OPENAI_VIDEO_MODEL=sora-2`

---

## 3) docker-compose (контейнеры)
Рекомендуемая схема:

- `api` (FastAPI)
- `worker` (фоновые jobs)
- `bot` (aiogram)
- `postgres`
- `redis`
- `minio` (если S3 backend)

### 3.1 Порты
- API: 8000 (внутри, наружу по необходимости)
- Postgres: 5432 (наружу обычно не надо)
- Redis: 6379 (наружу обычно не надо)
- MinIO: 9000 (S3), 9001 (console) — наружу опционально

---

## 4) Быстрый старт (локально)
1) Скопировать env:
   - `cp .env.example .env`
2) Поднять сервисы:
   - `docker compose up -d --build`
3) Применить миграции:
   - `docker compose exec api alembic upgrade head`
4) Проверить health:
   - `curl http://localhost:8000/health`
5) Проверить бот:
   - отправить `/start`

---

## 5) Deploy на сервер (стандартный runbook)

### 5.1 Первый деплой
1) Подготовить папку:
   - `/opt/tryonlab/`
2) Клонировать репо:
   - `git clone ... /opt/tryonlab`
3) Настроить `.env`:
   - `/opt/tryonlab/.env`
4) Запустить:
   - `docker compose up -d --build`
5) Миграции:
   - `docker compose exec api alembic upgrade head`

### 5.2 Обновление (новый код)
1) `git pull`
2) `docker compose up -d --build`
3) если есть миграции:
   - `docker compose exec api alembic upgrade head`
4) проверить логи:
   - `docker compose logs -f --tail=200 api`
   - `docker compose logs -f --tail=200 worker`
   - `docker compose logs -f --tail=200 bot`

---

## 6) Миграции Alembic (политика)
### 6.1 Правила
- Миграции генерируем и проверяем локально.
- В проде применяем только `alembic upgrade head`.
- Откат (downgrade) в проде делать только при понятном плане и бэкапах.

### 6.2 Бэкап перед миграциями (прод)
- `pg_dump`:
  - `pg_dump -Fc -f backup.dump $DBNAME`
или snapshot volume (если есть).

---

## 7) Логи и диагностика
### 7.1 Что логировать
- `job_id` в каждом логе (корреляция)
- `provider` + `model` + `attempt`
- время вызова провайдера + HTTP код
- error_code (auth/rate_limit/bad_request/timeout/5xx)

### 7.2 Что НЕ логировать
- сырые фото/байты
- приватные URL с токенами (если провайдер отдаёт временные ссылки)
- API keys

### 7.3 Типовые источники проблем
1) **AuthError**
   - неправильный ключ
   - ключ не имеет доступа к модели
2) **RateLimit**
   - слишком много запросов
   - решается: rate-limit + retry + переключатель провайдера
3) **BadRequest**
   - неверный формат файла
   - слишком большой файл
   - неподдерживаемые параметры
4) **Timeout / 5xx**
   - временная проблема провайдера
   - решается: retry + fallback на другой провайдер

---

## 8) Управление очередью и воркерами
### 8.1 Общая логика
- API создаёт job и кладёт в очередь Redis
- Worker берёт job, ставит lock, выполняет, обновляет БД и Redis status

### 8.2 Locking
- `lock:job:{job_id}` с TTL
- если lock есть — другой worker не берёт job

### 8.3 Scaling
- Можно поднять несколько worker контейнеров:
  - `docker compose up -d --scale worker=3`
- Важно: lock обязателен.

---

## 9) Storage (MinIO/S3 или local)
### 9.1 MinIO (рекомендовано)
- Хорошо для:
  - временных job медиа
  - долговременных user фото
- Нужны креды, бакет, политики.

### 9.2 Локальный FS (только для теста)
- проще старт
- плохо для прод:
  - бэкапы
  - масштабирование
  - чистка

---

## 10) Cleanup (TTL) — обязательная эксплуатация
### 10.1 Что чистим
- job input/output медиа по `RETENTION_HOURS`
- expired jobs помечаем `expired`

### 10.2 Как чистим
- отдельная periodic task (worker cron) каждые N минут:
  1) найти jobs с `expires_at < now()` и `status in (done,failed)`
  2) удалить storage keys job-scope
  3) обновить job `status=expired`

### 10.3 User photos
- удаляем только по команде пользователя
- опционально retention_days (если включили)

---

## 11) Rate limiting (защита от “кнопкодавов”)
Минимум:
- ограничение на пользователя по job/час
- ограничение на видео (дорого) отдельно

Реализация:
- Redis counter `rl:user:{tg_user_id}` with TTL

Поведение:
- если лимит превышен: мягкое сообщение в panel + блокируем кнопку на время

---

## 12) Healthchecks
### 12.1 API
- `/health`:
  - OK если:
    - DB connection OK
    - Redis connection OK
    - Storage доступен (если нужно)

### 12.2 Worker
- лог “heartbeat” раз в N минут
- optional endpoint `/health/worker` если worker встроен в api (не рекомендуется)

### 12.3 Bot
- лог старта + periodic “alive” раз в N минут

---

## 13) Инциденты и быстрые действия (runbook)

### 13.1 Провайдер лёг / бесконечные 5xx
- временно выключить провайдер через ENV allowlist:
  - `AI_PROVIDER_ALLOWLIST=openai` (например)
- перезапустить сервисы:
  - `docker compose up -d --build`

### 13.2 Накопились job’ы в очереди
- проверить worker логи
- проверить lock’и (не залипли ли)
- при необходимости перезапустить worker:
  - `docker compose restart worker`

### 13.3 БД упала
- проверить `postgres` health
- поднять/перезапустить
- проверить миграции

### 13.4 MinIO недоступен
- временно переключить `STORAGE_BACKEND=local` (если прод допускает)
- или быстро поднять MinIO
- результаты генераций с временными ссылками провайдера не хранить “как есть”, а скачивать сразу

---

## 14) Обновление secrets
- ключи провайдеров меняются через `.env`
- после изменения:
  - `docker compose up -d` (или `restart api worker bot`)

---

## 15) Минимальные проверки перед релизом
- `alembic upgrade head` проходит
- `/health` OK
- `/start` в боте отрабатывает
- 1 job image проходит на каждом включённом провайдере (grok/openai)
- 1 job video preset проходит (если провайдер поддерживает видео)

---

## 16) Чек-лист продовой гигиены (без фанатизма)
- `.env` только на сервере, права 600
- наружу не торчим Postgres/Redis/MinIO console без нужды
- ограничить исходящие запросы (если есть firewall) до доменов провайдеров
- дневной лимит генераций (чтобы не проснуться бедным)
- логи ротировать (docker logging driver / logrotate)

---
