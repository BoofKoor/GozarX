import { describe, expect, it } from "vitest";

import { checkTelegramHtml } from "./telegramHtml";

// The same cases as the server's tests/test_telegram_html.py — the two must agree.
describe("checkTelegramHtml", () => {
  it.each([
    "plain text, no markup",
    "<b>bold</b> <i>it</i> <u>u</u> <s>s</s> <code>x</code> <pre>y</pre>",
    '<a href="https://t.me/x">link</a> and <tg-spoiler>secret</tg-spoiler>',
    '<span class="tg-spoiler">hidden</span>',
    "<blockquote expandable>quote</blockquote>",
    "&lt;GOZAR&gt; is escaped, and Tom & Jerry keeps a bare ampersand",
    "<B>case</B> does not matter",
    "<b><i>nested</i></b>",
  ])("accepts %s", (text) => {
    expect(checkTelegramHtml(text)).toBeNull();
  });

  it.each([
    ["use the code <GOZAR> to join", "unsupported"],
    ["a < b", "stray"],
    ["I <3 this", "stray"],
    ["<b>never closed", "unclosed"],
    ["<b><i>crossed</b></i>", "mismatch"],
    ["stray close</b>", "mismatch"],
    ["<span>no class</span>", "spoiler"],
    ["line<br>break", "unsupported"],
  ])("rejects %s as %s", (text, kind) => {
    expect(checkTelegramHtml(text)?.kind).toBe(kind);
  });
});
