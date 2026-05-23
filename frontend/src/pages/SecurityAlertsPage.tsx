import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link } from "react-router";
import { ArrowLeft, ShieldAlert, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import {
  apiClient,
  type SecurityAlert,
  type SecurityAlertSeverity,
} from "@/lib/apiClient";
import { useEnvironment } from "@/lib/env";
import { cn, formatDateTime } from "@/lib/utils";
import { SEEN_KEY } from "@/features/security/useUnreadAlerts";

const SEVERITY_CLASS: Record<SecurityAlertSeverity, string> = {
  low: "bg-cream text-ink border-parchment",
  medium: "bg-saffron-50 text-saffron-700 border-saffron-100",
  high: "bg-rose-50 text-rose-700 border-rose-100",
  critical: "bg-rose-600 text-ivory border-rose-700",
};

export function SecurityAlertsPage() {
  const { environment } = useEnvironment();
  const prevCountRef = useRef<number | null>(null);

  // Mark all current alerts as seen so the header dot clears immediately
  useEffect(() => {
    localStorage.setItem(SEEN_KEY, String(Date.now()));
    window.dispatchEvent(new Event("security-alerts-seen"));
  }, []);

  const query = useQuery<SecurityAlert[]>({
    queryKey: ["securityAlerts", environment],
    queryFn: () => apiClient.listSecurityAlerts(environment),
  });

  useEffect(() => {
    if (!query.data) return;
    const current = query.data.length;
    if (prevCountRef.current !== null && current > prevCountRef.current) {
      const newest = query.data[0];
      toast.error(
        newest
          ? `New ${newest.severity} alert: ${newest.alertType.replace(/_/g, " ")}`
          : "New security alert received",
        { duration: 6000 }
      );
    }
    prevCountRef.current = current;
  }, [query.data]);

  return (
    <AppShell>
      <section className="mx-auto w-full max-w-5xl px-6 py-12">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to home
        </Link>

        <header className="mt-6">
          <h1 className="mt-2 font-serif text-4xl text-ink">Security alerts</h1>
          <p className="mt-2 text-sm text-muted max-w-xl">
            Suspicious key usage and traffic anomalies for{" "}
            <span
              className={cn(
                "font-medium",
                environment === "live" ? "text-rose-700" : "text-ink"
              )}
            >
              {environment.toUpperCase()}
            </span>{" "}
            mode.
          </p>
        </header>

        <div className="mt-8 card-surface overflow-hidden">
          {query.isLoading ? (
            <div className="px-8 py-12 text-center text-sm text-muted">
              Loading alerts…
            </div>
          ) : query.isError ? (
            <div className="px-8 py-12 text-center text-sm text-rose-700">
              {(query.error as Error)?.message ?? "Failed to load alerts."}
            </div>
          ) : (query.data ?? []).length === 0 ? (
            <EmptyState />
          ) : (
            <ul className="divide-y divide-parchment/70">
              {query.data!.map((a) => (
                <AlertRow key={a.id} alert={a} />
              ))}
            </ul>
          )}
        </div>
      </section>
    </AppShell>
  );
}

function AlertRow({ alert }: { alert: SecurityAlert }) {
  return (
    <li className="px-6 py-4">
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border",
            SEVERITY_CLASS[alert.severity]
          )}
        >
          <ShieldAlert className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm text-ink">{alert.alertType}</span>
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-xs font-medium uppercase",
                SEVERITY_CLASS[alert.severity]
              )}
            >
              {alert.severity}
            </span>
            <span className="text-xs text-muted">
              {formatDateTime(alert.createdAt)}
            </span>
          </div>
          {Object.keys(alert.details ?? {}).length > 0 && (
            <pre className="mt-2 rounded-xl border border-parchment bg-cream/60 p-3 text-xs text-ink overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(alert.details, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </li>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center px-8 py-16 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
        <ShieldCheck className="h-6 w-6" />
      </span>
      <h3 className="mt-5 font-serif text-xl text-ink">All clear</h3>
      <p className="mt-2 max-w-sm text-sm text-muted">
        No security alerts yet for this environment. We'll surface revoked-key
        usage, expired-key usage, and request spikes here automatically.
      </p>
    </div>
  );
}
