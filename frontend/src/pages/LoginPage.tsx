import { useState } from "react";
import { Navigate } from "react-router";
import { useAuth } from "@/auth/AuthProvider";

export function LoginPage() {
  const { session, signInWithGoogle, loading } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  if (!loading && session) {
    return <Navigate to="/" replace />;
  }

  async function handleSignIn() {
    setSubmitting(true);
    try {
      await signInWithGoogle();
    } finally {
      // signInWithOAuth navigates away; reset only if it returns.
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-ivory px-6">
      <div
        className="pointer-events-none absolute inset-0 saffron-glow"
        aria-hidden
      />
      <div className="relative w-full max-w-md card-surface px-8 py-10 text-center animate-fade-in">
        {/* <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-saffron-50 text-2xl font-serif text-saffron">
          ॐ
        </span> */}
        {/* <p className="eyebrow mt-6">DEVELOPER PLATFORM</p> */}
        <h1 className="mt-3 font-serif text-3xl leading-tight text-ink">
          Ragini Payment Gateway
        </h1>
        <p className="mt-3 text-sm text-muted">
          Sign in to manage API keys and webhooks.
        </p>

        <button
          type="button"
          onClick={handleSignIn}
          disabled={submitting}
          className="btn-primary mt-8 w-full"
        >
          <GoogleMark />
          <span>{submitting ? "Redirecting…" : "Continue with Google"}</span>
        </button>

      </div>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden>
      <path
        fill="#FFFFFF"
        d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.616z"
      />
      <path
        fill="#FFFFFF"
        opacity="0.9"
        d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.583-5.036-3.71H.957v2.332A8.997 8.997 0 0 0 9 18z"
      />
      <path
        fill="#FFFFFF"
        opacity="0.7"
        d="M3.964 10.708A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.708V4.96H.957A8.997 8.997 0 0 0 0 9c0 1.452.348 2.827.957 4.04l3.007-2.332z"
      />
      <path
        fill="#FFFFFF"
        opacity="0.5"
        d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.96l3.007 2.332C4.672 5.163 6.656 3.58 9 3.58z"
      />
    </svg>
  );
}
