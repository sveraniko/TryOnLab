# 40_prompts — TryOnLab (шаблоны, пресеты, правила)

## 0) Цели промптов
1) **Try-on изображение**: оставить человека “как есть” (лицо/волосы/поза/фон), заменить одежду на товар.
2) **Стабильность**: минимизировать “галлюцинации” (лишние принты/логотипы/смена лица/анатомии).
3) **Управляемость**: единые параметры для fit (slim/regular/oversize) и (опционально) мерок.
4) **Видео**: короткие предсказуемые пресеты 1..5 без сложной хореографии.

> В V1 промпты делаем короткими и “жёсткими”. Чем длиннее поэма, тем больше модель считает себя художником.

---

## 1) Термины и входы
### 1.1 Входные изображения
- **PERSON_IMAGE** — фото пользователя (база)
- **GARMENT_IMAGE** — фото товара (референс одежды)

### 1.2 Параметры из wizard
- `fit_pref`: `slim` | `regular` | `oversize`
- `height_cm` (опционально)
- `measurements` (опционально): грудь/талия/бедра/плечи/inseam и т.д.

### 1.3 Выходы
- **TRYON_IMAGE** — результат (jpeg/png)
- **TRYON_VIDEO** — видео (mp4)

---

## 2) Общие правила (для всех провайдеров)
1) **Identity lock**: “do not change face / do not change hair”.
2) **Pose lock**: “keep exact pose, camera angle, background”.
3) **No extra content**: “no text, no logos, no watermark, no extra accessories”.
4) **Garment fidelity**: “match garment’s color, pattern, silhouette, neckline, sleeves”.
5) **Photorealistic**: “realistic fabric folds and lighting”.

### Негативные ограничения (важно)
- не добавлять надписей/логотипов
- не менять лицо
- не менять фон
- не менять телосложение (если не просили)

---

## 3) PromptPack: структура (как хранить в коде)
Рекомендуем хранить в `app/services/prompts.py` как структуру:

- `SYSTEM_RULES` (общие правила)
- `TRYON_TEMPLATE` (шаблон для изображения)
- `RETRY_SUFFIXES[]` (варианты для retry)
- `VIDEO_PRESETS[1..5]`

И обязательно **provider overrides**:
- `GROK_OVERRIDES` (короче, прямее)
- `OPENAI_OVERRIDES` (может любить структуру)

---

## 4) Try-on Image — базовый шаблон (универсальный)
### 4.1 SYSTEM_RULES (коротко, жёстко)
Используем как верхний блок всегда:

```
You are an image editing assistant.
Goal: keep the person photo unchanged (identity, face, hair, body shape, pose, background).
Replace only the clothing with the garment from the product photo.
Photorealistic. No text, no logos, no watermark. No extra accessories.
Do not change skin tone or facial features. Preserve original lighting direction.
```

### 4.2 TRYON_TEMPLATE (с переменными)
```
Use PERSON_IMAGE as the base image.
Put the clothing from GARMENT_IMAGE onto the person.
Match the garment's exact color, pattern, texture, and silhouette.

Fit preference: {fit_pref}.
If fit_pref is slim: slightly closer fit but realistic.
If fit_pref is regular: natural fit.
If fit_pref is oversize: slightly looser fit but realistic.

Keep: face, hair, body proportions, pose, hands, background.
Change only: the clothing area needed to wear the garment.
Add realistic fabric folds and seams. Keep the photo natural.
```

### 4.3 Вставка мерок (опционально, V1 эксперимент)
Добавлять отдельным блоком, только если есть данные:

```
Body proportions reference (do not redesign the body):
Height: {height_cm} cm.
Measurements: {measurements_compact}.
Use this only to keep garment proportions realistic, not to change identity.
```

> Сноска: мерки могут давать небольшой прирост или ноль. Мы тестируем.

---

## 5) Retry (регенерация) — правила
Ретраи должны:
- менять “вариант складок/драпировки”, но не менять идентичность
- не менять фон и позу

### RETRY_SUFFIXES (пример)
1)
```
Variant: keep all constraints. Only change natural drape and folds slightly.
```
2)
```
Variant: same garment and fit. Slightly different realistic wrinkles and lighting micro-variations.
```
3)
```
Variant: preserve face and background perfectly. Improve garment edges and seams.
```

В коде: при retry выбираем suffix по round-robin или случайно.

---

## 6) Классификация типов одежды (если добавим в V1)
Если в будущем в wizard будет выбор категории, можно добавлять уточнения:

