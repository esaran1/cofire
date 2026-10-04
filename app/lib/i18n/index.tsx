"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { MessageKey } from "./en";
import { REVIEWED } from "./es";
import { type Lang, locale, translate } from "./translate";

export { REVIEWED as SPANISH_REVIEWED, locale, translate };
export type { Lang };

const STORE = "cofire_lang";

type Ctx = { lang: Lang; setLang: (l: Lang) => void };
const LangContext = createContext<Ctx>({ lang: "en", setLang: () => undefined });

/**
 * The reader's language: from `?lang=` when a link names it, else what they
 * chose last time in this browser, else English. Rendered in English first and
 * switched after mount, so the static export needs no per-language pages.
 */
export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("lang");
    let saved: string | null = null;
    try {
      saved = window.localStorage.getItem(STORE);
    } catch {
      saved = null;
    }
    const pick = q === "es" || q === "en" ? q : saved === "es" ? "es" : "en";
    setLangState(pick);
    // A link that names the language counts as the reader's choice.
    if (q === "es" || q === "en") {
      try {
        window.localStorage.setItem(STORE, q);
      } catch {
        /* storage blocked */
      }
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORE, l);
    } catch {
      /* storage blocked: the choice lasts for this visit */
    }
    const url = new URL(window.location.href);
    if (url.searchParams.has("lang")) {
      url.searchParams.set("lang", l);
      window.history.replaceState(window.history.state, "", url.toString());
    }
  }, []);

  const value = useMemo(() => ({ lang, setLang }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang(): Ctx {
  return useContext(LangContext);
}

/** `t(key, vars)` in the reader's language. */
export function useT() {
  const { lang } = useContext(LangContext);
  const t = useCallback((key: MessageKey, vars?: Record<string, string | number>) => translate(lang, key, vars), [lang]);
  return { lang, t };
}
