-- Ragini Payment Gateway — Supabase schema (Phase 2 end-state)
-- Run this in the Supabase SQL Editor against a fresh project.
-- For an existing Phase-1 project, run `alembic upgrade head` from backend/ instead.
--
-- Backend uses the service-role connection (RLS bypassed); RLS policies below
-- are defense-in-depth for any direct PostgREST access. After the Phase-2
-- cutover the frontend no longer reads/writes these tables directly — it goes
-- through the FastAPI backend.

-- ---------------------------------------------------------------------------
-- api_keys
-- ---------------------------------------------------------------------------
create table if not exists public.api_keys (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  name            text not null,
  environment     text not null default 'test' check (environment in ('test','live')),
  key_id          text not null unique,
  key_prefix      text not null,
  key_hash        text not null,
  last_four       text not null,
  status          text not null default 'active' check (status in ('active','revoked','expired')),
  created_at      timestamptz not null default now(),
  last_used_at    timestamptz,
  expires_at      timestamptz,
  revoked_at      timestamptz,
  revoked_reason  text
);

create index if not exists api_keys_user_id_idx         on public.api_keys (user_id);
create index if not exists api_keys_user_env_status_idx on public.api_keys (user_id, environment, status);

alter table public.api_keys enable row level security;
drop policy if exists "api_keys are visible to owner"   on public.api_keys;
drop policy if exists "api_keys are insertable by owner" on public.api_keys;
drop policy if exists "api_keys are updatable by owner"  on public.api_keys;
drop policy if exists "api_keys are deletable by owner"  on public.api_keys;
create policy "api_keys are visible to owner"
  on public.api_keys for select using (auth.uid() = user_id);
create policy "api_keys are insertable by owner"
  on public.api_keys for insert with check (auth.uid() = user_id);
create policy "api_keys are updatable by owner"
  on public.api_keys for update using (auth.uid() = user_id);
create policy "api_keys are deletable by owner"
  on public.api_keys for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- webhooks
-- ---------------------------------------------------------------------------
create table if not exists public.webhooks (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  environment  text not null default 'test' check (environment in ('test','live')),
  url          text not null,
  description  text,
  events       text[] not null default '{}',
  secret       text not null,
  status       text not null default 'active' check (status in ('active','disabled')),
  created_at   timestamptz not null default now()
);

create index if not exists webhooks_user_id_idx         on public.webhooks (user_id);
create index if not exists webhooks_user_env_status_idx on public.webhooks (user_id, environment, status);

alter table public.webhooks enable row level security;
drop policy if exists "webhooks are visible to owner"   on public.webhooks;
drop policy if exists "webhooks are insertable by owner" on public.webhooks;
drop policy if exists "webhooks are updatable by owner"  on public.webhooks;
drop policy if exists "webhooks are deletable by owner"  on public.webhooks;
create policy "webhooks are visible to owner"
  on public.webhooks for select using (auth.uid() = user_id);
create policy "webhooks are insertable by owner"
  on public.webhooks for insert with check (auth.uid() = user_id);
create policy "webhooks are updatable by owner"
  on public.webhooks for update using (auth.uid() = user_id);
create policy "webhooks are deletable by owner"
  on public.webhooks for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- webhook_events  (canonical event source, backend-only)
-- ---------------------------------------------------------------------------
create table if not exists public.webhook_events (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  environment text not null check (environment in ('test','live')),
  event_type  text not null,
  payload     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists webhook_events_user_env_idx on public.webhook_events (user_id, environment, created_at);

alter table public.webhook_events enable row level security;
-- Default deny: only the backend service role reads/writes this table.

-- ---------------------------------------------------------------------------
-- webhook_deliveries
-- ---------------------------------------------------------------------------
create table if not exists public.webhook_deliveries (
  id              uuid primary key default gen_random_uuid(),
  webhook_id      uuid not null references public.webhooks(id) on delete cascade,
  user_id         uuid not null references auth.users(id) on delete cascade,
  environment     text not null default 'test' check (environment in ('test','live')),
  event_id        uuid references public.webhook_events(id) on delete set null,
  event_type      text not null,
  status          text not null check (status in ('success','failed','pending','retrying','dead_lettered')),
  attempt         int  not null default 1,
  response_code   int,
  response_body   text,
  next_attempt_at timestamptz,
  created_at      timestamptz not null default now()
);

create index if not exists webhook_deliveries_webhook_id_idx      on public.webhook_deliveries (webhook_id);
create index if not exists webhook_deliveries_user_id_idx         on public.webhook_deliveries (user_id);
create index if not exists webhook_deliveries_webhook_created_idx on public.webhook_deliveries (webhook_id, created_at desc);

alter table public.webhook_deliveries enable row level security;
drop policy if exists "deliveries are visible to owner"   on public.webhook_deliveries;
drop policy if exists "deliveries are insertable by owner" on public.webhook_deliveries;
drop policy if exists "deliveries are updatable by owner"  on public.webhook_deliveries;
drop policy if exists "deliveries are deletable by owner"  on public.webhook_deliveries;
create policy "deliveries are visible to owner"
  on public.webhook_deliveries for select using (auth.uid() = user_id);
create policy "deliveries are insertable by owner"
  on public.webhook_deliveries for insert with check (auth.uid() = user_id);
create policy "deliveries are updatable by owner"
  on public.webhook_deliveries for update using (auth.uid() = user_id);
create policy "deliveries are deletable by owner"
  on public.webhook_deliveries for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- api_key_usage_events  (backend-only, append-only metrics)
-- ---------------------------------------------------------------------------
create table if not exists public.api_key_usage_events (
  id          uuid primary key default gen_random_uuid(),
  api_key_id  uuid,
  user_id     uuid,
  environment text,
  route       text not null,
  status_code int  not null,
  latency_ms  int,
  ip          text,
  user_agent  text,
  created_at  timestamptz not null default now()
);
create index if not exists api_key_usage_key_created_idx on public.api_key_usage_events (api_key_id, created_at);

alter table public.api_key_usage_events enable row level security;
-- Default deny: backend service role only.

-- ---------------------------------------------------------------------------
-- security_alerts  (backend writes; owner reads via dashboard)
-- ---------------------------------------------------------------------------
create table if not exists public.security_alerts (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  environment text not null,
  api_key_id  uuid,
  alert_type  text not null,
  severity    text not null default 'low',
  details     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists security_alerts_user_created_idx on public.security_alerts (user_id, created_at desc);

alter table public.security_alerts enable row level security;
drop policy if exists "security alerts visible to owner" on public.security_alerts;
create policy "security alerts visible to owner"
  on public.security_alerts for select using (auth.uid() = user_id);
-- No insert/update/delete policy → only the backend service role can write.
