"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { MapView } from "@/components/MapView";
import { PlaceCard } from "@/components/PlaceCard";
import { TimeScrubber } from "@/components/TimeScrubber";
import { UncertaintyChip } from "@/components/UncertaintyBadge";
import { ErrorNote } from "@/components/ui/Controls";
import { API, Place, UncertaintyStatus, getParsed } from "@/lib/api";
import { IssuesSchema, MetaSchema, PlaceSchema, UncertaintySchema } from "@/lib/schemas";
import { set } from "idb-keyval";

export default function HomePage() {
  const router = useRouter();
  const [issues, setIssues] = useState<string[]>([]);
  const [issue, setIssue] = useState("");
  const [horizon, setHorizon] = useState("4");
  const [layer, setLayer] = useState<"drought" | "fire">("fire");
  const [place, setPlace] = useState<Place | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [resolutionM, setResolutionM] = useState(4000);
  const [resolutionNote, setResolutionNote] = useState("");
  const [shippingArm, setShippingArm] = useState("");
  const [unc, setUnc] = useState<UncertaintyStatus | null>(null);

  useEffect(() => {
    getParsed("/forecast/issues", IssuesSchema)
      .then((d) => {
        setIssues(d.issues);
        setIssue(d.issues[d.issues.length - 1] ?? "");
      })
      .catch((e: Error) => setErr(e.message));
    getParsed("/meta", MetaSchema)
      .then((d) => {
        setResolutionM(d.resolution_m || 4000);
        setResolutionNote(d.resolution_note ?? "");
        setShippingArm(d.shipping_arm ?? "");
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    getParsed(`/uncertainty/status${issue ? `?issue=${issue}` : ""}`, UncertaintySchema)
      .then(setUnc)
      .catch(() => setUnc(null));
  }, [issue]);

  const onClick = useCallback(
    async (lat: number, lon: number) => {
      try {
        const q = `/forecast?lat=${lat}&lon=${lon}${issue ? `&issue=${issue}` : ""}`;
        const p = await getParsed(q, PlaceSchema);
        setPlace(p);
        await set("last_place", p);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "forecast failed");
      }
    },
    [issue],
  );

  return (
    <div className="grid h-[calc(100dvh-4rem)] grid-rows-[1fr_auto] lg:grid-cols-[22rem_1fr] lg:grid-rows-1">
      {/* Reading panel. The map alone does not explain itself, so the state of
          the forecast lives beside it rather than in a box floating over it. */}
      <aside className="order-2 overflow-y-auto border-t border-rule bg-paper-raised lg:order-1 lg:border-r lg:border-t-0">
        <div className="p-6">
          <h1 className="display text-2xl">Fire-spread conditions</h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">
            Forecast of the conditions that let fire spread. Not a forecast of ignitions.
          </p>

          <dl className="mt-6 space-y-3 border-t border-rule pt-5 text-sm">
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-mute">Issued</dt>
              <dd className="num text-ink">{issue || "n/a"}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-mute">Cell size</dt>
              <dd className="num text-ink">{place?.resolution_m ?? resolutionM} m</dd>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-mute">Model</dt>
              <dd className="text-ink">{shippingArm || "n/a"}</dd>
            </div>
          </dl>

          {unc?.available && (
            <div className="mt-6 border-t border-rule pt-5">
              <UncertaintyChip status={unc.status} />
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                {unc.status === "uncalibrated"
                  ? "Intervals are hidden on this view. The calibration record does not support one for these conditions."
                  : unc.status === "extrapolating"
                    ? `Conditions run past the calibrated range, so intervals are widened ${unc.widen_factor.toFixed(2)}x and should be read as a floor.`
                    : "Conditions sit inside the range the intervals were checked against."}
              </p>
              <Link href="/about" className="mt-2 inline-block text-sm text-ember underline underline-offset-4">
                Why
              </Link>
            </div>
          )}

          {err && (
            <div className="mt-6">
              <ErrorNote message={err} onRetry={() => setErr(null)} />
            </div>
          )}

          <p className="mt-6 border-t border-rule pt-5 text-sm text-mute">
            Select a cell on the map to see its forecast and the drivers behind it.
          </p>
          {resolutionNote && <p className="mt-2 text-xs leading-relaxed text-mute">{resolutionNote}</p>}
        </div>
      </aside>

      <div className="relative order-1 min-h-[45dvh] lg:order-2">
        <MapView issue={issue} horizon={horizon} layer={layer} onClick={onClick} />
        <TimeScrubber
          issues={issues}
          issue={issue}
          horizon={horizon}
          layer={layer}
          onIssue={setIssue}
          onHorizon={setHorizon}
          onLayer={setLayer}
        />
      </div>

      {place && (
        <PlaceCard
          place={place}
          horizon={horizon}
          onHorizon={setHorizon}
          onClose={() => setPlace(null)}
          onAdopt={() => {
            const raw = window.localStorage.getItem("adopted") ?? "[]";
            const list = JSON.parse(raw) as string[];
            if (!list.includes(place.cell_id)) list.push(place.cell_id);
            window.localStorage.setItem("adopted", JSON.stringify(list));
          }}
          onPredict={() => router.push(`/beat?cell=${place.cell_id}`)}
          onReport={() => router.push(`/observe?lat=${place.lat}&lon=${place.lon}`)}
        />
      )}
      <span className="hidden">{API}</span>
    </div>
  );
}
