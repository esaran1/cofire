/**
 * The app's design tokens and fonts, imported rather than copied, so the film
 * and the app cannot drift apart. The film's grade is the app's dark map:
 * ink ground, paper type, the one ember accent, ochre for drought.
 */
import { staticFile } from "remotion";
import tw from "../../app/tailwind.config";

const c = (tw.theme?.extend?.colors ?? {}) as Record<string, string>;

export const T = {
  paper: c.paper,
  paperSunk: c["paper-sunk"],
  paperRaised: c["paper-raised"],
  ink: c.ink,
  inkSoft: c["ink-soft"],
  mute: c.mute,
  rule: c.rule,
  ember: c.ember,
  emberSoft: c["ember-soft"],
  ochre: c.ochre,
  ochreSoft: c["ochre-soft"],
  slate: c.slate,
  // The basemap's own tones (app/lib/basemap.ts), for frames around the map.
  land: "#1f2126",
  // Ember lifted for type on the dark ground; the same hue as the token.
  emberBright: "#e2643c",
};

// Drought category colours, D1 to D4, taken from the app's map ramps
// (components/MapView.tsx: the drought ramp's 25 stop, then the fire ramp's
// 60, 75 and 90 stops). Category 0 (none or D0) is left clear, as the app does.
export const DROUGHT = ["rgba(0,0,0,0)", "#e6c15c", "#eab26b", "#cf6a2c", "#8a2410"];

export const FONT = {
  serif: "Newsreader, Georgia, serif",
  sans: "Outfit, system-ui, sans-serif",
  mono: "IBMPlexMono, ui-monospace, monospace",
};

/** @font-face rules for the app's own OFL files (copied to public/fonts by scripts/prepare.mjs). */
export const fontCss = `
@font-face { font-family: Newsreader; src: url(${staticFile("fonts/Newsreader-latin.woff2")}) format("woff2"); font-weight: 300 500; font-style: normal; }
@font-face { font-family: Newsreader; src: url(${staticFile("fonts/Newsreader-Italic-latin.woff2")}) format("woff2"); font-weight: 300 500; font-style: italic; }
@font-face { font-family: Outfit; src: url(${staticFile("fonts/Outfit-latin.woff2")}) format("woff2"); font-weight: 300 600; }
@font-face { font-family: IBMPlexMono; src: url(${staticFile("fonts/IBMPlexMono-Regular-latin.woff2")}) format("woff2"); font-weight: 400; }
@font-face { font-family: IBMPlexMono; src: url(${staticFile("fonts/IBMPlexMono-Medium-latin.woff2")}) format("woff2"); font-weight: 500; }
`;
