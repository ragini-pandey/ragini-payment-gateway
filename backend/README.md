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

`api_key.expired`, `api_key.revoked`, `security.alert`, `payment.success`,
`payment.error`. Webhooks subscribe to a subset of events at create time.

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

## Endpoints (selected)

| Method | Path                                  | Auth         |
| ------ | ------------------------------------- | ------------ |
| GET    | `/healthz`                            | —            |
| POST   | `/v1/keys`                            | dashboard    |
| GET    | `/v1/keys?environment=test\|live`     | dashboard    |
| POST   | `/v1/keys/{id}/revoke`                | dashboard    |
| GET    | `/v1/keys/{id}/usage?range=24h\|7d\|30d` | dashboard |
| POST   | `/v1/webhooks`                        | dashboard    |
| GET    | `/v1/webhooks?environment=…`          | dashboard    |
| PATCH  | `/v1/webhooks/{id}`                   | dashboard    |
| DELETE | `/v1/webhooks/{id}`                   | dashboard    |
| GET    | `/v1/webhooks/{id}/deliveries`        | dashboard    |
| POST   | `/v1/webhooks/{id}/test`              | dashboard    |
| POST   | `/v1/deliveries/{id}/retry`           | dashboard    |
| GET    | `/v1/security/alerts`                 | dashboard    |
| GET    | `/v1/audit`                           | dashboard    |
| POST   | `/v1/webhooks/{id}/rotate-secret`     | dashboard    |
| POST   | `/v1/payments`                        | API key      |
| POST   | `/v1/events`                          | API key      |

## Background tasks

| Task                  | Trigger              | Purpose                                    |
| --------------------- | -------------------- | ------------------------------------------ |
| `fanout_event`        | event emission       | Insert pending deliveries for matchers     |
| `dispatch_delivery`   | per-delivery (+ETA)  | POST signed payload, retry with backoff    |
| `scan_anomalies`      | every 60 s (beat)    | Detect per-key request spikes              |
| `sweep_expired_keys`  | every 5 min (beat)   | Auto-expire keys past `expires_at`         |

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
