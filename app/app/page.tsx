"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { set } from "idb-keyval";
import { MapCell, MapView } from "@/components/MapView";
import { PlaceCard } from "@/components/PlaceCard";
import { TimeScrubber } from "@/components/TimeScrubber";
import { ErrorNote } from "@/components/ui/Controls";
import type { Place } from "@/lib/api";
import { getBundle, getDomains, nearestCell, placeFromCell } from "@/lib/data";
import { useDomain } from "@/lib/domain";
import { Adopted, readAdopted, toggleAdopted } from "@/lib/adopted";
import type { Bundle, DomainsIndex } from "@/lib/schemas";

export default function HomePage() {
  const router = useRouter();
  const [domain, , ready] = useDomain();
  const [index, setIndex] = useState<DomainsIndex | null>(null);
  const [issue, setIssue] = useState("");
  const [horizon, setHorizon] = useState("4");
  const [layer, setLayer] = useState<"drought" | "fire">("fire");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [adopted, setAdopted] = useState<Adopted[]>([]);
  // Settings named in the link (the Hindcast page's replay link, a shared URL):
  // read once, after the page mounts, then kept in the URL as they change.
  const [linked, setLinked] = useState<{ issue?: string; cell?: string } | null>(null);
  // The linked cell applies to the first load only; after that the card follows
  // the reader's clicks and area changes.
  const linkedCell = useRef<string | undefined>(undefined);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const h = q.get("horizon");
    if (h === "2" || h === "4" || h === "8") setHorizon(h);
    const l = q.get("layer");
    if (l === "fire" || l === "drought") setLayer(l);
    linkedCell.current = q.get("cell") ?? undefined;
    setLinked({ issue: q.get("issue") ?? undefined, cell: linkedCell.current });
    setAdopted(readAdopted());
  }, []);

  useEffect(() => {
    if (!linked) return;
    getDomains()
      .then((d) => {
        setIndex(d);
        const wanted = linked.issue && d.issues.includes(linked.issue) ? linked.issue : "";
        setIssue((cur) => cur || wanted || d.issues[d.issues.length - 1] || "");
      })
      .catch((e: Error) => setErr(e.message));
  }, [linked]);

  // Keep the URL describing what is on screen, so a link or Back returns here.
  useEffect(() => {
    if (!ready || !issue) return;
    const url = new URL(window.location.href);
    url.searchParams.set("domain", domain);
    url.searchParams.set("issue", issue);
    url.searchParams.set("horizon", horizon);
    url.searchParams.set("layer", layer);
    if (place && place.domain === domain) url.searchParams.set("cell", place.cell_id);
    else url.searchParams.delete("cell");
    window.history.replaceState(window.history.state, "", url.toString());
  }, [ready, domain, issue, horizon, layer, place]);

  const meta = index?.domains[domain] ?? null;

  // Load the area's forecast, and open the card on the cell nearest its centre
  // so the page never lands on an empty map.
  useEffect(() => {
    if (!ready || !index || !issue) return;
    let live = true;
    getBundle(domain, issue)
      .then((b) => {
        if (!live) return;
        setBundle(b);
        // Read and clear outside the updater: React may run an updater twice.
        const fromLink = linkedCell.current?.match(/^(-?[\d.]+)_(-?[\d.]+)$/);
        linkedCell.current = undefined;
        setPlace((prev) => {
          const m = index.domains[domain];
          const anchor =
            prev && prev.domain === domain
              ? [prev.lat, prev.lon]
              : fromLink
                ? [Number(fromLink[1]), Number(fromLink[2])]
                : [m.center[1], m.center[0]];
          const c = nearestCell(b, anchor[0], anchor[1]);
          return c ? placeFromCell(b, c, index.history_years) : null;
        });
      })
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, [ready, index, domain, issue]);

  const onClick = useCallback(
    (lat: number, lon: number) => {
      if (!bundle || !index) return;
      const c = nearestCell(bundle, lat, lon);
      // A click well outside the area's cells selects nothing.
      if (!c || Math.abs(c.lat - lat) > 0.05 || Math.abs(c.lon - lon) > 0.05) return;
      const p = placeFromCell(bundle, c, index.history_years);
      setPlace(p);
      void set("last_place", p).catch(() => undefined);
    },
    [bundle, index],
  );

  const cells: MapCell[] = useMemo(() => {
    if (!bundle) return [];
    const ti = bundle.targets.indexOf(`d_ge2_h${horizon}`);
    return bundle.cells.map((c) => ({
      id: c.id,
      lat: c.lat,
      lon: c.lon,
      value: layer === "fire" ? (c.h[horizon]?.[0] ?? null) : ti >= 0 && c.p[ti] !== null ? (c.p[ti] as number) * 100 : null,
    }));
  }, [bundle, horizon, layer]);

  return (
    <div className="grid h-[calc(100dvh-4.0625rem)] grid-rows-[55dvh_1fr] overflow-hidden lg:grid-cols-[24rem_1fr] lg:grid-rows-1">
      <aside className="row-start-2 overflow-y-auto border-t border-rule bg-paper-raised lg:col-start-1 lg:row-start-1 lg:border-r lg:border-t-0">
        <div className="p-6 pb-0">
          <h1 className="display text-2xl" data-testid="map-title">
            {meta?.label ?? "Loading"}
          </h1>
          {meta ? <p className="mt-1 text-sm leading-relaxed text-ink-soft">{meta.note}</p> : null}
          <p className="mt-2 text-xs leading-relaxed text-mute">
            Drought and the conditions that let fire spread, 2 to 8 weeks ahead. Not a forecast of ignitions.
          </p>
          {err && (
            <div className="mt-4">
              <ErrorNote message={err} onRetry={() => setErr(null)} />
            </div>
          )}
        </div>

        {place ? (
          <PlaceCard
            place={place}
            meta={meta}
            sources={bundle?.sources ?? {}}
            horizon={horizon}
            onHorizon={setHorizon}
            onClose={() => setPlace(null)}
            adopted={adopted.some((a) => a.cell_id === place.cell_id && a.domain === domain)}
            onAdopt={() =>
              setAdopted(toggleAdopted({ cell_id: place.cell_id, domain, lat: place.lat, lon: place.lon }))
            }
            onPredict={() => router.push(`/beat?cell=${place.cell_id}&domain=${domain}`)}
            onReport={() => router.push(`/observe?lat=${place.lat}&lon=${place.lon}&domain=${domain}`)}
          />
        ) : (
          <p className="px-6 pt-5 text-sm text-mute">Select a cell on the map to see its forecast.</p>
        )}
      </aside>

      <div className="relative row-start-1 min-h-0 lg:col-start-2 lg:row-start-1">
        <MapView cells={cells} bbox={meta?.bbox ?? null} layer={layer} selectedId={place?.cell_id} onClick={onClick} />
        <TimeScrubber
          issues={index?.issues ?? []}
          issue={issue}
          horizon={horizon}
          layer={layer}
          onIssue={setIssue}
          onHorizon={setHorizon}
          onLayer={setLayer}
        />
      </div>
    </div>
  );
}
