"use client";

import { useState } from "react";
import { flagCC, locName } from "@/components/widget/flags";

// A location's round flag (public/flags/{cc}.svg), or its initials where there is no file. Its own
// module: the picker needs it on the first screen, and in `pieces` it pulled every post-claim part
// (the copy field, the meters, the countdown) into the first visit's JavaScript with it.
// `fluid` leaves the size to the stylesheet (`.flag` is 40px), for a place that resizes it by
// breakpoint — an inline size would outrank any media query. `eager` is for a flag on the first
// screen — the picker's visible rows, the delivered config's location (C-63): `loading="lazy"`
// there made the browser wait for layout before it even asked for the image. Lazy stays the
// default, for the long lists below the fold.
export function Flag({
  name,
  size = 40,
  fluid = false,
  eager = false,
}: {
  name: string;
  size?: number;
  fluid?: boolean;
  eager?: boolean;
}) {
  const cc = flagCC(name);
  const [errored, setErrored] = useState(false);
  const style = fluid ? undefined : ({ inlineSize: size, blockSize: size } as const);
  if (cc && !errored) {
    return (
      <img
        className="flag"
        src={`/flags/${cc}.svg`}
        alt=""
        style={style}
        loading={eager ? undefined : "lazy"}
        onError={() => setErrored(true)}
      />
    );
  }
  return (
    <span className="flag flag-fallback" style={style} aria-hidden>
      {locName(name).slice(0, 2).toUpperCase()}
    </span>
  );
}
