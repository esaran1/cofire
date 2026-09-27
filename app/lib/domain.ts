"use client";

import { useCallback, useEffect, useState } from "react";
import { DEFAULT_DOMAIN, DOMAIN_LABELS } from "./domainNames";

export { DEFAULT_DOMAIN, DOMAIN_LABELS, DOMAIN_ORDER, domainLabel } from "./domainNames";

/**
 * The forecast area the whole app is looking at.
 *
 * Denver is the default because it is the district being judged. The choice
 * lives in the URL (`?domain=`) so a link opens the same area, and in local
 * storage so it survives moving between routes. Read in an effect rather than
 * through `useSearchParams`, which would force every page out of static
 * rendering.
 */

const EVENT = "cofire:domain";
const KEY = "cofire_domain";

function valid(d: string | null | undefined): d is string {
  return !!d && d in DOMAIN_LABELS;
}

function readInitial(): string {
  if (typeof window === "undefined") return DEFAULT_DOMAIN;
  const fromUrl = new URLSearchParams(window.location.search).get("domain");
  if (valid(fromUrl)) return fromUrl;
  try {
    const stored = window.localStorage.getItem(KEY);
    if (valid(stored)) return stored;
  } catch {
    /* storage can be blocked; the default still works */
  }
  return DEFAULT_DOMAIN;
}

export function useDomain(): [string, (d: string) => void, boolean] {
  const [domain, setDomainState] = useState<string>(DEFAULT_DOMAIN);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setDomainState(readInitial());
    setReady(true);
    const onChange = (e: Event) => {
      const d = (e as CustomEvent<string>).detail;
      if (valid(d)) setDomainState(d);
    };
    window.addEventListener(EVENT, onChange);
    return () => window.removeEventListener(EVENT, onChange);
  }, []);

  const setDomain = useCallback((d: string) => {
    if (!valid(d)) return;
    setDomainState(d);
    try {
      window.localStorage.setItem(KEY, d);
    } catch {
      /* ignore */
    }
    const url = new URL(window.location.href);
    url.searchParams.set("domain", d);
    window.history.replaceState(window.history.state, "", url.toString());
    window.dispatchEvent(new CustomEvent(EVENT, { detail: d }));
  }, []);

  return [domain, setDomain, ready];
}
