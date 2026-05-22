# Ragini Payment Gateway — architecture & roadmap

Living planning doc. Replaces the original Phase-1 frontend-only plan; the current codebase ships everything that doc called "Phase 2" and most of "Phase 3".

## Goals

A developer-grade API key + webhook platform that a backend engineer can integrate against without surprises:

1. Predictable Stripe-style key format with safe storage.
2. Signed, idempotent, async webhook delivery with retries and a dead-letter terminal state.
3. First-class operational signals: usage analytics, security alerts, audit log.
4. A calm dashboard for managing keys + webhooks and inspecting delivery history.

## High-level architecture

```
┌──────────────────┐   Supabase JWT     ┌────────────────────────────────┐
│ React dashboard  │ ─────────────────▶ │  FastAPI                       │
│ (Vite + RQ)      │                    │   ├ routers (keys/webhooks/…)  │
└──────────────────┘                    │   ├ deps: JWT / API-key auth   │
                                        │   ├ rate limiter (Redis)       │
┌──────────────────┐  rpg_* bearer      │   ├ audit.record               │
│ Caller backend   │ ─────────────────▶ │   └ event_emitter.emit         │
└──────────────────┘                    └───────────┬────────────────────┘
                                                    │
                                        Postgres ◀──┤ async SQLAlchemy
                                                    │
                                            Redis ◀─┤  rate / anomaly / idem
                                                    │
                                            Celery ◀┘  fanout / dispatch / beat
                                                │
                                                ▼
                                      Webhook receivers (user URLs)
```

- **Frontend** ([`frontend/`](frontend/)): Vite + React 18 + TS + Tailwind + shadcn/ui, Yarn classic, react-router v7, TanStack Query. Supabase Google OAuth only — never reaches into Supabase for resource data.
- **Backend** ([`backend/`](backend/)): FastAPI + Pydantic v2, async SQLAlchemy 2 + asyncpg, Alembic, Celery 5 + Redis, httpx, structlog. Postgres lives behind Supabase (service-role connection via Supavisor transaction pooler — 5 s statement timeout enforced server-side in [`app/db.py`](backend/app/db.py)).
- **Supabase** ([`supabase/schema.sql`](supabase/schema.sql)): base auth-owned tables + RLS. Phase-2 schema (env-scoped keys, usage events, webhook events/deliveries, security alerts, audit events) is layered on top via Alembic migrations in [`backend/alembic/versions/`](backend/alembic/versions/).

## What's shipped

### API keys
- Format: `rpg_<env>_<key_id>_<secret>` ([`backend/app/security/api_keys.py`](backend/app/security/api_keys.py)). `key_id` is unique-indexed for O(1) lookup; `secret` is verified against `HMAC-SHA256(API_KEY_PEPPER, secret)`.
- Plaintext is returned **only once** in the create response — surfaced through [`RevealKeyOnceDialog`](frontend/src/features/api-keys/) in the dashboard.
- Optional `expires_at`; the `sweep_expired_keys` beat task auto-revokes and emits `api_key.expired`.
- Revoke action records an audit entry and emits `api_key.revoked`.
- Per-key usage analytics: every verified request increments a Redis minute-bucket and is persisted as a `api_key_usage_events` row. `GET /v1/keys/{id}/usage?range=24h|7d|30d` powers the dashboard chart.

### Webhooks & signed delivery
- Server-generated `whsec_*` secrets ([`backend/app/services/webhook_service.py`](backend/app/services/webhook_service.py)).
- Signing scheme: `X-Ragini-Signature: t=<unix>,v1=<hex_hmac_sha256(secret, "<t>.<body>")>` plus `X-Ragini-Event` and `X-Ragini-Delivery` companion headers. 300 s replay window. Reference verifier in [`backend/scripts/verify_signature.py`](backend/scripts/verify_signature.py).
- `POST /v1/webhooks/{id}/rotate-secret` reveals a new plaintext once and invalidates the old immediately.
- Async dispatch via Celery: `fanout_event` → per-delivery `dispatch_delivery` with exponential backoff `60s → 5m → 30m → 2h → 12h → 24h`, ±15 % jitter, 6 attempts max, then `dead_lettered` and a `security.alert` is emitted.
- Every attempt is persisted as a `webhook_deliveries` row (status `pending | retrying | success | failed | dead_lettered`). `POST /v1/deliveries/{id}/retry` lets the dashboard force a new attempt.
- `POST /v1/webhooks/{id}/test` dispatches a synthetic event to validate a receiver.

