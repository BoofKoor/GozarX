import { createContext, type ReactNode, useCallback, useContext, useRef, useState } from "react";

import { useI18n } from "@/i18n";

import { Button } from "./Button";
import { Modal } from "./Modal";

interface ConfirmOptions {
  title?: string;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "brand";
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

/**
 * Promise-based confirm dialog built on the accessible Modal — a styled, RTL replacement for the
 * native window.confirm (which is LTR, unstyled, and breaks the premium feel). `await confirm({...})`
 * resolves true on confirm, false on cancel / backdrop / Esc.
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((v: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((o) => {
    setOpts(o);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const settle = useCallback((result: boolean) => {
    resolver.current?.(result);
    resolver.current = null;
    setOpts(null);
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {opts && (
        <Modal onClose={() => settle(false)} className="max-w-sm p-5" labelledBy="confirm-title">
          <h2 id="confirm-title" className="text-lg font-bold">
            {opts.title ?? t("ui.confirm")}
          </h2>
          <div className="mt-2 text-sm text-content-muted">{opts.message}</div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => settle(false)}>
              {opts.cancelLabel ?? t("ui.cancel")}
            </Button>
            <Button
              variant={opts.tone === "danger" ? "danger" : "primary"}
              onClick={() => settle(true)}
            >
              {opts.confirmLabel ?? t("ui.confirm")}
            </Button>
          </div>
        </Modal>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within a ConfirmProvider");
  return ctx;
}

/**
 * `guard(dirty, then)` runs `then` — closing an editor, switching to another record — at once when
 * nothing is unsaved, and only after the operator agrees to lose the edits when something is.
 *
 * Every editor used to discard silently: Esc or a click outside the FAQ and button editors, and a
 * click on another key in Texts, threw away whatever had been typed, with no way back.
 */
export function useDiscardGuard(): (dirty: boolean, then: () => void) => Promise<void> {
  const confirm = useConfirm();
  const { t } = useI18n();
  return useCallback(
    async (dirty: boolean, then: () => void) => {
      if (
        dirty &&
        !(await confirm({
          title: t("ui.discard.title"),
          message: t("ui.discard.message"),
          confirmLabel: t("ui.discard.confirm"),
          cancelLabel: t("ui.discard.keep"),
          tone: "danger",
        }))
      ) {
        return;
      }
      then();
    },
    [confirm, t],
  );
}
