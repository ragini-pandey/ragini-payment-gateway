# Ragini Payment Gateway

A developer-grade API key & webhook management platform — Stripe-style key formats, signed deliveries, async retries, anomaly detection, and an audit trail.

[![CI](https://github.com/your-org/ragini-payment-gateway/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)

> Case-study implementation. Architecture rationale is in [`plan.md`](./plan.md).

## What's in the box

- **API keys** with environment scoping (`test` / `live`), peppered HMAC hashing, one-time reveal, indexed `key_id` lookup, expiry, and revocation with audit reason.
- **Webhooks** with server-generated `whsec_*` secrets, **rotate-secret** endpoint, per-endpoint event subscriptions, paginated + status-filtered delivery history.
- **Signed delivery** using a combined header `X-Ragini-Signature: t=<unix>,v1=<hex>` (plus `X-Ragini-Event`, `X-Ragini-Delivery`). Replay window: 5 min.
- **Async dispatch** via Celery with exponential backoff (60 s → 24 h, 6 attempts ± 15 % jitter), automatic **dead-lettering**, and manual retry from the dashboard.
- **Rate limiting** via Redis fixed-window per `key_id` (`RATE_LIMIT_PER_MINUTE`, default 120). A trip emits a deduped `rate_limit_exceeded` security alert.
- **Anomaly detection** via Celery beat: request spikes per-key, deduped 10 min, surface as `security.alert` events and dashboard alerts.
- **Audit trail** (`audit_events`): every dashboard mutation (key create/revoke, webhook create/update/delete/rotate, delivery manual retry) is captured with actor, IP, user-agent, target.
- **Per-request observability**: `X-Request-ID` middleware binds `request_id`, `client_ip`, `method`, `path` into every structlog line.
- **Generic event ingestion** (`POST /v1/events`) with `Idempotency-Key` support — write any catalog event from outside the gateway.

## Architecture

```
┌──────────────────┐     Supabase JWT     ┌────────────────────────────────┐
│ React dashboard  │  ─────────────────▶  │  FastAPI                       │
│ (Vite + RQ)      │                      │   ├ routers (keys/webhooks/…)  │
└──────────────────┘                      │   ├ deps: JWT / API-key auth   │
                                          │   ├ rate limiter (Redis)       │
┌──────────────────┐    rpg_* bearer      │   ├ audit.record               │
│ Your backend     │  ─────────────────▶  │   └ event_emitter.emit         │
└──────────────────┘                      └───────────┬────────────────────┘
                                                      │
                                          Postgres ◀──┤ async SQLAlchemy
                                                      │
                                              Redis ◀─┤  rate, anomaly, idem
                                                      │
                                              Celery ◀┘  fanout / dispatch / beat
                                                  │
                                                  ▼
                                        Webhook receivers (your URLs)
```

## Repo layout

```
ragini-payment-gateway/
├── frontend/   Vite + React 18 + TS + Tailwind + shadcn/ui  (Yarn classic)
├── backend/    FastAPI + Celery + Postgres + Redis           (Python 3.11)
├── supabase/   schema.sql + RLS policies (Phase-1 base tables)
└── .github/    CI workflow (lint, migrate, pytest, frontend build)
```

## Quickstart

### Prerequisites

- Node ≥ 20, Yarn classic v1
- Python ≥ 3.11
- Docker (for Postgres + Redis), or local equivalents
- A [Supabase](https://supabase.com) project with Google OAuth enabled

### 1. Supabase

1. New project on supabase.com.
2. Auth → Providers → Google. Redirect URL: `http://localhost:5173/auth/callback`.
3. SQL Editor → paste & run [`supabase/schema.sql`](./supabase/schema.sql).
4. Copy project URL + anon key (frontend) and JWT secret / JWKS URL (backend).

### 2. Backend

```bash
cd backend
cp .env.example .env
# fill DATABASE_URL, SUPABASE_*, generate API_KEY_PEPPER:
python -c "import secrets; print(secrets.token_hex(32))"
docker compose up   # api + worker + beat + redis
```

API on `http://localhost:8000`. The full curl walkthrough lives in [`backend/README.md`](./backend/README.md#walkthrough).

### 3. Frontend

```bash
cd frontend
cp .env.example .env
# fill VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL=http://localhost:8000
yarn install
yarn dev
```

Open http://localhost:5173, sign in with Google.

## Assignment alignment

| Requirement                          | Where                                                                |
| ------------------------------------ | -------------------------------------------------------------------- |
| Generate & manage API keys           | `backend/app/security/api_keys.py`, `routers/keys.py`, `ApiKeysPage` |
| Hashed at rest, plaintext shown once | HMAC-SHA256 + pepper; `RevealKeyOnceDialog`                          |
| Webhook configuration                | `routers/webhooks.py`, `WebhooksPage`, `CreateWebhookDialog`         |
| Signed deliveries                    | `security/hmac_sign.py`, verified by `scripts/verify_signature.py`   |
| Async + retries + DLQ                | `workers/tasks/dispatch_delivery.py`, backoff in `test_backoff.py`   |
| Delivery log / retry from UI         | `WebhookDetailDrawer`, `POST /v1/deliveries/{id}/retry`              |
| Analytics                            | `UsageChart` (recharts) + `GET /v1/keys/{id}/usage`                  |
| Security alerts                      | `routers/security.py`, `SecurityAlertsPage`, anomaly scan beat task  |
| Rate limiting                        | `security/rate_limit.py` wired into `deps.get_current_api_key`       |
| Audit log                            | `services/audit.py`, `audit_events` table, `GET /v1/audit`           |
| CI                                   | `.github/workflows/ci.yml`                                           |

## What I'd improve with more time

1. **Integration tests** end-to-end against a real Postgres+Redis container, covering the rate-limit → alert path, retry-and-dead-letter, and rotate-secret invalidating in-flight deliveries.
2. **Key scopes / permissions** (read-only, write, restricted resources) — currently a key has uniform power within its environment.
3. **Pepper rotation** with dual-pepper verify + lazy re-hash on next auth.
4. **OpenTelemetry traces** flowing through Celery so a single trace covers the API call → fanout → dispatch → receiver response.
5. **Multi-tenant teams** + role-based dashboard access on top of the per-user model.
6. **Frontend audit page** + signed-URL exports of usage data.
