/**
 * Environment selector — Stripe-style "Test mode" / "Live mode" toggle.
 * Persisted to localStorage so the dashboard remembers across reloads.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Environment = "test" | "live";

const STORAGE_KEY = "ragini.environment";

interface Ctx {
  environment: Environment;
  setEnvironment: (env: Environment) => void;
}

const EnvironmentContext = createContext<Ctx | undefined>(undefined);

function read(): Environment {
  if (typeof window === "undefined") return "test";
  const v = window.localStorage.getItem(STORAGE_KEY);
  return v === "live" ? "live" : "test";
}

export function EnvironmentProvider({ children }: { children: ReactNode }) {
  const [environment, setEnv] = useState<Environment>(() => read());

  const setEnvironment = useCallback((next: Environment) => {
    setEnv(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  // Sync across tabs.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === STORAGE_KEY) setEnv(read());
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const value = useMemo(() => ({ environment, setEnvironment }), [environment, setEnvironment]);
  return <EnvironmentContext.Provider value={value}>{children}</EnvironmentContext.Provider>;
}

export function useEnvironment(): Ctx {
  const ctx = useContext(EnvironmentContext);
  if (!ctx) throw new Error("useEnvironment must be used inside <EnvironmentProvider>");
  return ctx;
}
