/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Vazirmatn", "Tahoma", "Segoe UI", "system-ui", "sans-serif"],
      },
      colors: {
        // Brand green (Gozar). Full ramp so cards/badges/charts can tint consistently.
        brand: {
          DEFAULT: "#7CB000",
          50: "#f3f9e6",
          100: "#e4f1c4",
          200: "#cde79a",
          400: "#9ccb33",
          500: "#7CB000",
          600: "#6a9700",
          700: "#577c00",
          900: "#33490a",
        },
        // Semantic palette — used by Badge/StatCard/Button beside the brand green.
        success: { DEFAULT: "#16a34a", 50: "#f0fdf4", 500: "#22c55e", 600: "#16a34a", 700: "#15803d" },
        warning: { DEFAULT: "#d97706", 50: "#fffbeb", 500: "#f59e0b", 600: "#d97706", 700: "#b45309" },
        danger: { DEFAULT: "#dc2626", 50: "#fef2f2", 500: "#ef4444", 600: "#dc2626", 700: "#b91c1c" },
        info: { DEFAULT: "#0284c7", 50: "#f0f9ff", 500: "#0ea5e9", 600: "#0284c7", 700: "#0369a1" },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
        "card-hover": "0 4px 12px -2px rgb(15 23 42 / 0.10), 0 2px 6px -2px rgb(15 23 42 / 0.06)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out both",
      },
    },
  },
  plugins: [],
};
