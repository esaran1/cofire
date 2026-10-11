/**
 * Option lists shared between a route and its preview on the landing page.
 *
 * Next.js page files may export only the page and its config, so a list that
 * two places need cannot live in a page. Keeping one copy here means the
 * landing preview can never offer a choice the real screen does not.
 */

export const DROUGHT_CATEGORIES = [
  { value: 0, label: "None", hint: "no drought" },
  { value: 1, label: "D1", hint: "moderate" },
  { value: 2, label: "D2", hint: "severe" },
  { value: 3, label: "D3", hint: "extreme" },
  { value: 4, label: "D4", hint: "exceptional" },
];

// Fire-spread bands on the dryness scale the model forecasts (the ERC
// percentile for the week, 50 is typical). 80 and 90 are the thresholds the
// fire-spread targets use, so a band means the same thing everywhere.
export const FIRE_BANDS = [
  { value: "low", label: "Low", hint: "under 50", min: 0, max: 50 },
  { value: "moderate", label: "Moderate", hint: "50 to 80", min: 50, max: 80 },
  { value: "high", label: "High", hint: "80 to 90", min: 80, max: 90 },
  { value: "very_high", label: "Very high", hint: "over 90", min: 90, max: 101 },
];

/** The band a dryness value falls in. */
export function fireBandFor(point: number): (typeof FIRE_BANDS)[number] {
  return FIRE_BANDS.find((b) => point >= b.min && point < b.max) ?? FIRE_BANDS[FIRE_BANDS.length - 1];
}

import type { MessageKey } from "./i18n/en";
import { type Lang, translate } from "./i18n/translate";

/** The drought categories in the reader's language; values unchanged. */
export function droughtCategories(lang: Lang): typeof DROUGHT_CATEGORIES {
  return DROUGHT_CATEGORIES.map((c) => ({
    ...c,
    label: c.value === 0 ? translate(lang, "opt.cat0") : c.label,
    hint: translate(lang, `opt.cat${c.value}hint` as MessageKey),
  }));
}

/** The fire-spread bands in the reader's language; values and edges unchanged. */
export function fireBands(lang: Lang): typeof FIRE_BANDS {
  return FIRE_BANDS.map((b) => ({
    ...b,
    label: translate(lang, `opt.band.${b.value}` as MessageKey),
    hint: translate(lang, `opt.bandhint.${b.value}` as MessageKey),
  }));
}

export const OBSERVATION_TYPES = [
  { value: "stock_tank_dry", label: "Stock tank dry" },
  { value: "creek_low", label: "Creek low" },
  { value: "lawn_crispy", label: "Grass crisp" },
  { value: "soil_cracked", label: "Soil cracked" },
  { value: "vegetation_green", label: "Still green" },
];
