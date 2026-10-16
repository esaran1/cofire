/**
 * The film's data: public/data/film.json, built by scripts/prepare.mjs from
 * facts.json and the project's artifacts. Nothing in src/ types a statistic.
 */
import raw from "../public/data/film.json";
import timelineJson from "../script/timeline.json";
import narrationJson from "../script/narration.json";

export type Field = { en: string; es?: string; source: string };
export type Comparison = { domain: string; target: string; horizon: number; estimable: boolean; diff: number | null; lo: number | null; hi: number | null; survivor: boolean };
export type Pair = { domain: string; horizon: number; tested: number; realtime: number; coverage_tested: number };
export type Area = { label: string; first: number; n: number; bbox?: [number, number, number, number]; kind?: string; source?: string };
export type FilmData = {
  fields: Record<string, Field>;
  drought: { issues: string[]; cells: [string, number, number][]; cat: string[]; d2: number[]; peak: number };
  areas: Record<string, Area>;
  reservoirs: Record<"dillon" | "strontia", { name: string; lon: number; lat: number; source: string }>;
  comparisons: Comparison[];
  intervals: { pairs: Pair[]; retraction: string };
  record: { issue: string; sha: string }[];
  basemap: { bounds: [number, number, number, number]; maxZoom: number };
};

export const DATA = raw as unknown as FilmData;

export type Shot = { id: string; start: number; end: number; visual: string; camera: string; text: string; sound: string; fields: string[]; cursor?: { capture: string; start: number; speed: number } };
export type Part = { id: string; title: string; start: number; end: number };
export const TIMELINE = timelineJson as unknown as { duration: number; vertical_duration: number; parts: Part[]; shots: Shot[] };

export type Line = { id: number; start: number; en: string; es: string; source?: string };
export const NARRATION = narrationJson as unknown as { lines: Line[] };

export function shot(id: string): Shot {
  const s = TIMELINE.shots.find((x) => x.id === id);
  if (!s) throw new Error(`no shot ${id} in timeline.json`);
  return s;
}
