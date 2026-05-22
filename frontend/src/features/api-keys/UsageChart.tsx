import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useQuery } from "@tanstack/react-query";
import { apiClient, type UsageResponse } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

const RANGES: Array<{ label: string; value: "24h" | "7d" | "30d" }> = [
  { label: "24h", value: "24h" },
  { label: "7d", value: "7d" },
  { label: "30d", value: "30d" },
];

interface Props {
  keyId: string;
}

export function UsageChart({ keyId }: Props) {
  const [range, setRange] = useState<"24h" | "7d" | "30d">("24h");
  const usage = useQuery<UsageResponse>({
    queryKey: ["api-key-usage", keyId, range],
    queryFn: () => apiClient.getApiKeyUsage(keyId, range),
    enabled: !!keyId,
  });

  const data = useMemo(
    () =>
      (usage.data?.points ?? []).map((p) => ({
        ...p,
        label: formatBucket(p.timestamp, range),
      })),
    [usage.data, range]
  );

  const totals = useMemo(() => {
    const points = usage.data?.points ?? [];
    return points.reduce(
      (acc, p) => {
        acc.total += p.total;
        acc.errors += p.errors;
        return acc;
      },
      { total: 0, errors: 0 }
    );
  }, [usage.data]);

  return (
    <section>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-serif text-lg text-ink">Request volume</h3>
          <p className="text-xs text-muted">
            {totals.total} requests · {totals.errors} errors
          </p>
        </div>
        <div className="flex gap-1.5">
          {RANGES.map((r) => (
            <button
              key={r.value}
              type="button"
              onClick={() => setRange(r.value)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition",
                range === r.value
                  ? "border-saffron-300 bg-saffron-50 text-saffron-700"
                  : "border-parchment bg-white text-muted hover:text-ink"
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 card-surface p-4">
        {usage.isLoading ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted">
            Loading usage…
          </div>
        ) : usage.isError ? (
          <div className="h-64 flex items-center justify-center text-sm text-rose-700">
            {(usage.error as Error)?.message ?? "Failed to load usage"}
          </div>
        ) : data.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted">
            No requests recorded in this range yet.
          </div>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="usageTotal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#C8612A" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#C8612A" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="usageErrors" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#b91c1c" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#b91c1c" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#E9DFC9" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "#6B5A47", fontSize: 11 }}
                  axisLine={{ stroke: "#E9DFC9" }}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "#6B5A47", fontSize: 11 }}
                  axisLine={{ stroke: "#E9DFC9" }}
                  tickLine={false}
                  width={32}
                />
                <Tooltip
                  contentStyle={{
                    background: "#FFFFFF",
                    border: "1px solid #E9DFC9",
                    borderRadius: 12,
                    fontSize: 12,
                    color: "#2A1F14",
                  }}
                  labelStyle={{ color: "#6B5A47" }}
                />
                <Area
                  type="monotone"
                  dataKey="total"
                  stroke="#C8612A"
                  strokeWidth={2}
                  fill="url(#usageTotal)"
                  name="Total"
                />
                <Area
                  type="monotone"
                  dataKey="errors"
                  stroke="#b91c1c"
                  strokeWidth={2}
                  fill="url(#usageErrors)"
                  name="Errors"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </section>
  );
}

function formatBucket(ts: string, range: "24h" | "7d" | "30d"): string {
  const d = new Date(ts);
  if (range === "24h") {
    return d.toLocaleTimeString([], { hour: "numeric" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}
