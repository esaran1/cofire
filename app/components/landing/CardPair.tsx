"use client";

import { useState } from "react";
import { PlaceCard } from "@/components/PlaceCard";
import { PlaceSchema } from "@/lib/schemas";
import story from "@/lib/story.json";

/**
 * The idea of the whole app, shown through the app.
 *
 * Two real Place Cards for real cells from the latest issue. One is in a place
 * and range where the forecast is sharper than history, so it draws a range.
 * The other is not, so it says so and shows the historical range instead. The
 * reader sees the difference instead of being told about it.
 *
 * The cells are chosen by `cofire.ship.story`, which refuses to build if either
 * card would claim a rendering state the export does not produce. Both payloads
 * are validated through PlaceSchema, the same schema the map uses.
 */

const LABELS: Record<string, { head: string; body: string }> = {
  interval: {
    head: "Sharper than history",
    body: "So it draws a forecast range.",
  },
  historical_range: {
    head: "No sharper than history",
    body: "So it says so, and shows what is typical instead.",
  },
};

function EmbeddedCard({ state }: { state: "interval" | "historical_range" }) {
  const entry = story.cards[state];
  const place = PlaceSchema.parse(entry.place);
  const [horizon, setHorizon] = useState(entry.horizon);
  const label = LABELS[state];
  return (
    <div>
      <p className="text-ink text-lg font-medium">{label.head}</p>
      <p className="text-ink-soft mt-1">{label.body}</p>
      {/* Clipped with a fade so the card reads as a picture of the product,
          not a second page. The part that carries the argument, the band, is
          at the top and always visible. */}
      <div className="relative mt-6 max-h-[23rem] overflow-hidden [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
        <PlaceCard place={place} horizon={horizon} onHorizon={setHorizon} embedded />
      </div>
    </div>
  );
}

export function CardPair() {
  return (
    <div className="grid gap-12 md:grid-cols-2 md:gap-10">
      <EmbeddedCard state="interval" />
      <EmbeddedCard state="historical_range" />
    </div>
  );
}
