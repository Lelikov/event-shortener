from datetime import UTC, datetime

import structlog
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from event_shortener import metrics
from event_shortener.auth import require_api_key
from event_shortener.interfaces.shortener import IShortenerController
from event_shortener.pages import EXPIRED_PAGE, NOT_ACTIVE_PAGE, NOT_FOUND_PAGE
from event_shortener.schemas.short_url import IdentResponse, IdentStatsResponse, ShortenRequest


logger = structlog.get_logger(__name__)

root_router = APIRouter(route_class=DishkaRoute)

# Every /api/v1/* route is gated by the static bearer key. The public redirect
# and the ops endpoints are deliberately mounted on separate, unauthenticated
# routers.
api_router = APIRouter(
    prefix="/api/v1/urls",
    tags=["urls"],
    route_class=DishkaRoute,
    dependencies=[Depends(require_api_key)],
)


@api_router.post("/shorten", response_model=IdentResponse, status_code=status.HTTP_201_CREATED)
async def shorten(body: ShortenRequest, controller: FromDishka[IShortenerController]) -> IdentResponse:
    ident, created = await controller.shorten(body.to_dto())
    if created:
        metrics.URLS_CREATED_TOTAL.inc()
    return IdentResponse(ident=ident)


@api_router.get("/external/{external_id}", response_model=IdentResponse)
async def get_by_external_id(external_id: str, controller: FromDishka[IShortenerController]) -> IdentResponse:
    ident = await controller.get_ident(external_id)
    if ident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"external_id {external_id!r} not found")
    return IdentResponse(ident=ident)


@api_router.patch("/external/{old_external_id}", response_model=IdentResponse)
async def update_by_external_id(
    old_external_id: str,
    body: ShortenRequest,
    controller: FromDishka[IShortenerController],
) -> IdentResponse:
    ident = await controller.update(old_external_id, body.to_dto())
    if ident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"external_id {old_external_id!r} not found",
        )
    return IdentResponse(ident=ident)


@api_router.delete("/external/{external_id}")
async def delete_by_external_id(external_id: str, controller: FromDishka[IShortenerController]) -> dict:
    await controller.delete(external_id)
    # Idempotent: deleting an unknown external_id still returns 200 {} so a
    # redelivered teardown is a no-op rather than an error.
    return {}


@api_router.get("/{ident}/stats", response_model=IdentStatsResponse)
async def ident_stats(ident: str, controller: FromDishka[IShortenerController]) -> IdentStatsResponse:
    record = await controller.resolve(ident)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ident {ident!r} not found")
    return IdentStatsResponse(ident=record.ident, click_count=record.click_count)


redirect_router = APIRouter(tags=["redirect"], route_class=DishkaRoute)

_NO_STORE = {"Cache-Control": "no-store"}


@redirect_router.get("/{ident}")
async def redirect(ident: str, controller: FromDishka[IShortenerController]) -> Response:
    """Public, unauthenticated redirect. 307 in-window, 410 outside it, 404 unknown.

    Error states render a minimal HTML page (browser-facing); API routes stay JSON.
    """
    record = await controller.resolve(ident)
    if record is None:
        metrics.REDIRECTS_TOTAL.labels(result="not_found").inc()
        return HTMLResponse(content=NOT_FOUND_PAGE, status_code=status.HTTP_404_NOT_FOUND, headers=_NO_STORE)

    now = datetime.now(UTC)
    if record.not_before is not None and now < record.not_before:
        metrics.REDIRECTS_TOTAL.labels(result="expired").inc()
        return HTMLResponse(content=NOT_ACTIVE_PAGE, status_code=status.HTTP_410_GONE, headers=_NO_STORE)
    if record.expires_at is not None and now >= record.expires_at:
        metrics.REDIRECTS_TOTAL.labels(result="expired").inc()
        return HTMLResponse(content=EXPIRED_PAGE, status_code=status.HTTP_410_GONE, headers=_NO_STORE)

    try:
        await controller.register_click(ident)
    except Exception:
        logger.exception("Failed to record click; serving redirect anyway", ident=ident)
    metrics.REDIRECTS_TOTAL.labels(result="ok").inc()
    return RedirectResponse(url=record.long_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


ops_router = APIRouter(tags=["ops"], route_class=DishkaRoute)

READY_CHECK_QUERY = "select 1"


@ops_router.get("/health")
async def health() -> dict:
    """Liveness probe: the process is up and serving HTTP. No dependency calls."""
    return {"status": "ok"}


@ops_router.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus exposition endpoint."""
    return metrics.metrics_response()


@ops_router.get("/ready")
async def ready(engine: FromDishka[AsyncEngine]) -> JSONResponse:
    """Readiness probe: verifies PostgreSQL connectivity (the only critical dependency)."""
    database_ok = False
    try:
        async with engine.connect() as connection:
            await connection.execute(text(READY_CHECK_QUERY))
        database_ok = True
    except Exception:
        logger.exception("Readiness check failed: database unreachable")

    checks = {"database": database_ok}
    if not database_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": checks},
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready", "checks": checks})


# Order matters: the ops + api routers are registered before the catch-all
# `/{ident}` redirect so /health, /ready, /metrics, /api/* are never swallowed.
root_router.include_router(api_router)
root_router.include_router(ops_router)
root_router.include_router(redirect_router)
