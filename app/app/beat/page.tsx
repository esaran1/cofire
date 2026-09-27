"use client";

import { DROUGHT_CATEGORIES, FIRE_BANDS } from "@/lib/options";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { API, LeaderRow, getParsed, postParsed } from "@/lib/api";
import { LeaderRowSchema, PredictionSchema } from "@/lib/schemas";
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

type Pick = { cell_id: string; horizon: number; drought_category: number; fire_band: string; issue: string };
type Locked = { drought_point?: number | null; fire_index?: number | null };

function BeatInner() {
  const params = useSearchParams();
  const reduce = useReducedMotion();
  const [cell, setCell] = useState(params.get("cell") ?? "");
  const [cat, setCat] = useState(2);
  const [band, setBand] = useState("high");
  const [locked, setLocked] = useState<Locked | null>(null);
  const [mine, setMine] = useState<Pick[] | null>(null);
  const [board, setBoard] = useState<LeaderRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    const id = deviceId();
    getParsed(`/predictions/me?device_id=${id}`, z.array(z.object({ id: z.string().nullish() }).passthrough()))
      .then((d) => {
        setMine(d as unknown as Pick[]);
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
      setLocked((body.locked_model ?? {}) as Locked);
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
        Lock your call for 4 weeks out before you see the model&apos;s. Both are scored against
        what actually happens once those weeks arrive.
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
        {locked && (
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
                <div>
                  <Numeral
                    value={locked.drought_point !== null && locked.drought_point !== undefined ? locked.drought_point.toFixed(1) : "n/a"}
                    tone="ochre"
                    size="xl"
                  />
                  <p className="mt-1 text-xs text-ink-soft">drought category</p>
                </div>
                <div>
                  <Numeral
                    value={locked.fire_index !== null && locked.fire_index !== undefined ? locked.fire_index.toFixed(0) : "n/a"}
                    tone="ember"
                    size="xl"
                  />
                  <p className="mt-1 text-xs text-ink-soft">fire-spread index</p>
                </div>
              </div>
              <p className="mt-4 text-xs leading-relaxed text-ink-soft">
                You picked {CATEGORIES.find((c) => c.value === cat)?.label} and{" "}
                {BANDS.find((b) => b.value === band)?.label.toLowerCase()}. Neither number is scored
                yet.
              </p>
            </Panel>
          </motion.div>
        )}
      </AnimatePresence>

      <h2 className="mt-12 text-lg font-medium">Your streak</h2>
      <div className="mt-3">
        {mine === null ? (
          <Skeleton rows={2} />
        ) : streak === 0 ? (
          <EmptyState
            title="No picks yet"
            body="Lock a call above and it shows up here. Your streak counts consecutive weeks with a pick."
          />
        ) : (
          <Panel>
            <div className="flex items-baseline gap-3">
              <Numeral value={streak} size="xl" />
              <span className="text-sm text-ink-soft">{streak === 1 ? "pick locked" : "picks locked"}</span>
            </div>
          </Panel>
        )}
      </div>

      <h2 className="mt-10 text-lg font-medium">County leaderboard</h2>
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
                <Numeral value={r.picks} size="sm" />
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
