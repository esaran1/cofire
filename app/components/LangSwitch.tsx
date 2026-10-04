"use client";

import { usePathname } from "next/navigation";
import { SPANISH_REVIEWED, useLang, useT } from "@/lib/i18n";

/** English or Spanish. Each option is labelled in its own language. */
export function LangSwitch() {
  const { lang, setLang } = useLang();
  const { t } = useT();
  return (
    <div role="group" aria-label={t("lang.label")} className="flex items-center rounded-full border border-rule text-xs">
      {(
        [
          ["en", "EN", "English"],
          ["es", "ES", "Español"],
        ] as const
      ).map(([l, short, name]) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-label={name}
          aria-pressed={lang === l}
          data-testid={`lang-${l}`}
          onClick={() => setLang(l)}
          className={`rounded-full px-1.5 py-1 min-[380px]:px-2 ${lang === l ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"}`}
        >
          {short}
        </button>
      ))}
    </div>
  );
}

// The screens with Spanish text so far. Others say so rather than mixing.
const TRANSLATED = ["/", "/ember", "/brief"];

/** Under the nav, in Spanish only: the draft notice, and a note on untranslated pages. */
export function LangNotice() {
  const { lang, t } = useT();
  const path = usePathname();
  if (lang !== "es") return null;
  const translated = TRANSLATED.some((p) => (p === "/" ? path === "/" : path.startsWith(p)));
  if (SPANISH_REVIEWED && translated) return null;
  return (
    <div className="border-b border-ochre/40 bg-ochre-soft px-6 py-1.5 text-center text-xs text-ochre" data-testid="lang-notice">
      {!translated ? <span lang="es">{t("lang.untranslated")} </span> : null}
      {!SPANISH_REVIEWED ? <span lang="es">{t("lang.draft")}</span> : null}
    </div>
  );
}
