# Plan: Ragini Payment Gateway — Frontend (Phase 1)

Build a monorepo with `frontend/` (Vite + React + TS + Tailwind + shadcn/ui, **Yarn** as package manager) and an empty `backend/` placeholder for a future Python FastAPI service. Phase 1 focuses entirely on the frontend: Supabase Google OAuth login, then an authenticated app titled **Ragini Payment Gateway** whose home screen presents **two large, beautifully-styled cards centered on the screen — API Keys and Webhooks** (NOT tabs). Clicking a card navigates to a dedicated detail page for that resource. API keys and webhooks are persisted in Supabase tables (RLS per user). Webhook delivery data is mocked.

## Visual Design (Daily Geeta–inspired)

The whole UX takes cues from https://www.dailygeeta.com/: serene, premium, spacious, with warm cream/ivory backgrounds, saffron/gold accents, deep ink text, and elegant serif headings paired with a clean sans-serif body. Generous whitespace. Soft shadows and rounded corners. No dark, fintech-y look — instead calm and editorial.

- **Palette**: ivory background `#FBF7F0`, card surface `#FFFFFF` with soft `#E9DFC9` border, primary saffron `#C8612A`, accent gold `#D4A24C`, deep ink `#2A1F14`, muted text `#6B5A47`.
- **Typography**: headings in a serif (e.g. `Fraunces` or `Cormorant Garamond` via Google Fonts), body in `Inter`. Large, generous heading sizes; tracked-out small uppercase labels for eyebrow text (like "TODAY'S VERSE" on Daily Geeta).
- **Decoration**: subtle 🪔/ॐ-style ornamental dividers and small saffron icon chips on cards; gentle gradient or radial glow behind the centered card pair.
- **Buttons**: solid saffron primary, ivory/outline secondary, all with rounded-full or rounded-2xl corners, generous padding.
- **Motion**: subtle fade/slide-in on the centered cards; soft hover lift.

## Home Screen Layout (the emphasis)

- Top bar: small Daily-Geeta-style wordmark **Ragini Payment Gateway** in serif, with the user's avatar + sign-out on the right.
- Centered hero region (vertically and horizontally centered in the viewport):
  - Eyebrow label "DEVELOPER PLATFORM" (small, tracked, saffron).
  - Serif headline "Build with confidence." (or similar warm tagline).
  - Two cards side-by-side (stacked on mobile), equal size, large (~360×280), with:
    - An icon chip at top (key icon for API Keys, lightning icon for Webhooks).
    - Card title in serif.
    - One-line description.
    - Small saffron "Open →" CTA.
  - Subtle ornamental divider beneath, with a tiny line like "Crafted for builders. Secure by default."

This centered two-card composition is the single focal point — no tabs, no sidebar, no dashboard chrome competing for attention.

## Monorepo Layout

```
ragini-payment-gateway/
├── README.md
├── .gitignore
├── plan.md                      # copy of this plan for revisit
├── frontend/                    # Vite + React + TS app
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── .env.example             # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── lib/
│       │   ├── supabase.ts      # Supabase client singleton
│       │   └── utils.ts         # cn() helper for shadcn
│       ├── auth/
│       │   ├── AuthProvider.tsx # session context + onAuthStateChange
│       │   └── ProtectedRoute.tsx
│       ├── pages/
│       │   ├── LoginPage.tsx       # serene Daily-Geeta-styled "Sign in with Google"
│       │   ├── AuthCallback.tsx    # handles /auth/callback redirect
│       │   ├── HomePage.tsx        # centered hero with two cards: API Keys & Webhooks
│       │   ├── ApiKeysPage.tsx     # dedicated route for API Keys
│       │   └── WebhooksPage.tsx    # dedicated route for Webhooks
│       ├── features/
│       │   ├── api-keys/
│       │   │   ├── ApiKeysTab.tsx
│       │   │   ├── CreateKeyDialog.tsx
│       │   │   ├── RevealKeyOnceDialog.tsx
│       │   │   ├── useApiKeys.ts          # CRUD via supabase-js
│       │   │   └── keyUtils.ts            # generate + hash (mock) + mask
│       │   └── webhooks/
│       │       ├── WebhooksTab.tsx
│       │       ├── CreateWebhookDialog.tsx
│       │       ├── WebhookDetailDrawer.tsx# delivery logs + retry status
│       │       ├── useWebhooks.ts
│       │       ├── useDeliveryLogs.ts
│       │       └── mockDeliveries.ts      # seed mocked delivery rows
│       └── components/ui/       # shadcn primitives (button, input, dialog, table, tabs, toast, badge, dropdown-menu)
├── backend/
│   └── README.md                # placeholder: "Python FastAPI service — TBD in Phase 2"
└── supabase/
    └── schema.sql               # tables + RLS policies (run in Supabase SQL editor)
```

