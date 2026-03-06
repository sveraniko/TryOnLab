import asyncio
from pathlib import Path

import pytest

from app.services.storage import LocalStorageBackend, StorageError


def test_local_storage_put_exists_get_delete(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=str(tmp_path))
    key = 'tryon/jobs/job-1/input/file.txt'
    payload = b'hello storage'

    asyncio.run(storage.put_bytes(key, payload, content_type='text/plain'))
    assert asyncio.run(storage.exists(key)) is True
    assert asyncio.run(storage.get_bytes(key)) == payload

    asyncio.run(storage.delete(key))
    assert asyncio.run(storage.exists(key)) is False


def test_local_storage_path_traversal_rejected(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=str(tmp_path))

    with pytest.raises(StorageError):
        asyncio.run(storage.put_bytes('../x', b'bad'))


def test_local_storage_empty_key_rejected(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=str(tmp_path))

    with pytest.raises(StorageError):
        asyncio.run(storage.put_bytes('   ', b'bad'))

    with pytest.raises(StorageError):
        asyncio.run(storage.put_bytes('./', b'bad'))
