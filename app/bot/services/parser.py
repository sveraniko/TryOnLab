from __future__ import annotations

import json
import re

KEY_ALIASES = {
    'рост': 'height_cm',
    'height': 'height_cm',
    'грудь': 'chest_cm',
    'талия': 'waist_cm',
    'бедра': 'hips_cm',
    'плечи': 'shoulders_cm',
    'inseam': 'inseam_cm',
}


def parse_measurements_text(text: str) -> dict[str, int]:
    raw = text.strip()
    if not raw:
        raise ValueError('Пустой ввод')

    if raw.startswith('{'):
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError('JSON должен быть объектом')
        return {str(k): int(v) for k, v in parsed.items()}

    result: dict[str, int] = {}
    parts = re.split(r'[,;/]', raw)
    for part in parts:
        token = part.strip().lower()
        if not token:
            continue
        m = re.match(r'([\wа-яё]+)\s*[:= ]\s*(\d{2,3})', token)
        if not m:
            continue
        key_raw, value = m.group(1), int(m.group(2))
        key = KEY_ALIASES.get(key_raw, key_raw)
        result[key] = value

    if not result:
        raise ValueError('Не удалось распарсить параметры')

    return result
