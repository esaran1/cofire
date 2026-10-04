"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { List, X } from "@phosphor-icons/react";
import { DomainSwitcher } from "./DomainSwitcher";
import { LangSwitch } from "./LangSwitch";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";

/**
 * One nav, one line at desktop, drawer below md.
 *
 * The previous build had only a six-across bottom bar at every width, which is
 * why the app was hard to navigate: no wayfinding, no sense of where you were,
 * and six equal-weight targets with no grouping.
 *
 * Grouping here is the fix. "Forecast" is the product. "Evidence" is the
 * research. "Get started" is the single primary action, one label per intent.
 */
const PRODUCT: { href: string; label: MessageKey }[] = [
  { href: "/", label: "nav.map" },
  { href: "/beat", label: "nav.predict" },
  { href: "/observe", label: "nav.observe" },
  { href: "/ember", label: "nav.harden" },
];

const EVIDENCE: { href: string; label: MessageKey }[] = [
  { href: "/hindcast", label: "nav.hindcast" },
  { href: "/about", label: "nav.method" },
];

export function SiteNav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const { t } = useT();

  // A route change must close the drawer, or the panel survives navigation.
  useEffect(() => {
    setOpen(false);
  }, [path]);

  const isOn = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-paper/90 backdrop-blur">
      <div className="measure flex h-16 items-center justify-between gap-2 px-4 sm:gap-6 sm:px-6">
        <Link href="/landing" className="flex shrink-0 items-baseline gap-2" aria-label={t("nav.home")}>
          <span className="display text-xl">
            CO<em className="not-italic text-ember">FIRE</em>
          </span>
        </Link>

        <nav aria-label={t("nav.primary")} className="hidden items-center gap-1 lg:flex">
          {PRODUCT.map((it) => (
            <Link
              key={it.href}
              href={it.href}
              aria-current={isOn(it.href) ? "page" : undefined}
              className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                isOn(it.href) ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
              }`}
            >
              {t(it.label)}
            </Link>
          ))}
          <span className="mx-2 h-4 w-px bg-rule" aria-hidden />
          {EVIDENCE.map((it) => (
            <Link
              key={it.href}
              href={it.href}
              aria-current={isOn(it.href) ? "page" : undefined}
              className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                isOn(it.href) ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
              }`}
            >
              {t(it.label)}
            </Link>
          ))}
        </nav>

        <div className="flex min-w-0 items-center gap-1.5 sm:gap-2">
          <LangSwitch />
          <DomainSwitcher />
          {/* One label per intent, and never pointed at the page you are on. */}
          {path !== "/" && (
            <Link
              href="/"
              className="hidden rounded-full bg-ember px-4 py-2 text-sm font-medium text-paper transition-transform active:scale-[0.98] xl:inline-flex"
            >
              {t("nav.openMap")}
            </Link>
          )}
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? t("nav.closeMenu") : t("nav.openMenu")}
            className="rounded-full p-2 text-ink lg:hidden"
          >
            {open ? <X size={20} weight="bold" /> : <List size={20} weight="bold" />}
          </button>
        </div>
      </div>

      {open && (
        <nav id="mobile-nav" aria-label={t("nav.primary")} className="border-t border-rule bg-paper lg:hidden">
          <ul className="measure px-6 py-2">
            {[...PRODUCT, ...EVIDENCE].map((it) => (
              <li key={it.href} className="border-b border-rule/60 last:border-0">
                <Link
                  href={it.href}
                  aria-current={isOn(it.href) ? "page" : undefined}
                  className={`block py-3 ${isOn(it.href) ? "text-ember" : "text-ink"}`}
                >
                  {t(it.label)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </header>
  );
}
