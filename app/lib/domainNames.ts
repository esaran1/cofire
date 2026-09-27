/** Domain ids and display names. Plain data, safe to import anywhere. */
export const DEFAULT_DOMAIN = "denver";

export const DOMAIN_ORDER = ["denver", "upper_south_platte", "dillon", "larimer", "pueblo"] as const;

export const DOMAIN_LABELS: Record<string, string> = {
  denver: "Denver",
  upper_south_platte: "Upper South Platte",
  dillon: "Dillon",
  larimer: "Larimer",
  pueblo: "Pueblo",
};

export function domainLabel(d: string | null | undefined): string {
  if (!d) return "";
  return DOMAIN_LABELS[d] ?? d.charAt(0).toUpperCase() + d.slice(1);
}
