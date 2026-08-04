import { describe, expect, it } from "vitest";

import {
  faDate,
  formatMb,
  formatNumber,
  humanBytes,
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
    expect(formatMb(1536)).toBe("\u2068۱.۵ GB\u2069");
  });

  it("isolates every byte size the same way", () => {
    expect(humanBytes(0)).toBe("\u2068۰ B\u2069");
    expect(humanBytes(3_375_000_000_000)).toBe("\u2068۳.۱ TB\u2069");
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
