"use client";

import { useEffect, useState } from "react";
import { locale, useT } from "@/lib/i18n";

// A Tuesday issue goes live with Friday's refresh and stays the newest until
// the next Friday, so a current issue is at most 10 days old. Past 11 days a
// refresh has been missed (a source down, or a run that failed), and the page
// says the numbers are the last good ones rather than letting them pass as new.
export const STALE_AFTER_DAYS = 11;

export function issueAgeDays(issue: string, now: Date): number {
  return Math.floor((now.getTime() - new Date(`${issue}T00:00:00Z`).getTime()) / 86_400_000);
}

/** Shown only when the newest issue is older than a working refresh allows. */
export function StaleBadge({ issue, className = "" }: { issue: string | null | undefined; className?: string }) {
  const { lang, t } = useT();
  // Read the clock after mount, so the server render and the first client
  // render agree.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);
  if (!issue || !now) return null;
  const age = issueAgeDays(issue, now);
  if (age <= STALE_AFTER_DAYS) return null;
  const when = new Date(`${issue}T12:00:00Z`).toLocaleDateString(locale(lang), { month: "long", day: "numeric", year: "numeric" });
  return (
    <p role="status" data-testid="stale-badge" className={`rounded border border-ochre/40 bg-ochre-soft px-3 py-2 text-xs leading-relaxed text-ochre ${className}`}>
      {t("stale.text", { date: when, days: age })}
    </p>
  );
}
