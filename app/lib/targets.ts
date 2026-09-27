/**
 * Human names for the forecast targets.
 *
 * The export names targets by internal id (`d_ge2_h4`, `f_gt90_h8`), and those
 * ids were leaking onto the Hindcast and About screens. This is the one table
 * that turns an id into the event it describes; the Place Card, About and
 * Hindcast all read it, so the same target is never called two things.
 */

const LABELS: Record<string, string> = {
  d_ge2: "Drought reaching D2 or worse",
  d_ge3: "Drought reaching D3 or worse",
  d_improve1: "Drought easing by a category",
  d_intensify1: "Drought worsening by a category",
  d_intensify2: "Drought worsening by two categories",
  d_nochange: "Drought staying where it is",
  f_gt80: "Fire-spread conditions above the 80th percentile",
  f_gt90: "Fire-spread conditions above the 90th percentile",
  f_gt97: "Fire-spread conditions above the 97th percentile",
};

// In a city the ERC percentile says how dry it is against the city's own
// record, not how readily a wildfire would run. Denver's fire targets pass
// their checks, but naming them "fire-spread conditions" would imply a
// wildland fire danger the city does not have.
const URBAN_LABELS: Record<string, string> = {
  f_gt80: "Drier than 80% of past weeks here",
  f_gt90: "Drier than 90% of past weeks here",
  f_gt97: "Drier than 97% of past weeks here",
};

/** The event a target id describes, without its horizon. */
export function targetLabel(id: string, kind?: string | null): string {
  const base = id.replace(/_h\d+$/, "");
  if (kind === "urban" && URBAN_LABELS[base]) return URBAN_LABELS[base];
  return LABELS[base] ?? base.replace(/_/g, " ");
}

/** The horizon in weeks, as a string, or "" when the id carries none. */
export function targetHorizon(id: string): string {
  return id.match(/_h(\d+)$/)?.[1] ?? "";
}

/** Domain id to display name. */
export { domainLabel as countyName } from "./domainNames";
