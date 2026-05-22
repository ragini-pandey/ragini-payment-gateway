/**
 * apiClient — talks to the Ragini FastAPI backend over HTTP.
 *
 * Auth: every request carries the Supabase access token as a Bearer JWT.
 * The backend verifies it against the Supabase project (HS256 or RS256/JWKS).
 *
 * Environment: requests that are environment-scoped accept an
 * `environment: "test" | "live"` argument; this is sent as `?environment=...`
 * (and `X-Environment` for safety).
 *
 * Note: the Supabase client is now used ONLY for authentication
 * (`supabase.auth.*`). All data reads/writes go through FastAPI.
 */

import { supabase } from "./supabase";

// ---------------------------------------------------------------------------
// Types — must match backend pydantic schemas (camelCase).
// ---------------------------------------------------------------------------

export type Environment = "test" | "live";
export type ApiKeyStatus = "active" | "revoked" | "expired";

export interface ApiKey {
  id: string;
  name: string;
  environment: Environment;
  keyPrefix: string;
  lastFour: string;
  status: ApiKeyStatus;
  createdAt: string;
  expiresAt: string | null;
  revokedAt: string | null;
  revokedReason: string | null;
  lastUsedAt: string | null;
}

export interface ApiKeyWithSecret extends ApiKey {
  /** Plaintext key — present ONLY in the create response. Never stored. */
  key: string;
}

export type WebhookStatus = "active" | "disabled";

export interface Webhook {
  id: string;
  url: string;
  description: string | null;
  events: string[];
  environment: Environment;
  /** Masked at rest; full secret only returned at create time. */
  secret: string;
  status: WebhookStatus;
  createdAt: string;
}

export type DeliveryStatus =
  | "pending"
  | "success"
  | "failed"
  | "retrying"
  | "dead_lettered";

export interface WebhookDelivery {
  id: string;
  webhookId: string;
  eventType: string;
  status: DeliveryStatus;
  attempt: number;
  responseCode: number | null;
  responseBody: string | null;
  createdAt: string;
}

