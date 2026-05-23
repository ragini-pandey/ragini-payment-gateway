import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient, type SecurityAlert } from "@/lib/apiClient";
import { useEnvironment } from "@/lib/env";

export const SEEN_KEY = "security_alerts_seen_at";

/**
 * Returns the count of high/critical alerts from the last 24 hours that
 * arrived after the user last visited the Security Alerts page.
 * Shared across HomePage and AppShell so React Query deduplicates the fetch.
 */
export function useUnreadAlerts() {
  const { environment } = useEnvironment();
  const [seenAt, setSeenAt] = useState<number>(() => {
    const stored = localStorage.getItem(SEEN_KEY);
    return stored ? parseInt(stored, 10) : 0;
  });

  useEffect(() => {
    function onSeen() {
      const stored = localStorage.getItem(SEEN_KEY);
      setSeenAt(stored ? parseInt(stored, 10) : 0);
    }
    window.addEventListener("security-alerts-seen", onSeen);
    return () => window.removeEventListener("security-alerts-seen", onSeen);
  }, []);

  const query = useQuery<SecurityAlert[]>({
    queryKey: ["securityAlerts", environment],
    queryFn: () => apiClient.listSecurityAlerts(environment),
  });

  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  const count = (query.data ?? []).filter(
    (a) =>
      (a.severity === "high" || a.severity === "critical") &&
      new Date(a.createdAt).getTime() >= cutoff &&
      new Date(a.createdAt).getTime() > seenAt
  ).length;

  return { count, environment };
}
