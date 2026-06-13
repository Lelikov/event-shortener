# event-shortener: Service Overview

## Domain

A minimal URL-shortener built to the event-* conventions. It replaces the
WireMock `shortify` stub in the contour and serves only what the system needs:
the four operations `event-booking` already calls, plus a public redirect.
There is intentionally **no** user/JWT/admin/pagination/rate-limit machinery.

A short URL is a row keyed by:
- **`ident`** — a 7-char base62 token; the public-facing slug (`/{ident}`).
- **`external_id`** — the caller's idempotency / lookup key (e.g. a booking-scoped id).

The caller (event-booking) creates a short URL synchronously, then builds
`{base_url}/{ident}` for inclusion in notifications — so the link must exist
before the notification fires. Hence all operations are REST, not async.

## Subsystems

| Subsystem | Entry point | Toggle |
|-----------|-------------|--------|
| Authenticated CRUD API (`/api/v1/urls`) | `routes.py` (`api_router`) | always on |
| Public redirect (`/{ident}`) | `routes.py` (`redirect_router`) | always on |
| Ops endpoints (`/health`, `/ready`, `/metrics`) | `routes.py` (`ops_router`) | always on |

No background tasks, no message consumers. The container is also the single
Alembic migration runner (`entrypoint.sh` runs `alembic upgrade head` first).

## Idempotency and ident allocation

- **`POST /shorten` is idempotent by `external_id`**: a redelivery returns the
  ident already minted instead of creating a second row. The metric
  `shortener_urls_created_total` only counts genuinely new rows.
- **Ident collision retry**: idents are random base62 (keyspace 62^7 ≈ 3.5e12).
  On the rare `ident` UNIQUE violation the adapter raises `IdentCollisionError`
  and the controller regenerates, up to `MAX_IDENT_ATTEMPTS` (5) before raising
  `IdentGenerationError`.

## Redirect time window

`GET /{ident}` resolves with a single indexed lookup on `ident`:
- `307` to `long_url` when `now ∈ [not_before, expires_at]` (null bound = open).
- `410 Gone` when `now` is before `not_before` or at/after `expires_at`.
- `404` when the ident is unknown or was deleted.

`expires_at` / `not_before` cross the wire as float epoch seconds and are stored
as `timestamptz`.

## Maturity / known limitations

- Single Postgres table; redirect is one indexed lookup, no cache (adequate for
  the internal meeting-link load).
- No public/internal URL split-horizon (booking builds the link from a single
  base URL today; `SHORTENER_PUBLIC_URL` in booking is a noted future option).
- Static single API key (no rotation, no per-caller keys).

## Verification

`uv run pytest` covers: shorten (201 + ident, idempotent re-call), get
(200/404), patch (updates + ident preserved), delete (200 then 404), redirect
(307 in-window / 410 expired / 410 not-yet-active / 404 unknown / 307 open
window), auth (401 missing / 401 wrong / 200 with key; public endpoints open),
and ident collision retry (faked adapter seam). Tests run against a real
PostgreSQL (ephemeral local cluster, or `TEST_POSTGRES_DSN`).
