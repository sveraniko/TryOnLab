from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import mimetypes
import time
from typing import Any, Awaitable, Callable

import httpx

from app.core.config import Settings
from app.providers.base import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderBase,
    ProviderCapabilities,
    ProviderRateLimitError,
    ProviderResult,
    ProviderTemporaryError,
)
from app.services.prompts import PROMPT_VERSION, build_tryon_prompt, build_video_prompt
from app.services.storage import StorageBackend
from app.services.storage_keys import job_key

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int], Awaitable[None]]


class GrokProvider(ProviderBase):
    name = 'grok'
    capabilities = ProviderCapabilities(image=True, video=True, async_video=True, image_edit=True)

    def __init__(self, storage: StorageBackend, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings

    async def generate_image(
        self,
        *,
        job_id: str,
        storage_key_product: str,
        storage_key_person: str,
        fit_pref: str | None = None,
        measurements: dict[str, Any] | None = None,
        mode: str | None = None,
        scope: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ProviderResult:
        person_bytes = await self.storage.get_bytes(storage_key_person)
        garment_bytes = await self.storage.get_bytes(storage_key_product)

        person_data_uri = _to_data_uri(storage_key_person, person_bytes)
        garment_data_uri = _to_data_uri(storage_key_product, garment_bytes)
        prompt = build_tryon_prompt(mode, scope, fit_pref, measurements)

        payload = {
            'model': self.settings.xai_image_model,
            'prompt': prompt,
            'images': [
                {'url': person_data_uri, 'type': 'image_url'},
                {'url': garment_data_uri, 'type': 'image_url'},
            ],
            'response_format': self.settings.xai_image_response_format,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(
                    f"{self.settings.xai_base_url.rstrip('/')}/images/edits",
                    json=payload,
                    headers={
                        'Authorization': f'Bearer {self.settings.xai_api_key}',
                        'Content-Type': 'application/json',
                    },
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                raise ProviderTemporaryError('Grok image generation timeout', code='timeout') from exc

        _raise_for_status(response)
        body = response.json()
        b64_payload = (body.get('data') or [{}])[0].get('b64_json')
        if not b64_payload:
            raise ProviderBadRequestError('Grok did not return image data')

        out_bytes = _safe_b64decode(b64_payload)
        if on_progress:
            await on_progress(60)
        out_key = job_key(job_id, 'output', 'image.jpg')
        await self.storage.put_bytes(out_key, out_bytes, content_type='image/jpeg')
        if on_progress:
            await on_progress(100)

        return ProviderResult(
            storage_key=out_key,
            content_type='image/jpeg',
            metadata={
                'provider': 'grok',
                'model': self.settings.xai_image_model,
                'prompt_version': PROMPT_VERSION,
                'dummy': False,
            },
        )

    async def generate_video(
        self,
        *,
        job_id: str,
        storage_key_image_result: str,
        preset: int,
        on_progress: ProgressCallback | None = None,
    ) -> ProviderResult:
        source_image_bytes = await self.storage.get_bytes(storage_key_image_result)
        image_data_uri = _to_data_uri(storage_key_image_result, source_image_bytes)
        prompt = build_video_prompt(preset)

        payload = {
            'model': self.settings.xai_video_model,
            'prompt': prompt,
            'image': {'url': image_data_uri},
            'duration': self.settings.xai_video_duration,
            'aspect_ratio': self.settings.xai_video_aspect_ratio,
            'resolution': self.settings.xai_video_resolution,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                create_response = await client.post(
                    f"{self.settings.xai_base_url.rstrip('/')}/videos/generations",
                    json=payload,
                    headers={'Authorization': f'Bearer {self.settings.xai_api_key}'},
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                raise ProviderTemporaryError('Grok video request timeout', code='timeout') from exc

            _raise_for_status(create_response)
            request_id = create_response.json().get('id') or create_response.json().get('request_id')
            if not request_id:
                raise ProviderBadRequestError('Grok did not return request_id')

            deadline = time.monotonic() + self.settings.xai_poll_timeout_seconds
            status = 'pending'
            video_url = None
            while time.monotonic() < deadline:
                try:
                    poll_response = await client.get(
                        f"{self.settings.xai_base_url.rstrip('/')}/videos/{request_id}",
                        headers={'Authorization': f'Bearer {self.settings.xai_api_key}'},
                    )
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    raise ProviderTemporaryError('Grok video poll timeout', code='timeout') from exc

                _raise_for_status(poll_response)
                poll_body = poll_response.json()
                status = str(poll_body.get('status', 'pending')).lower()
                if status == 'done':
                    video_url = ((poll_body.get('video') or {}).get('url'))
                    break
                if status == 'expired':
                    raise ProviderTemporaryError('Grok video request expired', code='timeout')

                if on_progress:
                    await on_progress(min(90, 20 + int((1 - ((deadline - time.monotonic()) / self.settings.xai_poll_timeout_seconds)) * 70)))
                await asyncio.sleep(self.settings.xai_poll_interval_seconds)

            if status != 'done' or not video_url:
                raise ProviderTemporaryError('Grok video generation timed out', code='timeout')

            try:
                download_response = await client.get(video_url)
                if download_response.status_code == 403:
                    download_response = await client.get(
                        video_url,
                        headers={'Authorization': f'Bearer {self.settings.xai_api_key}'},
                    )
                download_response.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError) as exc:
                raise ProviderTemporaryError('Failed to download Grok video', code='timeout') from exc

        out_key = job_key(job_id, 'output', f'video_preset_{preset}.mp4')
        await self.storage.put_bytes(out_key, download_response.content, content_type='video/mp4')
        if on_progress:
            await on_progress(100)
        logger.info('Grok video saved to storage', extra={'job_id': job_id, 'request_id': request_id})

        return ProviderResult(
            storage_key=out_key,
            content_type='video/mp4',
            metadata={
                'provider': 'grok',
                'model': self.settings.xai_video_model,
                'request_id': request_id,
                'duration': self.settings.xai_video_duration,
                'prompt_version': PROMPT_VERSION,
                'dummy': False,
            },
        )


def _to_data_uri(storage_key: str, data: bytes) -> str:
    mime = mimetypes.guess_type(storage_key)[0] or 'image/jpeg'
    return f'data:{mime};base64,{base64.b64encode(data).decode("utf-8")}'


def _safe_b64decode(payload: str) -> bytes:
    try:
        return base64.b64decode(payload)
    except binascii.Error as exc:
        raise ProviderBadRequestError('Invalid base64 payload from Grok') from exc


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise ProviderAuthError('Grok authentication failed')
    if response.status_code == 429:
        raise ProviderRateLimitError('Grok rate limit reached')
    if response.status_code == 400:
        try:
            message = response.json().get('error', {}).get('message') or response.text
        except Exception:
            message = response.text
        raise ProviderBadRequestError(message or 'Grok bad request')
    if response.status_code >= 500:
        raise ProviderTemporaryError('Grok upstream temporary error', code='provider_5xx')
    if response.status_code >= 400:
        raise ProviderBadRequestError(f'Grok request failed: {response.status_code}')
