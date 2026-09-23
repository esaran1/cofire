"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Check } from "@phosphor-icons/react";
import { Segmented } from "@/components/ui/Controls";
import { DROUGHT_CATEGORIES, OBSERVATION_TYPES } from "@/lib/options";
import story from "@/lib/story.json";

/**
 * What a reader can do with a forecast, shown as working miniatures.
 *
 * Each preview uses the real control from its screen, with the real options,
 * so trying it here is trying the feature. Nothing is submitted from the
 * landing page; the link carries the reader to the screen that does.
 *
 * Layout is deliberately unequal: Harden leads, because acting on a bad
 * outlook is the point, and the other two stack beside it.
 */

function Tile({
  verb,
  line,
  href,
  children,
  large = false,
}: {
  verb: string;
  line: string;
  href: string;
  children: React.ReactNode;
  large?: boolean;
}) {
  return (
    <div className={`bg-paper flex flex-col p-7 md:p-10 ${large ? "lg:col-span-3" : ""}`}>
      <h4 className={`display ${large ? "text-4xl md:text-5xl" : "text-3xl"}`}>{verb}</h4>
      <p className="text-ink-soft mt-2 max-w-[40ch]">{line}</p>
      <div className="mt-8 flex-1">{children}</div>
      <Link
        href={href}
        className="text-ember mt-8 inline-flex items-center gap-1.5 text-sm font-medium"
      >
        Open {verb.toLowerCase()}
        <ArrowRight size={15} weight="bold" />
      </Link>
    </div>
  );
}

function HardenPreview() {
  const [done, setDone] = useState<Record<string, boolean>>({});
  const n = Object.values(done).filter(Boolean).length;
  const items = story.quick_wins;
  return (
    <div>
      <ul className="space-y-2">
        {items.map((i) => {
          const on = !!done[i.id];
          return (
            <li key={i.id}>
              <button
                onClick={() => setDone((d) => ({ ...d, [i.id]: !d[i.id] }))}
                aria-pressed={on}
                className="border-rule hover:bg-paper-sunk flex w-full items-center gap-3 border px-4 py-3 text-left transition-colors active:scale-[0.99]"
              >
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center border transition-colors ${
                    on ? "border-ember bg-ember text-paper" : "border-rule"
                  }`}
                >
                  {on ? <Check size={13} weight="bold" /> : null}
                </span>
                <span className={on ? "text-mute line-through" : "text-ink"}>{i.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="text-mute mt-4 text-sm">
        <span className="num text-ink">{n}</span> of {items.length} free actions done
      </p>
    </div>
  );
}

function PredictPreview() {
  const [v, setV] = useState(2);
  return (
    <Segmented
      options={DROUGHT_CATEGORIES}
      value={v}
      onChange={setV}
      label="Your call for 4 weeks out"
      tone="ochre"
    />
  );
}

function ObservePreview() {
  const [v, setV] = useState("lawn_crispy");
  return (
    <Segmented options={OBSERVATION_TYPES} value={v} onChange={setV} label="What you saw" tone="ochre" />
  );
}

export function ActPreviews() {
  return (
    <div className="bg-rule grid gap-px overflow-hidden border border-rule lg:grid-cols-5">
      <Tile verb="Harden" line="Turn a bad outlook into a checklist for your property." href="/ember" large>
        <HardenPreview />
      </Tile>
      <div className="bg-rule grid gap-px lg:col-span-2">
        <Tile verb="Predict" line="Lock your call before the model shows its own." href="/beat">
          <PredictPreview />
        </Tile>
        <Tile verb="Observe" line="Report what the satellite cannot see." href="/observe">
          <ObservePreview />
        </Tile>
      </div>
    </div>
  );
}
