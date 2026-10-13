import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        panel: "0 1px 2px rgb(15 23 42 / 0.05), 0 6px 18px rgb(15 23 42 / 0.04)",
      },
      colors: {
        ink: "#172033",
        muted: "#62708a",
        line: "#e6eaf0",
        surface: "#f7f8fa",
        brand: "#3158c8",
      },
    },
  },
  plugins: [],
};

export default config;
