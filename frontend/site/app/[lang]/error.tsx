"use client";

import Link from "@/components/Link";
import { useRouter } from "next/navigation";
import { startTransition } from "react";
import { useT } from "@/lib/useT";
import { useSite } from "@/lib/useSite";
import { Icon } from "@/components/Icon";

// The page-level error boundary (C-35). There was none, so a render error showed Next's bare
// default. A calm sentence that puts the fault where it is, a retry that re-runs the server render
// as well as the client one (`refresh` + `reset` — `reset` alone repeats the same failed payload),
// and the way home. It sits inside the root layout, so the header, the footer and the locale stay.
export default function PageError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { locale } = useSite();
  const t = useT();
  const router = useRouter();
  return (
    <section className="sec nf">
      <div className="container nf-inner">
        <span className="nf-ic" aria-hidden>
          <Icon name="plug" sw={2} />
        </span>
        <h1>{t("err.title")}</h1>
        <p className="nf-sub">{t("err.sub")}</p>
        <div className="nf-actions">
          <button
            type="button"
            className="btn"
            onClick={() =>
              startTransition(() => {
                router.refresh();
                reset();
              })
            }
          >
            {t("offline.retry")}
          </button>
          <Link href="/" className="btn secondary">
            {t("notfound.home")}
          </Link>
        </div>
      </div>
    </section>
  );
}
