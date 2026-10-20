import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        panel: "0 1px 2px rgb(15 23 42 / 0.05), 0 6px 18px rgb(15 23 42 / 0.04)",
      },
      colors: {
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        line: "rgb(var(--color-line) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        brand: "rgb(var(--color-brand) / <alpha-value>)",
        // Existing workspace utilities share the same warm-neutral / green scale.
        slate: {
          50: "#f8f9f5", 100: "#edf1e7", 200: "#dce3d5", 300: "#c1cbb8",
          400: "#87957e", 500: "#687667", 600: "#56634f", 700: "#3d503d",
          800: "#263e33", 900: "#173c32", 950: "#102a23",
        },
        indigo: {
          50: "#f0f6e8", 100: "#e3efcf", 200: "#ccdfa9", 300: "#aecf7f",
          400: "#8baf5b", 500: "#6b8f42", 600: "#496a36", 700: "#34542d",
          800: "#24462e", 900: "#173c32", 950: "#102a23",
        },
      },
    },
  },
  plugins: [],
};

export default config;
