import { useEnvironment, type Environment } from "@/lib/env";
import { cn } from "@/lib/utils";

const OPTIONS: { value: Environment; label: string }[] = [
  { value: "test", label: "Test" },
  { value: "live", label: "Live" },
];

export function EnvSwitcher() {
  const { environment, setEnvironment } = useEnvironment();
  return (
    <div
      role="tablist"
      aria-label="Environment"
      className="inline-flex items-center rounded-full border border-parchment bg-white p-0.5 text-xs font-medium"
    >
      {OPTIONS.map((opt) => {
        const active = environment === opt.value;
        const isLive = opt.value === "live";
        return (
          <button
            key={opt.value}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => setEnvironment(opt.value)}
            className={cn(
              "rounded-full px-3 py-1.5 transition-colors cursor-pointer",
              active
                ? isLive
                  ? "bg-rose-600 text-ivory"
                  : "bg-ink text-ivory"
                : "text-muted hover:text-ink"
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
