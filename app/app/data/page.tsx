"use client";

import { useEffect, useState } from "react";
import { getOpenIndex, openDataUrl, type OpenIndex } from "@/lib/data";
import { locale, useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";

/**
 * Open data: every published forecast as CSV, GeoJSON and JSON, the data
 * dictionary, and the endpoint a program starts from
 * (cofire/v13/open_data.py). The field list comes from the index itself, so
 * the page and the files cannot disagree; each field's description is
 * translated here.
 */
const FIELD_KEYS: Record<string, MessageKey> = {
  issue: "data.f.issue",
  vintage: "data.f.vintage",
  area: "data.f.area",
  cell: "data.f.cell",
  lat: "data.f.lat",
  lon: "data.f.lon",
  target: "data.f.target",
  horizon_weeks: "data.f.horizon",
  probability: "data.f.probability",
  state: "data.f.state",
  reason: "data.f.reason",
};

function size(bytes: number, lang: string): string {
  const mb = bytes / 1e6;
  return mb >= 1 ? `${mb.toLocaleString(locale(lang as "en" | "es"), { maximumFractionDigits: 1 })} MB` : `${Math.max(1, Math.round(bytes / 1e3)).toLocaleString(locale(lang as "en" | "es"))} kB`;
}

export default function DataPage() {
  const { lang, t } = useT();
  const [idx, setIdx] = useState<OpenIndex | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    getOpenIndex().then(setIdx).catch((e: Error) => setErr(e.message));
  }, []);
  const day = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(locale(lang), { year: "numeric", month: "long", day: "numeric" });
  const link = (name: string, label: string) => (
    <a href={openDataUrl(name)} className="underline underline-offset-2" data-file={name} download>
      {label}
    </a>
  );
  return (
    <div className="reading px-6 pb-24 pt-12">
      <h1 className="display text-4xl" data-testid="data-title">{t("data.title")}</h1>
      <p className="mt-3 leading-relaxed text-ink-soft">{t("data.lede")}</p>

      {err ? <p className="mt-6 text-sm text-ember" role="alert">{t("data.error")}</p> : null}

      {idx ? (
        <>
          <section className="mt-8 rounded border border-rule bg-paper-raised p-4" data-testid="data-latest">
            <h2 className="text-base font-medium">{t("data.latestTitle", { date: day(idx.latest.issue) })}</h2>
            <ul className="mt-2 space-y-1 text-sm">
              <li>{link(idx.latest.csv, "CSV")} <span className="text-mute">({size(idx.files[idx.latest.csv].bytes, lang)}) {t("data.csvNote")}</span></li>
              <li>{link(idx.latest.geojson, "GeoJSON")} <span className="text-mute">({size(idx.files[idx.latest.geojson].bytes, lang)}) {t("data.geojsonNote")}</span></li>
              <li>{link(idx.latest.json, "JSON")} <span className="text-mute">({size(idx.files[idx.latest.json].bytes, lang)}) {t("data.jsonNote")}</span></li>
            </ul>
          </section>

          <section className="mt-8">
            <h2 className="text-lg font-medium">{t("data.endpointTitle")}</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">{t("data.endpoint")}</p>
            <p className="mt-2 font-mono text-sm" data-testid="data-endpoint">{link("index.json", openDataUrl("index.json").replace(/^https?:\/\/[^/]+/, ""))}</p>
          </section>

          <section className="mt-8" data-testid="data-dictionary">
            <h2 className="text-lg font-medium">{t("data.dictTitle")}</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">{t("data.dictLede")}</p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[34rem] text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wide text-mute">
                    <th className="pb-1 pr-4 font-normal">{t("data.colField")}</th>
                    <th className="pb-1 pr-4 font-normal">{t("data.colType")}</th>
                    <th className="pb-1 font-normal">{t("data.colMeaning")}</th>
                  </tr>
                </thead>
                <tbody>
                  {idx.fields.map((f) => (
                    <tr key={f.name} className="border-t border-rule align-top" data-field={f.name}>
                      <td className="py-2 pr-4 font-mono">{f.name}</td>
                      <td className="py-2 pr-4 text-mute">{f.type}</td>
                      <td className="py-2 leading-relaxed text-ink-soft">{FIELD_KEYS[f.name] ? t(FIELD_KEYS[f.name]) : f.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="mt-8">
            <h2 className="text-lg font-medium">{t("data.licenseTitle")}</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">
              {t("data.license")}{" "}
              <a href={idx.license.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">{idx.license.name}</a>
            </p>
            <p className="mt-3 text-sm leading-relaxed text-ink-soft">{t("data.upstream")}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-ink-soft" data-testid="data-upstream">
              {idx.license.upstream.map((u) => (
                <li key={u.name}>
                  <a href={u.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">{u.name}</a>: {u.credit}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-sm leading-relaxed text-ink-soft">{t("data.not")}</p>
          </section>

          <section className="mt-8">
            <h2 className="text-lg font-medium">{t("data.allTitle")}</h2>
            <p className="mt-1 text-sm text-mute" data-testid="data-count">{t("data.allLede", { n: idx.issues.length })}</p>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[24rem] text-sm">
                <tbody>
                  {[...idx.issues].reverse().map((i) => (
                    <tr key={i.issue} className="border-t border-rule" data-issue={i.issue}>
                      <td className="py-1.5 pr-4 font-mono">{i.issue}</td>
                      <td className="py-1.5 pr-4">{link(i.csv, "CSV")} <span className="text-mute">({size(idx.files[i.csv].bytes, lang)}, gzip)</span></td>
                      <td className="py-1.5">{link(i.geojson, "GeoJSON")} <span className="text-mute">({size(idx.files[i.geojson].bytes, lang)}, gzip)</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : !err ? (
        <p className="mt-8 text-sm text-mute">{t("data.loading")}</p>
      ) : null}
    </div>
  );
}
