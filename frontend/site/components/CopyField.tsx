"use client";

import { useState } from "react";
import { copyText } from "@/lib/clipboard";

// Small LTR copy-field used in the guide "copy the config" step (shows a sample link + copy button).
export function CopyField({ value, copyLabel, copiedLabel }: { value: string; copyLabel: string; copiedLabel: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (await copyText(value)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    }
  }

  return (
    <div className="row mt-2" style={{ gap: 8, alignItems: "stretch" }}>
      <code className="codebox" style={{ flex: 1 }}>
        {value}
      </code>
      <button className="btn btn-ghost" onClick={copy} aria-live="polite" style={{ flex: "0 0 auto" }}>
        {copied ? copiedLabel : copyLabel}
      </button>
    </div>
  );
}
