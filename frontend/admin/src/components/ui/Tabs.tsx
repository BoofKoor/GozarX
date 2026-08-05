import { clsx } from "clsx";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { NavLink } from "react-router-dom";

export interface TabItem {
  to: string;
  label: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  /** Small trailing count (unread messages, draft pages). Hidden when 0/undefined. */
  count?: number;
}

/** How far the fade runs in from an edge that still has tabs behind it. */
const FADE = "2.25rem";

/**
 * Track which physical edge of a scroller still hides content.
 *
 * Measured physically (left / right), not logically: RTL Chromium counts `scrollLeft` DOWN from 0
 * at the start, so a single "how far from the start" number means opposite things in the two
 * directions and one of them fades the wrong edge.
 */
function useEdgeFade<T extends HTMLElement>() {
  const el = useRef<T>(null);
  const [edges, setEdges] = useState({ left: false, right: false });

  const measure = useCallback(() => {
    const node = el.current;
    if (!node) return;
    const range = node.scrollWidth - node.clientWidth;
    const rtl = getComputedStyle(node).direction === "rtl";
    const min = rtl ? -range : 0;
    const max = rtl ? 0 : range;
    setEdges({ left: node.scrollLeft - min > 1, right: max - node.scrollLeft > 1 });
  }, []);

  useEffect(() => {
    const node = el.current;
    if (!node) return;
    measure();
    node.addEventListener("scroll", measure, { passive: true });
    // Fonts land late and windows resize; both change what fits, and a fade that was right at
    // mount would otherwise stay wrong for the rest of the session.
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    for (const child of Array.from(node.children)) ro.observe(child);
    return () => {
      node.removeEventListener("scroll", measure);
      ro.disconnect();
    };
  }, [measure]);

  // A MASK fades the content itself, so the strip never has to know what colour it is sitting on —
  // it appears on the content well on one page and inside a card on another. It also says the one
  // true thing: this continues beyond the frame. On a phone 345px of the dashboard's tab strip and
  // 588px of the website's were simply gone, and `scrollbar-thin` is invisible under the overlay
  // scrollbars every touch device uses.
  return { ref: el, style: edges.left || edges.right ? maskFor(edges) : undefined };
}

function maskFor({ left, right }: { left: boolean; right: boolean }) {
  const from = left ? `transparent 0, black ${FADE}` : "black 0";
  const to = right ? `black calc(100% - ${FADE}), transparent 100%` : "black 100%";
  const gradient = `linear-gradient(to right, ${from}, ${to})`;
  return { maskImage: gradient, WebkitMaskImage: gradient };
}

/** Id for one tab, so a panel can name the tab that opened it and vice versa. */
export function tabId(base: string, value: string): string {
  return `${base}-${value}`;
}

/** The scrolling strip. `border-b` sits on the WRAPPER so the mask never eats the rule. */
const STRIP = "scrollbar-thin -mb-px flex gap-1 overflow-x-auto overflow-y-hidden";
const TAB =
  "flex shrink-0 items-center gap-2 border-b-2 px-3 py-2 text-[0.8rem] font-medium transition";
// `text-brand-700` — the ramp's designated "ink" shade — rather than `text-brand`, which is the
// FILL shade and measured 3.63:1 as text on the console's own ground. The 2px rule keeps the fill.
const TAB_ON = "border-brand text-brand-700";
const TAB_OFF = "border-transparent text-content-muted hover:border-line-strong hover:text-content";

/**
 * Route-driven tab bar (underline style) for a section's sub-navigation.
 *
 * `overflow-y-hidden` is not redundant beside `overflow-x-auto`: when one axis is not `visible` the
 * other computes from `visible` to `auto`, so a strip that overflows its content box by a single
 * pixel — which this one does, by exactly the 1px the underline overlap costs — becomes a VERTICAL
 * scroll container. Under overlay scrollbars that is invisible; on Windows it draws a stubby
 * scrollbar with arrows beside the tabs. Naming the axis is the whole fix.
 */
export function NavTabs({ items, className }: { items: TabItem[]; className?: string }) {
  const { ref, style } = useEdgeFade<HTMLDivElement>();
  return (
    <div className={clsx("relative border-b border-line", className)}>
      <div ref={ref} className={STRIP} style={style}>
        {items.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end
            className={({ isActive }) => clsx(TAB, isActive ? TAB_ON : TAB_OFF)}
          >
            {t.icon && <t.icon className="h-4 w-4" />}
            {t.label}
            {typeof t.count === "number" && t.count > 0 && (
              <span className="rounded-full bg-brand/15 px-1.5 py-0.5 text-[10px] font-bold tabular-nums text-brand-700">
                {t.count}
              </span>
            )}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

/**
 * Local (non-routed) tab bar for switching panels inside one page. Same axis note as `NavTabs`.
 *
 * `role="tablist"` promises a keyboard contract, and this one used to keep only the half a screen
 * reader can see: the roles and `aria-selected` were right, but the arrow keys did nothing, every
 * tab sat in the tab order (the seventh took seven presses to reach) and no panel was associated
 * with any tab. Roving tabindex + arrows + `aria-controls` are what the role actually means.
 */
export function Tabs<T extends string>({
  value,
  onChange,
  items,
  className,
  panelId,
  idBase = "tab",
}: {
  value: T;
  onChange: (next: T) => void;
  items: { value: T; label: ReactNode; icon?: ComponentType<{ className?: string }> }[];
  className?: string;
  /** The panel these tabs drive, so each tab can point at it with `aria-controls`. */
  panelId?: string;
  /** Prefix for the generated tab ids — only needs changing if one page has two tablists. */
  idBase?: string;
}) {
  const { ref, style } = useEdgeFade<HTMLDivElement>();

  function select(index: number) {
    const item = items[index];
    if (!item) return;
    onChange(item.value);
    // Selecting re-renders the strip, so reach for the new tab by id afterwards rather than
    // holding a node that is about to be replaced.
    requestAnimationFrame(() => {
      const el = ref.current?.querySelector<HTMLElement>(`[data-tab="${item.value}"]`);
      el?.focus();
      // Optional call: jsdom has no layout and no `scrollIntoView`, and a keyboard handler is not
      // worth throwing over a tab that is already on screen.
      el?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    });
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((t) => t.value === value);
    if (index < 0) return;
    // In RTL the visually NEXT tab is to the left, so the arrows swap with the reading direction —
    // otherwise ArrowRight walks backwards through a Persian tab strip.
    const rtl = getComputedStyle(e.currentTarget).direction === "rtl";
    const forward = rtl ? "ArrowLeft" : "ArrowRight";
    const back = rtl ? "ArrowRight" : "ArrowLeft";
    if (e.key === forward) select((index + 1) % items.length);
    else if (e.key === back) select((index - 1 + items.length) % items.length);
    else if (e.key === "Home") select(0);
    else if (e.key === "End") select(items.length - 1);
    else return;
    e.preventDefault();
  }

  return (
    <div className={clsx("relative border-b border-line", className)}>
      <div ref={ref} role="tablist" className={STRIP} style={style} onKeyDown={onKeyDown}>
        {items.map((t) => {
          const active = t.value === value;
          return (
            <button
              key={t.value}
              id={tabId(idBase, t.value)}
              data-tab={t.value}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={panelId}
              // Roving tabindex: one stop for the whole strip, arrows move inside it.
              tabIndex={active ? 0 : -1}
              onClick={() => onChange(t.value)}
              className={clsx(TAB, active ? TAB_ON : TAB_OFF)}
            >
              {t.icon && <t.icon className="h-4 w-4" />}
              {t.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
