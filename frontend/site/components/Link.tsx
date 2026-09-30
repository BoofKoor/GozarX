"use client";

import NextLink from "next/link";
import type { ComponentProps, MouseEvent } from "react";

type Props = ComponentProps<typeof NextLink>;

// Every internal link on the site, WITHOUT Next's automatic prefetch. The pages are static now
// (C-61), and for a static route Next prefetches the WHOLE route — its server payload, the shared
// layout's (which carries the page's copy) and the route's JavaScript — for every link that comes
// within 200px of the viewport, the closed phone menu's included. Measured on the homepage's first
// visit: 12 requests and ~36 KB gzip for pages nobody had asked for, on the mobile data this site's
// visitors pay for. A click costs one fetch of an already-rendered page instead.
//
// And a link to an anchor on the page it is already on scrolls there itself. Next 16.3's router
// scrolls after a navigation only into the segments that navigation created, or on a hash-only
// change — and a query-only change to a static page creates none, the page not being rendered per
// query. So the homepage's flags (`/?loc=<name>#hero-widget`) picked the location in a widget left
// 1,100px up the page, and the phone menu's «دریافت کانفیگ» did nothing from `/?loc=…`. Scrolling
// on the click works whatever the router decides; where Next scrolls as well, it is to the same place.
export default function Link({ onClick, ...props }: Props) {
  return (
    <NextLink
      prefetch={false}
      {...props}
      onClick={(e) => {
        onClick?.(e);
        if (!e.defaultPrevented) scrollToAnchorHere(e, props.href);
      }}
    />
  );
}

function scrollToAnchorHere(e: MouseEvent<HTMLAnchorElement>, href: Props["href"]) {
  // A click the browser takes elsewhere (a new tab or window) leaves this page where it is.
  if (typeof href !== "string" || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const target = e.currentTarget.getAttribute("target");
  if (target && target !== "_self") return;
  const url = new URL(href, window.location.href);
  if (url.origin !== window.location.origin || url.pathname !== window.location.pathname || !url.hash) return;
  document.getElementById(decodeURIComponent(url.hash.slice(1)))?.scrollIntoView();
}
