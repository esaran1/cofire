/**
 * The shape of the explanation tables (cofire/v13/explain.py), checked when
 * they are fetched. Kept apart from ./explain so the validator library loads
 * with the data, after the page has painted, not before.
 */
import { z } from "zod";

const Row = z.object({ key: z.string(), season: z.string(), row: z.array(z.number()), cases: z.record(z.string(), z.array(z.number())) });
const Drought = z.object({ global_row: z.array(z.number()), prior_strength: z.number(), persistence_weight: z.number(), rows: z.record(z.string(), Row) });
const Fire = z.object({
  intercept: z.number(),
  slope: z.number(),
  fill: z.number(),
  cases: z.record(z.string(), z.record(z.string(), z.record(z.string(), z.tuple([z.number(), z.number()])))),
});
export const ExplainSchema = z.object({
  domain: z.string(),
  train: z.tuple([z.string(), z.string()]),
  drought: z.record(z.string(), Drought),
  fire: z.record(z.string(), z.record(z.string(), Fire)),
  live: z.array(z.object({ target: z.string(), horizon: z.number(), a: z.number(), b: z.number(), applies_from: z.string() })),
});
export type Explain = z.infer<typeof ExplainSchema>;
