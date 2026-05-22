# Ragini Payment Gateway

Monorepo:
- `frontend/` — Vite + React 18 + TS + Tailwind + shadcn/ui. **Yarn classic (v1)**. Supabase Google OAuth + data.
- `backend/` — FastAPI + SQLAlchemy (async) + Alembic + Celery + Redis. Owns API keys, webhook dispatch, HMAC signing, anomaly detection, rate limiting, audit trail.
- `supabase/schema.sql` — Phase-1 tables + RLS policies. The backend layers an Alembic-managed Phase-2 schema (env-scoped keys, usage events, webhook events/deliveries, security alerts, audit events) on top.
- `plan.md` — read before any architectural change.

## Cross-cutting rules

- Never commit secrets. `.env` files are gitignored; update `.env.example` whenever a new env var is introduced.
- **API key generation + hashing live in the backend only.** Format: `rpg_<env>_<key_id>_<secret>` where `key_id` is the indexed lookup column and the secret is verified via `HMAC-SHA256(API_KEY_PEPPER, secret)`. The frontend never generates, hashes, or stores plaintext keys beyond the one-time reveal returned from a create mutation.
- **Webhook secrets (`whsec_…`) are generated server-side.** Signature scheme: combined header `X-Ragini-Signature: t=<unix>,v1=<hex_hmac_sha256(secret, "<t>.<body>")>` plus `X-Ragini-Event` and `X-Ragini-Delivery` companion headers. Receivers reject if `|now - t| > 300s`.
- **Public API auth** (`/v1/payments`, `/v1/events`) uses a bearer `rpg_*` key. Dashboard endpoints use the Supabase JWT. The two auth modes never mix on a single route.
- **Rate limiting**: every verified API-key request passes through a Redis fixed-window limiter (`RATE_LIMIT_PER_MINUTE`, default 120/min/key). A 429 emits a deduped `rate_limit_exceeded` security alert.
- **Audit trail**: every state-changing dashboard mutation (`api_key.create|revoke`, `webhook.create|update|delete|rotate_secret`, `webhook_delivery.manual_retry`) writes to `audit_events` via `app.services.audit.record(...)`. Add a corresponding call whenever you add a new mutation.
- Frontend talks to the backend via `frontend/src/lib/apiClient.ts`. All server state flows through **TanStack React Query** — no hand-rolled loading/error state in components.
- Routing uses **`react-router` v7 unified package** — always import from `"react-router"`, never `"react-router-dom"`.
- Ownership: every backend query MUST filter by `user_id` derived from the verified Supabase JWT (or the API key's owner). There is no admin bypass.
- Each protected route in the frontend is wrapped in `<ErrorBoundary>` (see `src/components/ErrorBoundary.tsx`).

## Visual direction (frontend)

Daily-Geeta–inspired. Palette: ivory `#FBF7F0`, card `#FFFFFF`, border `#E9DFC9`, saffron `#C8612A`, gold `#D4A24C`, ink `#2A1F14`, muted `#6B5A47`. Headings in `Fraunces` (serif), body in `Inter`. Generous whitespace, rounded-2xl, soft shadows. No dark/fintech look. Home screen is **two centered cards** (API Keys, Webhooks) — never tabs or a sidebar.

## Commands

- Frontend dev: `cd frontend && yarn dev`
- Frontend build (must pass with zero TS errors before PR): `cd frontend && yarn build`
- Backend dev (full stack): `cd backend && docker compose up`
- Backend tests: `cd backend && pytest`
- New migration: `cd backend && alembic revision --autogenerate -m "msg"` → review → `alembic upgrade head`

## Don't

- Don't add `react-router-dom` to the frontend.
- Don't generate or hash API keys in the frontend.
- Don't perform synchronous outbound HTTP from FastAPI request handlers — enqueue a Celery task.
- Don't edit Alembic revisions that have already been applied; create a new one.
- Don't add a dashboard mutation without an `audit.record(...)` call in the same handler.
- Don't bypass the rate limiter for "internal" callers — promote the work to a Celery task instead.
