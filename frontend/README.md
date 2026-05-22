# Ragini Payment Gateway — Frontend

Vite + React 18 + TypeScript + Tailwind + shadcn/ui dashboard for the Ragini Payment Gateway. Authenticates via Supabase Google OAuth and talks to the FastAPI backend in [`../backend`](../backend) over HTTP with the Supabase JWT as bearer.

## Stack

| Concern          | Choice                                                    |
| ---------------- | --------------------------------------------------------- |
| Build / dev      | Vite 5                                                    |
| Language         | TypeScript 5                                              |
| UI               | React 18, Tailwind 3, shadcn/ui primitives, lucide-react  |
| Routing          | `react-router` v7 (unified package — never `react-router-dom`) |
| Data             | TanStack React Query 5 (all server state)                 |
| Auth             | `@supabase/supabase-js` (Google OAuth)                    |
| Charts           | recharts                                                  |
| Toasts           | sonner                                                    |
| Package manager  | **Yarn classic v1** (committed `yarn.lock`)               |

## Setup

```bash
cd frontend
cp .env.example .env
# fill in the three VITE_ vars (see below)
yarn install
yarn dev          # http://localhost:5173
```

Open http://localhost:5173 and click **Continue with Google**. The Supabase project must allow the redirect URL `http://localhost:5173/auth/callback`.

## Environment variables

| Variable                  | Purpose                                                         |
| ------------------------- | --------------------------------------------------------------- |
| `VITE_SUPABASE_URL`       | Supabase project URL.                                           |
| `VITE_SUPABASE_ANON_KEY`  | Supabase anon/public key (safe to ship to the client).          |
| `VITE_API_BASE_URL`       | Base URL of the FastAPI backend (e.g. `http://localhost:8000`). |

Env vars are read only inside [`src/lib/supabase.ts`](src/lib/supabase.ts) and [`src/lib/env.tsx`](src/lib/env.tsx).

## Scripts

| Script           | What it does                                                    |
| ---------------- | --------------------------------------------------------------- |
| `yarn dev`       | Vite dev server with HMR on port 5173.                          |
| `yarn build`     | Type-check (`tsc -b`) then `vite build`. Must pass before PR.   |
| `yarn typecheck` | `tsc -b --noEmit`.                                              |
| `yarn preview`   | Serve the production build locally.                             |

## Routes

Wired in [`src/App.tsx`](src/App.tsx):

| Path              | Protected | Page                                                      |
| ----------------- | --------- | --------------------------------------------------------- |
| `/login`          | no        | [`LoginPage`](src/pages/LoginPage.tsx) — Google OAuth CTA. |
| `/auth/callback`  | no        | [`AuthCallback`](src/pages/AuthCallback.tsx).             |
| `/`               | yes       | [`HomePage`](src/pages/HomePage.tsx) — two centered cards. |
| `/api-keys`       | yes       | [`ApiKeysPage`](src/pages/ApiKeysPage.tsx).               |
| `/webhooks`       | yes       | [`WebhooksPage`](src/pages/WebhooksPage.tsx).             |
| `/security`       | yes       | [`SecurityAlertsPage`](src/pages/SecurityAlertsPage.tsx). |

Every protected route is wrapped in [`ProtectedRoute`](src/auth/ProtectedRoute.tsx) and [`ErrorBoundary`](src/components/ErrorBoundary.tsx).

## Data flow

`Page → feature hook → apiClient → FastAPI`. All server state goes through [`src/lib/apiClient.ts`](src/lib/apiClient.ts) and TanStack React Query — no `useEffect + fetch`, no SWR. Feature hooks live in `src/features/<feature>/` (e.g. `useApiKeys`, `useWebhooks`, `useDeliveryLogs`). Paginated endpoints return `{ items, total, limit, offset }`, not bare arrays.

The dashboard never generates, hashes, or masks-then-stores API keys or webhook secrets. The backend returns the plaintext exactly once at create time, displayed inside a reveal-once dialog ([`RevealKeyOnceDialog`](src/features/api-keys/), [`RevealWebhookSecretDialog`](src/features/webhooks/)) and never persisted to state, localStorage, or logs.

## Environment switcher

The dashboard runs in a global `test` / `live` context via [`EnvironmentProvider`](src/lib/env.tsx). Hooks forward the active env to backend list endpoints as `?environment=test|live`. The CORS layer also allows the `X-Environment` header for callers that prefer it.

## Visual direction

Daily-Geeta-inspired: ivory backgrounds, saffron + gold accents, deep ink text, serif headings (`Fraunces`), body in `Inter`. Tokens are defined in [`tailwind.config.js`](tailwind.config.js) (`ivory`, `saffron`, `gold`, `ink`, `muted`, `parchment`). Never hardcode hex.

`HomePage` is two centered `FeatureCard`s by design — no sidebar, no tabs.

## See also

- [`../README.md`](../README.md) — repo overview, quickstart, known limitations.
- [`../backend/README.md`](../backend/README.md) — full backend API reference and curl walkthrough.
- [`CLAUDE.md`](CLAUDE.md) — frontend-specific conventions for contributors.
