from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str | None = None) -> None:
        super().__init__(detail or '')
        self.status_code = status_code
        self.detail = detail


@dataclass
class UploadFile:
    filename: str
    file: Any
    headers: dict[str, str] | None = None

    @property
    def content_type(self) -> str | None:
        if not self.headers:
            return None
        return self.headers.get('content-type')

    async def read(self) -> bytes:
        return self.file.read()


class _Status:
    HTTP_401_UNAUTHORIZED = 401
    HTTP_403_FORBIDDEN = 403
    HTTP_404_NOT_FOUND = 404
    HTTP_409_CONFLICT = 409
    HTTP_422_UNPROCESSABLE_ENTITY = 422


status = _Status()
