"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import latest from "@/lib/brief_latest.json";
import { BRIEF_HORIZON, type AreaBrief, type Brief, buildBrief } from "@/lib/brief";
import { getBundle, getDomains } from "@/lib/data";
import { type Lang, SPANISH_REVIEWED, locale, translate, useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import emberEs from "@/lib/i18n/ember_es.json";
import { LINKS } from "@/lib/links";
import type { DomainsIndex } from "@/lib/schemas";
import { ErrorNote } from "@/components/ui/Controls";
import { StaleBadge } from "@/components/StaleBadge";

/**
 * The weekly district brief: one printable page for a Denver resident or a
 * caseworker answering one. Every number is read from the week's bundles
 * (lib/brief.ts); the page adds no estimate of its own.
 */

const WATER = ["upper_south_platte", "dillon"] as const;
const HELP = ["denver_water_drought", "denver_water_conserve", "smoke_map", "air_advisory", "denver_311"] as const;
const ES_ITEMS = (emberEs as { items: Record<string, { label: string; rationale: string }> }).items;

function pct(p: number | null | undefined): string {
  if (p === null || p === undefined) return "";
  if (p <= 0) return "0%";
  if (p * 100 < 1) return "<1%";
  return `${(p * 100).toFixed(0)}%`;
}

function week(iso: string, lang: Lang): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(locale(lang), { year: "numeric", month: "long", day: "numeric" });
}

function plusWeeks(iso: string, w: number): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 7 * w);
  return d.toISOString().slice(0, 10);
}

type Todo = { id: string; label: string }[];

// The newest week, precomputed by the weekly refresh (cofire/v12/brief_static.py),
// so the page renders at once; older weeks are built from their bundles.
const LATEST = latest as unknown as { brief: Brief; todo: Todo };

