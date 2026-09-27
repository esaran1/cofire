"use client";

import { DOMAIN_LABELS, DOMAIN_ORDER, useDomain } from "@/lib/domain";

/**
 * Which area the app is showing. Denver first: it is the district being judged,
 * and the two watersheds after it are where Denver's water comes from.
 */
export function DomainSwitcher({ className = "" }: { className?: string }) {
  const [domain, setDomain] = useDomain();
  return (
    <label className={`flex items-center gap-2 text-sm ${className}`}>
      <span className="sr-only">Forecast area</span>
      <select
        data-testid="domain-switcher"
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        className="rounded-full border border-rule bg-paper-raised px-3 py-1.5 text-sm text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-ember"
      >
        <optgroup label="District">
          <option value="denver">{DOMAIN_LABELS.denver}</option>
        </optgroup>
        <optgroup label="Denver's water">
          <option value="upper_south_platte">{DOMAIN_LABELS.upper_south_platte}</option>
          <option value="dillon">{DOMAIN_LABELS.dillon}</option>
        </optgroup>
        <optgroup label="Counties">
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