## Phases & Steps

### Phase 1 — Repo & tooling scaffold
1. Initialize git repo, root `README.md`, `.gitignore` (node, env, dist, `.yarn/`), copy this plan to root `plan.md`.
2. Create `backend/README.md` placeholder describing the future FastAPI service (scope: api-key verification, webhook dispatcher with retries, usage metering).
3. Scaffold `frontend/` with `yarn create vite frontend --template react-ts`.
4. Install deps with **Yarn** (`yarn add` / `yarn add -D`): `@supabase/supabase-js`, **`react-router`** (v7 latest, unified package — `yarn add react-router`), `@tanstack/react-query`, `@tanstack/react-query-devtools`, `tailwindcss`, `clsx`, `tailwind-merge`, `lucide-react`, `sonner`, `@fontsource/fraunces`, `@fontsource/inter`, shadcn/ui primitives. Configure Tailwind + shadcn `components.json`. Add a `packageManager` field and commit `yarn.lock`. Wrap the app in `<QueryClientProvider>` at `main.tsx` so React Query is available everywhere (auth session check, API keys, webhooks, deliveries).
5. Extend Tailwind config with the Daily-Geeta-inspired palette (ivory, saffron, gold, ink, muted) and font families (`serif: 'Fraunces'`, `sans: 'Inter'`). Add a global stylesheet importing fonts and setting body background to ivory.
6. Add `.env.example` with `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.

### Phase 2 — Supabase project & schema (manual + SQL file)
6. Document Supabase setup in `README.md`: create project, enable Google provider, add OAuth redirect `http://localhost:5173/auth/callback`.
7. Author `supabase/schema.sql`:
   - `api_keys (id uuid pk, user_id uuid references auth.users, name text, key_prefix text, key_hash text, last_four text, status text check in ('active','revoked'), created_at timestamptz, last_used_at timestamptz)`
   - `webhooks (id uuid pk, user_id uuid, url text, description text, events text[], secret text, status text, created_at timestamptz)`
   - `webhook_deliveries (id uuid pk, webhook_id uuid references webhooks on delete cascade, user_id uuid, event_type text, status text check in ('success','failed','pending','retrying'), attempt int, response_code int, response_body text, created_at timestamptz)` — seeded with mock rows for demo.
   - RLS enabled on all three; policies: `auth.uid() = user_id` for select/insert/update/delete.

### Phase 3 — Auth flow (parallel with Phase 4 once supabase.ts exists)
8. `lib/supabase.ts`: create client from env vars.
9. `AuthProvider`: subscribe to `supabase.auth.onAuthStateChange`, expose `{ session, user, loading, signOut }` via context.
10. `LoginPage`: centered card, title "Ragini Payment Gateway", single "Continue with Google" button calling `supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin + '/auth/callback' } })`.
11. `AuthCallback`: lets supabase-js process the hash, then `navigate('/')`.
12. `ProtectedRoute`: redirects to `/login` when no session; shows spinner while loading.
13. Wire React Router routes in `App.tsx`: `/login`, `/auth/callback`, `/` (protected → DashboardPage).

### Phase 4 — Home screen & app shell (parallel with Phase 3)
14. **`AppShell`** layout component: ivory background, top bar with serif wordmark **Ragini Payment Gateway** on the left and user avatar + sign-out on the right. No sidebar.
15. **`HomePage`**: the centerpiece of the app.
    - Vertically + horizontally centered hero block.
    - Eyebrow `DEVELOPER PLATFORM` (tracked, saffron, uppercase, small).
    - Serif H1 headline (e.g. "Build with confidence.").
    - Subtle muted subheading (one line).
    - A flex row (stack on `<md`) containing exactly **two `FeatureCard` components**:
      - **API Keys card** — key icon chip, serif title "API Keys", description "Create, manage and revoke programmatic access.", "Open →" link to `/api-keys`.
      - **Webhooks card** — bolt icon chip, serif title "Webhooks", description "Subscribe to events and inspect deliveries.", "Open →" link to `/webhooks`.
    - Soft radial saffron glow behind the cards; ornamental divider beneath with the line "Crafted for builders. Secure by default."
