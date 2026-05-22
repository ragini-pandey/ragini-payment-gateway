import { Component, type ErrorInfo, type ReactNode } from "react";
import { Link } from "react-router";
import { AlertTriangle, RefreshCcw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches render-time errors anywhere in the component tree below it and
 * shows a palette-styled fallback instead of a blank white screen. Async
 * errors (fetch, promises) are NOT caught here — those surface via toasts.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-screen bg-cream flex items-center justify-center px-6 py-16">
        <div className="card-surface max-w-lg w-full p-8 text-center">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-saffron-50 text-saffron">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <h1 className="mt-5 font-serif text-2xl text-ink">
            Something went wrong
          </h1>
          <p className="mt-2 text-sm text-muted">
            An unexpected error happened while rendering this page. The team
            has logged it. You can try reloading, or go back to the home page.
          </p>
          <pre className="mt-5 max-h-40 overflow-auto rounded-xl border border-parchment bg-cream/60 p-3 text-left text-xs text-ink whitespace-pre-wrap">
            {this.state.error.message}
          </pre>
          <div className="mt-6 flex justify-center gap-2">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                this.reset();
                window.location.reload();
              }}
            >
              <RefreshCcw className="h-4 w-4" />
              Reload
            </button>
            <Link to="/" className="btn-primary" onClick={this.reset}>
              Back to home
            </Link>
          </div>
        </div>
      </div>
    );
  }
}
