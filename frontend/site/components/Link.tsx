import NextLink from "next/link";
import type { ComponentProps } from "react";

// Every internal link on the site, WITHOUT Next's automatic prefetch. The pages are static now
// (C-61), and for a static route Next prefetches the WHOLE route — its server payload, the shared
// layout's (which carries the page's copy) and the route's JavaScript — for every link that comes
// within 200px of the viewport, the closed phone menu's included. Measured on the homepage's first
// visit: 12 requests and ~36 KB gzip for pages nobody had asked for, on the mobile data this site's
// visitors pay for. A click costs one fetch of an already-rendered page instead.
export default function Link(props: ComponentProps<typeof NextLink>) {
  return <NextLink prefetch={false} {...props} />;
}
