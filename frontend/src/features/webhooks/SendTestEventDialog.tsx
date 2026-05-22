import { useState, useEffect } from "react";
import { Modal } from "@/components/Overlay";
import { EVENT_TYPES, type EventType } from "@/lib/apiClient";
import { useDeliveryLogs } from "./useDeliveryLogs";
import { toast } from "sonner";

const DEFAULT_PAYLOADS: Record<string, Record<string, unknown>> = {
  "payment.success": {
    amount: 1000,
    currency: "usd",
    payment_id: "pay_test_abc123",
    description: "Test charge",
  },
  "payment.error": {
    amount: 1000,
    currency: "usd",
    payment_id: "pay_test_abc123",
    error: "card_declined",
    decline_code: "insufficient_funds",
  },
  "api_key.revoked": {
    key_prefix: "sk_test",
    reason: "Test revocation",
  },
  "api_key.expired": {
    key_prefix: "sk_test",
    expires_at: new Date().toISOString(),
  },
  "security.alert": {
    severity: "low",
    message: "Test security alert",
    source_ip: "127.0.0.1",
  },
};

interface Props {
  webhookId: string | null;
  open: boolean;
  onClose: () => void;
}

export function SendTestEventDialog({ webhookId, open, onClose }: Props) {
  const { sendTest } = useDeliveryLogs(webhookId);

  const [eventType, setEventType] = useState<EventType>("payment.success");
  const [payloadText, setPayloadText] = useState(
    JSON.stringify(DEFAULT_PAYLOADS["payment.success"], null, 2)
  );
  const [parseError, setParseError] = useState<string | null>(null);

  // Refresh default payload when event type changes
  useEffect(() => {
    const def = DEFAULT_PAYLOADS[eventType] ?? {};
    setPayloadText(JSON.stringify(def, null, 2));
    setParseError(null);
  }, [eventType]);

  function handlePayloadChange(value: string) {
    setPayloadText(value);
    try {
      JSON.parse(value);
      setParseError(null);
    } catch {
      setParseError("Invalid JSON");
    }
  }

  function handleClose() {
    if (sendTest.isPending) return;
    onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(payloadText);
    } catch {
      setParseError("Invalid JSON — fix before sending");
      return;
    }
    try {
      await sendTest.mutateAsync({ eventType, data });
      toast.success(`Test "${eventType}" event dispatched`);
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send test event");
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Send test event"
      description="Dispatch a test event to this webhook endpoint."
      size="lg"
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            className="btn-secondary"
            disabled={sendTest.isPending}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="test-event-form"
            className="btn-primary"
            disabled={sendTest.isPending || !!parseError}
          >
            {sendTest.isPending ? "Sending…" : "Send test event"}
          </button>
        </>
      }
    >
      <form id="test-event-form" onSubmit={handleSubmit} className="space-y-5">
        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-muted">
            Event type
          </span>
          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value as EventType)}
            className="input mt-1.5"
          >
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-muted">
            Payload (JSON)
          </span>
          <textarea
            value={payloadText}
            onChange={(e) => handlePayloadChange(e.target.value)}
            rows={10}
            spellCheck={false}
            className={`input mt-1.5 font-mono text-xs resize-y ${
              parseError ? "border-rose-400 focus:ring-rose-300" : ""
            }`}
          />
          {parseError && (
            <p className="mt-1 text-xs text-rose-600">{parseError}</p>
          )}
        </label>
      </form>
    </Modal>
  );
}
