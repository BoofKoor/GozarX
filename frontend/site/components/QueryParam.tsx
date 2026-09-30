"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";

// One query-string value, handed to the page after hydration. The pages are prerendered (C-61): the
// HTML is the same whatever the query says, so a value carried in it — `?loc=` from a flag on
// /locations, `?q=` from the 404's search box — can only be read in the browser; reading it on the
// server is what made the page dynamic. `useSearchParams` makes everything up to the nearest Suspense
// boundary client-only, so the reader sits alone inside its own boundary and renders nothing.
function Reader({ name, onValue }: { name: string; onValue: (value: string | undefined) => void }) {
  const value = useSearchParams().get(name)?.trim() || undefined;
  useEffect(() => {
    onValue(value);
  }, [value, onValue]);
  return null;
}

export function QueryParam(props: { name: string; onValue: (value: string | undefined) => void }) {
  return (
    <Suspense fallback={null}>
      <Reader {...props} />
    </Suspense>
  );
}
