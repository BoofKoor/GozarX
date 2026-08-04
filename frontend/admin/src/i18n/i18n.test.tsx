import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { LanguagePill } from "@/components/layout/LanguagePill";
import { formatNumber, langLabel, localizeDigits } from "@/lib/format";

import { I18nProvider, dirFor, getLocale, translate, useI18n } from ".";
import { MESSAGES } from "./messages";

beforeEach(() => localStorage.clear());
afterEach(() => {
  localStorage.clear();
  document.documentElement.dir = "rtl";
  document.documentElement.lang = "fa";
});

describe("catalogue", () => {
  it("translates every Persian key into English", () => {
    // messages.ts types EN against FA, so this can only fail if someone widens that annotation.
    const missing = Object.keys(MESSAGES.fa).filter(
      (k) => !(k in MESSAGES.en) || !(MESSAGES.en as Record<string, string>)[k],
    );
    expect(missing).toEqual([]);
  });

  it("substitutes only the placeholders it is given", () => {
    expect(translate("en", "chart.trendLabel", { days: 14 })).toBe("Trend over the last 14 days");
    // An unsupplied token stays literal rather than rendering "undefined" into the page.
    expect(translate("en", "chart.trendLabel")).toContain("{days}");
  });

  it("falls back to the key rather than rendering undefined", () => {
    expect(translate("fa", "nope.missing" as never)).toBe("nope.missing");
  });
});

describe("dirFor", () => {
  it("maps Persian to RTL and English to LTR", () => {
    expect(dirFor("fa")).toBe("rtl");
    expect(dirFor("en")).toBe("ltr");
  });
});

function Probe() {
  const { t, locale, dir } = useI18n();
  return (
    <div>
      <span data-testid="label">{t("nav.dashboard")}</span>
      <span data-testid="state">{`${locale}/${dir}`}</span>
      <span data-testid="num">{formatNumber(1234)}</span>
      <span data-testid="lang">{langLabel("ru")}</span>
    </div>
  );
}

describe("LanguagePill", () => {
  it("switches the catalogue, the document direction and number formatting together", async () => {
    render(
      <I18nProvider>
        <LanguagePill />
        <Probe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("label")).toHaveTextContent("داشبورد");
    expect(screen.getByTestId("state")).toHaveTextContent("fa/rtl");
    expect(screen.getByTestId("num")).toHaveTextContent("۱٬۲۳۴");
    expect(screen.getByTestId("lang")).toHaveTextContent("روسی");

    await userEvent.click(screen.getByRole("button", { name: "EN" }));

    expect(screen.getByTestId("label")).toHaveTextContent("Dashboard");
    expect(screen.getByTestId("state")).toHaveTextContent("en/ltr");
    // The ~140 plain-function format callers have to follow the switch too, which is the whole
    // reason the locale is also a module-level value and not only React state.
    expect(screen.getByTestId("num")).toHaveTextContent("1,234");
    expect(screen.getByTestId("lang")).toHaveTextContent("Russian");
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.documentElement.lang).toBe("en");
    expect(getLocale()).toBe("en");
  });

  it("keeps each option written in its own script", () => {
    render(
      <I18nProvider>
        <LanguagePill />
      </I18nProvider>,
    );
    // A switch that renames its options into the language you are trying to leave is unusable to
    // the person who cannot read it.
    expect(screen.getByRole("button", { name: "EN" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "فا" })).toBeInTheDocument();
  });

  it("restores a stored English choice on mount", () => {
    localStorage.setItem("locale", "en");
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("state")).toHaveTextContent("en/ltr");
  });
});

describe("localizeDigits", () => {
  it("is a no-op in English, where the digits already are Latin", () => {
    localStorage.setItem("locale", "en");
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(localizeDigits("12 GB")).toBe("12 GB");
  });
});
