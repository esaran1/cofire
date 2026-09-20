"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MapView } from "@/components/MapView";
import { PlaceCard } from "@/components/PlaceCard";
import { TimeScrubber } from "@/components/TimeScrubber";
import { UncertaintyChip } from "@/components/UncertaintyBadge";
import { API, Place, UncertaintyStatus, getJson } from "@/lib/api";
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
    getJson<{ issues: string[] }>("/forecast/issues")
      .then((d) => {
        setIssues(d.issues);
        setIssue(d.issues[d.issues.length - 1] ?? "");
      })
      .catch((e: Error) => setErr(e.message));
    getJson<{ resolution_m: number; resolution_note: string; shipping_arm: string }>("/meta")
      .then((d) => {
        setResolutionM(d.resolution_m || 4000);
        setResolutionNote(d.resolution_note ?? "");
        setShippingArm(d.shipping_arm ?? "");
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    getJson<UncertaintyStatus>(`/uncertainty/status${issue ? `?issue=${issue}` : ""}`)
      .then(setUnc)
      .catch(() => setUnc(null));
  }, [issue]);

  const onClick = useCallback(
    async (lat: number, lon: number) => {
      try {
        const q = `/forecast?lat=${lat}&lon=${lon}${issue ? `&issue=${issue}` : ""}`;
        const p = await getJson<Place>(q);
        setPlace(p);
        await set("last_place", p);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "forecast failed");
      }
    },
    [issue],
  );

  return (
    <div className="relative h-[100dvh]">
      <MapView issue={issue} horizon={horizon} layer={layer} onClick={onClick} />
      <div className="absolute top-3 left-3 z-20 text-xs bg-ink/85 px-3 py-2 rounded-lg max-w-[19rem] leading-relaxed">
        <div className="text-paper">
          Shipping resolution {place?.resolution_m ?? resolutionM} m · issued {issue || "-"}
        </div>
        <div className="text-mute">
          Forecast of conditions that allow fires to spread, not of ignitions.
        </div>
        {resolutionNote && <div className="text-mute mt-0.5">{resolutionNote}</div>}
        {shippingArm && <div className="text-mute mt-0.5">Arm: {shippingArm}</div>}
        {unc?.available && (
          <div className="mt-1.5 flex items-center gap-1.5">
            <UncertaintyChip status={unc.status} />
            <span className="text-mute">
              {unc.status === "uncalibrated"
                ? "intervals hidden"
                : unc.status === "extrapolating"
                  ? `intervals widened ${unc.widen_factor.toFixed(2)}×`
                  : "intervals calibrated"}
            </span>
          </div>
        )}
      </div>
      {err && <p className="absolute top-12 left-3 z-20 text-fire text-sm">{err}</p>}
      <TimeScrubber
        issues={issues}
        issue={issue}
        horizon={horizon}
        layer={layer}
        onIssue={setIssue}
        onHorizon={setHorizon}
        onLayer={setLayer}
      />
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
