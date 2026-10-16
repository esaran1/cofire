"use client";

import Link from "next/link";
import { useT } from "@/lib/i18n";

/**
 * Footer. Repeats the IA and carries the provenance line, because a judge
 * reading this needs to know what it is and what it does not claim.
 */
export function SiteFooter() {
  const { t } = useT();
  return (
    <footer className="border-t border-rule bg-paper-sunk">
      <div className="measure px-6 py-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <span className="display text-lg">
              CO<span className="text-ember">FIRE</span>
            </span>
            <p className="mt-2 max-w-[34ch] text-sm leading-relaxed text-mute">{t("foot.tagline")}</p>
          </div>

          <nav aria-label={t("foot.forecast")}>
            <h2 className="text-sm font-medium">{t("foot.forecast")}</h2>
            <ul className="mt-3 space-y-2 text-sm text-mute">
              <li><Link href="/" className="hover:text-ink">{t("nav.map")}</Link></li>
              <li><Link href="/beat" className="hover:text-ink">{t("nav.predict")}</Link></li>
              <li><Link href="/observe" className="hover:text-ink">{t("nav.observe")}</Link></li>
              <li><Link href="/ember" className="hover:text-ink">{t("nav.harden")}</Link></li>
              <li><Link href="/brief" className="hover:text-ink">{t("nav.brief")}</Link></li>
            </ul>
          </nav>

          <nav aria-label={t("foot.evidence")}>
            <h2 className="text-sm font-medium">{t("foot.evidence")}</h2>
            <ul className="mt-3 space-y-2 text-sm text-mute">
              <li><Link href="/hindcast" className="hover:text-ink">{t("foot.hindcast")}</Link></li>
              <li><Link href="/scoreboard" className="hover:text-ink">{t("foot.record")}</Link></li>
              <li><Link href="/data" className="hover:text-ink">{t("foot.data")}</Link></li>
              <li><Link href="/about" className="hover:text-ink">{t("foot.method")}</Link></li>
              <li><Link href="/landing" className="hover:text-ink">{t("foot.how")}</Link></li>
            </ul>
          </nav>

          <div>
            <h2 className="text-sm font-medium">{t("foot.notTitle")}</h2>
            <p className="mt-3 max-w-[32ch] text-sm leading-relaxed text-mute">{t("foot.not")}</p>
          </div>
        </div>

        <p className="mt-10 border-t border-rule pt-6 text-xs text-mute">{t("foot.credits")}</p>
      </div>
    </footer>
  );
}
