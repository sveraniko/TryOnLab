# 90_testing — TryOnLab (Testing, QA, Regression, Cost Control)

## 0) Цель тестирования
TryOnLab тестируем не как “библиотеку”, а как продукт:
- стабильность UX (панель, шаги, отсутствие дублей)
- корректность жизненного цикла jobs
- предсказуемость провайдеров (ошибки, ретраи, таймауты)
- приватность (удаление сообщений, удаление user photos, TTL)
- контроль затрат (лимиты, rate-limit, максимальные размеры)

---

## 1) Тестовая пирамида (практичная)
### 1.1 Unit (быстро, локально)
- парсер мерок из текста
- сборка PromptPack
- маппинг ошибок провайдера → error_code
- генерация callback data и роутинг действий
- storage key naming

### 1.2 Integration (с контейнерами)
- API ↔ Postgres ↔ Redis ↔ Storage (MinIO)
- worker берёт job и обновляет статусы
- cleanup TTL удаляет media и помечает job expired

### 1.3 E2E (через Telegram в тестовом чате)
- wizard flow от /start до результата
- retry
- video preset 1..5
- переключатель провайдера

---

## 2) Набор тестовых данных (фиксированный “пак”)
Чтобы сравнивать качество, нужен одинаковый набор:

### 2.1 Пользовательские фото (PERSON_IMAGE)
- P1: полный рост, нейтральный фон, хорошее освещение
- P2: полный рост, сложный фон
- P3: частичный рост (до колен) (ожидаем хуже, но не падение)
- P4: плохой свет/размытость (ожидаем предупреждение/отказ)

### 2.2 Фото товара (GARMENT_IMAGE)
- G1: футболка/лонгслив на белом фоне
- G2: куртка/пальто (outerwear)
- G3: брюки (bottom)
- G4: платье
- G5: вещь со сложным принтом (проверка “сохранения узора”)

> Эти изображения держать локально в `tests/assets/` (не в публичном репо, если есть права/коммерция).  
> Для CI можно держать синтетические/нейтральные изображения.

---

## 3) Smoke tests (перед каждым релизом)
### 3.1 API smoke
- `/health` = OK
- `POST /jobs` создаёт job image
- `GET /jobs/{id}` возвращает status
- `POST /jobs/{id}/retry` увеличивает attempts
- `POST /jobs/{id}/video?preset=1` создаёт video job (если provider supports)

### 3.2 Worker smoke
- job из очереди берётся
- status становится running
- результат появляется в storage
- status done
- ошибки классифицируются

### 3.3 Bot smoke
- `/start` создаёт панель
- upload product → сообщение удаляется best-effort
- user photo reuse работает (сохранил → выбрал)
- generate image → result message появляется
- retry → новая картинка появляется
- video preset → видео появляется (если доступно)

---

## 4) Unit tests (что обязательно)
### 4.1 Measurements parser
Кейсы:
- `рост 182, грудь 106, талия 86`
- `height=182; chest=106; waist=86`
- `182/106/86/102` (если поддерживаем такой режим)
Ожидаем:
- нормализованный JSON (int)
- игнор мусора
- отказ при отсутствии рост/мерок (если режим требует)

### 4.2 PromptPack builder
- правильная подстановка `fit_pref`
- корректное добавление блока мерок только если они есть
- правильный `prompt_version`
- provider override применяется

### 4.3 Provider error mapping
Подставляем типичные ответы:
- 401 → AuthError → error_code=auth
- 429 → RateLimitError → error_code=rate_limit, retryable=true
- 400 → BadRequestError → error_code=bad_request, retryable=false
- timeout → TemporaryError → error_code=timeout, retryable=true
- 5xx → TemporaryError → error_code=provider_5xx, retryable=true

### 4.4 Callback routing
- callback `video:3` вызывает правильную команду
- callback `provider:openai` сохраняет настройки и меняет UI
- повторный клик идемпотентен

---

