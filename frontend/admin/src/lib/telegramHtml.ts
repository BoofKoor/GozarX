/**
 * Telegram's HTML parse mode, checked as you type.
 *
 * The port of `gozar/services/telegram_html.check` (the server refuses the same markup, so this is
 * the early warning, not the gate). Every bot message is sent as HTML, and Telegram refuses the
 * WHOLE message when the markup does not parse: a broadcast saying "use the code <GOZAR>" failed
 * every send and was found out only when the job ended.
 *
 * The rules are Telegram's, not a browser's: every unescaped `<` must open a supported tag, an end
 * tag must close the tag opened last, nothing may stay open, and `<span>` must be a spoiler. `&` is
 * lenient — Telegram keeps an unknown entity as literal text.
 */
export type HtmlProblemKind = "stray" | "unsupported" | "mismatch" | "unclosed" | "spoiler";

export interface HtmlProblem {
  kind: HtmlProblemKind;
  /** The offending tag, lowercased; empty for a stray `<`. */
  tag: string;
  /** Character index of the `<` that caused it. */
  offset: number;
}

const SUPPORTED = new Set([
  "b",
  "strong",
  "i",
  "em",
  "u",
  "ins",
  "s",
  "strike",
  "del",
  "span",
  "tg-spoiler",
  "a",
  "tg-emoji",
  "code",
  "pre",
  "blockquote",
]);

const CLASS = /\bclass\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))/i;

export function checkTelegramHtml(text: string): HtmlProblem | null {
  // Sticky, so each match is tried exactly AT the `<` being looked at.
  const tag = /<(\/?)([A-Za-z][A-Za-z0-9-]*)([^<>]*)>/y;
  const stack: { name: string; at: number }[] = [];
  let i = 0;
  for (;;) {
    i = text.indexOf("<", i);
    if (i < 0) break;
    tag.lastIndex = i;
    const match = tag.exec(text);
    if (!match) return { kind: "stray", tag: "", offset: i };
    const [, closing, rawName, attrs] = match;
    const name = rawName.toLowerCase();
    if (!SUPPORTED.has(name)) return { kind: "unsupported", tag: name, offset: i };
    if (closing) {
      if (stack.length === 0 || stack[stack.length - 1].name !== name) {
        return { kind: "mismatch", tag: name, offset: i };
      }
      stack.pop();
    } else {
      if (name === "span") {
        const found = CLASS.exec(attrs);
        const value = found ? (found[1] ?? found[2] ?? found[3] ?? "") : "";
        if (value !== "tg-spoiler") return { kind: "spoiler", tag: name, offset: i };
      }
      stack.push({ name, at: i });
    }
    i = tag.lastIndex;
  }
  const open = stack[stack.length - 1];
  return open ? { kind: "unclosed", tag: open.name, offset: open.at } : null;
}
