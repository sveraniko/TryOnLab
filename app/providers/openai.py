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
    ProviderUnsupportedError,
)
from app.services.prompts import PROMPT_VERSION, build_tryon_prompt, build_video_prompt
from app.services.storage import StorageBackend
from app.services.storage_keys import job_key

ProgressCallback = Callable[[int], Awaitable[None]]
logger = logging.getLogger(__name__)


class OpenAIProvider(ProviderBase):
    name = 'openai'

    def __init__(self, storage: StorageBackend, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings
        self.capabilities = ProviderCapabilities(
            image=True,
            video=bool(self.settings.openai_api_key and self.settings.openai_video_model),
            async_video=True,
            image_edit=True,
        )

    async def generate_image(
        self,
        *,
        job_id: str,
        storage_key_product: str | None = None,
        storage_key_product_clean: str | None = None,
        storage_key_product_fit: str | None = None,
        storage_key_person: str,
        fit_pref: str | None = None,
        measurements: dict[str, Any] | None = None,
        mode: str | None = None,
        scope: str | None = None,
        force_lock: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> ProviderResult:
        person_bytes = await self.storage.get_bytes(storage_key_person)
        clean_key = storage_key_product_clean or storage_key_product
        fit_key = storage_key_product_fit
        if not clean_key and not fit_key:
            raise ProviderBadRequestError('OpenAI requires at least one garment reference')

        clean_bytes = await self.storage.get_bytes(clean_key) if clean_key else None
        fit_bytes = await self.storage.get_bytes(fit_key) if fit_key else None
        prompt = build_tryon_prompt(
            mode,
            scope,
            fit_pref,
            measurements,
            force_lock=force_lock,
            has_clean_ref=bool(clean_key),
            has_fit_ref=bool(fit_key),
        )

        form_files, form_data = _build_edit_form(
            model=self.settings.openai_image_model,
            prompt=prompt,
            person_key=storage_key_person,
            person_bytes=person_bytes,
            garment_clean_key=clean_key,
            garment_clean_bytes=clean_bytes,
            garment_fit_key=fit_key,
            garment_fit_bytes=fit_bytes,
            include_response_format=True,
        )

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                response = await client.post(
                    f"{self.settings.openai_base_url.rstrip('/')}/images/edits",
                    headers={'Authorization': f'Bearer {self.settings.openai_api_key}'},
                    data=form_data,
                    files=form_files,
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                raise ProviderTemporaryError('OpenAI image timeout', code='timeout') from exc

            if response.status_code == 400 and 'unsupported parameter' in response.text.lower():
                form_files, form_data = _build_edit_form(
                    model=self.settings.openai_image_model,
                    prompt=prompt,
                    person_key=storage_key_person,
                    person_bytes=person_bytes,
                    garment_clean_key=clean_key,
                    garment_clean_bytes=clean_bytes,
                    garment_fit_key=fit_key,
                    garment_fit_bytes=fit_bytes,
                    include_response_format=False,
                )
                response = await client.post(
                    f"{self.settings.openai_base_url.rstrip('/')}/images/edits",
                    headers={'Authorization': f'Bearer {self.settings.openai_api_key}'},
                    data=form_data,
                    files=form_files,
                )
            if fit_key and clean_key and response.status_code == 400 and _is_unsupported_multiref(response):
                logger.info('OpenAI multiref unsupported, fallback to clean-only', extra={'job_id': job_id})
                form_files, form_data = _build_edit_form(
                    model=self.settings.openai_image_model,
                    prompt=build_tryon_prompt(
                        mode,
                        scope,
                        fit_pref,
                        measurements,
                        force_lock=force_lock,
                        has_clean_ref=bool(clean_key),
                        has_fit_ref=False,
                    ),
                    person_key=storage_key_person,
                    person_bytes=person_bytes,
                    garment_clean_key=clean_key,
                    garment_clean_bytes=clean_bytes,
                    garment_fit_key=None,
                    garment_fit_bytes=None,
                    include_response_format=False,
                )
                response = await client.post(
                    f"{self.settings.openai_base_url.rstrip('/')}/images/edits",
                    headers={'Authorization': f'Bearer {self.settings.openai_api_key}'},
                    data=form_data,
                    files=form_files,
                )

            _raise_for_status(response, provider='OpenAI')
            body = response.json()
            first_data = (body.get('data') or [{}])[0]

            image_bytes: bytes | None = None
            if first_data.get('b64_json'):
                image_bytes = _safe_b64decode(first_data['b64_json'])
            elif first_data.get('url'):
                image_bytes = await _download_bytes(client, first_data['url'], self.settings.openai_api_key)

        if image_bytes is None:
            raise ProviderBadRequestError('OpenAI image result missing content')

        if on_progress:
            await on_progress(60)
        out_key = job_key(job_id, 'output', 'image.jpg')
        await self.storage.put_bytes(out_key, image_bytes, content_type='image/jpeg')
        if on_progress:
            await on_progress(100)

        return ProviderResult(
            storage_key=out_key,
            content_type='image/jpeg',
            metadata={
                'provider': 'openai',
                'model': self.settings.openai_image_model,
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
        if not self.settings.openai_api_key or not self.settings.openai_video_model:
            raise ProviderUnsupportedError('video not configured')

        source_image_bytes = await self.storage.get_bytes(storage_key_image_result)
        prompt = build_video_prompt(preset)

        video_mime = mimetypes.guess_type(storage_key_image_result)[0] or 'image/jpeg'
        files = {
            'input_reference': ('input_reference.jpg', source_image_bytes, video_mime),
        }
        data = {
            'prompt': prompt,
            'model': self.settings.openai_video_model,
            'size': self.settings.openai_video_size,
            'seconds': self.settings.openai_video_seconds,
        }

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                create_response = await client.post(
                    f"{self.settings.openai_base_url.rstrip('/')}/videos",
                    headers={'Authorization': f'Bearer {self.settings.openai_api_key}'},
                    data=data,
                    files=files,
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                raise ProviderTemporaryError('OpenAI video timeout', code='timeout') from exc

            _raise_for_status(create_response, provider='OpenAI')
            video_id = create_response.json().get('id')
            if not video_id:
                raise ProviderBadRequestError('OpenAI did not return video id')

            deadline = time.monotonic() + self.settings.openai_poll_timeout_seconds
            final_status = 'queued'
            while time.monotonic() < deadline:
                poll_response = await client.get(
                    f"{self.settings.openai_base_url.rstrip('/')}/videos/{video_id}",
                    headers={'Authorization': f'Bearer {self.settings.openai_api_key}'},
                )
                _raise_for_status(poll_response, provider='OpenAI')
                poll_body = poll_response.json()
                final_status = str(poll_body.get('status', 'queued')).lower()
                if final_status == 'completed':
                    break
                if final_status == 'failed':
                    error_message = ((poll_body.get('error') or {}).get('message')) or 'OpenAI video failed'
                    raise ProviderBadRequestError(error_message)

                if on_progress:
                    await on_progress(min(90, 20 + int((1 - ((deadline - time.monotonic()) / self.settings.openai_poll_timeout_seconds)) * 70)))
                await asyncio.sleep(self.settings.openai_poll_interval_seconds)

            if final_status != 'completed':
                raise ProviderTemporaryError('OpenAI video generation timed out', code='timeout')

            content_response = await client.get(
                f"{self.settings.openai_base_url.rstrip('/')}/videos/{video_id}/content",
                headers={'Authorization': f'Bearer {self.settings.openai_api_key}'},
            )
            _raise_for_status(content_response, provider='OpenAI')

        out_key = job_key(job_id, 'output', f'video_preset_{preset}.mp4')
        await self.storage.put_bytes(out_key, content_response.content, content_type='video/mp4')
        if on_progress:
            await on_progress(100)
        return ProviderResult(
            storage_key=out_key,
            content_type='video/mp4',
            metadata={
                'provider': 'openai',
                'model': self.settings.openai_video_model,
                'video_id': video_id,
                'duration': self.settings.openai_video_seconds,
                'prompt_version': PROMPT_VERSION,
                'dummy': False,
            },
        )


def _build_edit_form(
    *,
    model: str,
    prompt: str,
    person_key: str,
    person_bytes: bytes,
    garment_clean_key: str | None,
    garment_clean_bytes: bytes | None,
    garment_fit_key: str | None,
    garment_fit_bytes: bytes | None,
    include_response_format: bool,
) -> tuple[list[tuple[str, tuple[str, bytes, str]]], dict[str, str | int]]:
    person_mime = mimetypes.guess_type(person_key)[0] or 'image/jpeg'

    files = [('image', ('person.jpg', person_bytes, person_mime))]
    if garment_clean_key and garment_clean_bytes is not None:
        garment_clean_mime = mimetypes.guess_type(garment_clean_key)[0] or 'image/jpeg'
        files.append(('image', ('garment_clean.jpg', garment_clean_bytes, garment_clean_mime)))
    if garment_fit_key and garment_fit_bytes is not None:
        garment_fit_mime = mimetypes.guess_type(garment_fit_key)[0] or 'image/jpeg'
        files.append(('image', ('garment_fit.jpg', garment_fit_bytes, garment_fit_mime)))
    data: dict[str, str | int] = {'model': model, 'prompt': prompt, 'n': 1}
    if include_response_format:
        data['response_format'] = 'b64_json'
    return files, data


def _is_unsupported_multiref(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    body = response.text.lower()
    return 'unsupported' in body or 'too many image' in body or 'invalid image' in body


async def _download_bytes(client: httpx.AsyncClient, url: str, api_key: str) -> bytes:
    response = await client.get(url)
    if response.status_code == 403:
        response = await client.get(url, headers={'Authorization': f'Bearer {api_key}'})
    _raise_for_status(response, provider='OpenAI')
    return response.content


def _safe_b64decode(payload: str) -> bytes:
    try:
        return base64.b64decode(payload)
    except binascii.Error as exc:
        raise ProviderBadRequestError('Invalid base64 payload from OpenAI') from exc


def _raise_for_status(response: httpx.Response, provider: str) -> None:
    if response.status_code in {401, 403}:
        raise ProviderAuthError(f'{provider} authentication failed')
    if response.status_code == 429:
        raise ProviderRateLimitError(f'{provider} rate limit reached')
    if response.status_code == 400:
        try:
            message = response.json().get('error', {}).get('message') or response.text
        except Exception:
            message = response.text
        raise ProviderBadRequestError(message or f'{provider} bad request')
    if response.status_code >= 500:
        raise ProviderTemporaryError(f'{provider} upstream temporary error', code='provider_5xx')
    if response.status_code >= 400:
        raise ProviderBadRequestError(f'{provider} request failed: {response.status_code}')
