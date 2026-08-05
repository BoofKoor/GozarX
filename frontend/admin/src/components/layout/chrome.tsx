import { clsx } from "clsx";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
  type RefCallback,
} from "react";
import { createPortal } from "react-dom";

/**
 * Two slots the SHELL owns and PAGES fill.
 *
 * The design puts the page's name in the top bar and the dashboard's live figures in a panel beside
 * the console, not inside it. Both belong to the shell's layout and to a page's content at the same
 * time, which is what a slot is for. Portals rather than "lift the JSX into context": the children
 * stay where they were written, so their hooks, queries and context all resolve in the page's tree
 * and only the DOM node moves.
 */

interface Chrome {
  titleHost: HTMLElement | null;
  sideHost: HTMLElement | null;
  /** Whether a page has claimed the side slot — an unclaimed panel must not take up space. */
  sideFilled: boolean;
  setTitleHost: RefCallback<HTMLElement>;
  setSideHost: RefCallback<HTMLElement>;
  claimSide: (claimed: boolean) => void;
}

const ChromeContext = createContext<Chrome | null>(null);

export function ChromeProvider({ children }: { children: ReactNode }) {
  const [titleHost, setTitleHost] = useState<HTMLElement | null>(null);
  const [sideHost, setSideHost] = useState<HTMLElement | null>(null);
  // A counter, not a flag: React mounts the next route's tree before unmounting the previous one in
  // some transitions, and a flag would be switched off by the outgoing page after the incoming one
  // already turned it on.
  const [claims, setClaims] = useState(0);
  const claimSide = useCallback((claimed: boolean) => {
    setClaims((n) => Math.max(0, n + (claimed ? 1 : -1)));
  }, []);
  return (
    <ChromeContext.Provider
      value={{
        titleHost,
        sideHost,
        sideFilled: claims > 0,
        setTitleHost,
        setSideHost,
        claimSide,
      }}
    >
      {children}
    </ChromeContext.Provider>
  );
}

/** Null outside the shell — the login screen and the setup wizard render without one. */
export function useChrome(): Chrome | null {
  return useContext(ChromeContext);
}

/**
 * True at the width where the console can carry a panel beside it. Matches Tailwind's `xl`, because
 * the host `<aside>` is `hidden xl:flex` — if the two disagreed the panel would either take space
 * while empty or have nowhere to render.
 */
const WIDE = "(min-width: 1280px)";

/**
 * The side panel's geometry, defined ONCE because it is placed twice — as the shell's `<aside>` at
 * desktop widths and as a block in the page below that. Drifting apart is how the inline copy lost
 * its rhythm entirely and let a near-square chart stretch to the width of the console.
 *
 * `[&>*]:shrink-0` is the load-bearing part. A scrollable flex COLUMN whose children may shrink does
 * not overflow — it squeezes, and `overflow-y: auto` then has nothing to scroll. Text-bearing
 * children resist (their content is their floor), but an SVG has no such floor, so the whole
 * shortfall lands on the one child that cannot object: measured on a 650px-tall window, the radar
 * rendered 280×35 against a natural 209 and the panel reported scrollHeight === clientHeight.
 */
export const SIDE_STACK = "flex flex-col gap-[0.7rem] [&>*]:shrink-0";
export const SIDE_WIDTH = "w-[19.5rem]";

export function useIsWide(): boolean {
  const [wide, setWide] = useState(
    () => typeof window !== "undefined" && window.matchMedia?.(WIDE).matches === true,
  );
  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia(WIDE);
    const sync = () => setWide(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return wide;
}

/**
 * The dashboard's live-figures panel: a sibling of the console at desktop widths, and an ordinary
 * block at the end of the page below that.
 *
 * It does not simply stack when narrow. The shell is a fixed-height flex row; turning that row into
 * a column makes `flex: 1` a HEIGHT instruction, and two panels then share one viewport's worth of
 * scroll between them — the console ends up as tall as the sidebar it was supposed to dwarf. So the
 * host is hidden below `xl` and the same subtree renders inline instead, where the page scrolls it.
 */
export function SidePanel({ children }: { children: ReactNode }) {
  const chrome = useChrome();
  const wide = useIsWide();
  const [inlineHost, setInlineHost] = useState<HTMLElement | null>(null);
  const host = wide ? (chrome?.sideHost ?? null) : inlineHost;

  // Tell the shell the slot is in use. Without this the panel stayed mounted and empty on every
  // other page — a 19.5rem blank card beside the users table, which is worse than not having one.
  const claimSide = chrome?.claimSide;
  useEffect(() => {
    if (!claimSide) return;
    claimSide(true);
    return () => claimSide(false);
  }, [claimSide]);

  return (
    <>
      {/* Below `xl` this is the panel's real home, so it carries the panel's own width and rhythm.
          Left to stretch it was neither: nine cards flush against each other and a 340×254 chart
          drawn 968 wide — and therefore 723 TALL, a single tile higher than the viewport. */}
      <div
        ref={setInlineHost}
        className={wide ? "hidden" : clsx("min-w-0 max-w-full", SIDE_WIDTH, SIDE_STACK)}
      />
      {host ? createPortal(children, host) : null}
    </>
  );
}
