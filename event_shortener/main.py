from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import getLevelNamesMapping

import structlog
from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI

from event_shortener.config import Settings
from event_shortener.ioc import AppProvider
from event_shortener.logger import setup_logger
from event_shortener.metrics import HttpMetricsMiddleware
from event_shortener.routes import root_router
from event_shortener.telemetry import instrument_asyncpg, instrument_fastapi, setup_tracing


container = make_async_container(AppProvider(), FastapiProvider())
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    settings = await container.get(Settings)
    log_level = getLevelNamesMapping().get(settings.log_level)
    setup_logger(log_level=log_level, console_render=settings.debug)

    logger.info("Starting event-shortener application", log_level=settings.log_level, debug=settings.debug)
    yield
    logger.info("Shutting down event-shortener application")
    await container.close()
    logger.info("Event-shortener application shutdown complete")


app = FastAPI(title="event-shortener", version="0.1.0", lifespan=lifespan)
setup_tracing()
instrument_fastapi(app)
instrument_asyncpg()
setup_dishka(container=container, app=app)
app.include_router(root_router)

# Auth is enforced per-router (require_api_key on the /api/v1 router only); the
# public redirect and /health, /ready, /metrics are intentionally open.
app.add_middleware(HttpMetricsMiddleware)
