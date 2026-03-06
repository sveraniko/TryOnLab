from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from urllib.parse import quote

import asyncio
try:
    import boto3
    from botocore.exceptions import ClientError
except ModuleNotFoundError:  # pragma: no cover - optional for local backend tests
    boto3 = None

    class ClientError(Exception):
        pass


if TYPE_CHECKING:
    from app.core.config import Settings


class StorageError(Exception):
    pass


class StorageBackend(Protocol):
    async def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None: ...

    async def get_bytes(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...

    async def get_url(self, key: str, expires_seconds: int | None = None) -> str: ...

    async def put_file(self, key: str, path: Path, content_type: str | None = None) -> None: ...


class LocalStorageBackend:
    def __init__(self, root_dir: str) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_key_path(self, key: str) -> Path:
        candidate = Path(key)
        if candidate.is_absolute():
            raise StorageError('Storage key must be a relative path')

        if any(part == '..' for part in candidate.parts):
            raise StorageError('Storage key cannot contain path traversal')

        resolved = (self.root_dir / candidate).resolve()
        if resolved != self.root_dir.resolve() and self.root_dir.resolve() not in resolved.parents:
            raise StorageError('Storage key resolves outside of storage root')

        return resolved

    async def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        _ = content_type
        target = self._resolve_key_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_bytes, data)

    async def put_file(self, key: str, path: Path, content_type: str | None = None) -> None:
        data = await asyncio.to_thread(path.read_bytes)
        await self.put_bytes(key, data, content_type=content_type)

    async def get_bytes(self, key: str) -> bytes:
        target = self._resolve_key_path(key)
        if not target.exists():
            raise StorageError(f'Key not found: {key}')
        return await asyncio.to_thread(target.read_bytes)

    async def delete(self, key: str) -> None:
        target = self._resolve_key_path(key)
        if target.exists():
            await asyncio.to_thread(target.unlink)

    async def exists(self, key: str) -> bool:
        target = self._resolve_key_path(key)
        return await asyncio.to_thread(target.exists)

    async def get_url(self, key: str, expires_seconds: int | None = None) -> str:
        _ = expires_seconds
        target = self._resolve_key_path(key)
        return target.as_uri()


class S3StorageBackend:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = 'us-east-1',
        use_ssl: bool = False,
        default_ttl_seconds: int = 3600,
        public_base_url: str = '',
    ) -> None:
        self.bucket = bucket
        self.default_ttl_seconds = default_ttl_seconds
        self.public_base_url = public_base_url.strip().rstrip('/')
        if boto3 is None:
            raise StorageError('boto3 is required for S3StorageBackend')

        self.client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            use_ssl=use_ssl,
        )

    async def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        kwargs: dict[str, str | bytes] = {'Bucket': self.bucket, 'Key': key, 'Body': data}
        if content_type:
            kwargs['ContentType'] = content_type
        await asyncio.to_thread(lambda: self.client.put_object(**kwargs))

    async def put_file(self, key: str, path: Path, content_type: str | None = None) -> None:
        data = await asyncio.to_thread(path.read_bytes)
        await self.put_bytes(key, data, content_type=content_type)

    async def get_bytes(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                lambda: self.client.get_object(Bucket=self.bucket, Key=key)
            )
        except ClientError as exc:
            raise StorageError(f'Failed to get object: {key}') from exc

        return await asyncio.to_thread(lambda: response['Body'].read())

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(lambda: self.client.delete_object(Bucket=self.bucket, Key=key))
        except ClientError as exc:
            raise StorageError(f'Failed to delete object: {key}') from exc

    async def exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(lambda: self.client.head_object(Bucket=self.bucket, Key=key))
            return True
        except ClientError as exc:
            error_code = exc.response.get('Error', {}).get('Code', '')
            if error_code in {'404', 'NoSuchKey', 'NotFound'}:
                return False
            raise StorageError(f'Failed to check object existence: {key}') from exc

    async def get_url(self, key: str, expires_seconds: int | None = None) -> str:
        ttl = expires_seconds or self.default_ttl_seconds

        if self.public_base_url:
            return f'{self.public_base_url}/{quote(key)}'

        try:
            return await asyncio.to_thread(
                lambda: self.client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket, 'Key': key},
                    ExpiresIn=ttl,
                )
            )
        except ClientError as exc:
            raise StorageError(f'Failed to generate URL for key: {key}') from exc


def create_storage(settings: "Settings") -> StorageBackend:
    backend = settings.storage_backend.lower().strip()
    if backend == 'local':
        return LocalStorageBackend(root_dir=settings.storage_local_dir)

    if backend == 's3':
        required = {
            'STORAGE_S3_ENDPOINT': settings.storage_s3_endpoint,
            'STORAGE_S3_BUCKET': settings.storage_s3_bucket,
            'STORAGE_S3_ACCESS_KEY': settings.storage_s3_access_key,
            'STORAGE_S3_SECRET_KEY': settings.storage_s3_secret_key,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise StorageError(f'Missing required S3 settings: {", ".join(missing)}')

        return S3StorageBackend(
            endpoint=settings.storage_s3_endpoint,
            bucket=settings.storage_s3_bucket,
            access_key=settings.storage_s3_access_key,
            secret_key=settings.storage_s3_secret_key,
            region=settings.storage_s3_region,
            use_ssl=settings.storage_s3_use_ssl,
            default_ttl_seconds=settings.signed_url_ttl_seconds,
            public_base_url=settings.storage_s3_public_base_url,
        )

    raise StorageError(f'Unsupported storage backend: {settings.storage_backend}')
