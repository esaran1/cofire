/**
 * Human names for the forecast targets.
 *
 * The export names targets by internal id (`d_ge2_h4`, `f_gt90_h8`), and those
 * ids were leaking onto the Hindcast and About screens. This is the one table
 * that turns an id into the event it describes; the Place Card, About and
 * Hindcast all read it, so the same target is never called two things.
 */

import type { MessageKey } from "./i18n/en";
import { type Lang, translate } from "./i18n/translate";

const KNOWN = new Set(["d_ge2", "d_ge3", "d_improve1", "d_intensify1", "d_intensify2", "d_nochange", "f_gt80", "f_gt90", "f_gt97"]);

// In a city the ERC percentile says how dry it is against the city's own
// record, not how readily a wildfire would run. Denver's fire targets pass
// their checks, but naming them "fire-spread conditions" would imply a
// wildland fire danger the city does not have.
const URBAN = new Set(["f_gt80", "f_gt90", "f_gt97"]);

/** The event a target id describes, without its horizon. */
export function targetLabel(id: string, kind?: string | null, lang: Lang = "en"): string {
  const base = id.replace(/_h\d+$/, "");
  if (kind === "urban" && URBAN.has(base)) return translate(lang, `target.urban.${base}` as MessageKey);
  return KNOWN.has(base) ? translate(lang, `target.${base}` as MessageKey) : base.replace(/_/g, " ");
}

/** The horizon in weeks, as a string, or "" when the id carries none. */
export function targetHorizon(id: string): string {
  return id.match(/_h(\d+)$/)?.[1] ?? "";
}

/** Domain id to display name. */
export { domainLabel as countyName } from "./domainNames";
