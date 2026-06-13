# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the server:**
```bash
uvicorn event_shortener.main:app --reload --port 8888
```

**Lint and format:**
```bash
uv run ruff check .
uv run ruff format .
```

**Tests:**
```bash
uv run pytest
```
Tests run against a real PostgreSQL. With no `TEST_POSTGRES_DSN` set, the suite
boots a throwaway local cluster via `initdb`/`pg_ctl` (Homebrew Postgres); if
neither is available the suite skips rather than failing. Point at an existing
DB with `TEST_POSTGRES_DSN=postgresql+asyncpg://...`.

**Pre-commit hooks:**
```bash
pre-commit run --all-files
```

**Alembic migrations:**
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

**Configuration:** Requires a `.env` file. See `.env.example`.

## Architecture

Minimal layered async FastAPI URL-shortener. Pure HTTP — no RabbitMQ, no
background tasks. Replaces the WireMock `shortify` stub in the contour; serves
exactly the contract `event-booking` calls plus a public redirect.

**Request flow:** `routes.py` → `controllers/shortener.py` → `adapters/short_url_db.py` → `adapters/sql.py` (`SqlExecutor`) → SQLAlchemy `AsyncSession` → PostgreSQL

**Layers:**

- **`routes.py`** — three routers on one app: the authenticated `/api/v1/urls`
  router, the public `/{ident}` redirect, and the ops endpoints
  (`/health`, `/ready`, `/metrics`). Converts request bodies → DTOs, calls the
  controller via DI, maps results to response schemas.
- **`controllers/shortener.py`** — business logic: idempotency by `external_id`,
  bounded ident-collision retry, redirect resolution.
- **`adapters/short_url_db.py`** — all SQL via `SqlExecutor`; maps `RowMapping`
  rows to DTOs; raises `IdentCollisionError` on the `ident` UNIQUE violation so
  the controller can regenerate.
- **`adapters/sql.py`** — `SqlExecutor` wraps `AsyncSession` with `text()` SQL.
- **`interfaces/`** — Protocol interfaces (`ISqlExecutor`, `IShortUrlDBAdapter`,
  `IShortenerController`) for loose coupling.
- **`dto/short_url.py`** — frozen dataclasses (`UpsertShortUrlDTO`, `ShortUrlDTO`).
- **`schemas/short_url.py`** — Pydantic request/response; converts float epoch
  seconds on the wire ↔ aware `datetime` for storage as `timestamptz`.
- **`ident.py`** — base62, 7-char random ident generator.
- **`auth.py`** — `require_api_key`: static `Authorization: Bearer` compared with
  `hmac.compare_digest`; gates the `/api/v1` router only.
- **`metrics.py`** — Prometheus: HTTP RED middleware (`http_requests_total`,
  `http_request_duration_seconds` by route template; `/metrics` + `/health`
  excluded), plus `shortener_urls_created_total` and
  `shortener_redirects_total{result=ok|expired|not_found}`.
- **`ioc.py`** — Dishka container. APP scope: `Settings`, `AsyncEngine`,
  `async_sessionmaker`. REQUEST scope: `AsyncSession`, `ISqlExecutor`,
  `IShortUrlDBAdapter`, `IShortenerController`.
- **`db/models.py`** — SQLAlchemy ORM model (`ShortUrl`); used by Alembic only,
  queries are raw SQL.

## Endpoints

| Method | Path | Auth | Behaviour |
|--------|------|------|-----------|
| POST | `/api/v1/urls/shorten` | Bearer | `201 {ident}`; idempotent by `external_id` |
| GET | `/api/v1/urls/external/{external_id}` | Bearer | `200 {ident}` / `404` |
| PATCH | `/api/v1/urls/external/{old_external_id}` | Bearer | `200 {ident}`; updates fields incl. `external_id`, ident preserved; `404` if unknown |
| DELETE | `/api/v1/urls/external/{external_id}` | Bearer | `200 {}` (idempotent) |
| GET | `/{ident}` | public | `307` to `long_url` in window; `410` outside; `404` unknown |
| GET | `/health` | public | liveness, no deps |
| GET | `/ready` | public | DB ping → `200`/`503` |
| GET | `/metrics` | public | Prometheus exposition |

`expires_at` / `not_before` are float epoch seconds on the wire. The redirect is
active when `now ∈ [not_before, expires_at]`; a null bound is open-ended.

## Configuration

| Env var | Meaning |
|---------|---------|
| `POSTGRES_DSN` | asyncpg URL for the service's own DB |
| `SHORTENER_API_KEY` | static bearer key gating `/api/v1/*` |
| `LOG_LEVEL` | log level (default `INFO`) |
| `DEBUG` | console log rendering (default `false`) |

## Service Documentation

- `docs/SERVICE_OVERVIEW.md` — architecture, maturity, known issues
- `docs/API_CONTRACTS.md` — HTTP endpoints, request/response schemas
- `docs/DEPENDENCIES.md` — external dependencies and failure modes
- `docs/AUDIT.md` — audit findings for this service

Cross-service architecture docs live in the monorepo root `../docs/`.
