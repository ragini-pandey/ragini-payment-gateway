import { memo, useCallback, useState } from "react";
import { Link } from "react-router";
import { ArrowLeft, Plus, Trash2, Webhook as WebhookIcon } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { useWebhooks } from "@/features/webhooks/useWebhooks";
import { CreateWebhookDialog } from "@/features/webhooks/CreateWebhookDialog";
import { WebhookDetailDrawer } from "@/features/webhooks/WebhookDetailDrawer";
import { RevealWebhookSecretDialog } from "@/features/webhooks/RevealWebhookSecretDialog";
import type { Webhook } from "@/lib/apiClient";
import { useEnvironment } from "@/lib/env";
import { cn, formatDate } from "@/lib/utils";
import { toast } from "sonner";

export function WebhooksPage() {
  const { environment } = useEnvironment();
  const { list, remove } = useWebhooks();
  const [createOpen, setCreateOpen] = useState(false);
  const [active, setActive] = useState<Webhook | null>(null);
  const [revealSecret, setRevealSecret] = useState<Webhook | null>(null);

  const handleDelete = useCallback(async (e: React.MouseEvent, w: Webhook) => {
    e.stopPropagation();
    if (!window.confirm(`Delete webhook for ${w.url}? This cannot be undone.`)) return;
    try {
      await remove.mutateAsync(w.id);
      toast.success("Webhook deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    }
  }, [remove]);

  const openCreate = useCallback(() => setCreateOpen(true), []);
  const closeCreate = useCallback(() => setCreateOpen(false), []);
  const handleCreated = useCallback((w: Webhook) => setRevealSecret(w), []);
  const closeReveal = useCallback(() => setRevealSecret(null), []);
  const closeDrawer = useCallback(() => setActive(null), []);

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
            <h1 className="mt-2 font-serif text-4xl text-ink">Webhooks</h1>
            <p className="mt-2 text-sm text-muted max-w-xl">
              Subscribe to events at your own HTTPS endpoints. You are viewing{" "}
              <span
                className={cn(
                  "font-medium",
                  environment === "live" ? "text-rose-700" : "text-ink"
                )}
              >
                {environment.toUpperCase()}
              </span>{" "}
              webhooks.
            </p>
          </div>
          <button type="button" className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" /> Add Webhook
          </button>
        </header>

        <div className="mt-8 card-surface overflow-hidden">
          {list.isLoading ? (
            <div className="px-8 py-12 text-center text-sm text-muted">Loading webhooks…</div>
          ) : list.isError ? (
            <div className="px-8 py-12 text-center text-sm text-rose-700">
              {(list.error as Error)?.message ?? "Failed to load webhooks."}
            </div>
          ) : (list.data ?? []).length === 0 ? (
            <EmptyState onCreate={openCreate} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-cream/60 text-left text-xs uppercase tracking-wider text-muted">
                    <th className="px-6 py-3 font-medium">URL</th>
                    <th className="px-6 py-3 font-medium">Events</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                    <th className="px-6 py-3 font-medium">Created</th>
                    <th className="px-6 py-3 font-medium" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-parchment/70">
                  {list.data!.map((w) => (
                    <WebhookRow
                      key={w.id}
                      webhook={w}
                      onSelect={setActive}
                      onDelete={handleDelete}
                      deleting={remove.isPending}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <CreateWebhookDialog open={createOpen} onClose={closeCreate} onCreated={handleCreated} />
      <RevealWebhookSecretDialog webhook={revealSecret} onClose={closeReveal} />
      <WebhookDetailDrawer webhook={active} onClose={closeDrawer} />
    </AppShell>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center px-8 py-16 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-saffron-50 text-saffron">
        <WebhookIcon className="h-6 w-6" />
      </span>
      <h3 className="mt-5 font-serif text-xl text-ink">No webhooks yet</h3>
      <p className="mt-2 max-w-sm text-sm text-muted">
        Configure your first endpoint to start receiving event notifications.
      </p>
      <button type="button" className="btn-primary mt-6" onClick={onCreate}>
        <Plus className="h-4 w-4" /> Add your first webhook
      </button>
    </div>
  );
}

interface WebhookRowProps {
  webhook: Webhook;
  onSelect: (w: Webhook) => void;
  onDelete: (e: React.MouseEvent, w: Webhook) => void;
  deleting: boolean;
}

const WebhookRow = memo(function WebhookRow({ webhook: w, onSelect, onDelete, deleting }: WebhookRowProps) {
  return (
    <tr className="hover:bg-cream/30 cursor-pointer" onClick={() => onSelect(w)}>
      <td className="px-6 py-4 font-medium text-ink max-w-xs truncate">{w.url}</td>
      <td className="px-6 py-4">
        <div className="flex flex-wrap gap-1">
          {w.events.slice(0, 3).map((e) => (
            <span key={e} className="badge-saffron">{e}</span>
          ))}
          {w.events.length > 3 && (
            <span className="badge-muted">+{w.events.length - 3}</span>
          )}
        </div>
      </td>
      <td className="px-6 py-4">
        {w.status === "active"
          ? <span className="badge-active">{w.status}</span>
          : <span className="badge-muted">{w.status}</span>}
      </td>
      <td className="px-6 py-4 text-muted">{formatDate(w.createdAt)}</td>
      <td className="px-6 py-4 text-right">
        <button
          type="button"
          onClick={(e) => onDelete(e, w)}
          className="btn-ghost text-rose-700 hover:bg-rose-50 hover:text-rose-700"
          disabled={deleting}
          aria-label="Delete webhook"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </td>
    </tr>
  );
});
