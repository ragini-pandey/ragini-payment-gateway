import { Link } from "react-router";
import { ArrowRight, KeyRound, ShieldAlert, Webhook } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/auth/AuthProvider";
import { useUnreadAlerts } from "@/features/security/useUnreadAlerts";

export function HomePage() {
  const { user } = useAuth();
  const { count: alertCount } = useUnreadAlerts();
  const greetingName =
    user?.user_metadata?.full_name ||
    user?.email?.split("@")[0] ||
    "builder";

  return (
    <AppShell>
      <section className="relative flex min-h-[calc(100vh-180px)] items-center justify-center px-6 py-16">
        <div className="pointer-events-none absolute inset-0 saffron-glow" aria-hidden />
        <div className="relative w-full max-w-5xl text-center animate-fade-in">
          <p className="mx-auto mt-5 max-w-xl text-base text-muted">
            Welcome back, <span className="text-ink">{greetingName}</span>. Manage
            your API keys, webhooks, and security signals.
          </p>

          <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-3">
            <FeatureCard
              to="/api-keys"
              icon={<KeyRound className="h-6 w-6" />}
              title="API Keys"
              description="Create, manage and revoke programmatic access for your integrations."
            />
            <FeatureCard
              to="/webhooks"
              icon={<Webhook className="h-6 w-6" />}
              title="Webhooks"
              description="Subscribe to events, inspect deliveries, and replay failed attempts."
            />
            <FeatureCard
              to="/security"
              icon={<ShieldAlert className="h-6 w-6" />}
              title="Security"
              description="Review suspicious key usage, revoked-key access, and traffic spikes."
              badge={alertCount}
            />
          </div>
        </div>
      </section>
    </AppShell>
  );
}

interface FeatureCardProps {
  to: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  badge?: number;
}

function FeatureCard({ to, icon, title, description, badge }: FeatureCardProps) {
  return (
    <Link
      to={to}
      className="group card-surface p-8 text-left transition-all hover:-translate-y-0.5 hover:shadow-lift focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-saffron focus-visible:ring-offset-2 focus-visible:ring-offset-ivory"
    >
      <span className="relative inline-flex">
        <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-saffron-50 text-saffron">
          {icon}
        </span>
        {badge != null && badge > 0 && (
          <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white">
            {badge > 99 ? "99+" : badge}
          </span>
        )}
      </span>
      <h2 className="mt-6 font-serif text-2xl text-ink">{title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
      <span className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-saffron group-hover:gap-2 transition-all">
        Open <ArrowRight className="h-4 w-4" />
      </span>
    </Link>
  );
}
