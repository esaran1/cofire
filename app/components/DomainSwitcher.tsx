"use client";

import { DOMAIN_LABELS, DOMAIN_ORDER, useDomain } from "@/lib/domain";
import { useT } from "@/lib/i18n";

/**
 * Which area the app is showing. Denver first: it is the district being judged,
 * and the two watersheds after it are where Denver's water comes from.
 */
export function DomainSwitcher({ className = "" }: { className?: string }) {
  const [domain, setDomain] = useDomain();
  const { t } = useT();
  return (
    <label className={`flex items-center gap-2 text-sm ${className}`}>
      <span className="sr-only">{t("domain.area")}</span>
      <select
        data-testid="domain-switcher"
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        className="w-[6.5rem] rounded-full border border-rule bg-paper-raised px-2.5 py-1.5 min-[380px]:w-[8.5rem] min-[380px]:px-3 text-sm text-ink sm:w-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-ember"
      >
        <optgroup label={t("domain.district")}>
          <option value="denver">{DOMAIN_LABELS.denver}</option>
        </optgroup>
        <optgroup label={t("domain.water")}>
          <option value="upper_south_platte">{DOMAIN_LABELS.upper_south_platte}</option>
          <option value="dillon">{DOMAIN_LABELS.dillon}</option>
        </optgroup>
        <optgroup label={t("domain.counties")}>
          {DOMAIN_ORDER.slice(3).map((d) => (
            <option key={d} value={d}>
              {DOMAIN_LABELS[d]}
            </option>
          ))}
        </optgroup>
      </select>
    </label>
  );
}
