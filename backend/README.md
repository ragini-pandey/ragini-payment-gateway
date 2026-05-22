# Ragini Payment Gateway — Backend

FastAPI + Celery + Redis service that powers the dashboard and exposes a public
HTTP API authenticated with `rpg_*` API keys. All payment events are fanned out
to user-configured webhook endpoints with HMAC-signed payloads and exponential
retries.

## Stack

| Concern              | Choice                                              |
| -------------------- | --------------------------------------------------- |
| HTTP                 | FastAPI 0.115+, Pydantic v2                         |
| ORM / DB             | SQLAlchemy 2 (async) + asyncpg, Alembic migrations  |
| Async jobs           | Celery 5 + Redis (broker, result backend, beat)     |
| Outbound HTTP        | httpx                                               |
| Auth (dashboard)     | Supabase JWT (HS256 or RS256/JWKS)                  |
| Auth (public API)    | Bearer `rpg_<env>_<key_id>_<secret>`                |
| Logging              | structlog (JSON)                                    |

## API key format

```
rpg_<env>_<key_id>_<secret>
        │       │       └─ 32 chars base62 (random; verified server-side)
        │       └───────── 16 chars base62 (UNIQUE INDEXED — used for lookup)
        └───────────────── "test" or "live"
```

The plaintext key is **shown exactly once at creation**. The server stores
`HMAC-SHA256(API_KEY_PEPPER, secret)` (constant-time compared on each request).
The pepper is held only in `API_KEY_PEPPER` — never in the database — so a
read-only DB compromise is insufficient to forge keys.

## Webhook signing

```
X-Ragini-Signature: t=<unix_seconds>,v1=<hex_hmac_sha256(secret, "<t>.<body>")>
```

Receivers should: (1) reject if `|now - t| > 300s`; (2) recompute v1 and compare
with `hmac.compare_digest`. See `scripts/verify_signature.py`.

## Events

Canonical strings live in [`app/events.py`](app/events.py). The full catalog is:

| Event             | Emitted when                                                                                  |
| ----------------- | --------------------------------------------------------------------------------------------- |
| `api_key.expired` | A key past `expires_at` is auto-revoked by the `sweep_expired_keys` beat task.                 |
| `api_key.revoked` | A dashboard caller revokes a key (`POST /v1/keys/{id}/revoke`).                                |
| `security.alert`  | Rate-limit trip, request spike, or use of a revoked/expired key.                              |
| `payment.success` | Caller posts to `POST /v1/payments`, or explicitly emits via `POST /v1/events`.                |
| `payment.error`   | `POST /v1/payments` records a failure, or explicit emit via `POST /v1/events`.                 |

Webhooks subscribe to a subset of these strings at create time; events outside the catalog are rejected at ingest.

## Local setup

```bash
# 1. Install (editable, with dev tools)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# 2. Configure
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # → API_KEY_PEPPER
# Fill DATABASE_URL / DATABASE_URL_SYNC / SUPABASE_* in .env

# 3. Migrate the database
alembic upgrade head

# 4. Run the stack
docker compose up redis -d                     # broker
uvicorn app.main:app --reload                  # API
celery -A app.workers.celery_app worker -l INFO   # dispatcher
celery -A app.workers.celery_app beat   -l INFO   # scheduler (anomaly + sweep)
```

Or in one shot:

```bash
docker compose up --build
```

## Endpoints

Dashboard routes require a Supabase JWT (`Authorization: Bearer <jwt>`). Public routes require a `rpg_*` API key. Health is unauthenticated.

