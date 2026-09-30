import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { LAST_CONFIG_KEY } from "@/lib/lastConfig";

// PWA offline fallback — not a real content page; keep it out of the index (also disallowed in robots).
export const metadata: Metadata = { robots: { index: false, follow: false } };

// It hands back the last config this browser was shown (lib/lastConfig), which is the one thing an
// offline visitor on a filtered network needs — it used to SAY «آخرین کانفیگ ذخیره‌شده‌ات این‌جاست»
// over nothing at all. Deliberately done by an INLINE script, not a client component: the service
// worker caches this page's HTML, not its JS chunks, so offline a component may never load. The
// script fills `#offline-slot`, which React renders as opaque HTML (dangerouslySetInnerHTML) so a
// hydration that does happen keeps what the script wrote instead of deleting it; and it wires the
// retry button, which is plain server HTML for the same reason. Text only ever goes in through
// textContent, and the link must look like a URL before it is shown.
const SCRIPT = `(function (S, KEY) {
  var retry = document.getElementById("offline-retry");
  if (retry) retry.addEventListener("click", function () { location.reload(); });
  var slot = document.getElementById("offline-slot");
  var c = null;
  try { c = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { c = null; }
  if (!slot || !c || typeof c.link !== "string" || !/^[a-z][a-z0-9+.-]*:\\/\\//i.test(c.link)) return;
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  var card = el("div", "card offline-cfg");
  var head = el("p", "oc-head", S.saved);
  if (typeof c.label === "string" && c.label) {
    head.appendChild(document.createTextNode(" · "));
    head.appendChild(el("b", "", c.label));
  }
  card.appendChild(head);
  // the widget's own copy-field markup (components/widget/pieces CopyField), so it looks the same
  var row = el("div", "copyfield");
  var shell = el("span", "code-shell");
  var code = el("code", "", c.link);
  code.setAttribute("dir", "ltr");
  shell.appendChild(code);
  var btn = el("button", "btn", S.copy);
  btn.type = "button";
  var live = el("span", "sr-only");
  live.setAttribute("role", "status");
  function select() {
    var r = document.createRange();
    r.selectNodeContents(code);
    var s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }
  btn.addEventListener("click", function () {
    function done() {
      btn.textContent = S.copied;
      live.textContent = S.copied;
      setTimeout(function () { btn.textContent = S.copy; live.textContent = ""; }, 1600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(c.link).then(done, select);
    else select();
  });
  row.appendChild(shell);
  row.appendChild(btn);
  card.appendChild(row);
  card.appendChild(live);
  var until = typeof c.expires_at === "string" ? Date.parse(c.expires_at) : NaN;
  if (!isNaN(until) && until > Date.now()) {
    var when = new Date(until).toLocaleString(S.locale, { dateStyle: "medium", timeStyle: "short" });
    card.appendChild(el("p", "hint oc-note", S.until.replace(/\\{t\\}/g, when)));
  } else {
    card.appendChild(el("p", "hint oc-note oc-exp", S.expired));
  }
  slot.textContent = "";
  slot.appendChild(el("p", "lead", S.sub));
  slot.appendChild(card);
})`;

function esc(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

export default async function OfflinePage() {
  const locale = await getLocale();
  const t = translator(locale);
  const strings = {
    sub: t("offline.sub"),
    saved: t("offline.saved"),
    until: t("offline.until"),
    expired: t("offline.expired"),
    copy: t("offline.copy"),
    copied: t("copied"),
    locale: locale === "fa" ? "fa-IR" : "en-US",
  };
  // `<` escaped so no string can close the script element early
  const args = `${JSON.stringify(strings)}, ${JSON.stringify(LAST_CONFIG_KEY)}`.replace(/</g, "\\u003c");
  return (
    <section>
      <div className="container center stack offline-page">
        {/* the page's title, so it is an h1 — it was a chip with no heading on the page at all */}
        <h1 className="chip chip-warning offline-h">{t("offline.title")}</h1>
        <div
          id="offline-slot"
          className="offline-slot"
          dangerouslySetInnerHTML={{ __html: `<p class="lead">${esc(t("offline.none"))}</p>` }}
        />
        <div className="center mt-4">
          <button id="offline-retry" type="button" className="btn btn-primary btn-lg">
            {t("offline.retry")}
          </button>
        </div>
        <script dangerouslySetInnerHTML={{ __html: `${SCRIPT}(${args});` }} />
      </div>
    </section>
  );
}
