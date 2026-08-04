import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar, initialsFor } from "./Avatar";

describe("initialsFor", () => {
  it("gives an Arabic-script name ONE letter", () => {
    // «علی رضایی» → «عر» is not a word, it is two consonants jammed together. Persian interfaces
    // use a single letter, the way Telegram itself does.
    expect(initialsFor("علی رضایی")).toBe("ع");
    expect(initialsFor("مریم کاظمی")).toBe("م");
  });

  it("gives a Latin name two", () => {
    expect(initialsFor("Sara Mohammadi")).toBe("SM");
    expect(initialsFor("dmitri volkov")).toBe("DV");
  });

  it("survives an empty or whitespace name", () => {
    expect(initialsFor("")).toBe("?");
    expect(initialsFor("   ")).toBe("?");
  });
});

describe("Avatar", () => {
  it("gives the same identity the same colour every time", () => {
    // A user who changes colour between the list and their record reads as a different person.
    const a = render(<Avatar name="Someone" seed="7314829" />).container.firstElementChild;
    const b = render(<Avatar name="Renamed Later" seed="7314829" />).container.firstElementChild;
    const tone = (el: Element | null) =>
      [...(el?.classList ?? [])].find((c) => c.startsWith("bg-chart-"));
    expect(tone(a)).toBeDefined();
    expect(tone(a)).toBe(tone(b));
  });

  it("does not paint every identity the same", () => {
    const tone = (seed: string) =>
      [
        ...(render(<Avatar name="x" seed={seed} />).container.firstElementChild?.classList ?? []),
      ].find((c) => c.startsWith("bg-chart-"));
    const tones = new Set(["1", "22", "333", "4444", "55555", "666666"].map(tone));
    expect(tones.size).toBeGreaterThan(1);
  });
});
