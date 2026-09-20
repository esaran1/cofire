"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MapView } from "@/components/MapView";
import { PlaceCard } from "@/components/PlaceCard";
import { TimeScrubber } from "@/components/TimeScrubber";
import { API, Place, getJson } from "@/lib/api";
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

  useEffect(() => {
    getJson<{ issues: string[] }>("/forecast/issues")
      .then((d) => {
        setIssues(d.issues);
        setIssue(d.issues[d.issues.length - 1] ?? "");
      })
      .catch((e: Error) => setErr(e.message));
    getJson<{ resolution_m: number }>("/meta")
      .then((d) => setResolutionM(d.resolution_m || 4000))
      .catch(() => undefined);
  }, []);

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
      <div className="absolute top-3 left-3 z-20 text-xs bg-ink/80 px-2 py-1 rounded">
        {place?.resolution_m ?? resolutionM} m cells · fire-spread conditions, not ignitions
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