16. **`FeatureCard`** component: white surface, soft `#E9DFC9` border, large rounded corners, generous padding, icon chip top-left, serif title, muted description, hover lift. Entire card is a `Link`.
17. Router (`App.tsx`): `/login`, `/auth/callback`, `/` (HomePage, protected), `/api-keys` (protected), `/webhooks` (protected). Detail pages reuse `AppShell` and include a small "← Back to home" link.

### Phase 5 — API Keys page (depends on Phases 2 + 3 + 4)
18. **`lib/apiClient.ts`** — thin abstraction that represents the future Python backend surface. Exposes typed methods like `createApiKey({ name })`, `revokeApiKey(id)`, `listApiKeys()`. **Key generation + hashing logic does NOT live in the frontend** — it belongs in the backend. For Phase 1, each method is a **mock implementation** clearly labeled `// TODO: replace with real fetch() call to FastAPI` that:
    - Generates a stub key string (`pk_live_<random>`) and stores rows directly in Supabase from the client (still RLS-scoped) so the UI can be exercised end-to-end.
    - Returns the same shape the real backend will: `{ id, name, key (plaintext, only on create), keyPrefix, lastFour, status, createdAt }`.
    - This keeps a clean seam: when the FastAPI service exists, only `apiClient.ts` swaps from mock to `fetch('/api/keys', …)` and the React components do not change.
19. `useApiKeys.ts` (**React Query**): `useQuery(['apiKeys'], apiClient.listApiKeys)`, `useMutation(apiClient.createApiKey)`, `useMutation(apiClient.revokeApiKey)`. Invalidate the `['apiKeys']` query on mutation success.
20. `ApiKeysPage` (inside `AppShell`): page header in serif "API Keys" + subheading + primary saffron "Create API Key" button. Below: card-surfaced table (Name, Key masked, Status badge, Created, Last used, Actions). Empty state with ornamental icon and CTA. `maskKey()` is a pure UI helper — no key generation in the frontend.
21. `CreateKeyDialog`: name input → calls `useApiKeys().create` mutation → on success opens `RevealKeyOnceDialog` showing the plaintext key returned by `apiClient.createApiKey` with copy-to-clipboard and a "I have saved this key" confirmation; key is never shown again.
22. Document in `backend/README.md` the planned `POST /api/keys`, `GET /api/keys`, `DELETE /api/keys/:id` endpoints, hashing strategy (SHA-256 of plaintext stored as `key_hash`), and that plaintext is returned **only** in the create response.

### Phase 6 — Webhooks page (parallel with Phase 5)
23. Extend `lib/apiClient.ts` with webhook methods: `listWebhooks()`, `createWebhook({ url, description, events })` (backend will also generate the `whsec_…` signing secret), `deleteWebhook(id)`, `listDeliveries(webhookId)`, `sendTestEvent(webhookId)`, `retryDelivery(deliveryId)`. All mock-implemented now, marked `// TODO: replace with FastAPI call`.
24. `useWebhooks.ts` & `useDeliveryLogs.ts` — **React Query** hooks (`useQuery` + `useMutation`) wrapping the apiClient methods, with proper query-key invalidation on mutations.
25. `WebhooksPage`: same serene page-header treatment as API Keys ("Webhooks" + subheading + "Add Webhook" button). Card-surfaced table with URL, Events (saffron badges), Status, Created, Actions (view details, delete). Empty state.
26. `CreateWebhookDialog`: URL input (validated), description, multi-select event types from a fixed list (`payment.succeeded`, `payment.failed`, `refund.created`, `payout.paid`). Submit calls `apiClient.createWebhook`.
27. `WebhookDetailDrawer`: opens from row click; shows webhook metadata, signing secret (masked with reveal), and a table of recent deliveries with status badges, attempt count, response code, expandable response body, "Send test event" and "Retry" buttons calling apiClient mocks.
28. Document planned endpoints in `backend/README.md`: `POST /api/webhooks`, `GET /api/webhooks`, `DELETE /api/webhooks/:id`, `GET /api/webhooks/:id/deliveries`, `POST /api/webhooks/:id/test`, `POST /api/deliveries/:id/retry`.

