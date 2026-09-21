import { z } from "zod";

/**
 * Runtime schemas for every API response. Types are DERIVED from these, never
 * declared alongside them, so the two cannot drift.
 *
 * Why this exists: `why[].value` was typed `number` and was `null` whenever the
 * SHAP cache missed. `.toFixed()` on it crashed the entire Place Card while the
 * endpoint returned 200 and `tsc` passed, because the types were asserted, not
 * validated. Every optional field was the same bug waiting.
 *
 * Nullability here is explicit and observed, not guessed. The fields marked
 * nullable were confirmed null in live responses:
 *   - why[].value            null on a SHAP cache miss (feature-z fallback)
 *   - fires[].h8_*           null when the 8-week issue precedes the record
 *   - manifest.sources[].records  null for sources that report no count
 */

/** Coerce a value that may be null, absent, or a non-finite number. */
const maybeNumber = z.number().finite().nullish().transform((v) => (v ?? null));

export const WhyBarSchema = z.object({
  group: z.string(),
  label: z.string(),
  // Null on a SHAP cache miss. The bar renders without a magnitude.
  value: maybeNumber,
  text: z.string().default(""),
  sign: z.string().default(""),
  raw: maybeNumber,
  top_feature: z.string().nullish(),
  source: z.string().nullish(),
});

// Probabilistic outputs are optional at the schema level because a cell can
// legitimately lack them: a target is skipped where the event never occurs in
// the training window, and a Markov reference does not exist for fire targets
// at all. Parsing them as required would turn an absent forecast into a client
// crash, which is how the earlier null-SHAP bug took down a whole Place Card.
export const ProbabilitySchema = z.object({
  value: maybeNumber,
  // True when this target has zero LODO resolution in the displayed domain, so
  // the probability is a regional base rate and is identical for every cell.
  // The list is domain dependent, 8 targets on Larimer against 4 on Pueblo, so
  // the client must read this flag rather than hard-code target names. The card
  // renders these without per-cell styling, because per-cell styling would
  // imply a spatial signal the forecast does not have.
  flat: z.boolean().default(false),
  // The Markov transition baseline for the same event, shown beside the model
  // rather than behind it. Null for fire targets, which have no Markov
  // reference: an empirical USDM category transition matrix cannot forecast ERC
  // exceedance. See docs/DECISIONS.md.
  baseline: maybeNumber,
});

export const HorizonSchema = z.object({
  drought_point: maybeNumber,
  drought_set: z.array(z.number()).default([]),
  fire_index: maybeNumber,
  fire_lo: maybeNumber,
  fire_hi: maybeNumber,
  confidence: maybeNumber,
  alpha: maybeNumber,
  // v1 probabilistic targets.
  p_intensify: ProbabilitySchema.nullish(),
  p_d2plus: ProbabilitySchema.nullish(),
  p_fire_gt90: ProbabilitySchema.nullish(),
});

export const UncertaintySchema = z.object({
  status: z.enum(["calibrated", "extrapolating", "uncalibrated"]),
  reason: z.string().default(""),
  // Absent when no calibration pool exists on disk.
  show_interval: z.boolean().default(false),
  widen_factor: z.number().finite().default(1),
  current_usdm: maybeNumber,
  pool_usdm_max: maybeNumber,
  exceedance_sd: maybeNumber,
  measured_coverage: maybeNumber,
  pool_years: z.array(z.number()).nullish(),
  available: z.boolean().default(false),
});

export const PlaceSchema = z.object({
  cell_id: z.string(),
  lat: z.number(),
  lon: z.number(),
  issue: z.string(),
  resolution_m: z.number().default(4000),
  shipping_arm: z.string().default("unknown"),
  why: z.array(WhyBarSchema).default([]),
  horizons: z.record(z.string(), HorizonSchema).default({}),
  uncertainty: UncertaintySchema.nullish(),
});

export const MetaSchema = z.object({
  shipping_arm: z.string().nullish(),
  shipping_arm_basis: z.string().default(""),
  resolution_m: z.number().default(4000),
  resolution_note: z.string().default(""),
  disclaimer: z.string().default(""),
  manifest: z
    .object({
      sources: z
        .array(
          z.object({
            name: z.string(),
            state: z.string().default(""),
            note: z.string().default(""),
            // Null for sources that report no record count.
            records: maybeNumber,
            optional: z.boolean().nullish(),
          }),
        )
        .default([]),
    })
    .default({ sources: [] }),
  manifest_hash: z.string().nullish(),
  git_sha: z.string().nullish(),
  status: z.string().default("unknown"),
  hindcast_looks: z
    .array(z.object({ config_hash: z.string(), look_index: z.number(), timestamp: z.string() }))
    .default([]),
  issue_dates: z.array(z.string()).default([]),
  // Absent when no cells are exported.
  center: z.tuple([z.number(), z.number()]).nullish(),
  zoom: z.number().nullish(),
});

