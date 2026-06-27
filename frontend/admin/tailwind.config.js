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
        brand: {
          DEFAULT: "#7CB000",
          50: "#f3f9e6",
          500: "#7CB000",
          600: "#6a9700",
          700: "#577c00",
        },
      },
    },
  },
  plugins: [],
};
