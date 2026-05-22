import { Modal } from "@/components/Overlay";
import { Copy, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import type { ApiKeyWithSecret } from "@/lib/apiClient";

interface Props {
  apiKey: ApiKeyWithSecret | null;
  onClose: () => void;
}

export function RevealKeyOnceDialog({ apiKey, onClose }: Props) {
  async function copy() {
    if (!apiKey) return;
    try {
      await navigator.clipboard.writeText(apiKey.key);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Couldn't copy — please copy manually");
    }
  }

  return (
    <Modal
      open={!!apiKey}
      onClose={onClose}
      title="Save your new API key"
      description="This is the only time the full key will be shown."
      size="lg"
      footer={
        <button type="button" className="btn-primary" onClick={onClose}>
          I have saved this key
        </button>
      }
    >
      <div className="rounded-2xl border border-saffron-100 bg-saffron-50/60 p-4 text-sm text-saffron-700 flex gap-3">
        <ShieldAlert className="h-5 w-5 shrink-0 mt-0.5" />
        <p>
          Copy this key and store it in a safe place. For security reasons we
          will never show it again. If you lose it, revoke it and create a new
          one.
        </p>
      </div>

      {apiKey && (
        <div className="mt-5">
          <div className="text-xs font-medium uppercase tracking-wider text-muted">
            {apiKey.name}
          </div>
          <div className="mt-2 flex items-stretch gap-2">
            <code className="flex-1 rounded-xl border border-parchment bg-cream/60 px-4 py-3 font-mono text-sm text-ink break-all">
              {apiKey.key}
            </code>
            <button type="button" onClick={copy} className="btn-secondary" aria-label="Copy key">
              <Copy className="h-4 w-4" />
              <span>Copy</span>
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
