# Backend

FastAPI service for API key management, webhook dispatch, and security signals. Async SQLAlchemy + Alembic + Celery + Redis. Python managed via `pyproject.toml`.

## Layout

- `app/main.py` — FastAPI app, CORS, RequestIdMiddleware, router wiring.
- `app/routers/` — HTTP routes: `health`, `keys`, `webhooks`, `deliveries`, `payments`, `events`, `security`, `audit`.
- `app/models/` — SQLAlchemy ORM (`api_key`, `api_key_usage`, `webhook`, `webhook_event`, `webhook_delivery`, `security_alert`, `audit_event`).
- `app/schemas/` — Pydantic request/response schemas. Keep ORM and wire-format separate.
- `app/services/` — business logic (`key_service`, `webhook_service`, `event_emitter`, `audit`).
- `app/security/` — `api_keys` (generation + HMAC-with-pepper hashing + verification), `hmac_sign` (webhook signature), `jwt` (Supabase JWT verification), `rate_limit` (Redis fixed-window).
- `app/middleware/` — `request_id` (per-request `X-Request-ID` + structlog binding).
- `app/workers/` — `celery_app.py` (beat schedule) + `tasks/` (`dispatch_delivery`, `fanout_event`, `scan_anomalies`). The `sweep_expired_keys` beat task lives inside `scan_anomalies.py`.
- `app/deps.py` — FastAPI dependencies (`get_current_user`, `get_current_api_key`, DB session, environment).
- `alembic/versions/` — migrations (`0001_phase2_schema`, `0002_audit_events`). Never edit an applied revision; always add a new one.

## Conventions

- Dashboard routes use `deps.get_current_user` (Supabase JWT). Public-API routes (`/v1/payments`, `/v1/events`) use `deps.get_current_api_key` (bearer `rpg_*`). Health is unauthenticated.
- DB access: use the async session via `app.deps.DbDep` (which calls `app.db.get_db`). No sync engine in request paths. Statement timeout is enforced server-side (5s).
- API keys: format `rpg_<env>_<key_id>_<secret>`. Store `key_id` (unique-indexed for O(1) lookup), `key_prefix`, `last_four`, and `key_hash = HMAC-SHA256(API_KEY_PEPPER, secret)`. Plaintext is returned **only** in the create response and is never logged.
- Webhook signing: combined header `X-Ragini-Signature: t=<unix>,v1=<hex_hmac_sha256(secret, "<t>.<body>")>`. Reject verification if `|now - t| > 300s` (see `scripts/verify_signature.py`).
- Webhook delivery: enqueue via Celery; exponential backoff (60s→24h, 6 attempts max, ±15% jitter); statuses `pending | retrying | success | failed | dead_lettered`. Persist every attempt in `webhook_deliveries`.
- Rate limiting: `app.security.rate_limit.check_and_consume` runs inside `get_current_api_key`. Tripping it records a 429 usage row + a deduped `rate_limit_exceeded` security alert.
- Idempotency: `POST /v1/payments` and `POST /v1/events` accept an optional `Idempotency-Key` header; the same `(key_id, Idempotency-Key)` pair returns the original response for 24 h via Redis.
- Environments: dashboard list endpoints accept `?environment=test|live`; CORS allows the `X-Environment` header. Webhook fan-out is env-scoped.
- Audit trail: every dashboard mutation MUST call `app.services.audit.record(...)` with `actor_user_id`, `action`, `target_type`, `target_id`. The audit row is committed alongside the mutation.
- Ownership: every query filters by `user_id` from the JWT or API key. No endpoint may return rows the caller doesn't own.
- Errors: raise `HTTPException` with stable error codes; do not leak internal messages.
- Logging: structlog is JSON-only; `request_id`, `method`, `path`, `client_ip` are bound automatically by `RequestIdMiddleware`.

## Commands

- Run full stack: `docker compose up`
- Run API only (with local venv): `source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`
- Tests: `pytest` (see `app/tests/`)
- New migration: `alembic revision --autogenerate -m "msg"` → review the generated SQL → `alembic upgrade head`
- Verify a webhook signature locally: `python scripts/verify_signature.py`

## Don't

- Don't log plaintext API keys, webhook secrets, JWTs, or request bodies that may contain PII.
- Don't perform synchronous outbound HTTP from a request handler — enqueue a Celery task.
- Don't bypass JWT auth or ownership checks "just for an admin tool" — add a proper scoped mechanism instead.
- Don't add blocking DB calls (sync session) inside async paths.
- Don't edit an already-applied Alembic revision; create a new one.
