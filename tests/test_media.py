import io
import asyncio

import pytest
from fastapi import HTTPException, UploadFile

from app.services.media import parse_measurements_json, validate_image_upload


def test_parse_measurements_json_valid_object() -> None:
    payload = '{"chest": 92, "waist": 74}'
    parsed = parse_measurements_json(payload)
    assert parsed == {'chest': 92, 'waist': 74}


def test_parse_measurements_json_empty_is_none() -> None:
    assert parse_measurements_json(None) is None
    assert parse_measurements_json('   ') is None


def test_parse_measurements_json_invalid_raises_422() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_measurements_json('[]')
    assert exc.value.status_code == 422


def test_validate_image_upload_ok() -> None:
    upload = UploadFile(filename='avatar.png', file=io.BytesIO(b'abc123'), headers={'content-type': 'image/png'})
    payload, content_type, filename = asyncio.run(validate_image_upload(upload, max_mb=1))

    assert payload == b'abc123'
    assert content_type == 'image/png'
    assert filename == 'avatar.png'


def test_validate_image_upload_size_limit() -> None:
    upload = UploadFile(filename='avatar.png', file=io.BytesIO(b'x' * 10), headers={'content-type': 'image/png'})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(validate_image_upload(upload, max_mb=0))
    assert exc.value.status_code == 422
