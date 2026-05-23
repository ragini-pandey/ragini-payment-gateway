import { Drawer } from "@/components/Overlay";
import type { DeliveryStatus, Webhook, WebhookDelivery } from "@/lib/apiClient";
import { useDeliveryLogs } from "./useDeliveryLogs";
import { SendTestEventDialog } from "./SendTestEventDialog";
import { RevealWebhookSecretDialog } from "./RevealWebhookSecretDialog";
import { ChevronLeft, ChevronRight, KeyRound, RefreshCw, Send } from "lucide-react";
import { toast } from "sonner";
import { cn, formatDateTime } from "@/lib/utils";
import { useState } from "react";

interface Props {
  webhook: Webhook | null;
  onClose: () => void;
}

const PAGE_SIZE = 25;
const STATUS_FILTERS: Array<{ label: string; value: DeliveryStatus | "all" }> = [
  { label: "All", value: "all" },
  { label: "Success", value: "success" },
  { label: "Failed", value: "failed" },
  { label: "Retrying", value: "retrying" },
  { label: "Dead-lettered", value: "dead_lettered" },
];

export function WebhookDetailDrawer({ webhook, onClose }: Props) {
  const [statusFilter, setStatusFilter] = useState<DeliveryStatus | "all">(
    "all"
  );
  const [page, setPage] = useState(0);
  const [testOpen, setTestOpen] = useState(false);
  const [rotatedSecret, setRotatedSecret] = useState<Webhook | null>(null);

  const { list, retry, rotateSecret } = useDeliveryLogs(webhook?.id ?? null, {
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    status: statusFilter === "all" ? undefined : statusFilter,
  });

  async function handleRetry(d: WebhookDelivery) {
    try {
      await retry.mutateAsync(d.id);
      toast.success("Delivery re-attempted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Retry failed");
    }
  }

  async function handleRotate() {
    if (!webhook) return;
    if (
      !window.confirm(
        "Rotate this webhook's signing secret? The old secret stops working immediately."
      )
    )
      return;
    try {
      const updated = await rotateSecret.mutateAsync();
      setRotatedSecret(updated);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Rotation failed");
    }
  }

  const total = list.data?.total ?? 0;
  const items = list.data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <Drawer
        open={!!webhook}
        onClose={onClose}
        title="Webhook details"
        description={webhook?.url}
      >
      {webhook && (
        <div className="space-y-8">
          <section>
            <h3 className="font-serif text-lg text-ink">Configuration</h3>
            <dl className="mt-3 space-y-3 text-sm">
              <Row
                label="URL"
                value={<code className="break-all">{webhook.url}</code>}
              />
              <Row
                label="Description"
                value={
                  webhook.description || (
                    <span className="text-muted">—</span>
                  )
                }
              />
              <Row
                label="Events"
                value={
                  <div className="flex flex-wrap gap-1.5">
                    {webhook.events.map((e) => (
                      <span key={e} className="badge-saffron">
                        {e}
                      </span>
                    ))}
                  </div>
                }
              />
              <Row
                label="Environment"
                value={
                  <span className="font-mono text-xs uppercase">
                    {webhook.environment}
                  </span>
                }
              />
              <Row
                label="Status"
                value={
                  webhook.status === "active" ? (
                    <span className="badge-active">{webhook.status}</span>
                  ) : (
                    <span className="badge-muted">{webhook.status}</span>
                  )
                }
              />
              <Row label="Created" value={formatDateTime(webhook.createdAt)} />
            </dl>
          </section>

          <section>
            <div className="flex items-center justify-between">
              <h3 className="font-serif text-lg text-ink">Signing secret</h3>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleRotate}
                disabled={rotateSecret.isPending}
              >
                <KeyRound className="h-4 w-4" />
                {rotateSecret.isPending ? "Rotating…" : "Rotate secret"}
              </button>
            </div>
            <p className="mt-1 text-xs text-muted">
              The full secret is only shown at creation or just after rotation.
              Stored keys are masked. Use the secret to verify the{" "}
              <code className="font-mono">X-Ragini-Signature</code> HMAC header.
            </p>
            <code className="mt-3 block rounded-xl border border-parchment bg-cream/60 px-4 py-3 font-mono text-xs text-ink break-all">
              {webhook.secret}
            </code>
          </section>

          <section>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <h3 className="font-serif text-lg text-ink">Recent deliveries</h3>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => list.refetch()}
                  disabled={list.isFetching}
                >
                  <RefreshCw className={cn("h-4 w-4", list.isFetching && "animate-spin")} />
                  {list.isFetching ? "Refreshing…" : "Refresh"}
                </button>
                <button
                  type="button"
                  onClick={() => setTestOpen(true)}
                  className="btn-primary"
                >
                  <Send className="h-4 w-4" />
                  Send test event
                </button>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {STATUS_FILTERS.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() => {
                    setStatusFilter(f.value);
                    setPage(0);
                  }}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs transition",
                    statusFilter === f.value
                      ? "border-saffron-300 bg-saffron-50 text-saffron-700"
                      : "border-parchment bg-white text-muted hover:text-ink"
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>

            <div className="mt-4 card-surface overflow-hidden">
              {list.isLoading ? (
                <div className="px-6 py-10 text-center text-sm text-muted">
                  Loading deliveries…
                </div>
              ) : items.length === 0 ? (
                <div className="px-6 py-10 text-center text-sm text-muted">
                  No deliveries match. Try a different filter or send a test
                  event.
                </div>
              ) : (
                <ul className="divide-y divide-parchment/70">
                  {items.map((d) => (
                    <DeliveryRow
                      key={d.id}
                      delivery={d}
                      onRetry={() => handleRetry(d)}
                      retrying={retry.isPending}
                    />
                  ))}
                </ul>
              )}
            </div>

            {total > PAGE_SIZE && (
              <div className="mt-3 flex items-center justify-between text-xs text-muted">
                <span>
                  Page {page + 1} of {totalPages} · {total} total
                </span>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    className="btn-secondary px-2 py-1"
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    className="btn-secondary px-2 py-1"
                    onClick={() =>
                      setPage((p) => Math.min(totalPages - 1, p + 1))
                    }
                    disabled={page + 1 >= totalPages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </Drawer>
    <SendTestEventDialog
      webhookId={webhook?.id ?? null}
      open={testOpen}
      onClose={() => setTestOpen(false)}
    />
    <RevealWebhookSecretDialog
      webhook={rotatedSecret}
      onClose={() => setRotatedSecret(null)}
    />
    </>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      <dt className="text-xs font-medium uppercase tracking-wider text-muted">
        {label}
      </dt>
      <dd className="col-span-2 text-ink">{value}</dd>
    </div>
  );
}

function statusClass(status: WebhookDelivery["status"]): string {
  switch (status) {
    case "success":
      return "badge-active";
    case "failed":
    case "dead_lettered":
      return "badge-revoked";
    case "pending":
    case "retrying":
    default:
      return "badge-saffron";
  }
}

function DeliveryRow({
  delivery,
  onRetry,
  retrying,
}: {
  delivery: WebhookDelivery;
  onRetry: () => void;
  retrying: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <li className="px-5 py-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 text-left"
      >
        <span className={cn(statusClass(delivery.status), "uppercase")}>
          {delivery.status}
        </span>
        <span className="font-mono text-sm text-ink">{delivery.eventType}</span>
        <span className="text-xs text-muted">attempt {delivery.attempt}</span>
        {delivery.responseCode !== null && (
          <span className="text-xs text-muted">{delivery.responseCode}</span>
        )}
        <span className="ml-auto text-xs text-muted">
          {formatDateTime(delivery.createdAt)}
        </span>
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          {delivery.responseBody && (
            <pre className="rounded-xl border border-parchment bg-cream/60 p-3 text-xs text-ink overflow-x-auto whitespace-pre-wrap">
              {delivery.responseBody}
            </pre>
          )}
          {(delivery.status === "failed" ||
            delivery.status === "dead_lettered") && (
            <button
              type="button"
              className="btn-secondary"
              onClick={onRetry}
              disabled={retrying}
            >
              <RefreshCw className="h-4 w-4" />{" "}
              {retrying ? "Retrying…" : "Retry"}
            </button>
          )}
        </div>
      )}
    </li>
  );
}
