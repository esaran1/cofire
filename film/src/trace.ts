/**
 * Number tracing. Every number the film shows reaches the screen through
 * `field()`, which reads public/data/film.json (each entry names the file and
 * key it came from) and remembers the digits it handed out.
 *
 * `assertTraced()` runs after every frame is laid out (src/Guard.tsx). It
 * reads all text on screen and fails the render if any run of digits did not
 * come from a field. App captures are images and carry the app's own numbers,
 * which come from its artifacts; they are not text here and are not checked
 * twice. Captions are checked by scripts/check.mjs.
 */
import { DATA } from "./data";

export type Lang = "en" | "es";
const handedOut = new Set<string>();
export const DIGITS = /\d+(?:[.,:]\d+)*/g;

function remember(text: string): string {
  for (const m of text.match(DIGITS) ?? []) handedOut.add(m);
  return text;
}

/** The text of a field, in English or Spanish. Throws on an unknown key. */
export function field(key: string, lang: Lang = "en"): string {
  const f = DATA.fields[key];
  if (!f) throw new Error(`Untraceable: no field "${key}" in public/data/film.json`);
  return remember(lang === "es" && f.es ? f.es : f.en);
}

/** Fill {key} references in a template from fields. Literal digits in the template are refused. */
export function fill(template: string, lang: Lang = "en"): string {
  const literal = template.replace(/\{[a-z0-9_]+\}/g, "").match(DIGITS);
  if (literal) throw new Error(`Untraceable: digits "${literal.join(", ")}" typed into "${template}"`);
  return template.replace(/\{([a-z0-9_]+)\}/g, (_, k: string) => field(k, lang));
}

/** Fail if any number on screen was not handed out by field(). */
export function assertTraced(root: HTMLElement, where: string): void {
  const text = root.innerText + " " + Array.from(root.querySelectorAll("svg text, svg tspan")).map((n) => n.textContent ?? "").join(" ");
  for (const m of text.match(DIGITS) ?? []) {
    if (!handedOut.has(m)) {
      throw new Error(`Untraced number "${m}" on screen at ${where}. Every number must come from field() (public/data/film.json).`);
    }
  }
}
