import type { Config } from "tailwindcss";

/**
 * One palette, locked. Four jobs, four colours, and no colour does two jobs.
 *
 * - Paper and ink carry the page. The neutrals lean faintly green-grey so they
 *   sit with the accent rather than against it.
 * - Spruce is the one interface accent: primary actions, links, focus, the
 *   current place in the site. It is the colour of the forested watersheds the
 *   forecasts are about, and it is the one hue no data layer uses, so an action
 *   can never be mistaken for a reading.
 * - Ink marks a selected option (segmented pickers, the active page, the chosen
 *   horizon), so "selected" looks the same everywhere.
 * - Ember and ochre are data, never decoration: ember is fire-spread
 *   conditions, ochre is drought. Each also carries the one status that shares
 *   its meaning: ember an error or a correction, ochre a caution notice (the
 *   seal, stale data, offline). Slate is "suppressed / not available", cool so
 *   it reads as absence.
 *
 * Radius scale, locked: surfaces 2px (near-sharp, instrument-like), interactive
 * elements full-pill. Nothing else.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f3f3ee",
        "paper-sunk": "#eaebe4",
        "paper-raised": "#fafaf6",
        ink: "#161a19",
        "ink-soft": "#383e3c",
        mute: "#5f655f",
        rule: "#d5d8cf",
        // The interface accent (6.8:1 on paper, and paper on it).
        spruce: "#245e50",
        "spruce-deep": "#1b4a3f",
        "spruce-soft": "#e1e9e3",
        // Data: fire-spread conditions; also alerts and corrections.
        ember: "#b33a1a",
        "ember-soft": "#efe1da",
        // Data: drought. Darkened from #9a7420 (2026-10-15) so ochre text on
        // paper and ochre-soft, and paper text on ochre, meet WCAG AA 4.5:1.
        ochre: "#7d5e14",
        "ochre-soft": "#ede7d4",
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