## 5) Integration tests (docker)
Запуск:
- `docker compose -f docker-compose.test.yml up -d`
- применить миграции
- прогнать тесты

Что проверяем:
- создание user, settings, job
- worker выполняет job без дублирования (lock)
- статус отражается в Redis и в БД
- cleanup удаляет storage keys по expires_at

---

## 6) E2E сценарии (manual)
### 6.1 Happy path image
1) /start
2) upload garment
3) upload user photo
4) fit regular
5) generate
Ожидаем:
- панель не дублируется
- сообщения с upload удалены (best-effort)
- результат отправлен, панель вернулась в Home

### 6.2 Retry
- нажать retry 2–3 раза
Ожидаем:
- новые результаты, attempts растёт
- rate-limit/cooldown срабатывает если спам

### 6.3 Video presets
- нажать preset 1..5
Ожидаем:
- отдельные видео сообщения
- анатомия не “ломается” в большинстве случаев (не гарантируем, но проверяем)

### 6.4 Provider toggle
- Grok → OpenAI
- повторить image
Ожидаем:
- провайдер переключился
- если видео у OpenAI недоступно — UI объясняет “unsupported”

### 6.5 User photo reuse
- загрузить 2 разных user photo
- выбрать активное
- генерировать с каждым
Ожидаем:
- активное фото меняется
- старое можно удалить
- “delete all” очищает всё и требует загрузку

---

## 7) Regression тестирование качества (визуально)
Проблема: качество “не тестируется юнитами”. Решение: фиксированный набор + визуальные чек-листы.

### 7.1 Чек-лист качества для image
- лицо не изменилось (identity)
- фон не изменился
- одежда похожа на товар (цвет/принт/силуэт)
- не появилось текстов/логотипов/водяных знаков
- руки/пальцы не сломаны критически

### 7.2 Чек-лист качества для video
- лицо стабильно
- нет “желе” одежды
- движения плавные, без телепортаций
- нет сильных деформаций конечностей

### 7.3 Версионирование
- сохраняем `prompt_version`
- при изменении промптов прогоняем тот же тест-пак и сравниваем

---

## 8) Тестирование приватности и retention
### 8.1 Delete uploads from chat (best-effort)
- после загрузки product/user фото бот вызывает delete
- если delete не разрешён — не падает

### 8.2 User photo delete
- удалить выбранное → storage key удалён, DB помечен/удалён
- delete all → всё исчезло, active=null

### 8.3 TTL cleanup
- выставить `RETENTION_HOURS=0.01` (для теста)
- дождаться cleanup
- проверить:
  - storage keys удалены
  - job status=expired

---

## 9) Тестирование cost controls
### 9.1 Входные лимиты
- слишком большой файл → отказ
- слишком большое разрешение → ресайз или отказ (policy V1)
- слишком много ретраев → кнопка блокируется, сообщение “лимит”

### 9.2 Rate limiting
- спам generate/retry/video → redis limit → cooldown

### 9.3 Provider budget
- (опционально) дневной лимит на провайдер
- если лимит достигнут → предлагаем переключиться

---

## 10) CI (минимум)
Если подключаем CI:
- lint/format (ruff/black) — по желанию
- unit tests
- integration tests (без реальных вызовов провайдера)

Важно:
- провайдеры в CI мокать (no real API calls)
- изображения для CI использовать синтетические

---

## 11) Моки провайдеров (обязательно для тестов)
### 11.1 FakeProvider
Реализация провайдера, который:
- “генерирует” результат как копию входа
- имитирует таймаут/429/401 по флагу
- возвращает предсказуемые ответы

Это позволит тестировать всю цепочку job/worker/storage без расходов.

---

## 12) Definition of Done (testing V1)
- unit tests: parser + prompt builder + error mapping + callbacks
- integration: job lifecycle + redis status + storage write + cleanup
- manual E2E checklist выполнен на тест-паке
- провайдеры мокируются для CI, реальные вызовы только руками
- лимиты и приватность проверены

---
