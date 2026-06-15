# event-shortener: API Contracts

Internal HTTP port **8888**. Auth applies to `/api/v1/*` only:
`Authorization: Bearer <SHORTENER_API_KEY>`, constant-time compared
(`hmac.compare_digest`). The redirect and ops endpoints are unauthenticated.

`expires_at` and `not_before` are **float epoch seconds** on the wire (nullable),
stored as `timestamptz`.

## Ident Format

**New links** (created after the format migration) use a **Google-Meet-style
ident**: three groups of three lowercase letters separated by hyphens —
`xxx-xxx-xxx` (e.g. `abc-def-ghi`). **Existing idents keep resolving** — the
redirect endpoint accepts both the old base62 format and the new format.

## click_count

The `short_urls` table has a `click_count` integer column (default 0). It is
incremented **only on a successful `307` redirect** — `410 Gone` and
`404 Not Found` outcomes do not increment it.

## POST /api/v1/urls/shorten

Create (or idempotently fetch) a short URL.

Request:
```json
{
  "long_url": "https://meet.example.org/room/abc",
  "expires_at": 1789000000.0,
  "not_before": 1788000000.0,
  "external_id": "booking-123"
}
```
`expires_at` / `not_before` may be `null`. Response `201`:
```json
{ "ident": "abc-def-ghi" }
```
**Idempotent by `external_id`**: a repeat call with the same `external_id`
returns the existing `ident` (the body fields are not re-applied — use PATCH to
mutate). Auth failure → `401`.

## GET /api/v1/urls/{ident}/stats

Fetch click statistics for a short URL.

```
200 { "ident": "abc-def-ghi", "click_count": 42 }
404   (unknown ident)
```

Auth: `Authorization: Bearer <SHORTENER_API_KEY>`. `click_count` reflects the
number of successful `307` redirects recorded for this ident.

## GET /api/v1/urls/external/{external_id}

```
200 { "ident": "aZ09bcD" }
404            (unknown external_id)
```

## PATCH /api/v1/urls/external/{old_external_id}

Update a record's mutable fields, including its `external_id`. The `ident` is
**preserved**. Request body is identical to `shorten`.
```
200 { "ident": "aZ09bcD" }   (ident unchanged)
404                          (old_external_id unknown)
```

## DELETE /api/v1/urls/external/{external_id}

```
200 {}
```
Idempotent: deleting an unknown `external_id` still returns `200 {}`.

## GET /{ident} — public redirect

```
307 Location: <long_url>   when now ∈ [not_before, expires_at]
410 Gone                   when now < not_before or now >= expires_at
404 Not Found              when ident is unknown / deleted
```
A null bound is open-ended. Unauthenticated.

## Ops endpoints (unauthenticated)

- `GET /health` — liveness; `200 {"status":"ok"}`, no dependency calls.
- `GET /ready` — readiness; pings PostgreSQL.
  `200 {"status":"ready","checks":{"database":true}}` or
  `503 {"status":"not_ready","checks":{"database":false}}`.
- `GET /metrics` — Prometheus exposition (text).

## Metrics

- `http_requests_total{method,route,status}` — RED counter; `route` is the
  template (`/{ident}`, not the raw slug). `/metrics` + `/health` excluded.
- `http_request_duration_seconds{method,route}` — RED histogram.
- `shortener_urls_created_total` — new short URLs minted (idempotent re-calls
  excluded).
- `shortener_redirects_total{result=ok|expired|not_found}` — redirect outcomes.
