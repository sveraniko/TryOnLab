from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_env: str = 'dev'
    log_level: str = 'INFO'
    telegram_bot_token: str = ''
    database_url: str = 'postgresql+asyncpg://tryonlab:tryonlab@postgres:5432/tryonlab'
    redis_url: str = 'redis://redis:6379/0'

    storage_backend: str = 'local'
    storage_local_dir: str = '/app/storage'
    storage_public_base_url: str = ''
    signed_url_ttl_seconds: int = 3600

    storage_s3_endpoint: str = ''
    storage_s3_bucket: str = ''
    storage_s3_access_key: str = ''
    storage_s3_secret_key: str = ''
    storage_s3_region: str = 'us-east-1'
    storage_s3_use_ssl: bool = False
    storage_s3_public_base_url: str = ''


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
