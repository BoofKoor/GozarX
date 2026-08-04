import { Component, type ErrorInfo, type ReactNode } from "react";

import { t } from "@/i18n";

interface Props {
  children: ReactNode;
}
interface State {
  hasError: boolean;
}

/**
 * App-wide error boundary. Without it, a render-time throw anywhere (a chart, a panel) unmounts the
 * whole SPA to a blank white page. This shows a recoverable fallback instead.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surfaced to the console for debugging; never sent anywhere (no telemetry).
    console.error("Admin panel render error:", error, info);
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
        <div className="text-lg font-bold text-content">{t("ui.crashed")}</div>
        <p className="max-w-sm text-sm text-content-muted">{t("ui.crashed.msg")}</p>
        <button
          onClick={() => window.location.reload()}
          className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-brand-600"
        >
          {t("ui.reload")}
        </button>
      </div>
    );
  }
}
