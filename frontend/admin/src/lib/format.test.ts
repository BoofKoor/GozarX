import { describe, expect, it } from "vitest";

import { formatMb, formatNumber, shortDay, splitLocations, telegramPreviewHtml } from "./format";

describe("format helpers", () => {
  it("formats MB into GB when large", () => {
    expect(formatMb(512)).toBe("512 MB");
    expect(formatMb(1024)).toBe("1 GB");
    expect(formatMb(1536)).toBe("1.5 GB");
  });

  it("groups digits", () => {
    expect(formatNumber(12345)).toBe("12,345");
  });

  it("shortens an ISO day", () => {
    expect(shortDay("2026-06-27")).toBe("06/27");
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