| Method | Path                                              | Auth      |
| ------ | ------------------------------------------------- | --------- |
| GET    | `/health`, `/healthz`                             | —         |
| GET    | `/readyz`                                         | —         |
| POST   | `/v1/keys`                                        | dashboard |
| GET    | `/v1/keys?environment=test\|live`                 | dashboard |
| POST   | `/v1/keys/{id}/revoke`                            | dashboard |
| GET    | `/v1/keys/{id}/usage?range=24h\|7d\|30d`          | dashboard |
| POST   | `/v1/webhooks`                                    | dashboard |
| GET    | `/v1/webhooks?environment=test\|live`             | dashboard |
| PATCH  | `/v1/webhooks/{id}`                               | dashboard |
| DELETE | `/v1/webhooks/{id}`                               | dashboard |
| GET    | `/v1/webhooks/{id}/deliveries`                    | dashboard |
| POST   | `/v1/webhooks/{id}/test`                          | dashboard |
| POST   | `/v1/webhooks/{id}/rotate-secret`                 | dashboard |
| POST   | `/v1/deliveries/{id}/retry`                       | dashboard |
| GET    | `/v1/security/alerts`                             | dashboard |
| GET    | `/v1/audit`                                       | dashboard |
| POST   | `/v1/payments`                                    | API key   |
| POST   | `/v1/events`                                      | API key   |

`POST /v1/payments` and `POST /v1/events` accept an optional `Idempotency-Key` header; the same `(key_id, Idempotency-Key)` pair returns the original response for 24 h. CORS also allows an `X-Environment` header for callers that want to forward the active env from the dashboard.

## Background tasks

All task modules live in [`app/workers/tasks/`](app/workers/tasks/). Beat schedule is wired in [`app/workers/celery_app.py`](app/workers/celery_app.py).

| Task                  | Trigger              | Purpose                                    |
| --------------------- | -------------------- | ------------------------------------------ |
| `fanout_event`        | event emission       | Insert pending deliveries for matchers     |
| `dispatch_delivery`   | per-delivery (+ETA)  | POST signed payload, retry with backoff    |
| `scan_anomalies`      | every 60 s (beat)    | Detect per-key request spikes              |
| `sweep_expired_keys`  | every 5 min (beat)   | Auto-expire keys past `expires_at` (lives inside `scan_anomalies.py`) |

Backoff: 60 s → 5 m → 30 m → 2 h → 12 h → 24 h, ±15 % jitter, 6 attempts max,
then `dead_lettered` and a `security.alert` is emitted.

## Anomaly detection

Each verified API request increments
`usage:<key_id>:<unix_minute>` in Redis. A beat task samples the previous
minute against a 60-minute baseline; if a key exceeds
`max(20, 5 × baseline)` requests in a minute, a `security.alert` of type
`request_spike` is emitted (deduped 10 minutes via `SETNX`). Use of an already
revoked or expired key also generates `security.alert` events synchronously
inside the auth dependency.

## Environment variables

All defaults live in [`app/config.py`](app/config.py). Mirror new vars into
[`.env.example`](.env.example).

| Variable                       | Required | Default                  | Purpose                                          |
| ------------------------------ | -------- | ------------------------ | ------------------------------------------------ |
| `DATABASE_URL`                 | yes      | —                        | Async SQLAlchemy URL (`postgresql+asyncpg://…`). |
| `DATABASE_URL_SYNC`            | yes      | —                        | Sync URL used by Alembic (`postgresql+psycopg2://…`). |
| `REDIS_URL`                    | no       | `redis://localhost:6379/0` | Broker, result backend, rate counters, idempotency cache. |
| `SUPABASE_PROJECT_REF`         | no¹      | `""`                     | Supabase project subdomain.                       |
| `SUPABASE_JWKS_URL`            | no¹      | `""`                     | JWKS endpoint for RS256 JWT verification.         |
| `SUPABASE_JWT_SECRET`          | no¹      | `""`                     | Shared secret for HS256 JWT verification.         |
| `API_KEY_PEPPER`               | yes      | —                        | Hex-encoded, decodes to ≥ 16 bytes. HMAC pepper.   |
| `FRONTEND_ORIGIN`              | no       | `http://localhost:5173`  | Fallback when `CORS_ALLOWED_ORIGINS` is empty.    |
| `CORS_ALLOWED_ORIGINS`         | no       | `""`                     | Comma-separated allow-list. `*` disables credentials. |
| `WEBHOOK_HTTP_TIMEOUT_SECONDS` | no       | `10`                     | Per-attempt outbound HTTP timeout.                |
| `WEBHOOK_MAX_ATTEMPTS`         | no       | `6`                      | Total dispatch attempts before dead-lettering.    |
| `RATE_LIMIT_PER_MINUTE`        | no       | `120`                    | Fixed-window cap per API key.                     |
| `RATE_LIMIT_BURST`             | no       | `60`                     | Reserved for a future token-bucket upgrade.       |
| `LOG_LEVEL`                    | no       | `INFO`                   | structlog level.                                  |

