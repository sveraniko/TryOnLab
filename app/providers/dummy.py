from __future__ import annotations

from app.providers.base import ProviderBase, ProviderCapabilities, ProviderResult, ProviderUnsupportedError
from app.services.storage import StorageBackend
from app.services.storage_keys import job_key


class DummyProvider(ProviderBase):
    name = 'dummy'
    capabilities = ProviderCapabilities(video=False)

    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage

    async def generate_image(
        self,
        *,
        job_id: str,
        storage_key_product: str,
        storage_key_person: str,
        fit_pref: str | None = None,
        measurements: dict | None = None,
    ) -> ProviderResult:
        _ = storage_key_product
        _ = fit_pref
        _ = measurements
        person_bytes = await self.storage.get_bytes(storage_key_person)
        output_key = job_key(job_id, 'output', 'image.jpg')
        await self.storage.put_bytes(output_key, person_bytes, content_type='image/jpeg')
        return ProviderResult(storage_key=output_key, content_type='image/jpeg', metadata={'dummy': True})

    async def generate_video(
        self,
        *,
        job_id: str,
        storage_key_image_result: str,
        preset: int,
    ) -> ProviderResult:
        _ = job_id
        _ = storage_key_image_result
        _ = preset
        raise ProviderUnsupportedError('video not supported in dummy')
