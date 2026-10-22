"use client";

import { useT } from "@/lib/i18n";
import { useState } from "react";
import { PlaceCard } from "@/components/PlaceCard";
import { PlaceSchema } from "@/lib/schemas";
import story from "@/lib/story.json";

/**
 * The idea of the whole app, shown through one real Place Card.
 *
 * The card is for a real cell from the latest issue, validated through
 * PlaceSchema. Beside it, three notes point at what the card does: it shows a
 * point forecast, it withholds the forecast band because no band has held up
 * in real time, and it separates the probabilities it will stand behind per
 * cell from the ones where it falls back to how often the event happens in the
 * county at this time of year.
 *
 * The counts in the notes come from the card itself, via cofire.ship.story,
 * which refuses to build if the cell stops carrying both kinds of row.
 */

export function CardPair() {
  const { t } = useT();
  const entry = story.card;
  const place = PlaceSchema.parse(entry.place);
  const [horizon, setHorizon] = useState(entry.horizon);

  const notes = [
    {
      head: t("land.card1h"),
      body: t("land.card1b"),
    },
    {
      head: t("land.card2h"),
      body: t("land.card2b"),
    },
    {
      head: t("land.card3h", { p: entry.n_probability, b: entry.n_base_rate }),
      body: t("land.card3b"),
    },
  ];

  return (
    <div className="grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-20">
      <ol className="order-2 space-y-10 lg:order-1">
        {notes.map((n, i) => (
          <li key={n.head} className="grid grid-cols-[2.5rem_1fr] gap-4">
            <span className="display text-3xl leading-none text-mute">{i + 1}</span>
            <div>
              <p className="text-ink text-lg font-medium md:text-xl">{n.head}</p>
              <p className="text-ink-soft mt-1.5 leading-relaxed">{n.body}</p>
            </div>
          </li>
        ))}
      </ol>
      {/* Clipped with a fade so the card reads as a picture of the product. */}
      <div className="relative order-1 max-h-[36rem] overflow-hidden [mask-image:linear-gradient(to_bottom,black_80%,transparent)] lg:order-2">
        <PlaceCard place={place} horizon={horizon} onHorizon={setHorizon} embedded />
      </div>
    </div>
  );
}
