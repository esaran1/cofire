"use client";

import { DROUGHT_CATEGORIES, FIRE_BANDS, fireBandFor } from "@/lib/options";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { API, LeaderRow, getParsed, postParsed } from "@/lib/api";
import { LeaderRowSchema, PickSchema, PredictionSchema } from "@/lib/schemas";
import type { PickRow } from "@/lib/schemas";
import type { LockedModel } from "@/lib/schemas";
import { resolvePlace } from "@/lib/data";
import { domainLabel, useDomain } from "@/lib/domain";
import { z } from "zod";
import { deviceId } from "@/lib/device";
import {
  Action,
  EmptyState,
  ErrorNote,
  Numeral,
  OfflineNote,
  Panel,
  Segmented,
  Skeleton,
} from "@/components/ui/Controls";

const CATEGORIES = DROUGHT_CATEGORIES;
const BANDS = FIRE_BANDS;

// What the model said for the same cell and horizon (LockedModelSchema): the
// dryness percentile and the drought category it makes most likely.
type Locked = LockedModel;

function BeatInner() {
  const params = useSearchParams();
  const reduce = useReducedMotion();
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
      setErr(e instanceof Error ? e.message : "Could not lock your pick.");
    } finally {
      setBusy(false);
    }
  }

  const streak = mine?.length ?? 0;

  return (
    <div className="reading px-6 pb-24 pt-12">
      <h1 className="display text-4xl">Beat the Model</h1>
      <p className="mt-2 leading-relaxed text-ink-soft">
        Make your call for this cell 4 weeks out, lock it, then see the model&apos;s call for the same
        cell. The model&apos;s call comes from the forecast, so it does not change with your pick; pick
        another cell on the map to see a different one. Your pick is scored once the week arrives: a
        point if your drought category matches the drought map that week, and a point if your
        fire-spread band matches that week&apos;s dryness. The model&apos;s call is not scored, because
        2026 is the sealed test year and scoring the model against it would be another look.
      </p>

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
        <Segmented label="Drought category" options={CATEGORIES} value={cat} onChange={setCat} tone="ochre" />
        <Segmented label="Fire-spread condition" options={BANDS} value={band} onChange={setBand} />
        <div className="flex flex-wrap items-center gap-3">
          <Action type="submit" busy={busy} disabled={!where}>
            {locked ? "Lock another" : "Lock my pick"}
          </Action>
          <span className="text-sm text-ink-soft">
            {where ? (
              <>
                for the {domainLabel(where.domain)} cell at{" "}
                <span className="num text-ink">
                  {where.lat.toFixed(2)}, {where.lon.toFixed(2)}
                </span>
                .{" "}
                <a href="/" className="text-ember underline underline-offset-2">
                  Pick another on the map
                </a>
              </>
            ) : (
              "Finding the nearest forecast cell"
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
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="mt-8"
          >
            <Panel>
              <p className="text-sm font-medium text-ink">The model said</p>
              <div className="mt-3 grid grid-cols-2 gap-4">
                <div data-testid="reveal-drought">
                  <Numeral
                    value={
                      locked.drought_likely !== null && locked.drought_likely !== undefined
                        ? (CATEGORIES.find((c) => c.value === locked.drought_likely)?.label ?? "not shown")
                        : "not shown"
                    }
                    tone="ochre"
                    size="xl"
                  />
                  <p className="mt-1 text-xs text-ink-soft">
                    the model&apos;s most likely drought category in 4 weeks
                    {locked.drought_likely_p !== null && locked.drought_likely_p !== undefined
                      ? `, ${Math.round(locked.drought_likely_p * 100)}% chance`
                      : ""}
                  </p>
                  {locked.drought_note ? (
                    <p className="mt-1 text-[11px] leading-relaxed text-mute" data-testid="drought-note">
                      {locked.drought_note.charAt(0).toUpperCase() + locked.drought_note.slice(1)}.
                    </p>
                  ) : null}
                  <p className="mt-2 text-xs text-ink" data-testid="compare-drought">
                    You: {CATEGORIES.find((c) => c.value === lockedPick.cat)?.label}.{" "}
                    {locked.drought_likely === lockedPick.cat ? "Same as the model." : "Different from the model."}
                  </p>
                </div>
                <div data-testid="reveal-fire">
                  <Numeral
                    value={
                      locked.point !== null && locked.point !== undefined
                        ? `${fireBandFor(locked.point).label}`
                        : "not shown"
                    }
                    tone="ember"
                    size="xl"
                  />
                  <p className="mt-1 text-xs text-ink-soft">
                    the model&apos;s fire-spread band in 4 weeks
                    {locked.point !== null && locked.point !== undefined
                      ? `: dryness ${locked.point.toFixed(0)} out of 100, where 50 is typical`
                      : ""}
                  </p>
                  <p className="mt-2 text-xs text-ink" data-testid="compare-fire">
                    You: {BANDS.find((x) => x.value === lockedPick.band)?.label}.{" "}
                    {locked.point !== null && locked.point !== undefined && fireBandFor(locked.point).value === lockedPick.band
                      ? "Same as the model."
                      : "Different from the model."}
                  </p>
                </div>
              </div>
              {cat !== lockedPick.cat || band !== lockedPick.band ? (
                <p className="mt-4 text-xs leading-relaxed text-ember" data-testid="pick-changed">
                  You have changed your pick since you locked it. Press Lock another to lock the new one.
                </p>
              ) : null}
            </Panel>
          </motion.div>
        )}
      </AnimatePresence>

      <h2 className="mt-12 text-lg font-medium">Your picks</h2>
      <div className="mt-3">
        {mine === null ? (
          <Skeleton rows={2} />
        ) : streak === 0 ? (
          <EmptyState title="No picks yet" body="Lock a call above and it shows up here, then gets scored when its week arrives." />
        ) : (
          <Panel>
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2" data-testid="pick-summary">
              <span className="flex items-baseline gap-2">
                <Numeral value={streak} size="xl" />
                <span className="text-sm text-ink-soft">{streak === 1 ? "pick" : "picks"}</span>
              </span>
              <span className="flex items-baseline gap-2">
                <Numeral value={mine.filter((m) => m.status === "scored").length} size="xl" />
                <span className="text-sm text-ink-soft">scored</span>
              </span>
              <span className="flex items-baseline gap-2">
                <Numeral value={mine.reduce((a, m) => a + (m.points ?? 0), 0)} size="xl" tone="ember" />
                <span className="text-sm text-ink-soft">points</span>
              </span>
            </div>
            <ul className="mt-4 divide-y divide-rule text-sm" data-testid="pick-list">
              {mine.slice(0, 10).map((m) => (
                <li key={m.id} className="py-2" data-testid={`pick-${m.status}`}>
                  <span className="text-ink">
                    {CATEGORIES.find((c) => c.value === m.drought_category)?.label} and{" "}
                    {BANDS.find((x) => x.value === m.fire_band)?.label.toLowerCase()}
                  </span>
                  <span className="text-mute"> for the week of {m.target_week}</span>
                  {m.status === "pending" ? (
                    <span className="block text-xs text-ink-soft">Scored once that week&apos;s data is in.</span>
                  ) : (
                    <span className="block text-xs text-ink-soft">
                      It was {CATEGORIES.find((c) => c.value === m.actual_category)?.label} (
                      {m.drought_correct ? "right" : "wrong"}) and{" "}
                      {BANDS.find((x) => x.value === m.actual_band)?.label.toLowerCase()}, dryness{" "}
                      {m.actual_dryness?.toFixed(0)} ({m.fire_correct ? "right" : "wrong"}): {m.points}{" "}
                      {m.points === 1 ? "point" : "points"}.
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </div>

      <h2 className="mt-10 text-lg font-medium">Leaderboard</h2>
      <p className="mt-1 text-xs text-ink-soft">All areas together. Ranked by points from scored picks.</p>
      <div className="mt-3">
        {board === null ? (
          <Skeleton rows={3} />
        ) : board.length === 0 ? (
          <EmptyState title="Nobody has played yet" body="The first locked pick in this area starts the board." />
        ) : (
          <ul className="divide-y divide-rule rounded-lg border border-rule">
            {board.slice(0, 8).map((r, i) => (
              <li key={r.device_id} className="flex items-center justify-between px-4 py-3">
                <span className="flex items-center gap-3">
                  <Numeral value={i + 1} size="sm" tone="mute" />
                  <span className="font-mono text-sm">
                    {r.device_id === me || me.startsWith(r.device_id) ? "You" : `Player ${r.device_id.slice(0, 4)}`}
                  </span>
                </span>
                <span className="text-right text-xs text-ink-soft">
                  <Numeral value={r.points} size="sm" /> points
                  <span className="block">
                    {r.scored} of {r.picks} scored
                  </span>
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
