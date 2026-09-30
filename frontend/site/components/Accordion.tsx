"use client";

import { type ReactNode, useEffect, useId, useRef } from "react";
import { Icon } from "@/components/Icon";

// One question of an FAQ accordion — the homepage teaser and /faq share it (C-43). The WAI-ARIA
// accordion shape: the toggle is a button inside a heading (so a screen reader's heading list
// reaches every question), it names the answer it controls, and the answer is labelled by it.
//
// A closed answer is `hidden="until-found"`: the browser's find-in-page searches it and fires
// `beforematch`, which opens it — before, every closed answer was `display:none`, so Ctrl-F on the
// FAQ found nothing but the questions. React writes `hidden` as a plain boolean (19.2 renders
// "until-found" as `hidden=""`), so the value is set after hydration; a browser without
// until-found treats it as ordinary `hidden`, which is what it had before.
export function AccItem({
  question,
  children,
  open,
  onToggle,
  onReveal,
  level = 3,
}: {
  question: ReactNode;
  children: ReactNode;
  open: boolean;
  onToggle: () => void;
  /** open this item — find-in-page matched text inside it */
  onReveal: () => void;
  level?: 2 | 3 | 4;
}) {
  const id = useId();
  const bodyRef = useRef<HTMLDivElement>(null);
  const revealRef = useRef(onReveal);
  revealRef.current = onReveal;

  useEffect(() => {
    const el = bodyRef.current;
    if (!el || open) return;
    el.setAttribute("hidden", "until-found");
    const reveal = () => revealRef.current();
    el.addEventListener("beforematch", reveal);
    return () => el.removeEventListener("beforematch", reveal);
  }, [open]);

  const Heading = `h${level}` as "h3";
  return (
    <div className="acc" data-open={open ? "true" : "false"}>
      <Heading className="acc-hd">
        <button
          type="button"
          id={`${id}-q`}
          className="acc-head"
          aria-expanded={open}
          aria-controls={`${id}-a`}
          onClick={onToggle}
        >
          <span>{question}</span>
          <Icon name="chev" sw={2} />
        </button>
      </Heading>
      <div id={`${id}-a`} className="acc-body" aria-labelledby={`${id}-q`} hidden={!open} ref={bodyRef}>
        {children}
      </div>
    </div>
  );
}
