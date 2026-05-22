import { type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { EnvSwitcher } from "@/components/EnvSwitcher";
import { LogOut } from "lucide-react";

export function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  const initials = (user?.email ?? "?").slice(0, 1).toUpperCase();

  return (
    <div className="flex min-h-screen flex-col bg-ivory">
      <header className="border-b border-parchment/70 bg-ivory/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5">
          <Link to="/" className="flex items-center gap-3 group">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-saffron-50 text-saffron text-lg font-serif">
              ॐ
            </span>
            <span className="font-serif text-xl text-ink group-hover:text-saffron transition-colors">
              Ragini Payment Gateway
            </span>
          </Link>
          <div className="flex items-center gap-3">
            <EnvSwitcher />
            {user?.email && (
              <span className="hidden sm:block text-sm text-muted">
                {user.email}
              </span>
            )}
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-cream text-ink text-sm font-medium border border-parchment">
              {initials}
            </span>
            <button
              type="button"
              onClick={handleSignOut}
              className="btn-ghost"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-parchment/60 py-6 text-center text-xs text-muted">
        <div className="mx-auto flex items-center gap-3 max-w-sm mb-2">
          <div className="h-px flex-1 bg-parchment" />
          <span className="uppercase tracking-[0.2em]">🪔</span>
          <div className="h-px flex-1 bg-parchment" />
        </div>
      </footer>
    </div>
  );
}