- `top` (футболка/лонгслив/рубашка)
- `outerwear` (куртка/пальто)
- `bottom` (брюки/джинсы/шорты)
- `dress` (платье)

Пример вставки:
```
Garment category: {category}. Ensure correct placement and layering for this category.
```

---

## 7) Video presets (1..5)
### Общие правила для видео
- длительность: 3–5 сек
- движения минимальные, “натуральные”
- не ломать анатомию, не менять лицо
- без резких смен позы
- без новых объектов

**VIDEO_SYSTEM_RULES**
```
Generate a short photorealistic video from the provided TRYON_IMAGE.
Keep the person's identity, face, and body intact.
No text, no logos, no watermark.
Natural motion, stable anatomy. No distortion.
```

> Если провайдер просит “input image + prompt”, используем TRYON_IMAGE как base.

---

### Preset 1 — “2 шага + 45°”
**Name:** `p1_walk_turn45`  
**Prompt:**
```
The person takes two small natural steps toward the camera, then turns 45 degrees to show the side fit, pauses, and returns to facing the camera. Slow, smooth motion. Keep background and lighting consistent.
```

### Preset 2 — “Поворот 180°”
**Name:** `p2_turn180`  
**Prompt:**
```
Slow 180-degree turn in place to show front and side, then stop facing the camera. Minimal movement, stable anatomy. Keep the face consistent.
```

### Preset 3 — “Подиумная проходка + поза”
**Name:** `p3_catwalk_pose`  
**Prompt:**
```
One to two confident catwalk steps forward, then a simple pose: slight hip shift and head turn. Smooth motion. Keep clothing details sharp and realistic.
```

### Preset 4 — “Руки для верхней одежды”
**Name:** `p4_arms_show_fit`  
**Prompt:**
```
Subtle arm movement: the person slightly raises and opens arms to show shoulder and chest fit, then relaxes. Keep hands natural and correct.
```

### Preset 5 — “Драпировка ткани”
**Name:** `p5_fabric_drape`  
**Prompt:**
```
Very subtle body sway and weight shift to show how the fabric drapes. No big gestures. Keep the garment texture and seams crisp, no distortions.
```

---

## 8) Provider-specific notes

### 8.1 Grok (xAI)
- Промпты лучше держать **короче** и менее “юридически-канцелярскими”.
- Retry лучше через короткий suffix, не переписывая весь промпт.
- Для видео: использовать именно preset prompt + общие правила.

**GROK_TRYON_MINI (альтернативный короткий)**
```
Edit PERSON_IMAGE: keep face, hair, pose, background exactly.
Replace only the clothing with GARMENT_IMAGE (same color/pattern).
Fit: {fit_pref}. Photorealistic. No text, no logos.
```

### 8.2 OpenAI
- Можно использовать более структурированное описание.
- Если появится доступ к `sora-2`, видео-пресеты работают как текстовый сценарий.
- Если изображение-редактирование использует “edits”, важно правильно передавать base image (PERSON_IMAGE) и reference (GARMENT_IMAGE).

**OPENAI_TRYON_STRUCTURED**
```
Task: Virtual try-on.
Base: PERSON_IMAGE (do not alter identity, face, hair, body shape, pose, background).
Reference: GARMENT_IMAGE (match exact color, pattern, silhouette).
Fit preference: {fit_pref}.
Output: photorealistic, natural lighting, realistic fabric folds.
Constraints: no text, no logos, no watermark, no extra accessories.
```

---

## 9) Шаблон подписи (caption) к результату
### Image result caption
```
✅ Try-on готов
Provider: {provider}
Fit: {fit_pref}
{optional_measurements_line}
🔁 Retry • 🎬 Video 1..5
```

### Video result caption
```
🎬 Video готов (preset {preset})
Provider: {provider}
Fit: {fit_pref}
```

---

## 10) Guardrails (если начнёт ломать лицо/анатомию)
Если замечаем, что модель “плывёт”:
1) Ужесточить identity lock:
   - “Do not change facial features. Keep the same person exactly.”
2) Добавить запрет на “beautify/retouch”:
   - “No beautification, no makeup changes, no skin smoothing.”
3) Уточнить ограничение на тело:
   - “Do not change body shape, weight, or proportions.”
4) Уточнить, что менять только область одежды:
   - “Modify only garment region. Do not modify skin, face, hair, background.”

---

## 11) Версии промптов (для контроля качества)
Рекомендуется вести версию промптов в коде:
- `PROMPT_VERSION = "v1.0"`
- сохранять `prompt_version` в `jobs.result_metadata`

Так можно сравнивать качество на разных версиях без гаданий.

---
