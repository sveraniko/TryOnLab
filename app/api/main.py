import logging

from fastapi import FastAPI

from app.api.routers.health import router as health_router
from app.core.config import get_settings
from app.core.constants import APP_NAME
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=APP_NAME)
app.include_router(health_router)


@app.on_event('startup')
async def on_startup() -> None:
    logger.info('API started', extra={'env': settings.app_env})