¹ At least one of `SUPABASE_JWKS_URL` / `SUPABASE_JWT_SECRET` must be set in environments that require dashboard auth.

## Testing

```bash
pytest -q
ruff check .
```

Unit tests cover key generation/parse/verify round-trips, tamper rejection,
pepper isolation, signature roundtrip & replay window, and the retry backoff
schedule. Integration tests around dispatch use `respx`.

## Pepper rotation (Phase 3)

Phase 2 ships a single pepper. To rotate without invalidating existing keys
you would: (1) add `API_KEY_PEPPER_NEXT`, (2) verify against both, (3)
re-hash secrets on next successful auth using the new pepper, (4) drop the
old pepper once a re-hash sweep completes. Not implemented yet.

## Walkthrough

End-to-end demo using only `curl` + [webhook.site](https://webhook.site) +
[httpstat.us](https://httpstat.us). Assumes the stack is running locally and
you already have a Supabase JWT in `$JWT` (grab one from the dashboard's
network tab or any Supabase client login).

```bash
API=http://localhost:8000

# 1. Create a webhook pointing at a temporary inbox.
INBOX=https://webhook.site/your-uuid
curl -s -X POST $API/v1/webhooks \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d "{\"url\":\"$INBOX\",\"events\":[\"payment.success\",\"payment.error\"],\"environment\":\"test\"}" \
  | tee /tmp/hook.json
WHID=$(jq -r .id /tmp/hook.json)
SECRET=$(jq -r .secret /tmp/hook.json)   # plaintext shown ONCE

# 2. Create an API key, capture the plaintext.
curl -s -X POST $API/v1/keys \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"name":"demo","environment":"test"}' | tee /tmp/key.json
RPG=$(jq -r .key /tmp/key.json)

# 3. Hit the public API with the bearer key, emit a payment.success event.
curl -s -X POST $API/v1/events \
  -H "Authorization: Bearer $RPG" -H "Content-Type: application/json" \
  -d '{"eventType":"payment.success","data":{"amount":1999,"currency":"USD"}}'
# → 202 { "eventId": "...", "queued": true }

# 4. Watch the delivery succeed in your webhook.site inbox. Verify the
#    signature header locally:
python scripts/verify_signature.py "$SECRET" \
  --header "$X_RAGINI_SIGNATURE" \
  --body '{"id":"...","type":"payment.success",...}'

# 5. Simulate a flaky receiver — point a fresh webhook at httpstat.us/500 and
#    re-emit. The dispatcher persists each attempt with status retrying,
#    then dead_lettered after 6 tries (or use POST /v1/deliveries/{id}/retry
#    from the dashboard to force an extra attempt).

# 6. Trip the rate limiter (default 120/min). The 121st call returns 429 with
#    Retry-After, and a security alert appears under GET /v1/security/alerts.
for i in $(seq 1 130); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer $RPG" $API/v1/payments
done | tail -15

# 7. Rotate the webhook secret. Old signatures stop verifying immediately.
curl -s -X POST $API/v1/webhooks/$WHID/rotate-secret \
  -H "Authorization: Bearer $JWT" | jq .secret

# 8. Inspect the audit trail — every mutation above is captured.
curl -s "$API/v1/audit?limit=20" -H "Authorization: Bearer $JWT" | jq .items
```
