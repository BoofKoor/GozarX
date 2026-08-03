/** @type {import('tailwindcss').Config} */

// Every colour resolves to a CSS custom property defined in src/styles/tokens.css. Wrapping them as
// `rgb(var(--x) / <alpha-value>)` keeps Tailwind's opacity modifiers working (`bg-brand/10`).
// Semantic roles (surface/line/text) flip with the theme in the token file, so components never
// need a `dark:` twin for their base colours.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

const ramp = (prefix, stops) =>
  Object.fromEntries(stops.map((s) => [s, token(`${prefix}-${s}`)]));

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
        success: { DEFAULT: token("success-600"), ...ramp("success", [400, 500, 600, 700]) },
        warning: { DEFAULT: token("warning-600"), ...ramp("warning", [400, 500, 600, 700]) },
        danger: { DEFAULT: token("danger-600"), ...ramp("danger", [400, 500, 600, 700]) },
        info: { DEFAULT: token("info-600"), ...ramp("info", [400, 500, 600, 700]) },

        // Semantic roles — the vocabulary components should reach for.
        canvas: token("bg"),
        surface: {
          DEFAULT: token("surface"),
          sunken: token("surface-sunken"),
          hover: token("surface-hover"),
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
      boxShadow: {
        card: "var(--shadow-card)",
        raised: "var(--shadow-raised)",
        overlay: "var(--shadow-overlay)",
        glow: "var(--shadow-glow)",
      },
      borderRadius: { xl: "0.75rem", "2xl": "1rem", "3xl": "1.5rem" },
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
