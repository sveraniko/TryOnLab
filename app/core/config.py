from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_env: str = 'dev'
    log_level: str = 'INFO'
    telegram_bot_token: str = ''
    database_url: str = 'postgresql+asyncpg://tryonlab:tryonlab@postgres:5432/tryonlab'
    redis_url: str = 'redis://redis:6379/0'


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
