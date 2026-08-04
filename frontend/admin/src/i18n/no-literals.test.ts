import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The panel is bilingual, and a hardcoded Persian string is the one way that quietly stops being
 * true: `tsc` catches a MISSING translation (EN is typed against FA) but not a literal that never
 * reached the catalogue at all. This walks the source and fails on one.
 *
 * Allowed: the catalogue itself, tests, and `lib/format` — which owns the locale tables and the
 * numeral/comma glyphs by design. Comments are allowed too: an explanation of a bidi bug is worth
 * more with the broken text in it than without.
 */
const SRC = join(__dirname, "..");
const PERSIAN = /[؀-ۿ]/;
const ALLOWED = [
  join("src", "i18n", "messages.ts"),
  join("src", "lib", "format.ts"),
  join("src", "components", "ui", "Avatar.tsx"), // an Arabic-script RANGE, not a string
  join("src", "components", "layout", "LanguagePill.tsx"), // «فا» names its own language
];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    if (!/\.tsx?$/.test(name) || /\.test\.tsx?$/.test(name)) return [];
    return [path];
  });
}

/** Strip line and block comments, so an explanatory comment can quote the broken rendering. */
function stripComments(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/**
 * Persian used as SEARCH DATA rather than as display text: the command palette matches a typed
 * query against both languages, so those keyword arrays are the feature, not a missed string.
 */
function stripKeywords(code: string): string {
  return code.replace(/keywords:\s*\[[^\]]*\]/g, "");
}

describe("no hardcoded Persian outside the catalogue", () => {
  it("every source file reads its user-facing text from i18n", () => {
    const offenders: string[] = [];
    for (const path of sourceFiles(SRC)) {
      if (ALLOWED.some((a) => path.endsWith(a))) continue;
      const code = stripKeywords(stripComments(readFileSync(path, "utf8")));
      code.split("\n").forEach((line, i) => {
        if (PERSIAN.test(line))
          offenders.push(`${path.slice(SRC.length + 1)}:${i + 1} ${line.trim()}`);
      });
    }
    expect(offenders).toEqual([]);
  });
});