### Public API
- `POST /v1/payments` records a payment outcome and emits `payment.success` / `payment.error`.
- `POST /v1/events` ingests any catalog event (e.g. from a caller's own backend).
- Both accept an optional `Idempotency-Key` header; the same `(key_id, Idempotency-Key)` pair returns the original response for 24 h (Redis-backed).

### Environments
- `test` / `live` scoping is baked into the key prefix and every dashboard list endpoint (`?environment=test|live`). CORS also allows the `X-Environment` header.
- Webhooks are env-scoped — `test` keys only fan out to `test` webhooks.

### Security signals
- Rate limiting: Redis fixed-window per `key_id` (`RATE_LIMIT_PER_MINUTE`, default 120/min). On trip → `429` with `Retry-After`, a `usage_events` row with status 429, and a deduped `rate_limit_exceeded` `security_alert` (5 min dedup window).
- Anomaly detection: per-key/minute Redis counter, 60-minute baseline; if a key exceeds `max(20, 5 × baseline)` requests in a minute the `scan_anomalies` beat task emits a `request_spike` `security.alert` (10 min dedup).
- Use of a revoked or expired key emits a `security.alert` synchronously inside the auth dependency.
- `GET /v1/security/alerts` powers [`SecurityAlertsPage`](frontend/src/pages/SecurityAlertsPage.tsx).

### Audit trail
- Every state-changing dashboard mutation writes to `audit_events` via [`app.services.audit.record(...)`](backend/app/services/audit.py): `api_key.create|revoke`, `webhook.create|update|delete|rotate_secret`, `webhook_delivery.manual_retry`, plus `sweep_expired` for the auto-revoke path.
- `GET /v1/audit` returns paginated entries with actor, IP, user-agent, target.

### Observability
- `RequestIdMiddleware` binds `request_id`, `client_ip`, `method`, `path` into every structlog line; the request ID is exposed via `X-Request-ID`.
- JSON logs throughout; no plaintext secrets or PII.

## Roadmap (not yet shipped)

1. **Hosted deployment** (managed Postgres + Redis + worker tier; reviewer-ready URL). Currently runs locally via `docker compose up`; ngrok is the demo path.
2. **API gateway in front of FastAPI** to offload edge rate limiting, mTLS / WAF, and global auth, instead of doing it all in-process.
3. **Integration tests** end-to-end against a real Postgres + Redis container — rate-limit → alert, retry → dead-letter, rotate-secret invalidating in-flight deliveries.
4. **Key scopes & permissions** (read-only vs write, resource-restricted) instead of uniform power per environment.
5. **Pepper rotation** with dual-pepper verify and lazy re-hash on next successful auth.
6. **OpenTelemetry** spans threading through Celery so a single trace covers API call → fanout → dispatch → receiver.
7. **Multi-tenant teams** with role-based dashboard access on top of the per-user model.
8. **Dashboard audit page** + signed CSV export of usage data.

## Reference files

- Entry points: [`backend/app/main.py`](backend/app/main.py), [`frontend/src/App.tsx`](frontend/src/App.tsx).
- Config: [`backend/app/config.py`](backend/app/config.py), [`backend/.env.example`](backend/.env.example), [`frontend/.env.example`](frontend/.env.example).
- Schema: [`supabase/schema.sql`](supabase/schema.sql) + Alembic in [`backend/alembic/versions/`](backend/alembic/versions/).
- Conventions for contributors: [`CLAUDE.md`](CLAUDE.md), [`backend/CLAUDE.md`](backend/CLAUDE.md), [`frontend/CLAUDE.md`](frontend/CLAUDE.md).