### Phase 7 — Polish & docs
28. Add `sonner` toasts (saffron-tinted) for create/revoke/copy actions; loading skeletons in tables; serene empty states with CTA.
29. Root `README.md`: prerequisites (Node + **Yarn**), Supabase setup steps, `.env` configuration, `yarn install && yarn dev` (run inside `frontend/`), screenshot placeholders, explicit "Backend is intentionally empty in Phase 1" note.
30. Add a `## What I'd improve with more time` section in README listing: real Python FastAPI backend, HMAC signing + verification on server, async webhook dispatcher with exponential backoff + DLQ (Celery/Arq + Redis), per-key rate limiting, usage charts, audit log, key scopes.

## Relevant Files (to be created)

- `frontend/src/lib/supabase.ts` — Supabase client (only place env vars are read).
- `frontend/src/auth/AuthProvider.tsx` — session context using `onAuthStateChange`.
- `frontend/src/pages/LoginPage.tsx` — Google OAuth entry point.
- `frontend/src/pages/DashboardPage.tsx` — title + `Tabs` shell.
- `frontend/src/features/api-keys/*` — keys CRUD + reveal-once dialog.
- `frontend/src/features/webhooks/*` — webhooks CRUD + delivery logs drawer.
- `supabase/schema.sql` — tables + RLS policies (single source of truth for DB).
- `backend/README.md` — placeholder.
- `plan.md` (root) — copy of this plan.

## Verification

1. `cd frontend && yarn install && yarn dev` boots without errors; `/login` renders in the Daily-Geeta-inspired serene style.
2. Clicking "Continue with Google" redirects to Google, returns to `/auth/callback`, then lands on `/` showing the **two centered cards** (API Keys, Webhooks) as the visual focal point — no tabs, no sidebar.
3. Visiting `/`, `/api-keys`, or `/webhooks` while signed out redirects to `/login`.
4. Clicking the **API Keys** card navigates to `/api-keys`; clicking **Webhooks** card navigates to `/webhooks`. Both pages have a "← Back to home" link.
5. **API Keys page**: creating "Test" key produces a `pk_live_…` value shown exactly once; copy works; after closing only masked form remains. Revoke flips badge to "Revoked".
6. **Webhooks page**: creating a webhook inserts a row; row click opens drawer with seeded deliveries; "Send test event" appends a new delivery row.
7. **RLS check**: a second Google account in incognito does not see the first account's data.
8. `supabase/schema.sql` runs cleanly in a fresh Supabase project.
9. `yarn build` in `frontend/` succeeds with no TS errors.
10. Visual check: ivory background, serif headings, saffron accents, generous whitespace — matches Daily Geeta's calm, premium feel.

## Decisions

- **Package manager**: **Yarn** (classic v1 recommended). `yarn.lock` committed.
- **Routing**: **`react-router` v7 (latest, unified package — installed via `yarn add react-router`)**. All imports come from `"react-router"` (not `"react-router-dom"`); uses `<BrowserRouter>` + `<Routes>` + `<Route>` + `<Link>` + `useNavigate`.
- **Data layer**: **TanStack React Query** for every server-state interaction (auth-aware queries, API keys, webhooks, delivery logs) — no hand-rolled loading/error state.
- **API key generation lives in the backend.** The frontend never generates or hashes keys. A `lib/apiClient.ts` module defines the future FastAPI contract; in Phase 1 it has a mock implementation (still writes to Supabase under RLS) so the UI is fully demo-able. Swapping to real `fetch()` calls in Phase 2 requires changes only inside `apiClient.ts`.
- **Stack**: Vite + React + TS + Tailwind + shadcn/ui; Fraunces + Inter fonts.
- **Visual direction**: Daily-Geeta-inspired — ivory + saffron + serif headings + generous whitespace.
- **Home screen is two centered cards, not tabs.** Each card has its own route (`/api-keys`, `/webhooks`).
- **Supabase**: Auth (Google) + data persistence with RLS.
- **Webhooks**: full UI; delivery data mocked via `apiClient` with `// TODO` markers.
- **Out of scope (Phase 1)**: real FastAPI service, server-side HMAC, async dispatcher, rate limiting, usage charts, teams/billing.

## Further Considerations

1. **Yarn version** — Classic (v1) is simplest; Berry (v4) is more modern but adds setup friction. *Recommend classic.*
2. **Backend stub now or later?** — Phase 1 keeps `backend/` as README-only; the frontend talks to a mock `apiClient` so the FastAPI boundary is already designed. *Recommend keeping backend empty for now.*
