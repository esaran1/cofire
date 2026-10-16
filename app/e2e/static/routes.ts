/** Every route of the static site, and what proves each one rendered. */
export const ROUTES: { path: string; name: string; ready: string }[] = [
  { path: "", name: "map", ready: '[data-testid="time-scrubber"]' },
  { path: "landing/", name: "landing", ready: "h1" },
  { path: "brief/", name: "brief", ready: '[data-testid="brief-title"]' },
  { path: "scoreboard/", name: "scoreboard", ready: '[data-testid="score-table"]' },
  { path: "data/", name: "data", ready: '[data-testid="data-dictionary"]' },
  { path: "about/", name: "method", ready: "h1" },
  { path: "hindcast/", name: "hindcast", ready: "h1" },
  { path: "beat/", name: "predict", ready: "h1" },
  { path: "observe/", name: "observe", ready: "h1" },
  { path: "ember/", name: "harden", ready: '[data-testid="ember-title"]' },
];
export const LANGS = ["en", "es"] as const;
