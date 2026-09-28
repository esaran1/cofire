import type { z } from "zod";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Every response is parsed at the boundary. A malformed or unexpectedly-null
 * field is surfaced here, where it can be defaulted, rather than thrown deep
 * inside a component where it takes the whole route down.
 */
export async function getParsed<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  const raw: unknown = await res.json();
  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    // Log the shape mismatch, then fail with a message a user can act on.
    console.error(`[api] ${path} did not match its schema`, parsed.error.issues.slice(0, 4));
    throw new Error(`The forecast service returned an unexpected shape for ${path}.`);
  }
  return parsed.data;
}

export async function postParsed<T>(path: string, body: unknown, schema: z.ZodType<T>): Promise<T> {
  return getParsed(path, schema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Raw JSON escape hatch for endpoints without a schema yet. */
export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json() as Promise<T>;
}

export type {
  Checklist,
  EmberItem,
  Fire,
  FiresPayload,
  Grid,
  HindcastSummary,
  Horizon,
  LeaderRow,
  Meta,
  Nudge,
  Observation,
  ObservationAck,
  Place,
  Prediction,
  RenderState,
  Target,
  UncertaintyStatus,
  WhyBar,
} from "./schemas";
