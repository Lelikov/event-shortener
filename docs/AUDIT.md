# event-shortener: Audit

New service (created 2026-06-13) built to the event-* conventions. No audit
findings carried over — this section tracks issues found in this service going
forward.

## Status

| Area | State |
|------|-------|
| Tests | `uv run pytest` green (route-level integration against real Postgres + controller-level collision retry). |
| Lint | `uv run ruff check .` clean; `ruff format` clean. |
| Auth | Static bearer key on `/api/v1/*`, constant-time compared. Redirect + ops endpoints intentionally public. |
| Migrations | Single Alembic revision (`0001_initial`); container runs `alembic upgrade head` on start. |

## Design notes / accepted limitations

- **Single static API key.** No rotation or per-caller keys. Adequate for an
  internal-only service behind the compose network; revisit if exposed.
- **No rate limiting.** The redirect is public but does only one indexed lookup;
  no abuse controls. Acceptable at the current (internal meeting-link) scale.
- **No public/internal URL split.** Booking builds links from a single base
  URL; a `SHORTENER_PUBLIC_URL` split-horizon is a noted future option, out of
  scope here.
- **Ident collision budget.** Bounded at 5 regenerations; at 62^7 keyspace and
  this scale, exhausting it is effectively impossible. Exhaustion raises
  `IdentGenerationError` → 500, surfaced rather than silently retried forever.

## Open items

_None._
