import { Modal } from "@/components/Overlay";
import { Copy, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import type { Webhook } from "@/lib/apiClient";

interface Props {
  webhook: Webhook | null;
  onClose: () => void;
}

export function RevealWebhookSecretDialog({ webhook, onClose }: Props) {
  async function copy() {
    if (!webhook) return;
    try {
      await navigator.clipboard.writeText(webhook.secret);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Couldn't copy — please copy manually");
    }
  }

  return (
    <Modal
      open={!!webhook}
      onClose={onClose}
      title="Save your signing secret"
      description="This is the only time the full secret will be shown."
      size="lg"
      footer={
        <button type="button" className="btn-primary" onClick={onClose}>
          I have saved this secret
        </button>
      }
    >
      <div className="rounded-2xl border border-saffron-100 bg-saffron-50/60 p-4 text-sm text-saffron-700 flex gap-3">
        <ShieldAlert className="h-5 w-5 shrink-0 mt-0.5" />
        <p>
          Store this secret in your application configuration. Use it to verify
          the <code className="font-mono">X-Ragini-Signature</code> HMAC header
          on incoming events. If you lose it, you'll need to recreate the
          webhook.
        </p>
      </div>

      {webhook && (
        <div className="mt-5">
          <div className="text-xs font-medium uppercase tracking-wider text-muted">
            {webhook.url}
          </div>
          <div className="mt-2 flex items-stretch gap-2">
            <code className="flex-1 rounded-xl border border-parchment bg-cream/60 px-4 py-3 font-mono text-sm text-ink break-all">
              {webhook.secret}
            </code>
            <button
              type="button"
              onClick={copy}
              className="btn-secondary"
              aria-label="Copy secret"
            >
              <Copy className="h-4 w-4" />
              <span>Copy</span>
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
