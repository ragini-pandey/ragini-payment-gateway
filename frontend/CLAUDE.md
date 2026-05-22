# Frontend

Vite + React 18 + TypeScript + Tailwind + shadcn/ui. **Yarn classic** — commit `yarn.lock`, never use npm/pnpm here.

## Layout

- `src/pages/` — route-level components (`LoginPage`, `AuthCallback`, `HomePage`, `ApiKeysPage`, `WebhooksPage`, `SecurityAlertsPage`).
- `src/features/<feature>/` — feature-scoped hooks, dialogs, drawers. API keys: `useApiKeys`, `CreateKeyDialog`, `RevealKeyOnceDialog`, `UsageChart`, `ApiKeyUsageDrawer`. Webhooks: `useWebhooks`, `useDeliveryLogs`, `CreateWebhookDialog`, `RevealWebhookSecretDialog`, `SendTestEventDialog`, `WebhookDetailDrawer`.
- `src/components/` — shared layout/UI primitives (`AppShell`, `EnvSwitcher`, `Overlay`, `ErrorBoundary`, shadcn/ui under `components/ui/`).
- `src/auth/` — `AuthProvider` (Supabase session context via `onAuthStateChange`) + `ProtectedRoute`.
- `src/lib/` — `supabase.ts` (client singleton, auth-only), `apiClient.ts` (typed fetch wrapper for the FastAPI backend), `env.tsx` (test/live switching), `utils.ts` (`cn()`, formatters).

## Conventions

- Routes: `/login`, `/auth/callback` are public. Everything else wraps in `ProtectedRoute` + `ErrorBoundary` (see `App.tsx`).
- Data access: components call hooks (`useApiKeys`, `useWebhooks`, `useDeliveryLogs`), hooks call `apiClient`, `apiClient` calls the FastAPI backend over HTTP with the Supabase JWT as bearer. Don't reach into `supabase` from components for resource data — only for auth.
- React Query: define query keys as tuples (e.g. `['apiKeys']`, `['deliveries', webhookId, limit, offset, status]`). Invalidate broadly on mutation success.
- Auth: read session via `useAuth()` from `AuthProvider`. Don't subscribe to `onAuthStateChange` outside the provider.
- Env vars: must be `VITE_`-prefixed and read only inside `src/lib/supabase.ts` / `src/lib/env.tsx`. Mirror new vars into `.env.example`. `VITE_API_BASE_URL` controls the backend origin.
- Charts use `recharts` with the saffron/rose palette (see `UsageChart.tsx`).
- Paginated lists (`listDeliveries`, `listAuditEvents`) return `{items, total, limit, offset}` — NOT a bare array.

## UI rules

- Use Tailwind tokens defined in `tailwind.config.js` (ivory, saffron, gold, ink, muted). Do not hardcode hex.
- Headings: `font-serif` (Fraunces). Body: default (Inter). Eyebrows: small, uppercase, tracked, saffron.
- Buttons: saffron primary, ivory/outline secondary, `rounded-2xl` or `rounded-full`, generous padding.
- Toasts via `sonner`.
- Reveal-once flow: plaintext API keys and webhook secrets are shown exactly once, inside the dedicated reveal dialog returned from a create mutation. Never persist them in state, localStorage, or logs.

## Don't

- Don't import from `react-router-dom` — use `"react-router"`.
- Don't add a sidebar or tabs to `HomePage`; it is two centered `FeatureCard`s by design.
- Don't generate, hash, or mask-then-store API keys client-side. `maskKey()` is a pure display helper.
- Don't introduce a second data-fetching pattern (no SWR, no raw `useEffect` + `fetch` for server state).
