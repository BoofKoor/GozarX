"use client";

import Link from "@/components/Link";
import { useCallback, useMemo, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { FAQ_CATS, FAQ_LABELS, type FaqItem } from "@/lib/content";
import { Icon } from "@/components/Icon";
import { AccItem } from "@/components/Accordion";
import { QueryParam } from "@/components/QueryParam";

// FAQ list — faithful reproduction of the design's `vFaq`: a search box + category tabs filtering a
// list of `.acc` accordions, with an empty state when nothing matches.
export function FaqList({ locale, items }: { locale: Locale; items: FaqItem[] }) {
  const labels = FAQ_LABELS[locale];
  const cats = FAQ_CATS[locale];
  const [cat, setCat] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<number | null>(0);
  // `?q=` — the 404 page's search box lands here with the words already typed. A search that
  // arrived from elsewhere opens nothing yet: the reader picks from what matched.
  const arrive = useCallback((q: string | undefined) => {
    if (!q) return;
    setQuery(q.slice(0, 80));
    setOpen(null);
  }, []);

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
      <QueryParam name="q" onValue={arrive} />
      <div className="faq-tools">
        <div className="idx-search">
          <Icon name="search" sw={2} />
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
        // nothing matched: the question is still worth asking, so say where (C-36)
        <div className="empty faq-empty">
          <p>{labels.empty}</p>
          <Link className="btn" href="/contact">
            <Icon name="mail" sw={2} />
            {labels.ask}
          </Link>
        </div>
      ) : (
        <div>
          {visible.map(({ it, i }) => (
            <AccItem
              key={i}
              question={it.q}
              open={open === i}
              onToggle={() => setOpen(open === i ? null : i)}
              onReveal={() => setOpen(i)}
              level={2}
            >
              {it.a}
            </AccItem>
          ))}
        </div>
      )}
    </>
  );
}