export const IssuesSchema = z.object({ issues: z.array(z.string()).default([]) });

export const CoverageRowSchema = z.object({
  split: z.string(),
  method: z.string(),
  horizon: z.number(),
  coverage: z.number(),
  width: z.number(),
  n: z.number().nullish(),
});

export const HindcastSummarySchema = z.object({
  comparison: z.string().default(""),
  coverage_rows: z.array(CoverageRowSchema).default([]),
  nominal: z.number().default(0.9),
  look_index: z.number().default(0),
  contaminated: z.boolean().default(false),
  contamination_note: z.string().default(""),
  coverage_plot: z.string().nullish(),
  may1_issue: z.string().nullish(),
});

export const FireSchema = z.object({
  name: z.string(),
  discovery: z.string().default(""),
  acres: z.number().default(0),
  in_domain: z.boolean().default(false),
  // Null when the 8-week issue precedes the exported record.
  h2_pct_rank: maybeNumber,
  h4_pct_rank: maybeNumber,
  h8_pct_rank: maybeNumber,
});

export const FiresPayloadSchema = z.object({
  fires: z.array(FireSchema).default([]),
  control: z
    .object({
      n: z.number().nullish(),
      mean_pct_rank: z.record(z.string(), z.number()).nullish(),
    })
    .default({}),
  n_in_domain: z.number().default(0),
  threshold_acres: z.number().default(1000),
  note: z.string().default(""),
});

export const EmberItemSchema = z.object({
  id: z.string(),
  label: z.string(),
  cost: z.string().default(""),
  rationale: z.string().default(""),
  source: z.string().default(""),
  group: z.string().default("other"),
  group_label: z.string().default("Other"),
  item_weight: z.number().default(0),
});

export const ChecklistSchema = z.object({
  score: z.number().default(0),
  zone: z.string().default("wui"),
  items: z.array(EmberItemSchema).default([]),
});

export const PredictionSchema = z.object({
  id: z.string().nullish(),
  locked_model: HorizonSchema.nullish(),
  issue: z.string().nullish(),
});

export const NudgeSchema = z.object({
  delta_drought: z.number().default(0),
  delta_fire: z.number().default(0),
  source: z.string().default(""),
});

export const ObservationAckSchema = z.object({
  id: z.string().nullish(),
  nudge: NudgeSchema.nullish(),
});

export const ObservationSchema = z.object({
  id: z.string(),
  lat: z.number(),
  lon: z.number(),
  type: z.string().default(""),
  note: z.string().default(""),
  created_at: z.string().nullish(),
});

export const LeaderRowSchema = z.object({ device_id: z.string(), picks: z.number().default(0) });

export const GridFeatureSchema = z.object({
  type: z.literal("Feature"),
  properties: z.object({
    cell_id: z.string(),
    value: maybeNumber,
    confidence: maybeNumber,
  }),
  geometry: z.object({ type: z.literal("Point"), coordinates: z.tuple([z.number(), z.number()]) }),
});

export const GridSchema = z.object({
  type: z.string().default("FeatureCollection"),
  features: z.array(GridFeatureSchema).default([]),
  resolution_m: z.number().default(4000),
});

// Types are derived, never hand-declared.
export type Probability = z.infer<typeof ProbabilitySchema>;
export type WhyBar = z.infer<typeof WhyBarSchema>;
export type Horizon = z.infer<typeof HorizonSchema>;
export type UncertaintyStatus = z.infer<typeof UncertaintySchema>;
export type Place = z.infer<typeof PlaceSchema>;
export type Meta = z.infer<typeof MetaSchema>;
export type HindcastSummary = z.infer<typeof HindcastSummarySchema>;
export type Fire = z.infer<typeof FireSchema>;
export type FiresPayload = z.infer<typeof FiresPayloadSchema>;
export type Checklist = z.infer<typeof ChecklistSchema>;
export type EmberItem = z.infer<typeof EmberItemSchema>;
export type Prediction = z.infer<typeof PredictionSchema>;
export type Nudge = z.infer<typeof NudgeSchema>;
export type ObservationAck = z.infer<typeof ObservationAckSchema>;
export type Observation = z.infer<typeof ObservationSchema>;
export type LeaderRow = z.infer<typeof LeaderRowSchema>;
export type Grid = z.infer<typeof GridSchema>;
