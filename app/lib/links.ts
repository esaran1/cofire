/**
 * Every outside link the app gives residents, in one place, so one test can
 * check them all (e2e/links.spec.ts). Each was opened and its page title read
 * when added; `checked` is that date.
 */
export type HelpLink = { id: string; url: string; publisher: string; en: string; es: string; checked: string };

export const LINKS: Record<string, HelpLink> = {
  denver_water_supply: {
    id: "denver_water_supply",
    url: "https://www.denverwater.org/your-water/water-supply-and-planning/collection-system",
    publisher: "Denver Water",
    en: "Denver Water: where the city's water comes from",
    es: "Denver Water: de dónde viene el agua de la ciudad",
    checked: "2026-10-04",
  },
  denver_water_watershed: {
    id: "denver_water_watershed",
    url: "https://www.denverwater.org/your-water/water-supply-and-planning/watershed-protection-and-management",
    publisher: "Denver Water",
    en: "Denver Water: wildfire and the water supply",
    es: "Denver Water: los incendios y el suministro de agua",
    checked: "2026-10-04",
  },
  smoke_map: {
    id: "smoke_map",
    url: "https://fire.airnow.gov/",
    publisher: "EPA and USFS",
    en: "AirNow Fire and Smoke Map: current smoke and air quality",
    es: "Mapa de Incendios y Humo de AirNow: humo y calidad del aire actuales",
    checked: "2026-10-04",
  },
  air_advisory: {
    id: "air_advisory",
    url: "https://www.colorado.gov/airquality/advisory.aspx",
    publisher: "Colorado Department of Public Health and Environment",
    en: "Colorado air quality advisories, including wildfire smoke",
    es: "Avisos de calidad del aire de Colorado, incluido el humo de incendios",
    checked: "2026-10-04",
  },
  denver_water_drought: {
    id: "denver_water_drought",
    url: "https://www.denverwater.org/drought",
    publisher: "Denver Water",
    en: "Denver Water: the drought stage in effect and its watering rules",
    es: "Denver Water: la etapa de sequía vigente y sus reglas de riego",
    checked: "2026-10-04",
  },
  denver_water_conserve: {
    id: "denver_water_conserve",
    url: "https://www.denverwater.org/residential/rebates-and-conservation-tips",
    publisher: "Denver Water",
    en: "Denver Water: rebates and ways to save water",
    es: "Denver Water: reembolsos y formas de ahorrar agua",
    checked: "2026-10-04",
  },
  denver_311: {
    id: "denver_311",
    url: "https://www.denvergov.org/311",
    publisher: "City and County of Denver",
    en: "Denver 311: city services and questions",
    es: "Denver 311: servicios y preguntas para la ciudad",
    checked: "2026-10-04",
  },
  csfs_mitigation: {
    id: "csfs_mitigation",
    url: "https://csfs.colostate.edu/wildfire-mitigation/",
    publisher: "Colorado State Forest Service",
    en: "Colorado State Forest Service: protecting a home from wildfire",
    es: "Servicio Forestal del Estado de Colorado: cómo proteger una casa de los incendios",
    checked: "2026-10-04",
  },
  firewise: {
    id: "firewise",
    url: "https://www.nfpa.org/education-and-research/wildfire/firewise-usa",
    publisher: "NFPA",
    en: "Firewise USA: wildfire preparedness for neighborhoods",
    es: "Firewise USA: preparación para incendios en los vecindarios",
    checked: "2026-10-04",
  },
};
