"use client";

import { OBSERVATION_TYPES } from "@/lib/options";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { API, Nudge, Observation, getParsed, postParsed } from "@/lib/api";
import { ObservationAckSchema, ObservationSchema, MetaSchema } from "@/lib/schemas";
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

const TYPES = OBSERVATION_TYPES;



function ObserveInner() {
  const params = useSearchParams();
  const reduce = useReducedMotion();
  const [lat, setLat] = useState(params.get("lat") ?? "");
  const [lon, setLon] = useState(params.get("lon") ?? "");
  const [type, setType] = useState("lawn_crispy");
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<string>("");
  const [nudge, setNudge] = useState<Nudge | null>(null);
  const [rows, setRows] = useState<Observation[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getParsed("/observations", z.array(ObservationSchema))
      .then((d) => {
        setRows(d);
        setOffline(false);
      })
      .catch(() => {
        setRows([]);
        setOffline(true);
      });
  }, []);

  useEffect(() => {
    if (!lat || !lon) {
      getParsed("/meta", MetaSchema)
        .then((m) => {
          if (m.center) {
            setLon(m.center[0].toFixed(3));
            setLat(m.center[1].toFixed(3));
          }
        })
        .catch(() => undefined);
    }
    load();
  }, [lat, lon, load]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const body = await postParsed(
        "/observations",
        { device_id: deviceId(), lat: Number(lat), lon: Number(lon), type, note, photo_path: photo },
        ObservationAckSchema,
      );
      setNudge(body.nudge ?? null);
      setNote("");
      setPhoto("");
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not file that report.");
    } finally {
      setBusy(false);
    }
  }

  const count = rows?.length ?? 0;
  const rank = count >= 12 ? "Sentinel" : count >= 4 ? "Ranger" : count >= 1 ? "Scout" : "n/a";

  return (
    <div className="reading px-6 pb-24 pt-12">
      <h1 className="display text-4xl">Observer Streaks</h1>
      <p className="mt-2 leading-relaxed text-ink-soft">
        What the satellite cannot see from orbit. Ground reports adjust the local forecast by a
        documented amount.
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
        <Segmented label="What did you see" options={TYPES} value={type} onChange={setType} tone="ochre" />

        <div className="flex flex-col gap-2">
          <label htmlFor="note" className="text-sm font-medium text-ink">
            Note
          </label>
          <textarea
            id="note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className="rounded-lg border border-rule bg-transparent px-3 py-2 text-paper placeholder:text-mute focus:border-ember focus:outline-none focus:ring-1 focus:ring-ember"
            placeholder="Optional detail, e.g. third week with no runoff"
          />
          <p className="text-xs text-ink-soft">Optional. Helps the next person reading this cell.</p>
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="photo" className="text-sm font-medium text-ink">
            Photo
          </label>
          <input
            id="photo"
            type="file"
            accept="image/*"
            onChange={(e) => setPhoto(e.target.files?.[0]?.name ?? "")}
            className="text-sm text-mute file:mr-3 file:rounded-full file:border-0 file:bg-white/10 file:px-4 file:py-2 file:text-sm file:text-paper"
          />
          <p className="text-xs text-ink-soft">Optional. Stored on this device for the demo.</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-2">
            <label htmlFor="lat" className="text-sm font-medium text-ink">
              Latitude
            </label>
            <input
              id="lat"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              inputMode="decimal"
              className="rounded-lg border border-rule bg-transparent px-3 py-2 font-mono text-paper focus:border-ember focus:outline-none focus:ring-1 focus:ring-ember"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label htmlFor="lon" className="text-sm font-medium text-ink">
              Longitude
            </label>
            <input
              id="lon"
              value={lon}
              onChange={(e) => setLon(e.target.value)}
              inputMode="decimal"
              className="rounded-lg border border-rule bg-transparent px-3 py-2 font-mono text-paper focus:border-ember focus:outline-none focus:ring-1 focus:ring-ember"
            />
          </div>
        </div>

        <Action type="submit" busy={busy} disabled={!lat || !lon}>
          File this report
        </Action>
      </form>

      {/* The delta is computed server-side from a documented feature weight. It is
          never decoration: if the API returns nothing, nothing is shown. */}
      <AnimatePresence>
        {nudge && (
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="mt-8"
          >
            <Panel>
              <p className="text-sm font-medium text-ink">Effect on this cell</p>
              <div className="mt-3 grid grid-cols-2 gap-4">
                <div>
                  <Numeral
                    value={`${nudge.delta_drought >= 0 ? "+" : ""}${nudge.delta_drought.toFixed(2)}`}
                    tone="ochre"
                    size="xl"
                  />
                  <p className="mt-1 text-xs text-ink-soft">drought category</p>
                </div>
                <div>
                  <Numeral
                    value={`${nudge.delta_fire >= 0 ? "+" : ""}${nudge.delta_fire.toFixed(1)}`}
                    tone="ember"
                    size="xl"
                  />
                  <p className="mt-1 text-xs text-ink-soft">fire-spread index</p>
                </div>
              </div>
              <p className="mt-4 text-xs leading-relaxed text-ink-soft">Source: {nudge.source}.</p>
            </Panel>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-12 grid grid-cols-2 gap-4">
        <Panel>
          <p className="text-sm font-medium text-ink">Rank</p>
          <p className="mt-2 text-2xl font-medium">{rank}</p>
        </Panel>
        <Panel>
          <p className="text-sm font-medium text-ink">Reports</p>
          <div className="mt-2">
            <Numeral value={count} size="xl" />
          </div>
        </Panel>
      </div>

      <h2 className="mt-10 text-lg font-medium">Recent reports</h2>
      <div className="mt-3">
        {rows === null ? (
          <Skeleton rows={3} />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No reports yet"
            body="File the first one above. Reports from this county show here with their location and type."
          />
        ) : (
          <ul className="divide-y divide-rule rounded-lg border border-rule">
            {rows.slice(-8).reverse().map((r) => (
              <li key={r.id} className="flex items-center justify-between px-4 py-3">
                <span className="text-sm">
                  {TYPES.find((t) => t.value === r.type)?.label ?? r.type}
                  {r.note && <span className="block text-xs text-ink-soft">{r.note}</span>}
                </span>
                <span className="font-mono text-xs text-ink-soft">
                  {Number(r.lat).toFixed(2)}, {Number(r.lon).toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function ObservePage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-xl px-4 pt-6"><Skeleton rows={5} /></div>}>
      <ObserveInner />
    </Suspense>
  );
}
