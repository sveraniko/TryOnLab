from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class ProviderError(Exception):
    message: str
    code: str
    retryable: bool

    def __str__(self) -> str:
        return self.message


class ProviderAuthError(ProviderError):
    def __init__(self, message: str = 'Provider authentication failed') -> None:
        super().__init__(message=message, code='auth', retryable=False)


class ProviderRateLimitError(ProviderError):
    def __init__(self, message: str = 'Provider rate limit reached') -> None:
        super().__init__(message=message, code='rate_limit', retryable=True)


class ProviderBadRequestError(ProviderError):
    def __init__(self, message: str = 'Provider bad request') -> None:
        super().__init__(message=message, code='bad_request', retryable=False)


class ProviderTemporaryError(ProviderError):
    def __init__(self, message: str = 'Provider temporary error', code: str = 'timeout') -> None:
        if code not in {'timeout', 'provider_5xx'}:
            code = 'timeout'
        super().__init__(message=message, code=code, retryable=True)


class ProviderUnsupportedError(ProviderError):
    def __init__(self, message: str = 'Provider operation unsupported') -> None:
        super().__init__(message=message, code='unsupported', retryable=False)


@dataclass
class ProviderCapabilities:
    image: bool = True
    video: bool = False
    async_video: bool = False
    image_edit: bool = True


@dataclass
class ProviderResult:
    storage_key: str
    content_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderBase(ABC):
    name: str
    capabilities: ProviderCapabilities

    async def generate_image(
        self,
        *,
        job_id: str,
        storage_key_product: str | None = None,
        storage_key_product_clean: str | None = None,
        storage_key_product_fit: str | None = None,
        storage_key_product_fit_extra: str | None = None,
        storage_key_person: str,
        fit_pref: str | None = None,
        measurements: dict[str, Any] | None = None,
        mode: str | None = None,
        scope: str | None = None,
        force_lock: bool = False,
        reference_strategy: str | None = None,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
    ) -> ProviderResult:
        raise NotImplementedError

    async def generate_video(
        self,
        *,
        job_id: str,
        storage_key_image_result: str,
        preset: int,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
    ) -> ProviderResult:
        raise NotImplementedError
