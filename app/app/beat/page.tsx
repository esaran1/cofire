"use client";

import { droughtCategories, fireBandFor, fireBands } from "@/lib/options";
import { useT } from "@/lib/i18n";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { usePrefersReducedMotion, useReduceMotion } from "@/lib/motion";
import { API, LeaderRow, getParsed, postParsed } from "@/lib/api";
import { LeaderRowSchema, PickSchema, PredictionSchema } from "@/lib/schemas";
import type { PickRow } from "@/lib/schemas";
import type { LockedModel } from "@/lib/schemas";
import { resolvePlace } from "@/lib/data";
import { domainLabel, useDomain } from "@/lib/domain";
import { z } from "zod";
import { deviceId } from "@/lib/device";
import { Action, EmptyState, ErrorNote, Numeral, OfflineNote, Panel, Skeleton } from "@/components/ui/Controls";
import { Segmented } from "@/components/ui/Animated";


// What the model said for the same cell and horizon (LockedModelSchema): the
// dryness percentile and the drought category it makes most likely.
type Locked = LockedModel;

function BeatInner() {
  const { lang, t } = useT();
  const CATEGORIES = droughtCategories(lang);
  const BANDS = fireBands(lang);
  const bandLabel = (v: string | null | undefined) => BANDS.find((x) => x.value === v)?.label ?? "";
  const params = useSearchParams();
  const reduce = useReduceMotion();
  const instant = usePrefersReducedMotion();
  const [cell, setCell] = useState(params.get("cell") ?? "");
  const [cat, setCat] = useState(2);
  const [band, setBand] = useState("high");
  const [locked, setLocked] = useState<Locked | null>(null);
  // What was locked, and for which cell: the reveal compares these, not the
  // selectors, which may have moved since.
  const [lockedPick, setLockedPick] = useState<{ cat: number; band: string; cell: string } | null>(null);
  const [mine, setMine] = useState<PickRow[] | null>(null);
  const [board, setBoard] = useState<LeaderRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    const id = deviceId();
    getParsed(`/predictions/me?device_id=${id}`, z.array(PickSchema))
      .then((d) => {
        setMine(d);
        setOffline(false);
      })
      .catch(() => setOffline(true));
    getParsed("/leaderboard", z.array(LeaderRowSchema))
      .then(setBoard)
      .catch(() => setBoard([]));
  }, []);

  // Resolve the pick to a real forecast cell.
  //
  // The default used to be a string built from the map's centre,
  // "39.3792_-105.1208". That point sits between the two counties, and the
  // string is not the ID of any cell, so a pick locked against it could never
  // be scored. Asking the API for the nearest cell snaps to one that exists,
  // and gives a name to show instead of the raw ID.
  const [where, setWhere] = useState<{ domain: string; lat: number; lon: number } | null>(null);
  const [domain, , ready] = useDomain();
  useEffect(() => {
    if (!ready) return;
    const fromCell = cell.match(/^(-?[\d.]+)_(-?[\d.]+)$/);
    // Snap to a real cell in the chosen area: the one named in the link, or the
    // one nearest the area's centre.
    resolvePlace(domain, fromCell ? Number(fromCell[1]) : undefined, fromCell ? Number(fromCell[2]) : undefined)
      .then((p) => {
        setWhere({ domain: p.domain ?? domain, lat: p.lat, lon: p.lon });
        if (p.cell_id !== cell) setCell(p.cell_id);
      })
      .catch(() => undefined);
    refresh();
  }, [cell, refresh, domain, ready]);

  const me = deviceId();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const body = await postParsed(
        "/predictions",
        { device_id: deviceId(), cell_id: cell, horizon: 4, drought_category: cat, fire_band: band },
        PredictionSchema,
      );
      setLocked(body.locked_model ?? null);
      setLockedPick({ cat, band, cell });
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("beat.lockFailed"));
    } finally {
      setBusy(false);
    }
  }

  const streak = mine?.length ?? 0;

  return (
    <div className="reading px-6 pb-24 pt-12">
      <h1 className="display text-4xl">{t("beat.title")}</h1>
      <p className="mt-2 max-w-[60ch] leading-relaxed text-ink-soft">{t("beat.intro")}</p>
      <details className="mt-3 max-w-[60ch] text-sm text-ink-soft">
        <summary className="cursor-pointer text-ink underline-offset-4 hover:underline">{t("beat.howTitle")}</summary>
        <p className="mt-2 leading-relaxed">{t("beat.how")}</p>
      </details>

      {offline && (
        <div className="mt-4">
          <OfflineNote />
        </div>
      )}
      {err && (
        <div className="mt-4">
          <ErrorNote message={err} onRetry={() => setErr(null)} />
        </div>
      )}

      <form onSubmit={onSubmit} className="mt-8 space-y-6">
        <Segmented label={t("beat.drought")} options={CATEGORIES} value={cat} onChange={setCat} />
        <Segmented label={t("beat.fire")} options={BANDS} value={band} onChange={setBand} />
        <div className="flex flex-wrap items-center gap-3">
          <Action type="submit" busy={busy} disabled={!where}>
            {locked ? t("beat.lockAnother") : t("beat.lock")}
          </Action>
          <span className="text-sm text-ink-soft">
            {where ? (
              <>
                {t("beat.forCell", { area: domainLabel(where.domain) })}{" "}
                <span className="num text-ink">
                  {where.lat.toFixed(2)}, {where.lon.toFixed(2)}
                </span>
                .{" "}
                <a href="/" className="text-spruce underline underline-offset-2">
                  {t("beat.pickAnother")}
                </a>
              </>
            ) : (
              t("beat.finding")
            )}
          </span>
        </div>
      </form>

      {/* One deliberate reveal: the model's number is hidden until the pick is locked. */}
      <AnimatePresence>
        {locked && lockedPick && lockedPick.cell === cell && (
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={instant ? { duration: 0 } : { duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="mt-8"
          >
            <Panel>
              <p className="text-sm font-medium text-ink">{t("beat.modelSaid")}</p>
              <div className="mt-3 grid grid-cols-2 gap-4">
                <div data-testid="reveal-drought">
                  <Numeral
                    value={
                      locked.drought_likely !== null && locked.drought_likely !== undefined
                        ? (CATEGORIES.find((c) => c.value === locked.drought_likely)?.label ?? t("card.notShown"))
                        : t("card.notShown")
                    }
                    tone="ochre"
                    size="xl"
                  />
                  <p className="mt-1 text-xs text-ink-soft">
                    {t("beat.droughtLikely")}
                    {locked.drought_likely_p !== null && locked.drought_likely_p !== undefined
                      ? t("beat.chance", { p: Math.round(locked.drought_likely_p * 100) })
                      : ""}
                  </p>
                  {locked.drought_note ? (
                    <p className="mt-1 text-[11px] leading-relaxed text-mute" data-testid="drought-note">
                      {lang === "es" || locked.drought_note.startsWith("some of the model")
                        ? t("beat.noteUnchecked")
                        : `${locked.drought_note.charAt(0).toUpperCase() + locked.drought_note.slice(1)}.`}
                    </p>
                  ) : null}
                  <p className="mt-2 text-xs text-ink" data-testid="compare-drought">
                    {t("beat.you", { pick: CATEGORIES.find((c) => c.value === lockedPick.cat)?.label ?? "" })}{" "}
                    {locked.drought_likely === lockedPick.cat ? t("beat.same") : t("beat.different")}
                  </p>
                </div>
                <div data-testid="reveal-fire">
                  <Numeral
                    value={
                      locked.point !== null && locked.point !== undefined
                        ? bandLabel(fireBandFor(locked.point).value)
                        : t("card.notShown")
                    }
                    tone="ember"
                    size="xl"
                  />
                  <p className="mt-1 text-xs text-ink-soft">
                    {t("beat.fireBand")}
                    {locked.point !== null && locked.point !== undefined
                      ? t("beat.dryness", { v: locked.point.toFixed(0) })
                      : ""}
                  </p>
                  <p className="mt-2 text-xs text-ink" data-testid="compare-fire">
                    {t("beat.you", { pick: bandLabel(lockedPick.band) })}{" "}
                    {locked.point !== null && locked.point !== undefined && fireBandFor(locked.point).value === lockedPick.band
                      ? t("beat.same")
                      : t("beat.different")}
                  </p>
                </div>
              </div>
              {cat !== lockedPick.cat || band !== lockedPick.band ? (
                <p className="mt-4 text-xs leading-relaxed text-ochre" data-testid="pick-changed">
                  {t("beat.changed")}
                </p>
              ) : null}
            </Panel>
          </motion.div>
        )}
      </AnimatePresence>

      <h2 className="mt-12 text-lg font-medium">{t("beat.yourPicks")}</h2>
      <div className="mt-3">
        {mine === null ? (
          <Skeleton rows={2} />
        ) : streak === 0 ? (
          <EmptyState title={t("beat.noPicks")} body={t("beat.noPicksBody")} />
        ) : (
          <Panel>
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2" data-testid="pick-summary">
              <span className="flex items-baseline gap-2">
                <Numeral value={streak} size="xl" />
                <span className="text-sm text-ink-soft">{streak === 1 ? t("beat.pick") : t("beat.picks")}</span>
              </span>
              <span className="flex items-baseline gap-2">
                <Numeral value={mine.filter((m) => m.status === "scored").length} size="xl" />
                <span className="text-sm text-ink-soft">{t("beat.scored")}</span>
              </span>
              <span className="flex items-baseline gap-2">
                <Numeral value={mine.reduce((a, m) => a + (m.points ?? 0), 0)} size="xl" tone="ember" />
                <span className="text-sm text-ink-soft">{t("beat.points")}</span>
              </span>
            </div>
            <ul className="mt-4 divide-y divide-rule text-sm" data-testid="pick-list">
              {mine.slice(0, 10).map((m) => (
                <li key={m.id} className="py-2" data-testid={`pick-${m.status}`}>
                  <span className="text-ink">
                    {t("beat.pickLine", {
                      cat: CATEGORIES.find((c) => c.value === m.drought_category)?.label ?? "",
                      band: bandLabel(m.fire_band).toLowerCase(),
                    })}
                  </span>
                  <span className="text-mute">{t("beat.forWeek", { week: m.target_week })}</span>
                  {m.status === "pending" ? (
                    <span className="block text-xs text-ink-soft">{t("beat.pending")}</span>
                  ) : (
                    <span className="block text-xs text-ink-soft">
                      {t("beat.scoredLine", {
                        cat: CATEGORIES.find((c) => c.value === m.actual_category)?.label ?? "",
                        dr: m.drought_correct ? t("beat.right") : t("beat.wrong"),
                        band: bandLabel(m.actual_band).toLowerCase(),
                        v: m.actual_dryness?.toFixed(0) ?? "",
                        fr: m.fire_correct ? t("beat.right") : t("beat.wrong"),
                        n: m.points ?? 0,
                        pts: m.points === 1 ? t("beat.point") : t("beat.points"),
                      })}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </div>

      <h2 className="mt-10 text-lg font-medium">{t("beat.board")}</h2>
      <p className="mt-1 text-xs text-ink-soft">{t("beat.boardNote")}</p>
      <div className="mt-3">
        {board === null ? (
          <Skeleton rows={3} />
        ) : board.length === 0 ? (
          <EmptyState title={t("beat.nobody")} body={t("beat.nobodyBody")} />
        ) : (
          <ul className="divide-y divide-rule rounded-lg border border-rule">
            {board.slice(0, 8).map((r, i) => (
              <li key={r.device_id} className="flex items-center justify-between px-4 py-3">
                <span className="flex items-center gap-3">
                  <Numeral value={i + 1} size="sm" tone="mute" />
                  <span className="font-mono text-sm">
                    {r.device_id === me || me.startsWith(r.device_id) ? t("beat.youRow") : t("beat.player", { id: r.device_id.slice(0, 4) })}
                  </span>
                </span>
                <span className="text-right text-xs text-ink-soft">
                  <Numeral value={r.points} size="sm" /> {t("beat.points")}
                  <span className="block">{t("beat.scoredOf", { s: r.scored, n: r.picks })}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function BeatPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-xl px-4 pt-6"><Skeleton rows={5} /></div>}>
      <BeatInner />
    </Suspense>
  );
}
