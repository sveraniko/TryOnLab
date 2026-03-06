from pathlib import Path
import asyncio

from app.providers.dummy import DummyProvider
from app.services.storage import LocalStorageBackend


def test_dummy_provider_generate_image_copies_person_bytes(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=str(tmp_path))
    provider = DummyProvider(storage=storage)

    person_key = 'tryon/jobs/job-1/input/person.jpg'
    asyncio.run(storage.put_bytes(person_key, b'person-bytes', content_type='image/jpeg'))

    result = asyncio.run(
        provider.generate_image(
            job_id='job-1',
            storage_key_product='tryon/jobs/job-1/input/product.jpg',
            storage_key_person=person_key,
        )
    )

    assert result.storage_key == 'tryon/jobs/job-1/output/image.jpg'
    assert result.content_type == 'image/jpeg'
    assert result.metadata == {'dummy': True}
    assert asyncio.run(storage.get_bytes(result.storage_key)) == b'person-bytes'
