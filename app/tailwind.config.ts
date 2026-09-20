import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0c0e12",
        paper: "#f2f0ea",
        mute: "#9a958b",
        fire: "#ff5a2a",
        drought: "#e6c15c",
      },
    },
  },
  plugins: [],
};
export default config;
