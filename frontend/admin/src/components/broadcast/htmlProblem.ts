import type { MessageKey } from "@/i18n";
import { formatNumber } from "@/lib/format";
import type { HtmlProblem, HtmlProblemKind } from "@/lib/telegramHtml";

const KEY: Record<HtmlProblemKind, MessageKey> = {
  stray: "tg.html.stray",
  unsupported: "tg.html.unsupported",
  mismatch: "tg.html.mismatch",
  unclosed: "tg.html.unclosed",
  spoiler: "tg.html.spoiler",
};

/** A markup problem in the operator's words. The tag is Latin markup inside a Persian sentence, so
 *  it rides in its own LTR isolate — bare, its angle brackets mirror and «<gozar>» reads «>gozar<». */
export function describeHtmlProblem(
  t: (key: MessageKey, tokens?: Record<string, string | number>) => string,
  problem: HtmlProblem,
): string {
  const tag = problem.kind === "mismatch" ? `</${problem.tag}>` : `<${problem.tag}>`;
  return t(KEY[problem.kind], {
    tag: `⁦${tag}⁩`,
    at: formatNumber(problem.offset + 1),
  });
}
