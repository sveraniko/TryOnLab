from __future__ import annotations

from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str, tg_user_id: int, tg_chat_id: int) -> None:
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'X-TG-User-Id': str(tg_user_id),
            'X-TG-Chat-Id': str(tg_chat_id),
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=60.0, headers=self.headers) as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return None

    async def get_me(self) -> dict[str, Any]:
        return await self._request('GET', '/me')

    async def patch_me(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request('PATCH', '/me', json=payload)

    async def list_photos(self, offset: int = 0, limit: int = 9) -> dict[str, Any]:
        return await self._request('GET', '/me/photos', params={'offset': offset, 'limit': limit})

    async def upload_user_photo(self, content: bytes, filename: str = 'user.jpg') -> dict[str, Any]:
        files = {'photo': (filename, content, 'image/jpeg')}
        return await self._request('POST', '/me/photos', files=files)

    async def activate_photo(self, photo_id: int) -> dict[str, Any]:
        return await self._request('POST', f'/me/photos/{photo_id}/activate')

    async def delete_photo(self, photo_id: int) -> dict[str, Any]:
        return await self._request('DELETE', f'/me/photos/{photo_id}')

    async def delete_all_photos(self) -> dict[str, Any]:
        return await self._request('DELETE', '/me/photos')

    async def purge_me(self) -> dict[str, Any]:
        return await self._request('POST', '/me/purge')

    async def list_providers(self) -> list[dict[str, Any]]:
        return await self._request('GET', '/meta/providers')

    async def create_job(
        self,
        *,
        product: bytes,
        user_photo_id: int,
        fit_pref: str | None,
        measurements_json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        files = {'product_image': ('product.jpg', product, 'image/jpeg')}
        data: dict[str, Any] = {'user_photo_id': str(user_photo_id)}
        if fit_pref:
            data['fit_pref'] = fit_pref
        if measurements_json:
            import json

            data['measurements_json'] = json.dumps(measurements_json)
        return await self._request('POST', '/jobs', files=files, data=data)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._request('GET', f'/jobs/{job_id}')

    async def retry_job(self, job_id: str) -> dict[str, Any]:
        return await self._request('POST', f'/jobs/{job_id}/retry')

    async def create_video(self, job_id: str, preset: int) -> dict[str, Any]:
        return await self._request('POST', f'/jobs/{job_id}/video', params={'preset': preset})

    async def list_jobs(self, offset: int = 0, limit: int = 10) -> dict[str, Any]:
        return await self._request('GET', '/jobs', params={'offset': offset, 'limit': limit})
