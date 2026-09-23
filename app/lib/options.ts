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

export const FIRE_BANDS = [
  { value: "low", label: "Low" },
  { value: "moderate", label: "Moderate" },
  { value: "high", label: "High" },
  { value: "very_high", label: "Very high" },
];

export const OBSERVATION_TYPES = [
  { value: "stock_tank_dry", label: "Stock tank dry" },
  { value: "creek_low", label: "Creek low" },
  { value: "lawn_crispy", label: "Grass crisp" },
  { value: "soil_cracked", label: "Soil cracked" },
  { value: "vegetation_green", label: "Still green" },
];
