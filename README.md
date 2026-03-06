# TryOnLab — быстрый тест виртуальной примерки (Telegram bot)
## Зачем
TryOnLab — отдельный тестовый бот для проверки качества "try-on" (фото товара + фото человека -> изображение/видео).
Без SIS/SizeBot на первом шаге. Но архитектура сразу плагинная: можно подключать разных провайдеров генерации (Grok, OpenAI, ...).

Цель MVP:
- Получить 1 try-on изображение
- Дать кнопку "Регенерировать"
- Если результат ок — сделать видео (пакет из 5 пресетов движения)

## Фичи MVP (V1)
- Wizard в Telegram:
  1) загрузка фото товара
  2) загрузка фото человека
  3) fit preference (slim/regular/oversize)
  4) (опц.) рост + мерки
  5) генерация 1 изображения + retry
- Переключатель провайдера: Grok / OpenAI
- Кнопки видео 1..5 (preset prompts) + генерация видео из итогового изображения
- Хранение задач и пользовательских настроек в БД (Postgres), быстрые статусы/TTL — в Redis

## Не делаем в V1
- Автовытаскивание кадра из видео товара (V2)
- Интеграция с SIS/SizeBot (V2)
- Мультиракурс (front/side/back) (V2)
- Платёжка/поинты (V2)

## Технологии (как в SocialBridge)
- FastAPI + Uvicorn
- SQLAlchemy 2 + Alembic
- Postgres
- Redis
- httpx
(см. requirements.txt)

## Архитектура в двух словах
- bot (aiogram) -> API (FastAPI) -> providers (grok/openai) -> storage
- Все провайдеры реализуют единый интерфейс ProviderBase
- API хранит jobs и отдаёт статус; bot просто управляет UX

Схема:
Telegram bot
  -> POST /jobs (create)
  -> GET /jobs/{id} (poll)
API
  -> Provider.generate_image(...)
  -> Provider.generate_video(...)
  -> сохраняет result_url

## Быстрый старт (docker)
1) cp .env.example .env
2) docker compose up -d --build
3) docker compose exec api alembic upgrade head
4) бот запускается сервисом `bot` (см. docker-compose)

## Конфиг (ENV)
- DATABASE_URL=postgresql+asyncpg://...
- REDIS_URL=redis://...
- TELEGRAM_BOT_TOKEN=...
- AI_PROVIDER_DEFAULT=grok|openai
- AI_PROVIDER_ALLOWLIST=grok,openai
- XAI_API_KEY=...         # для Grok
- OPENAI_API_KEY=...      # для OpenAI
- OPENAI_VIDEO_MODEL=sora-2 (опционально)
- RETENTION_HOURS=72

## Документация
- docs/00_overview.md — что строим и зачем
- docs/10_architecture.md — слои, модули, зависимости
- docs/20_bot_flow.md — wizard, клавиатуры, UX
- docs/30_providers.md — интерфейс провайдера, модели, нюансы
- docs/40_prompts.md — шаблоны промптов, пресеты видео 1..5
- docs/50_data_model.md — таблицы БД, ключи Redis
- docs/60_ops.md — deploy, логи, миграции, мониторинг
- docs/70_security_privacy.md — хранение фото, TTL, согласия
- docs/80_backlog.md — V2/V3
- docs/90_testing.md — тесты, стабилизация, метрики качества

## Правила для Codex
- Не менять структуру модулей без необходимости
- Провайдеры только через ProviderBase + registry
- Не хардкодить ключи, только ENV
- Все network calls через httpx, таймауты обязательны
- Любая генерация -> job, статус, ретраи, понятные ошибки