export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type WhyBar = {
  group: string;
  label: string;
  value: number | null;
  text: string;
  sign: string;
  top_feature?: string;
};

export type Horizon = {
  drought_point: number | null;
  drought_set: number[];
  fire_index: number | null;
  fire_lo: number | null;
  fire_hi: number | null;
  confidence: number | null;
};

export type UncertaintyStatus = {
  status: "calibrated" | "extrapolating" | "uncalibrated";
  reason: string;
  show_interval: boolean;
  widen_factor: number;
  current_usdm: number;
  pool_usdm_max: number;
  exceedance_sd: number;
  measured_coverage: number;
  pool_years?: number[];
  available: boolean;
};

export type Place = {
  cell_id: string;
  lat: number;
  lon: number;
  issue: string;
  resolution_m: number;
  shipping_arm: string;
  why: WhyBar[];
  horizons: Record<string, Horizon>;
  uncertainty?: UncertaintyStatus;
};

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json() as Promise<T>;
}

export function overlayUrl(issue: string, horizon: number, variable: string): string {
  return `${API}/overlay/${issue}/${horizon}/${variable}.png`;
}
