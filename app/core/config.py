from functools import lru_cache

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - lightweight test env fallback
    class BaseSettings:
        def __init__(self, **kwargs):
            for name, value in self.__class__.__dict__.items():
                if name.startswith('_') or callable(value):
                    continue
                setattr(self, name, kwargs.get(name, value))

    def SettingsConfigDict(**kwargs):
        return kwargs


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_env: str = 'dev'
    log_level: str = 'INFO'
    telegram_bot_token: str = ''
    api_base_url: str = 'http://api:8000'
    database_url: str = 'postgresql+asyncpg://tryonlab:tryonlab@postgres:5432/tryonlab'
    redis_url: str = 'redis://redis:6379/0'

    retention_hours: int = 72
    max_upload_mb: int = 12
    job_queue_key: str = 'queue:jobs'
    job_status_ttl_seconds: int = 3600
    cleanup_interval_seconds: int = 300
    bot_rate_limit_image_per_hour: int = 20
    bot_rate_limit_video_per_hour: int = 10
    bot_rate_limit_retry_per_hour: int = 20
    bot_provider_meta_cache_ttl_seconds: int = 60
    ai_provider_default: str = 'dummy'
    ai_provider_allowlist: str = 'grok,openai,dummy'

    xai_api_key: str = ''
    xai_base_url: str = 'https://api.x.ai/v1'
    xai_image_model: str = 'grok-imagine-image'
    xai_video_model: str = 'grok-imagine-video'
    xai_image_response_format: str = 'b64_json'
    xai_video_duration: int = 4
    xai_video_aspect_ratio: str = '9:16'
    xai_video_resolution: str = '480p'
    xai_poll_interval_seconds: int = 5
    xai_poll_timeout_seconds: int = 600

    openai_api_key: str = ''
    openai_base_url: str = 'https://api.openai.com/v1'
    openai_image_model: str = 'gpt-image-1'
    openai_video_model: str = 'sora-2'
    openai_video_size: str = '1280x720'
    openai_video_seconds: str = '4'
    openai_poll_interval_seconds: int = 10
    openai_poll_timeout_seconds: int = 900

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

    vision_parsing_backend: str = 'none'
    vision_parsing_model_path: str = '/app/models/human_parsing.onnx'
    vision_mask_margin_px: int = 24
    vision_mask_dilate_px: int = 12
    vision_mask_feather_px: int = 16
    vision_debug_save_masks: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
