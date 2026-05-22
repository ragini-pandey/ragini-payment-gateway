import { Drawer } from "@/components/Overlay";
import type { ApiKey } from "@/lib/apiClient";
import { formatDate, formatDateTime, maskKey } from "@/lib/utils";
import { UsageChart } from "./UsageChart";

interface Props {
  apiKey: ApiKey | null;
  onClose: () => void;
}

export function ApiKeyUsageDrawer({ apiKey, onClose }: Props) {
  return (
    <Drawer
      open={!!apiKey}
      onClose={onClose}
      title="API key usage"
      description={apiKey?.name}
    >
      {apiKey && (
        <div className="space-y-8">
          <section>
            <dl className="space-y-3 text-sm">
              <Row
                label="Key"
                value={
                  <code className="font-mono">
                    {maskKey(apiKey.keyPrefix, apiKey.lastFour)}
                  </code>
                }
              />
              <Row
                label="Environment"
                value={
                  <span className="font-mono text-xs uppercase">
                    {apiKey.environment}
                  </span>
                }
              />
              <Row label="Status" value={apiKey.status} />
              <Row label="Created" value={formatDate(apiKey.createdAt)} />
              <Row
                label="Last used"
                value={
                  apiKey.lastUsedAt ? formatDateTime(apiKey.lastUsedAt) : "—"
                }
              />
              <Row
                label="Expires"
                value={apiKey.expiresAt ? formatDate(apiKey.expiresAt) : "Never"}
              />
            </dl>
          </section>

          <UsageChart keyId={apiKey.id} />
        </div>
      )}
    </Drawer>
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
