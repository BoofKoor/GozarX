import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";

import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ConfirmProvider } from "./components/ui/confirm";
import { I18nProvider, useI18n } from "./i18n";
import "./index.css";

/** Toasts have to follow the language too — sonner takes `dir` as a prop, not from the document. */
function ToastHost() {
  const { dir } = useI18n();
  return <Toaster position="top-center" richColors dir={dir} />;
}

// A tab left open across a deploy still holds the OLD index, whose route chunks no longer exist on
// the server: the next navigation to a page it has not loaded yet fails to import and lands on the
// crash screen. Vite reports exactly that as `vite:preloadError`; reload once to pick up the new
// build. The timestamp guard keeps a genuinely missing chunk from looping the reload.
window.addEventListener("vite:preloadError", (event) => {
  const KEY = "gozarx_chunk_reload_at";
  let last = 0;
  try {
    last = Number(sessionStorage.getItem(KEY) ?? 0);
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    // storage blocked: fall through to one reload attempt
  }
  if (Date.now() - last > 60_000) {
    event.preventDefault();
    window.location.reload();
  }
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <I18nProvider>
          <BrowserRouter basename="/admin">
            <ConfirmProvider>
              <App />
            </ConfirmProvider>
            <ToastHost />
          </BrowserRouter>
        </I18nProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
