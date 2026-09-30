"use client";

import { type ComponentProps, useState } from "react";
import { ClaimWidget } from "@/components/ClaimWidget";
import { QueryParam } from "@/components/QueryParam";

// The homepage's claim widget, pre-set from `?loc=<remark>` — a location picked on /locations or in
// the flag strip (C-27). Tapping another flag on the same page changes the query without remounting
// anything, and the widget applies each NEW value once (see `preselect` in ClaimWidget).
export function HomeWidget(props: Omit<ComponentProps<typeof ClaimWidget>, "preselect">) {
  const [loc, setLoc] = useState<string>();
  return (
    <>
      <QueryParam name="loc" onValue={setLoc} />
      <ClaimWidget {...props} preselect={loc} />
    </>
  );
}
