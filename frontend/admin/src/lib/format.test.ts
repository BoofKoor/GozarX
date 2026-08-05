import { describe, expect, it } from "vitest";

import {
  faDate,
  faRelative,
  formatMb,
  formatMs,
  formatNumber,
  humanBytes,
  humanHours,
  humanUptime,
  localizeDigits,
  shortDay,
  splitLocations,
  telegramPreviewHtml,
} from "./format";

describe("format helpers", () => {
  it("formats MB into GB when large (Persian numerals)", () => {
    // Each quantity is wrapped FSI…PDI: a Latin unit beside its own Persian-numeral value reorders
    // in an RTL sentence, and «۱ GB» rendered as «GB ۱» — the unit ahead of the number it measures.
    expect(formatMb(512)).toBe("\u2068۵۱۲ MB\u2069");
    expect(formatMb(1024)).toBe("\u2068۱ GB\u2069");
    expect(formatMb(1536)).toBe("\u2068۱٫۵ GB\u2069"); // Persian decimal mark, not an ASCII dot
  });

  it("isolates a latency the same way, so «۱۲۴ ms» stops rendering as «ms ۱۲۴»", () => {
    // The three call sites used to build this string by hand and put `unicode-bidi: isolate` on the
    // element instead. An isolate does not change the base direction INSIDE itself, so the digits
    // and the Latin unit still swapped — on the dashboard's health list and all four probe chips.
    expect(formatMs(124)).toBe("⁨۱۲۴ ms⁩");
    expect(formatMs(87.6)).toBe("⁨۸۸ ms⁩");
  });

  it("says the uptime unit in the panel's own language", () => {
    // `${d}d ${h}h` put Latin letters in a Persian console, and `no-literals` cannot catch it —
    // it only looks for Persian, and `d`/`h`/`m` are not.
    expect(humanUptime(3 * 86400 + 4 * 3600)).toBe("⁨۳ روز ۴ ساعت⁩");
    expect(humanUptime(5 * 3600 + 12 * 60)).toBe("⁨۵ ساعت ۱۲ دقیقه⁩");
    expect(humanUptime(90)).toBe("⁨۱ دقیقه⁩");
  });

  it("carries a rounded-up relative time into the next unit", () => {
    // 23.6 hours is under a day, so it fell into the hour bucket and rounded to 24 — «۲۴ ساعت پیش»
    // in the same column as «دیروز», two sentences for one distance.
    const ago = (h: number) => new Date(Date.now() - h * 3600_000).toISOString();
    expect(faRelative(ago(23.6))).toBe("دیروز");
    expect(faRelative(ago(24))).toBe("دیروز");
    expect(faRelative(ago(20))).toBe("۲۰ ساعت پیش");
  });

  it("uses the locale's decimal mark, so ۳٫۱ TB matches the ۳۷٫۵٪ beside it", () => {
    // Only a dot BETWEEN digits converts — a sentence's full stop is left alone.
    expect(localizeDigits("v1.2 beta.")).toBe("v۱٫۲ beta.");
  });

  it("isolates every byte size the same way", () => {
    expect(humanBytes(0)).toBe("\u2068۰ B\u2069");
    expect(humanBytes(3_375_000_000_000)).toBe("\u2068۳٫۱ TB\u2069");
  });

  it("humanHours picks a unit the figure survives", () => {
    // The bug this exists for: the live median is 0.0058 hours. As hours it printed "0", which
    // reads as a missing number rather than as 21 seconds.
    expect(humanHours(0.0058)).toBe("\u2068۲۱s\u2069");
    expect(humanHours(0)).toBe("\u2068۰s\u2069");
    // A minute and over switches unit rather than showing a fraction of an hour.
    expect(humanHours(0.5)).toBe("\u2068۳۰m\u2069");
    expect(humanHours(1 / 60)).toBe("\u2068۱m\u2069");
    // Past an hour it keeps one decimal, because a period comparison reads the difference
    // between 6.9 and 7.
    expect(humanHours(6.92)).toBe("\u2068۶٫۹h\u2069");
  });

  it("groups digits with Persian numerals", () => {
    expect(formatNumber(12345)).toBe("۱۲٬۳۴۵");
  });

  it("shortens an ISO day to a compact Jalali date", () => {
    expect(shortDay("2026-06-27")).toBe("۰۴/۰۶"); // 6 Tir 1405
  });

  it("formats a full Jalali date and handles empty input", () => {
    expect(faDate("2026-07-17")).toBe("۲۶ تیر ۱۴۰۵");
    expect(faDate(null)).toBe("—");
  });

  it("splits locations on ASCII or Persian comma, trimming blanks", () => {
    expect(splitLocations("آلمان، هلند ,  , فرانسه")).toEqual(["آلمان", "هلند", "فرانسه"]);
    expect(splitLocations("")).toEqual([]);
  });

  describe("telegramPreviewHtml", () => {
    it("keeps supported Telegram formatting tags", () => {
      expect(telegramPreviewHtml("<b>bold</b> <i>x</i>")).toBe("<b>bold</b> <i>x</i>");
    });

    it("neutralizes script/img and event handlers", () => {
      expect(telegramPreviewHtml('<img src=x onerror="steal()">')).toBe(
        '&lt;img src=x onerror="steal()"&gt;',
      );
      expect(telegramPreviewHtml("<script>alert(1)</script>")).toBe(
        "&lt;script&gt;alert(1)&lt;/script&gt;",
      );
    });

    it("allows http(s)/tg links but drops javascript: hrefs", () => {
      expect(telegramPreviewHtml('<a href="https://x.co">go</a>')).toBe(
        '<a href="https://x.co" target="_blank" rel="noopener noreferrer">go</a>',
      );
      expect(telegramPreviewHtml('<a href="javascript:alert(1)">x</a>')).toBe(
        '&lt;a href="javascript:alert(1)"&gt;x</a>',
      );
    });
  });
});
