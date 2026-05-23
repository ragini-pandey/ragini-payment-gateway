import { useState } from "react";
import { Modal } from "@/components/Overlay";
import { useWebhooks } from "./useWebhooks";
import { useEnvironment } from "@/lib/env";
import { EVENT_TYPES, type Webhook } from "@/lib/apiClient";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated?: (webhook: Webhook) => void;
}

export function CreateWebhookDialog({ open, onClose, onCreated }: Props) {
  const { environment } = useEnvironment();
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<string[]>([
    "payment.success",
    "payment.error",
  ]);
  const { create } = useWebhooks();

  function reset() {
    setUrl("");
    setDescription("");
    setSelected(["payment.success", "payment.error"]);
  }

  function handleClose() {
    if (create.isPending) return;
    reset();
    onClose();
  }

  function toggle(ev: string) {
    setSelected((s) =>
      s.includes(ev) ? s.filter((e) => e !== ev) : [...s, ev]
    );
  }

  function isValidUrl(value: string) {
    try {
      const u = new URL(value);
      if (environment === "live" && u.protocol === "http:") return false;
      return u.protocol === "https:" || u.protocol === "http:";
    } catch {
      return false;
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValidUrl(url)) {
      toast.error(
        environment === "live"
          ? "Live webhook endpoints must use HTTPS"
          : "Please enter a valid HTTP(S) URL"
      );
      return;
    }
    if (selected.length === 0) {
      toast.error("Select at least one event");
      return;
    }
    try {
      const created = await create.mutateAsync({
        url: url.trim(),
        description: description.trim() || undefined,
        events: selected,
      });
      toast.success("Webhook added");
      reset();
      onClose();
      onCreated?.(created);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create webhook");
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Add webhook"
      description={`Send ${environment === "live" ? "LIVE" : "TEST"} events to your endpoint.`}
      size="lg"
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            className="btn-secondary"
            disabled={create.isPending}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="create-webhook-form"
            className="btn-primary"
            disabled={create.isPending}
          >
            {create.isPending ? "Adding…" : "Add webhook"}
          </button>
        </>
      }
    >
      <form id="create-webhook-form" onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-muted">
            Endpoint URL
          </span>
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://api.example.com/webhooks/ragini"
            className="input mt-1.5"
            autoFocus
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-muted">
            Description (optional)
          </span>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is this endpoint for?"
            className="input mt-1.5"
            maxLength={120}
          />
        </label>

        <fieldset>
          <legend className="text-xs font-medium uppercase tracking-wider text-muted">
            Events
          </legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {EVENT_TYPES.map((ev) => {
              const active = selected.includes(ev);
              return (
                <button
                  key={ev}
                  type="button"
                  onClick={() => toggle(ev)}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-xs font-mono font-medium transition-colors",
                    active
                      ? "border-saffron bg-saffron text-ivory"
                      : "border-parchment bg-white text-ink hover:bg-cream"
                  )}
                >
                  {ev}
                </button>
              );
            })}
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}
