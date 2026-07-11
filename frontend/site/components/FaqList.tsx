"use client";

import { useMemo, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { FAQ_CATS, FAQ_ITEMS, FAQ_LABELS } from "@/lib/content";
import { Icon } from "@/components/Icon";

// FAQ list — faithful reproduction of the design's `vFaq`: a search box + category tabs filtering a
// list of `.acc` accordions, with an empty state when nothing matches.
export function FaqList({ locale }: { locale: Locale }) {
  const labels = FAQ_LABELS[locale];
  const cats = FAQ_CATS[locale];
  const items = FAQ_ITEMS[locale];
  const [cat, setCat] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<number | null>(0);

  const q = query.trim().toLowerCase();
  const visible = useMemo(
    () =>
      items
        .map((it, i) => ({ it, i }))
        .filter(({ it }) => (cat === "all" ? true : it.cat === cat))
        .filter(({ it }) =>
          q === "" ? true : it.q.toLowerCase().includes(q) || it.a.toLowerCase().includes(q),
        ),
    [items, cat, q],
  );

  return (
    <>
      <div className="faq-tools">
        <div className="idx-search">
          <Icon name="help" sw={2} />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={labels.search}
            aria-label={labels.search}
          />
        </div>
      </div>

      <div className="tabs" role="group" aria-label={labels.categories}>
        <button className="tab" aria-pressed={cat === "all"} onClick={() => setCat("all")}>
          {labels.all}
        </button>
        {cats.map((c) => (
          <button
            key={c.id}
            className="tab"
            aria-pressed={cat === c.id}
            onClick={() => setCat(c.id)}
          >
            {c.label}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <div className="empty">{labels.empty}</div>
      ) : (
        <div>
          {visible.map(({ it, i }) => (
            <div className="acc" key={i} data-open={open === i ? "true" : "false"}>
              <button
                className="acc-head"
                aria-expanded={open === i}
                onClick={() => setOpen(open === i ? null : i)}
              >
                <span>{it.q}</span>
                <Icon name="chev" sw={2} />
              </button>
              <div className="acc-body">{it.a}</div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
