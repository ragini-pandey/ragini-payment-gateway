import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/auth/AuthProvider";
import { supabase } from "@/lib/supabase";

/**
 * Opens a single Supabase Realtime channel for the authenticated user and
 * invalidates the "securityAlerts" React Query cache whenever a new row is
 * inserted into security_alerts.
 *
 * Mount this once in AppShell — do NOT call it in individual pages.
 * Realtime is enabled on security_alerts via migration 0003_realtime_security_alerts.
 */
export function useSecurityAlertStream() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!user?.id) return;

    const channel = supabase
      .channel(`security_alerts:${user.id}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "security_alerts",
          filter: `user_id=eq.${user.id}`,
        },
        (payload) => {
          // Invalidate only the environment that received the new alert
          const env = (payload.new as { environment?: string }).environment;
          queryClient.invalidateQueries({
            queryKey: ["securityAlerts", ...(env ? [env] : [])],
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [user?.id, queryClient]);
}