export interface DeliveryListResponse {
  items: WebhookDelivery[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditEvent {
  id: string;
  action: string;
  targetType: string;
  targetId: string;
  environment: string | null;
  metadata: Record<string, unknown>;
  ip: string | null;
  userAgent: string | null;
  createdAt: string;
}

export interface AuditListResponse {
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export type SecurityAlertSeverity = "low" | "medium" | "high" | "critical";

export interface SecurityAlert {
  id: string;
  environment: Environment;
  alertType: string;
  severity: SecurityAlertSeverity;
  apiKeyId: string | null;
  details: Record<string, unknown>;
  createdAt: string;
}

export interface UsagePoint {
  timestamp: string;
  total: number;
  errors: number;
}

export interface UsageResponse {
  range: "24h" | "7d" | "30d";
  points: UsagePoint[];
}

/** Canonical event-type list (must mirror backend `app.events.EventType`). */
export const EVENT_TYPES = [
  "payment.success",
  "payment.error",
  "api_key.revoked",
  "api_key.expired",
  "security.alert",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

// ---------------------------------------------------------------------------
// HTTP client
// ---------------------------------------------------------------------------

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new ApiError(401, "Not authenticated", null);
  return { Authorization: `Bearer ${token}` };
}

/**
 * Handle a 401 by attempting one Supabase session refresh. If refresh
 * fails (no refresh token, or refresh token expired), sign the user out
 * and redirect to /login so we never leave them on a broken page.
 *
 * Returns `true` if the caller should retry the original request.
 */
async function handleUnauthorized(): Promise<boolean> {
  try {
    const { data, error } = await supabase.auth.refreshSession();
    if (error || !data.session) {
      await supabase.auth.signOut();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
      return false;
    }
    return true;
  } catch {
    await supabase.auth.signOut();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    return false;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  environment?: Environment;
  query?: Record<string, string | number | undefined>;
  headers?: Record<string, string>;
}

async function apiFetch<T>(
  path: string,
  opts: RequestOptions = {},
  _retried = false,
): Promise<T> {
  const auth = await authHeader();
  const params = new URLSearchParams();
  if (opts.environment) params.set("environment", opts.environment);
  if (opts.query) {
    for (const [k, v] of Object.entries(opts.query)) {
      if (v !== undefined) params.set(k, String(v));
    }
  }
  const qs = params.toString();
  const url = `${BASE_URL}${path}${qs ? `?${qs}` : ""}`;

  const headers: Record<string, string> = { ...auth, ...(opts.headers ?? {}) };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.environment) headers["X-Environment"] = opts.environment;

  const res = await fetch(url, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  // 401 → try once to refresh the Supabase session, then retry. If refresh
  // fails, handleUnauthorized() will sign out + redirect to /login.
  if (res.status === 401 && !_retried) {
    const refreshed = await handleUnauthorized();
    if (refreshed) {
      return apiFetch<T>(path, opts, true);
    }
  }

  const text = await res.text();
  const parsed = text ? safeJson(text) : null;
  if (!res.ok) {
    const message =
      (parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as { detail: unknown }).detail)
        : null) ?? `${res.status} ${res.statusText}`;
    throw new ApiError(res.status, message, parsed);
  }
  return parsed as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const apiClient = {
  // -------------------- API Keys --------------------

  listApiKeys(environment: Environment): Promise<ApiKey[]> {
    return apiFetch<ApiKey[]>("/v1/keys", { environment });
  },

  createApiKey(input: {
    name: string;
    environment: Environment;
    expiresAt?: string | null;
  }): Promise<ApiKeyWithSecret> {
    return apiFetch<ApiKeyWithSecret>("/v1/keys", {
      method: "POST",
      body: {
        name: input.name,
        environment: input.environment,
        expiresAt: input.expiresAt ?? null,
      },
    });
  },

  revokeApiKey(id: string, reason?: string): Promise<ApiKey> {
    return apiFetch<ApiKey>(`/v1/keys/${id}/revoke`, {
      method: "POST",
      body: { reason: reason ?? null },
    });
  },

  getApiKeyUsage(
    id: string,
    range: "24h" | "7d" | "30d" = "24h"
  ): Promise<UsageResponse> {
    return apiFetch<UsageResponse>(`/v1/keys/${id}/usage`, { query: { range } });
  },

  // -------------------- Webhooks --------------------

  listWebhooks(environment: Environment): Promise<Webhook[]> {
    return apiFetch<Webhook[]>("/v1/webhooks", { environment });
  },

  createWebhook(input: {
    url: string;
    description?: string;
    events: string[];
    environment: Environment;
  }): Promise<Webhook> {
    return apiFetch<Webhook>("/v1/webhooks", {
      method: "POST",
      body: {
        url: input.url,
        description: input.description ?? null,
        events: input.events,
        environment: input.environment,
      },
    });
  },

  updateWebhook(
    id: string,
    patch: Partial<{
      url: string;
      description: string | null;
      events: string[];
      status: WebhookStatus;
    }>
  ): Promise<Webhook> {
    return apiFetch<Webhook>(`/v1/webhooks/${id}`, { method: "PATCH", body: patch });
  },

  deleteWebhook(id: string): Promise<void> {
    return apiFetch<void>(`/v1/webhooks/${id}`, { method: "DELETE" });
  },

  rotateWebhookSecret(id: string): Promise<Webhook> {
    return apiFetch<Webhook>(`/v1/webhooks/${id}/rotate-secret`, {
      method: "POST",
    });
  },

  // -------------------- Deliveries --------------------

  listDeliveries(
    webhookId: string,
    opts?: { limit?: number; offset?: number; status?: DeliveryStatus }
  ): Promise<DeliveryListResponse> {
    return apiFetch<DeliveryListResponse>(
      `/v1/webhooks/${webhookId}/deliveries`,
      {
        query: {
          limit: opts?.limit,
          offset: opts?.offset,
          status: opts?.status,
        },
      }
    );
  },

  sendTestEvent(
    webhookId: string,
    opts?: { eventType?: EventType; data?: Record<string, unknown> }
  ): Promise<{ eventId: string; queued: boolean }> {
    return apiFetch(`/v1/webhooks/${webhookId}/test`, {
      method: "POST",
      body: {
        event_type: opts?.eventType ?? "payment.success",
        data: opts?.data ?? null,
      },
    });
  },

  // -------------------- Audit --------------------

  listAuditEvents(opts?: {
    limit?: number;
    offset?: number;
    action?: string;
    targetType?: string;
  }): Promise<AuditListResponse> {
    return apiFetch<AuditListResponse>("/v1/audit", {
      query: {
        limit: opts?.limit,
        offset: opts?.offset,
        action: opts?.action,
        target_type: opts?.targetType,
      },
    });
  },

  // -------------------- Generic event ingestion --------------------

  ingestEvent(input: {
    eventType: EventType | string;
    data?: Record<string, unknown>;
    idempotencyKey?: string;
  }): Promise<{ eventId: string; queued?: boolean; status?: string }> {
    return apiFetch("/v1/events", {
      method: "POST",
      body: { eventType: input.eventType, data: input.data ?? {} },
      headers: input.idempotencyKey
        ? { "Idempotency-Key": input.idempotencyKey }
        : undefined,
    });
  },

  retryDelivery(
    deliveryId: string
  ): Promise<{ deliveryId: string; queued: boolean }> {
    return apiFetch(`/v1/deliveries/${deliveryId}/retry`, { method: "POST" });
  },

  // -------------------- Security --------------------

  listSecurityAlerts(
    environment: Environment,
    limit = 100
  ): Promise<SecurityAlert[]> {
    return apiFetch<SecurityAlert[]>("/v1/security/alerts", {
      environment,
      query: { limit },
    });
  },
};
