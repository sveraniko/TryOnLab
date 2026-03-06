# 80_backlog — TryOnLab (Roadmap, Tasks, DoD)

## 0) Как читать backlog
- **V1** — быстрый тест качества (image + video presets), без интеграций.
- **V1.1** — стабилизация: метрики, дедуп, UX полировка, cost controls.
- **V2** — подключаем SIS/SizeBot, авто-кадр из видео, multi-view, поинты.
- **V3** — “красиво и богато”: advanced fitting, луки, персонализация, B2B.

Формат карточек:
- **ID**: OB/TOL-xxx
- **Scope**: bot/api/worker/providers/storage/db
- **Priority**: P0/P1/P2
- **DoD**: Definition of Done

---

## 1) V1 (MVP) — “работает и не бесит”
### TOL-001 — Repo skeleton + docker-compose
- Scope: ops
- Priority: P0
- DoD:
  - docker compose поднимает api/worker/bot/postgres/redis/(minio)
  - `.env.example` есть
  - `alembic upgrade head` проходит

### TOL-002 — Panel UX pattern (single editable panel)
- Scope: bot
- Priority: P0
- DoD:
  - 1 panel message per user, всегда edit
  - inline кнопки, шаги назад/вперёд
  - no duplicate panels, no spam

### TOL-003 — Upload product image (delete message after accept)
- Scope: bot + storage
- Priority: P0
- DoD:
  - продукт фото сохраняется в storage
  - сообщение пользователя best-effort удаляется
  - панель показывает ✅ “товар загружен”

### TOL-004 — User photos: save + reuse + delete
- Scope: bot + db + storage
- Priority: P0
- DoD:
  - пользователь может загрузить и сохранить фото
  - может выбрать активное из списка
  - может удалить одно или все
  - панель показывает активное фото

### TOL-005 — Fit preference & measurements input
- Scope: bot + api
- Priority: P0
- DoD:
  - fit pref: slim/regular/oversize через кнопки
  - measurements: ввод текстом, парсинг в JSON
  - сохранить в session/job draft

### TOL-006 — Jobs API (create/poll/retry/video)
- Scope: api + db + redis
- Priority: P0
- DoD:
  - POST /jobs создаёт job image
  - GET /jobs/{id} возвращает статус/результат
  - POST /jobs/{id}/retry работает
  - POST /jobs/{id}/video?preset=N создаёт video job

### TOL-007 — Provider interface + registry
- Scope: providers
- Priority: P0
- DoD:
  - ProviderBase + единые ошибки
  - Registry + allowlist + default
  - выбор провайдера per-user/per-job

### TOL-008 — Grok provider (image + video)
- Scope: providers + worker
- Priority: P0
- DoD:
  - image generation отрабатывает стабильно (1 результат)
  - video generation по preset 1..5 отрабатывает
  - временные URL провайдера скачиваются в storage

### TOL-009 — OpenAI provider (image) + video placeholder
- Scope: providers
- Priority: P1
- DoD:
  - image generation работает
  - video: если модель недоступна — graceful “unsupported” + UI сообщение
  - переключатель провайдера в боте работает

### TOL-010 — Prompts v1
- Scope: services
- Priority: P0
- DoD:
  - базовый try-on prompt pack
  - retry suffixes
  - video presets 1..5
  - prompt_version сохраняется в job metadata

### TOL-011 — Cleanup TTL for job media
- Scope: worker + storage + db
- Priority: P1
- DoD:
  - cron/periodic cleanup удаляет job media по expires_at
  - job помечается expired
  - user photos не трогаются

### TOL-012 — Rate limit basic
- Scope: bot + redis
- Priority: P1
- DoD:
  - лимит по jobs/час
  - лимит по видео отдельно
  - UI реакция: мягкое сообщение + блок кнопки на cooldown

---

## 2) V1.1 (Stabilization) — “не ломается и стоит денег меньше”
### TOL-101 — Dedup uploads (hash)
- Priority: P1
- DoD:
  - sha256 для user photo
  - если уже есть — не дублировать storage

### TOL-102 — Cost guardrails
- Priority: P0
- DoD:
  - лимит на размер/разрешение входных фото
  - лимит на количество ретраев
  - лимит на количество видео/день

### TOL-103 — Better error UX
- Priority: P1
- DoD:
  - error_code маппится в понятный текст
  - кнопка “сменить провайдер” предлагается при rate_limit/5xx

### TOL-104 — Simple metrics export
- Priority: P1
- DoD:
  - таблица/endpoint с агрегациями: success rate, p50 latency, failures by code

### TOL-105 — “Delete my data”
- Priority: P0
- DoD:
  - команда/кнопка удаляет user photos + settings
  - jobs либо удаляются, либо анонимизируются

---

## 3) V2 (Integrations) — “связка с экосистемой”
### TOL-201 — SizeBot API integration (optional)
- Priority: P0
- DoD:
  - если есть size_profile_id → подтягиваем мерки
  - fit verdict возвращается в panel/result caption
  - fallback на ручной ввод

### TOL-202 — SIS stub integration
- Priority: P1
- DoD:
  - accept sis_product_id вместо загрузки garment photo
  - pull garment try-on asset via API (если есть)
  - fallback: ручная загрузка

### TOL-203 — Garment parameters support
- Priority: P1
- DoD:
  - принимать garment measurements/material/stretch
  - вставлять в PromptPack (эксперимент)

### TOL-204 — Video-to-hero-frame extraction (admin select)
- Priority: P1
- DoD:
  - из видео товара извлекаем 10–30 кадров
  - admin выбирает кадр в мини-UI (может быть telegram-only)
  - выбранный кадр становится tryon asset

### TOL-205 — Multi-view try-on (front/side/back)
- Priority: P2
- DoD:
  - режим “точно”: 2–3 результата по разным ракурсам
  - UI выбора ракурса/галерея

### TOL-206 — Points / pricing v0
- Priority: P1
- DoD:
  - image = X points, video = Y points
  - wallet + transactions
  - ограничения при нуле

---

## 4) V3 (Advanced) — “делаем продукт, а не игрушку”
### TOL-301 — Consistency improvements (face lock / pose control)
- Priority: P1
- DoD:
  - опциональная предобработка: лицо/волосы сохраняются жёстче
  - уменьшение “плывущих рук” на видео

### TOL-302 — Category-specific prompt packs
- Priority: P1
- DoD:
  - отдельные правила для outerwear / dress / pants
  - auto category selection (или ручная)

### TOL-303 — “Looks” mode (комплект)
- Priority: P2
- DoD:
  - try-on с несколькими товарами (верх+низ)
  - логика слоёв и приоритета

### TOL-304 — Analytics for commerce
- Priority: P1
- DoD:
  - события try-on → add-to-cart/purchase (если интегрировано)
  - сегменты по регионам/размерам/категориям

---

## 5) Acceptance Criteria (общие)
### UX
- не спамит чат панелями
- понятно, что загружено, что выбрано
- легко заменить user photo, легко удалить

### Stability
- job lifecycle прозрачен
- worker не дублирует выполнение
- ошибки классифицированы и понятны

### Privacy
- входные фото удаляются из чата best-effort
- user photos управляемы пользователем
- job media чистятся по TTL

---

## 6) “Что делаем первым” (очередность)
**P0 V1:** TOL-001..008 + 010 (каркас + bot flow + grok)  
Потом: TOL-009 (openai image) + 011 (cleanup) + 012 (rate-limit).  
Стабилизация: 101–105.  
Интеграции: 201–206.

---
