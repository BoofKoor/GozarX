"use client";

import { useMemo, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { FAQ_CATS, FAQ_ITEMS, FAQ_LABELS } from "@/lib/content";

export function FaqList({ locale }: { locale: Locale }) {
  const labels = FAQ_LABELS[locale];
  const cats = FAQ_CATS[locale];
  const items = FAQ_ITEMS[locale];
  const [cat, setCat] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<number | null>(null);

  const q = query.trim().toLowerCase();
  const visible = useMemo(
    () =>
      items
        .map((it, i) => ({ it, i }))
        .filter(({ it }) => (cat === "all" ? true : it.cat === cat))
        .filter(({ it }) => (q === "" ? true : it.q.toLowerCase().includes(q) || it.a.toLowerCase().includes(q))),
    [items, cat, q],
  );

  return (
    <div className="mt-6">
      <input
        className="input"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={labels.search}
        aria-label={labels.search}
      />

      <div className="seg mt-4" role="group" aria-label={labels.categories} style={{ flexWrap: "wrap" }}>
        <button aria-pressed={cat === "all"} onClick={() => setCat("all")}>
          {labels.all}
        </button>
        {cats.map((c) => (
          <button key={c.id} aria-pressed={cat === c.id} onClick={() => setCat(c.id)}>
            {c.label}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="muted mt-6">{labels.empty}</p>
      ) : (
        <div className="stack mt-4">
          {visible.map(({ it, i }) => (
            <div key={i} className="card card-pad">
              <button
                className="between"
                style={{ width: "100%", textAlign: "start", color: "var(--text)", fontWeight: 700 }}
                aria-expanded={open === i}
                aria-controls={`faq-panel-${i}`}
                onClick={() => setOpen(open === i ? null : i)}
              >
                <span>{it.q}</span>
                <span aria-hidden style={{ color: "var(--faint)", flex: "0 0 auto" }}>
                  {open === i ? "−" : "+"}
                </span>
              </button>
              {open === i && (
                <p id={`faq-panel-${i}`} role="region" className="mt-2">
                  {it.a}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
