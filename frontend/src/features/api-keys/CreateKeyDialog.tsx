import { useState } from "react";
import { Modal } from "@/components/Overlay";
import { useApiKeys } from "./useApiKeys";
import { useEnvironment } from "@/lib/env";
import type { ApiKeyWithSecret } from "@/lib/apiClient";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type Expiry = "never" | "30d" | "90d" | "1y" | "custom";

const EXPIRY_DAYS: Record<Exclude<Expiry, "never" | "custom">, number> = {
  "30d": 30,
  "90d": 90,
  "1y": 365,
};

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (key: ApiKeyWithSecret) => void;
}

export function CreateKeyDialog({ open, onClose, onCreated }: Props) {
  const { environment } = useEnvironment();
  const [name, setName] = useState("");
  const [expiry, setExpiry] = useState<Expiry>("never");
  const [customDate, setCustomDate] = useState("");
  const { create } = useApiKeys();

  function reset() {
    setName("");
    setExpiry("never");
    setCustomDate("");
  }

  function handleClose() {
    if (create.isPending) return;
    reset();
    onClose();
  }

  function computeExpiresAt(): string | null {
    if (expiry === "never") return null;
    if (expiry === "custom") {
      if (!customDate) return null;
      const d = new Date(customDate);
      return Number.isNaN(d.getTime()) ? null : d.toISOString();
    }
    const days = EXPIRY_DAYS[expiry];
    return new Date(Date.now() + days * 86_400_000).toISOString();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    if (expiry === "custom" && !customDate) {
      toast.error("Pick a custom expiry date");
      return;
    }
    try {
      const result = await create.mutateAsync({
        name: trimmed,
        expiresAt: computeExpiresAt(),
      });
      toast.success("API key created");
      reset();
      onCreated(result);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create key");
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Create API key"
      description={`A new ${environment === "live" ? "LIVE" : "TEST"} mode key.`}
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
            form="create-key-form"
            className="btn-primary"
            disabled={create.isPending || !name.trim()}
          >
            {create.isPending ? "Creating…" : "Create key"}
          </button>
        </>
      }
    >
      <form id="create-key-form" onSubmit={handleSubmit} className="space-y-5">
        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-muted">
            Name
          </span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Production server"
            className="input mt-1.5"
            autoFocus
            maxLength={60}
          />
        </label>

        <fieldset>
          <legend className="text-xs font-medium uppercase tracking-wider text-muted">
            Expiry
          </legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {(["never", "30d", "90d", "1y", "custom"] as Expiry[]).map((opt) => {
              const active = expiry === opt;
              const label =
                opt === "never"
                  ? "Never"
                  : opt === "1y"
                    ? "1 year"
                    : opt === "custom"
                      ? "Custom"
                      : opt;
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setExpiry(opt)}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                    active
                      ? "border-saffron bg-saffron text-ivory"
                      : "border-parchment bg-white text-ink hover:bg-cream"
                  )}
                >
                  {label}
                </button>
              );
            })}
          </div>
          {expiry === "custom" && (
            <input
              type="datetime-local"
              value={customDate}
              onChange={(e) => setCustomDate(e.target.value)}
              className="input mt-3"
              min={new Date(Date.now() + 3_600_000).toISOString().slice(0, 16)}
            />
          )}
        </fieldset>
      </form>
    </Modal>
  );
}
