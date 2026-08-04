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
