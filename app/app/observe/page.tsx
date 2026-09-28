"use client";

import { OBSERVATION_TYPES } from "@/lib/options";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { API, Observation, getParsed, postParsed } from "@/lib/api";
import { ObservationAckSchema, ObservationSchema } from "@/lib/schemas";
import { resolvePlace } from "@/lib/data";
import { domainLabel, useDomain } from "@/lib/domain";
import { Adopted, readAdopted } from "@/lib/adopted";
import type { ObservationCell } from "@/lib/schemas";
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
  // What happened to the last report: attached to a cell, or outside both areas.
  const [filed, setFiled] = useState<{ cell: ObservationCell | null } | null>(null);
  const [locating, setLocating] = useState(false);
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

  // Default to a real forecast cell. The map's centre sits between the two
  // counties, where there is no forecast, so it used to be the default point
  // and every report filed without editing it landed outside both areas.
  // Asking the API for the nearest cell to the centre snaps to one that exists.
  const [domain, , ready] = useDomain();
  const [adopted, setAdopted] = useState<Adopted[]>([]);
  useEffect(() => setAdopted(readAdopted()), []);
  const [explicit] = useState(() => !!(params.get("lat") && params.get("lon")));
  useEffect(() => {
    // Default to the cell nearest the chosen area's centre, and follow the area
    // when it changes, unless the link named a point.
    if (!ready || explicit) return;
    resolvePlace(domain)
      .then((p) => {
        setLat(p.lat.toFixed(3));
        setLon(p.lon.toFixed(3));
      })
      .catch(() => undefined);
  }, [domain, ready, explicit]);

  useEffect(() => {
    load();
  }, [load]);

  function useMyLocation() {
    if (!("geolocation" in navigator)) {
      setErr("This browser cannot share its location. Enter coordinates instead.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude.toFixed(3));
        setLon(pos.coords.longitude.toFixed(3));
        setLocating(false);
      },
      () => {
        setErr("Location was not shared. Enter coordinates instead.");
        setLocating(false);
      },
      { enableHighAccuracy: false, timeout: 8000 },
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    // Check the location here: the service rejects anything that is not a
    // number, and its error is not written for a reader.
    const la = Number(lat), lo = Number(lon);
    if (!lat.trim() || !lon.trim() || !Number.isFinite(la) || !Number.isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) {
      setErr("Enter the location as decimal degrees: latitude north and longitude west of Greenwich, which is negative in Colorado.");
      return;
    }
    setBusy(true);
    try {
      const body = await postParsed(
        "/observations",
        { device_id: deviceId(), lat: Number(lat), lon: Number(lon), type, note, photo_path: photo },
        ObservationAckSchema,
      );
      setFiled({ cell: body.cell ?? null });
      setNote("");
      setPhoto("");
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not file that report.");
    } finally {
      setBusy(false);
    }
  }

  // Your own reports. The rank used to count every report in the database,
  // so a new visitor inherited everyone else's total.
  const me = deviceId();
  const count = rows?.filter((r) => r.device_id === me).length ?? 0;
  const rank = count >= 12 ? "Sentinel" : count >= 4 ? "Ranger" : count >= 1 ? "Scout" : "Not ranked yet";

  return (
    <div className="reading px-6 pb-24 pt-12">
      <h1 className="display text-4xl">Observer Streaks</h1>
      <p className="mt-2 leading-relaxed text-ink-soft">
        Report what the satellite cannot see. Reports are logged against their forecast cell for
        anyone reading it. They do not change the forecast.
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
            className="rounded-lg border border-rule bg-paper-raised px-3 py-2 text-ink placeholder:text-mute focus:border-ember focus:outline-none focus:ring-1 focus:ring-ember"
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
            className="text-sm text-mute file:mr-3 file:rounded-full file:border-0 file:bg-paper-sunk file:px-4 file:py-2 file:text-sm file:text-ink hover:file:bg-rule"
          />
          <p className="text-xs text-ink-soft">Optional. Stored on this device for the demo.</p>
        </div>

        {adopted.length > 0 ? (
          <div className="flex flex-col gap-2" data-testid="adopted-picks">
            <p className="text-sm font-medium text-ink">Your adopted cells</p>
            <div className="flex flex-wrap gap-2">
              {adopted.map((a) => (
                <button
                  key={`${a.domain}-${a.cell_id}`}
                  type="button"
                  onClick={() => {
                    setLat(a.lat.toFixed(3));
                    setLon(a.lon.toFixed(3));
                  }}
                  className="rounded-full border border-rule bg-paper-raised px-3 py-1.5 text-xs text-ink hover:border-ember"
                >
                  {domainLabel(a.domain)} {a.lat.toFixed(2)}, {a.lon.toFixed(2)}
                </button>
              ))}
            </div>
          </div>
        ) : null}

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
              className="rounded-lg border border-rule bg-paper-raised px-3 py-2 font-mono text-ink focus:border-ember focus:outline-none focus:ring-1 focus:ring-ember"
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
              className="rounded-lg border border-rule bg-paper-raised px-3 py-2 font-mono text-ink focus:border-ember focus:outline-none focus:ring-1 focus:ring-ember"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Action type="submit" busy={busy} disabled={!lat || !lon}>
            File this report
          </Action>
          <button
            type="button"
            onClick={useMyLocation}
            disabled={locating}
            className="rounded-full border border-rule px-5 py-2.5 text-sm text-ink transition-colors hover:bg-paper-sunk active:scale-[0.98] disabled:opacity-60"
          >
            {locating ? "Finding you" : "Use my location"}
          </button>
        </div>
      </form>

      {/* What happened to the report, stated plainly. There used to be an
          "effect on this cell" here built from a hardcoded constant; the model
          does not read reports, so the honest thing to show is where it went. */}
      <AnimatePresence>
        {filed && (
          <motion.div
            initial={reduce ? false : { y: 12 }}
            animate={{ y: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="mt-8"
            role="status"
          >
            <Panel>
              <p className="text-sm font-medium text-ink">Report filed</p>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                {filed.cell
                  ? `Logged against the ${filed.cell.domain ? filed.cell.domain.charAt(0).toUpperCase() + filed.cell.domain.slice(1) : ""} cell at ${filed.cell.lat.toFixed(2)}, ${filed.cell.lon.toFixed(2)}. Anyone reading that cell will see it.`
                  : "Logged. This point is outside both forecast areas, so it is not attached to a forecast cell."}
              </p>
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
            body="File the first one above. Reports from this area show here with their location and type."
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
