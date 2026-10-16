import type { Config } from "tailwindcss";

/**
 * One palette, locked.
 *
 * Paper and ink carry the page. The accent is a single deep ember, used for
 * exactly one thing: the primary action and the fire-spread measurement. Drought
 * gets a muted ochre because it is a second data series, not a second brand
 * colour. Slate is the "suppressed / not available" tone, deliberately cool so
 * it reads as absence rather than as a third series.
 *
 * Radius scale, locked: surfaces 2px (near-sharp, instrument-like), interactive
 * elements full-pill. Nothing else.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f4f2ec",
        "paper-sunk": "#eceae2",
        "paper-raised": "#faf9f5",
        ink: "#17181b",
        "ink-soft": "#3d3f45",
        mute: "#66686e",
        rule: "#d9d6cc",
        ember: "#b33a1a",
        "ember-soft": "#e8ddd6",
        // Darkened from #9a7420 (2026-10-15) so ochre text on paper and ochre-soft,
        // and paper text on ochre, meet WCAG AA 4.5:1 (axe, e2e/static/axe.spec.ts).
        ochre: "#7d5e14",
        "ochre-soft": "#ece5d2",
        slate: "#4a5568",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "2px",
        sm: "2px",
        md: "2px",
        lg: "2px",
      },
      maxWidth: {
        prose: "68ch",
      },
    },
  },
  plugins: [],
};
export default config;
