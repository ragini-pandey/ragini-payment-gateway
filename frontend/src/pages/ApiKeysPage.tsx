import { memo, useCallback, useState } from "react";
import { Link } from "react-router";
import { Activity, ArrowLeft, KeyRound, Plus, Trash2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { useApiKeys } from "@/features/api-keys/useApiKeys";
import { CreateKeyDialog } from "@/features/api-keys/CreateKeyDialog";
import { RevealKeyOnceDialog } from "@/features/api-keys/RevealKeyOnceDialog";
import { ApiKeyUsageDrawer } from "@/features/api-keys/ApiKeyUsageDrawer";
import type { ApiKey, ApiKeyWithSecret } from "@/lib/apiClient";
import { useEnvironment } from "@/lib/env";
import { cn, formatDate, maskKey } from "@/lib/utils";
import { toast } from "sonner";

export function ApiKeysPage() {
  const { environment } = useEnvironment();
  const { list, revoke } = useApiKeys();
  const [createOpen, setCreateOpen] = useState(false);
  const [revealKey, setRevealKey] = useState<ApiKeyWithSecret | null>(null);
  const [usageKey, setUsageKey] = useState<ApiKey | null>(null);

  const handleRevoke = useCallback(async (k: ApiKey) => {
    if (
      !window.confirm(
        `Revoke "${k.name}"? Applications using this key will lose access immediately.`
      )
    ) return;
    try {
      await revoke.mutateAsync({ id: k.id, reason: "manual_dashboard_revoke" });
      toast.success("API key revoked");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to revoke");
    }
  }, [revoke]);

  const openCreate = useCallback(() => setCreateOpen(true), []);
  const closeCreate = useCallback(() => setCreateOpen(false), []);
  const handleCreated = useCallback((k: ApiKeyWithSecret) => {
    setCreateOpen(false);
    setRevealKey(k);
  }, []);
  const closeReveal = useCallback(() => setRevealKey(null), []);
  const closeUsage = useCallback(() => setUsageKey(null), []);

  return (
    <AppShell>
      <section className="mx-auto w-full max-w-5xl px-6 py-12">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to home
        </Link>

        <header className="mt-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="mt-2 font-serif text-4xl text-ink">API Keys</h1>
            <p className="mt-2 text-sm text-muted max-w-xl">
              Programmatic access for your integrations. You are viewing{" "}
              <span
                className={cn(
                  "font-medium",
                  environment === "live" ? "text-rose-700" : "text-ink"
                )}
              >
                {environment.toUpperCase()}
              </span>{" "}
              keys. Each key is shown once at creation — store it safely.
            </p>
          </div>
          <button type="button" className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" /> Create API Key
          </button>
        </header>

        <div className="mt-8 card-surface overflow-hidden">
          {list.isLoading ? (
            <div className="px-8 py-12 text-center text-sm text-muted">Loading keys…</div>
          ) : list.isError ? (
            <div className="px-8 py-12 text-center text-sm text-rose-700">
              {(list.error as Error)?.message ?? "Failed to load keys."}
            </div>
          ) : (list.data ?? []).length === 0 ? (
            <EmptyState onCreate={openCreate} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-cream/60 text-left text-xs uppercase tracking-wider text-muted">
                    <th className="px-6 py-3 font-medium">Name</th>
                    <th className="px-6 py-3 font-medium">Key</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                    <th className="px-6 py-3 font-medium">Created</th>
                    <th className="px-6 py-3 font-medium">Expires</th>
                    <th className="px-6 py-3 font-medium">Last used</th>
                    <th className="px-6 py-3 font-medium text-center">Usage</th>
                    <th className="px-6 py-3 font-medium text-right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-parchment/70">
                  {list.data!.map((k) => (
                    <KeyRow
                      key={k.id}
                      apiKey={k}
                      onUsage={setUsageKey}
                      onRevoke={handleRevoke}
                      revoking={revoke.isPending}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <CreateKeyDialog open={createOpen} onClose={closeCreate} onCreated={handleCreated} />
      <RevealKeyOnceDialog apiKey={revealKey} onClose={closeReveal} />
      <ApiKeyUsageDrawer apiKey={usageKey} onClose={closeUsage} />
    </AppShell>
  );
}

interface KeyRowProps {
  apiKey: ApiKey;
  onUsage: (k: ApiKey) => void;
  onRevoke: (k: ApiKey) => void;
  revoking: boolean;
}

const KeyRow = memo(function KeyRow({ apiKey: k, onUsage, onRevoke, revoking }: KeyRowProps) {
  return (
    <tr className="hover:bg-cream/30">
      <td className="px-6 py-4 font-medium text-ink">{k.name}</td>
      <td className="px-6 py-4 w-36 max-w-[9rem]">
        <span className="block truncate font-mono text-xs text-muted">{maskKey(k.keyPrefix, k.lastFour)}</span>
      </td>
      <td className="px-6 py-4"><StatusBadge status={k.status} /></td>
      <td className="px-6 py-4 text-muted">{formatDate(k.createdAt)}</td>
      <td className="px-6 py-4 text-muted">{k.expiresAt ? formatDate(k.expiresAt) : "Never"}</td>
      <td className="px-6 py-4 text-muted">{formatDate(k.lastUsedAt)}</td>
      <td className="px-6 py-4 text-center">
        <button type="button" onClick={() => onUsage(k)} className="btn-ghost" aria-label="View usage">
          <Activity className="h-4 w-4" /><span>Usage</span>
        </button>
      </td>
      <td className="px-6 py-4 text-right">
        {k.status === "active" && (
          <button
            type="button"
            onClick={() => onRevoke(k)}
            className="btn-ghost text-rose-700 hover:bg-rose-50 hover:text-rose-700"
            disabled={revoking}
          >
            <Trash2 className="h-4 w-4" /><span>Revoke</span>
          </button>
        )}
      </td>
    </tr>
  );
});

const StatusBadge = memo(function StatusBadge({ status }: { status: ApiKey["status"] }) {
  if (status === "active") return <span className="badge-active">Active</span>;
  if (status === "revoked") return <span className="badge-revoked">Revoked</span>;
  return <span className="badge-muted">Expired</span>;
});

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center px-8 py-16 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-saffron-50 text-saffron">
        <KeyRound className="h-6 w-6" />
      </span>
      <h3 className="mt-5 font-serif text-xl text-ink">No API keys yet</h3>
      <p className="mt-2 max-w-sm text-sm text-muted">
        Create your first key to start authenticating requests against the platform.
      </p>
      <button type="button" className="btn-primary mt-6" onClick={onCreate}>
        <Plus className="h-4 w-4" /> Create your first key
      </button>
    </div>
  );
}
