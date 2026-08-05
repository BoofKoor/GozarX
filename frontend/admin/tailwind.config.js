/** @type {import('tailwindcss').Config} */

// Every colour resolves to a CSS custom property defined in src/styles/tokens.css. Wrapping them as
// `rgb(var(--x) / <alpha-value>)` keeps Tailwind's opacity modifiers working (`bg-brand/10`).
// Semantic roles (surface/line/text) flip with the theme in the token file, so components never
// need a `dark:` twin for their base colours.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

const ramp = (prefix, stops) => Object.fromEntries(stops.map((s) => [s, token(`${prefix}-${s}`)]));

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Vazirmatn", "Tahoma", "Segoe UI", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          DEFAULT: token("brand-500"),
          ...ramp("brand", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]),
        },
        accent: { DEFAULT: token("accent-500"), ...ramp("accent", [400, 500, 600]) },

        // The hero tile's gradient pair and the ink on its always-white delta pill.
        hero: { a: token("hero-a"), b: token("hero-b"), ink: token("hero-ink") },

        // The primary button is its own role, not "the brand colour": the mock keeps it periwinkle
        // in dark and charcoal in light, so a component that wrote `bg-brand` could not follow.
        btn: { DEFAULT: token("btn-primary"), ink: token("btn-primary-ink") },

        success: { DEFAULT: token("success-600"), ...ramp("success", [400, 500, 600, 700]) },
        warning: { DEFAULT: token("warning-600"), ...ramp("warning", [400, 500, 600, 700]) },
        danger: { DEFAULT: token("danger-600"), ...ramp("danger", [400, 500, 600, 700]) },
        info: { DEFAULT: token("info-600"), ...ramp("info", [400, 500, 600, 700]) },

        // The categorical series palette, so a legend swatch or a tinted glyph can name the same
        // colour its chart uses (`bg-chart-2`) instead of re-deriving it. lib/chartTheme reads the
        // identical custom properties for the SVG side.
        chart: Object.fromEntries([1, 2, 3, 4, 5, 6].map((i) => [i, token(`chart-${i}`)])),

        // Semantic roles — the vocabulary components should reach for.
        canvas: token("bg"),
        surface: {
          DEFAULT: token("surface"),
          sunken: token("surface-sunken"),
          hover: token("surface-hover"),
          raised: token("surface-raised"),
        },
        nav: token("nav"),
        line: { DEFAULT: token("line"), strong: token("line-strong") },
        content: {
          DEFAULT: token("text"),
          muted: token("text-muted"),
          subtle: token("text-subtle"),
        },
      },
      borderColor: { DEFAULT: token("line") },
      ringColor: { DEFAULT: token("ring") },
      backgroundImage: {
        // The hero tile is a GRADIENT, not a flat brand wash — the mock's own fill.
        hero: "linear-gradient(157deg, rgb(var(--hero-a)), rgb(var(--hero-b)))",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        raised: "var(--shadow-raised)",
        overlay: "var(--shadow-overlay)",
        glow: "var(--shadow-glow)",
        hero: "var(--shadow-hero)",
      },
      // `card` is the design's own card geometry — 14px corners and a 17.6px inset. Named rather
      // than written as arbitrary values, because the table and the card footer have to bleed back
      // out by exactly the same amount (`-mx-card px-card`) and an arbitrary value in three files
      // is three chances for them to drift apart.
      spacing: { card: "18px" },
      borderRadius: { card: "14px", xl: "0.75rem", "2xl": "1rem", "3xl": "1.5rem" },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "100%": { transform: "translateX(-100%)" }, // RTL: sweep runs right → left
        },
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out both",
        "scale-in": "scale-in 0.15s ease-out both",
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};
