import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  // Surface this loudly during dev — without these, nothing else can work.
  // eslint-disable-next-line no-console
  console.error(
    "Missing Supabase env vars. Copy frontend/.env.example to frontend/.env and fill in VITE_SUPABASE_URL & VITE_SUPABASE_ANON_KEY."
  );
}

export const supabase = createClient(url ?? "", anonKey ?? "", {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
