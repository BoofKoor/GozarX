import type { RewardResponse } from "@/lib/api";
import { type Locale, type Translator, fill } from "@/lib/i18n";
import { formatMb } from "@/lib/format";

// What a reward claim did, in words — a bare «✓» / «—» told the visitor neither how much they got
// nor why nothing happened. `doneKey` is the sentence for a success that carries no amount (a
// reward the operator set to 0), so the toast never reads «۰ مگابایت اضافه شد». `r` is null when the
// request itself failed. `t` is the caller's `useT()` — this runs in the browser.
export function rewardMessage(
  t: Translator,
  locale: Locale,
  r: RewardResponse | null,
  fallbackMb: number | undefined,
  doneKey: string,
): string {
  if (r?.ok) {
    const mb = r.amount_mb ?? fallbackMb ?? 0;
    const added =
      mb > 0 ? fill(t("reward_added"), { v: formatMb(mb, locale) }) : null;
    return added ?? t(doneKey);
  }
  return r?.reason === "already_claimed" ? t("reward_taken") : t("reward_err");
}

// Share an invite through the system sheet WITH a sentence — a bare URL told the friend nothing about
// why they were getting it. Resolves false where there is no share sheet (the caller copies instead)
// and when the person dismisses it; never throws. `t` is the caller's `useT()`.
export async function shareInvite(link: string, t: Translator): Promise<boolean> {
  if (typeof navigator === "undefined" || !navigator.share) return false;
  try {
    await navigator.share({ title: "GozarX", text: t("invite_share"), url: link });
    return true;
  } catch {
    return false;
  }
}