function BriefSheet({ brief, lang, todo }: { brief: Brief; lang: Lang; todo: Todo }) {
  const t = (k: MessageKey, v?: Record<string, string | number>) => translate(lang, k, v);
  const h = BRIEF_HORIZON;
  const catName = (c: number) => t(`brief.cat${Math.min(4, Math.max(0, c))}` as MessageKey);
  const d = brief.denver;
  const cell = (v: number | null | "impossible") =>
    v === "impossible" ? <span className="text-mute">{t("brief.impossible")}</span> : v === null ? <span className="text-mute">{t("brief.notChecked")}</span> : pct(v);
  const fire = (o: AreaBrief["f80"]) =>
    o?.mean === null || o?.mean === undefined ? "" : (
      <>
        {pct(o.mean)}
        {o.state === "base_rate" ? "*" : ""}
      </>
    );
  const areas: (AreaBrief & { name: string })[] = [
    { ...d, name: t("brief.denverRow") },
    ...brief.water.map((w) => ({ ...w, name: w.label })),
  ];

  // What changed since the previous issue, each line a difference between
  // two bundles.
  const changes: string[] = [];
  if (brief.prevIssue) {
    const moved = d.rows.filter((r) => r.cellsPrev !== null && r.cellsPrev !== r.cells);
    changes.push(
      moved.length === 0
        ? t("brief.catSame")
        : t("brief.catChanged", {
            list: moved.map((r) => t("brief.catItem", { cat: `D${r.cat}`, from: r.cellsPrev ?? 0, to: r.cells })).join("; "),
          }),
    );
    for (const a of areas) {
      if (a.dryNow !== null && a.dryNowPrev !== null) {
        const diff = a.dryNow - a.dryNowPrev;
        const dir = Math.abs(diff) < 5 ? t("brief.same") : diff > 0 ? t("brief.drier") : t("brief.wetter");
        changes.push(t("brief.dryChange", { area: a.label, from: a.dryNowPrev.toFixed(0), to: a.dryNow.toFixed(0), dir }));
      }
    }
    for (const a of brief.water) {
      if (a.f80?.mean !== null && a.f80?.mean !== undefined && a.f80Prev !== null) {
        changes.push(t("brief.f80Change", { area: a.label, h, from: pct(a.f80Prev), to: pct(a.f80.mean) }));
      }
    }
  }

  return (
    <article lang={lang} className="brief-sheet" data-testid={`brief-${lang}`}>
      <header className="border-b border-rule pb-4">
        <p className="text-xs uppercase tracking-wide text-mute">COFIRE</p>
        <h1 className="display mt-1 text-3xl" data-testid="brief-title">
          {t("brief.title")}
        </h1>
        <p className="mt-2 text-sm text-ink-soft" data-testid="brief-issued">
          {t("brief.issued", { issue: week(brief.issue, lang), h, target: week(plusWeeks(brief.issue, Number(h)), lang) })}
        </p>
        {lang === "es" && !SPANISH_REVIEWED ? <p className="mt-1 text-xs text-ochre">{t("lang.draft")}</p> : null}
      </header>

      <section className="mt-5">
        <h2 className="text-lg font-semibold">{t("brief.droughtTitle")}</h2>
        <ul className="mt-1 text-sm" data-testid="brief-drought-now">
          {d.rows.map((r) => (
            <li key={r.cat}>{t("brief.droughtNow", { n: r.cells, total: d.cells, cat: catName(r.cat) })}</li>
          ))}
        </ul>
        <table className="mt-3 w-full text-sm" data-testid="brief-drought-odds">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-mute">
              <th className="pb-1 font-normal">{t("brief.colNow")}</th>
              <th className="pb-1 text-right font-normal">{t("brief.colStay")}</th>
              <th className="pb-1 text-right font-normal">{t("brief.colEase")}</th>
              <th className="pb-1 text-right font-normal">{t("brief.colWorsen")}</th>
            </tr>
          </thead>
          <tbody>
            {d.rows.map((r) => (
              <tr key={r.cat} className="border-t border-rule">
                <td className="py-1.5">D{r.cat}</td>
                <td className="num py-1.5 text-right">{cell(r.stay)}</td>
                <td className="num py-1.5 text-right">{cell(r.ease)}</td>
                <td className="num py-1.5 text-right">{cell(r.worsen)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-1 text-[11px] leading-relaxed text-mute">{t("brief.droughtNote", { h })}</p>
      </section>

      <section className="mt-5">
        <h2 className="text-lg font-semibold">{t("brief.waterTitle")}</h2>
        <p className="mt-1 text-sm leading-relaxed text-ink-soft">
          {t("brief.waterLede")}{" "}
          <span className="text-[11px] text-mute">
            (
            {(["denver_water_sources", "denver_water_watershed"] as const).map((id, i) => (
              <span key={id}>
                {i > 0 ? "; " : ""}
                <a href={LINKS[id].url} className="underline underline-offset-2" data-link={id}>
                  {LINKS[id][lang]}
                </a>
              </span>
            ))}
            )
          </span>
        </p>
        <div className="overflow-x-auto">
        <table className="mt-3 w-full min-w-[30rem] text-sm print:min-w-0" data-testid="brief-fire">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-mute">
              <th className="pb-1 font-normal">{t("brief.colArea")}</th>
              <th className="pb-1 text-right font-normal">{t("brief.colDryNow")}</th>
              <th className="pb-1 text-right font-normal">{t("brief.colDryAhead", { h })}</th>
              <th className="pb-1 text-right font-normal">{t("brief.colF80")}</th>
              <th className="pb-1 text-right font-normal">{t("brief.colF90")}</th>
            </tr>
          </thead>
          <tbody>
            {areas.map((a) => (
              <tr key={a.id} className="border-t border-rule" data-area={a.id}>
                <td className="py-1.5 pr-2">{a.name}</td>
                <td className="num py-1.5 text-right">{a.dryNow?.toFixed(0) ?? ""}</td>
                <td className="num py-1.5 text-right">{a.dryAhead?.toFixed(0) ?? ""}</td>
                <td className="num py-1.5 text-right">{fire(a.f80)}</td>
                <td className="num py-1.5 text-right">{fire(a.f90)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-mute">{t("brief.dryNote")}</p>
      </section>

      <section className="mt-5">
        <h2 className="text-lg font-semibold">
          {brief.prevIssue ? t("brief.changedTitle", { prev: week(brief.prevIssue, lang) }) : t("brief.changedTitleNone")}
        </h2>
        <ul className="mt-1 list-disc pl-5 text-sm leading-relaxed" data-testid="brief-changes">
          {brief.prevIssue ? changes.map((c) => <li key={c}>{c}</li>) : <li>{t("brief.noPrev")}</li>}
        </ul>
      </section>

      <section className="mt-5">
        <h2 className="text-lg font-semibold">{t("brief.doTitle")}</h2>
        <ul className="mt-1 list-disc pl-5 text-sm leading-relaxed" data-testid="brief-actions">
          {todo.map((i) => (
            <li key={i.id}>{lang === "es" && ES_ITEMS[i.id] ? ES_ITEMS[i.id].label : i.label}</li>
          ))}
        </ul>
        <p className="mt-1 text-[11px] text-mute">{t("brief.doMore")}</p>
      </section>

      <section className="mt-5">
        <h2 className="text-lg font-semibold">{t("brief.helpTitle")}</h2>
        <ul className="mt-1 space-y-1 text-sm" data-testid="brief-help">
          {HELP.map((id) => (
            <li key={id}>
              <a href={LINKS[id].url} className="underline underline-offset-2" data-link={id}>
                {LINKS[id][lang]}
              </a>
              <span className="block break-all text-[11px] text-mute print:inline print:before:content-['_']">{LINKS[id].url}</span>
            </li>
          ))}
        </ul>
        <ul className="mt-3 space-y-1 text-sm print:hidden" data-testid="brief-map-links">
          <li>
            <Link href={`/?domain=denver&layer=fire&horizon=${h}&lang=${lang}`} className="underline underline-offset-2">
              {t("brief.mapLink")}
            </Link>
          </li>
          <li>
            <Link href={`/?domain=denver&layer=burden&lang=${lang}`} className="underline underline-offset-2">
              {t("brief.burdenLink")}
            </Link>
          </li>
        </ul>
        <p className="mt-3 text-sm font-medium">{t("brief.emergency")}</p>
        <p className="mt-2 text-[11px] leading-relaxed text-mute">{t("brief.source")}</p>
      </section>
    </article>
  );
}

export default function BriefPage() {
  const { lang, t } = useT();
  const [index, setIndex] = useState<DomainsIndex | null>(null);
  const [issue, setIssue] = useState(LATEST.brief.issue);
  const [brief, setBrief] = useState<Brief | null>(LATEST.brief);
  const todo = LATEST.todo;
  const [both, setBoth] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("issue");
    getDomains()
      .then((d) => {
        setIndex(d);
        setIssue(wanted && d.issues.includes(wanted) ? wanted : (d.issues[d.issues.length - 1] ?? ""));
      })
      .catch((e: Error) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (!index || !issue) return;
    const url = new URL(window.location.href);
    url.searchParams.set("issue", issue);
    url.searchParams.set("lang", lang);
    window.history.replaceState(window.history.state, "", url.toString());
    if (issue === LATEST.brief.issue) {
      setBrief(LATEST.brief);
      return;
    }
    let live = true;
    const i = index.issues.indexOf(issue);
    const prev = i > 0 ? index.issues[i - 1] : null;
    const load = (dom: string, iss: string | null) => (iss ? getBundle(dom, iss).catch(() => null) : Promise.resolve(null));
    Promise.all([getBundle("denver", issue), ...WATER.map((w) => getBundle(w, issue)), load("denver", prev), ...WATER.map((w) => load(w, prev))])
      .then(([den, usp, dil, pden, pusp, pdil]) => {
        if (!live || !den || !usp || !dil) return;
        setBrief(
          buildBrief(
            den,
            [
              { id: "upper_south_platte", label: index.domains.upper_south_platte?.label ?? "Upper South Platte", bundle: usp },
              { id: "dillon", label: index.domains.dillon?.label ?? "Dillon", bundle: dil },
            ],
            pden,
            { upper_south_platte: pusp, dillon: pdil },
          ),
        );
      })
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, [index, issue, lang]);

  // Print both languages: render the second copy, then open the print dialog.
  useEffect(() => {
    if (!both) return;
    const id = setTimeout(() => window.print(), 100);
    const done = () => setBoth(false);
    window.addEventListener("afterprint", done);
    return () => {
      clearTimeout(id);
      window.removeEventListener("afterprint", done);
    };
  }, [both]);

  const other: Lang = lang === "es" ? "en" : "es";
  const issues = useMemo(() => [...(index?.issues ?? [])].reverse(), [index]);

  return (
    <div className="reading px-6 pb-24 pt-8 print:p-0">
      <div className="mb-6 flex flex-wrap items-end gap-3 print:hidden">
        <label className="text-xs text-mute">
          {t("brief.week")}
          <select
            value={issue}
            onChange={(e) => setIssue(e.target.value)}
            data-testid="brief-issue"
            className="ml-2 rounded-full border border-rule bg-paper-raised px-3 py-1.5 text-sm text-ink"
          >
            {issues.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => window.print()} className="rounded-full bg-ink px-4 py-2 text-sm text-paper">
          {t("brief.print")}
        </button>
        <button type="button" onClick={() => setBoth(true)} className="rounded-full border border-rule px-4 py-2 text-sm" data-testid="brief-print-both">
          {t("brief.printBoth")}
        </button>
      </div>

      <StaleBadge issue={index?.issues[index.issues.length - 1]} className="mb-4" />
      {err ? <ErrorNote message={err} onRetry={() => setErr(null)} /> : null}
      {!brief && !err ? <p className="text-sm text-mute">{t("brief.loading")}</p> : null}
      {brief ? <BriefSheet brief={brief} lang={lang} todo={todo} /> : null}
      {brief && both ? (
        <div className="mt-10 break-before-page border-t border-rule pt-10 print:mt-0 print:border-0 print:pt-0">
          <BriefSheet brief={brief} lang={other} todo={todo} />
        </div>
      ) : null}
    </div>
  );
}
