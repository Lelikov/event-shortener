# event-shortener: Dependencies

## Runtime dependencies

| Dependency | Purpose | Failure mode |
|------------|---------|--------------|
| PostgreSQL (`pg-shortener`) | Sole datastore; one `short_urls` table | All API + redirect requests fail (5xx); `/ready` returns `503`. `/health` still `200` (liveness only). |

No RabbitMQ, no external HTTP calls, no caches. The service is pure HTTP over a
single database.

## Callers (inbound)

| Caller | Calls | Notes |
|--------|-------|-------|
| `event-booking` | `POST /shorten`, `PATCH`, `DELETE` via its shortener adapter; sends `Authorization: Bearer <SHORTENER_API_KEY>` | Replaces the prior WireMock `shortify` stub. Booking is **unchanged** — it builds `{SHORTENER_URL}/{ident}`. |
| End users / browsers | `GET /{ident}` | Public redirect to the meeting link. |
| Prometheus | `GET /metrics` | Scrape job `event-shortener`. |
| Orchestrator / probes | `GET /health`, `GET /ready` | Liveness / readiness. |

## Configuration

| Env var | Required | Default | Meaning |
|---------|----------|---------|---------|
| `POSTGRES_DSN` | yes | — | asyncpg URL, e.g. `postgresql+asyncpg://postgres:postgres@pg-shortener:5432/event_shortener` |
| `SHORTENER_API_KEY` | yes | — | static bearer key gating `/api/v1/*` |
| `LOG_LEVEL` | no | `INFO` | one of DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `DEBUG` | no | `false` | console (vs JSON) log rendering |

## Build / deploy

- Dockerfile build context is the **`event-shortener` directory itself** (this
  service has no dependency on `event-schemas`).
- `entrypoint.sh` runs `alembic upgrade head`, then
  `uvicorn event_shortener.main:app --host 0.0.0.0 --port 8888`.
- The service owns its schema; the container is the single migration runner.

## Schema (`short_urls`)

`id bigserial PK, ident text UNIQUE NOT NULL, external_id text UNIQUE NOT NULL,
long_url text NOT NULL, not_before timestamptz NULL, expires_at timestamptz NULL,
created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL
DEFAULT now()`. Redirect lookups use the `ident` unique index;
`ix_short_urls_external_id` backs the external-id lookups.
