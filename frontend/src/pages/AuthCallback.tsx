import { useEffect } from "react";
import { useNavigate } from "react-router";
import { supabase } from "@/lib/supabase";

export function AuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    // supabase-js with detectSessionInUrl=true picks up the OAuth code/hash
    // automatically. We just wait for it and then route home.
    let cancelled = false;
    async function go() {
      // Allow the SDK a tick to process the URL.
      await new Promise((r) => setTimeout(r, 200));
      const { data } = await supabase.auth.getSession();
      if (cancelled) return;
      if (data.session) {
        navigate("/", { replace: true });
      } else {
        navigate("/login", { replace: true });
      }
    }
    void go();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return (
    <div className="flex h-screen items-center justify-center bg-ivory">
      <p className="text-sm text-muted">Completing sign-in…</p>
    </div>
  );
}
