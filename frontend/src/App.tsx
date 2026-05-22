import { BrowserRouter, Route, Routes } from "react-router";
import { AuthProvider } from "@/auth/AuthProvider";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { EnvironmentProvider } from "@/lib/env";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { LoginPage } from "@/pages/LoginPage";
import { AuthCallback } from "@/pages/AuthCallback";
import { HomePage } from "@/pages/HomePage";
import { ApiKeysPage } from "@/pages/ApiKeysPage";
import { WebhooksPage } from "@/pages/WebhooksPage";
import { SecurityAlertsPage } from "@/pages/SecurityAlertsPage";
import { Toaster } from "sonner";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <EnvironmentProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <ErrorBoundary>
                    <HomePage />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            />
            <Route
              path="/api-keys"
              element={
                <ProtectedRoute>
                  <ErrorBoundary>
                    <ApiKeysPage />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            />
            <Route
              path="/webhooks"
              element={
                <ProtectedRoute>
                  <ErrorBoundary>
                    <WebhooksPage />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            />
            <Route
              path="/security"
              element={
                <ProtectedRoute>
                  <ErrorBoundary>
                    <SecurityAlertsPage />
                  </ErrorBoundary>
                </ProtectedRoute>
              }
            />
          </Routes>
          <Toaster
            position="top-right"
            toastOptions={{
              classNames: {
                toast:
                  "!bg-white !text-ink !border !border-parchment !shadow-soft !rounded-2xl",
                title: "!font-medium",
                description: "!text-muted",
              },
            }}
          />
        </EnvironmentProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
