/** Plain lookup, safe to import anywhere (no React). */
import { en, type MessageKey } from "./en";
import { es } from "./es";

export type Lang = "en" | "es";

const TABLES: Record<Lang, Record<MessageKey, string>> = { en, es };

/** A message with its `{name}` slots filled. */
export function translate(lang: Lang, key: MessageKey, vars: Record<string, string | number> = {}): string {
  const text = TABLES[lang][key] ?? en[key];
  return text.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

/** The BCP 47 locale for dates and numbers. */
export function locale(lang: Lang): string {
  return lang === "es" ? "es-US" : "en-US";
}
