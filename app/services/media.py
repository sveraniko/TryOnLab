from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

ALLOWED_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


def _sanitize_filename(filename: str | None, fallback: str = 'upload.jpg') -> str:
    name = Path(filename or fallback).name.strip()
    return name or fallback


async def validate_image_upload(upload: UploadFile, max_mb: int) -> tuple[bytes, str, str]:
    content_type = (upload.content_type or '').lower().strip()
    if content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Unsupported image MIME type: {content_type or "unknown"}',
        )

    payload = await upload.read()
    max_bytes = max_mb * 1024 * 1024
    if len(payload) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'File too large. Max size is {max_mb} MB',
        )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Uploaded file is empty',
        )

    return payload, content_type, _sanitize_filename(upload.filename)


def parse_measurements_json(raw: str | None) -> dict | None:
    if raw is None or not raw.strip():
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='measurements_json must be valid JSON',
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='measurements_json must be a JSON object',
        )

    return parsed
