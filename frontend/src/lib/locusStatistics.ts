/**
 * The numbers on the locus card that are *computed* rather than read — and the rules for what each
 * one may claim.
 *
 * ⛔ **Three of these were re-derived on the published page and must not be here.** The separation
 * percentile is a precomputed midrank over measurable loci (`separation_percentile`), the Pfam
 * verdict is the audit's own (`pfam.concordance_class`), and the display name and best product are
 * ingest columns. What remains genuinely client-side is arithmetic over numbers the response
 * carries: distance → similarity, cohesion against the null, and the separation banding.
 */

/**
 * ⛔ The payload stores cosine **DISTANCE**, not similarity, and the reason is precision: 85 % of
 * ESM loci arrive as an indistinguishable `1.000` if the similarity is stored directly, because a
 * similarity near 1 has no decimal places left to round into. So every read converts here, once.
 */
export function similarityFromDistance(distance: number | null): number | null {
  return distance === null ? null : 1 - distance;
}

/**
 * Cohesion: how far a locus sits from a random pair, **towards a perfect one**.
 *
 * ⛔ **Deliberately NOT a catalogue percentile.** Almost every locus in these catalogues is
 * cohesive, so ranking cohesion against its peers says the opposite of the truth — `traC` sits at
 * p12 on Bacformer while actually being 84 % of the way from a random pair to a perfect one. The
 * percentile belongs on SEPARATION, which is where the variation genuinely lives.
 *
 * ⚠ `nullMeanCosine` is per representation and the two are nowhere near each other: ESM's random
 * pairs sit at ~0.645 and Bacformer's at ~0.065, so the same raw similarity means opposite things
 * in the two. Returns `null` where the baseline is missing or degenerate rather than inventing one.
 */
export function cohesion(
  withinSimilarity: number | null,
  nullMeanCosine: number | null,
): number | null {
  if (withinSimilarity === null || nullMeanCosine === null || nullMeanCosine >= 1) return null;
  return Math.max(0, Math.min(1, (withinSimilarity - nullMeanCosine) / (1 - nullMeanCosine)));
}

/** How clearly a locus is bounded: its own members' closeness minus the nearest rival's. */
export function separation(
  withinSimilarity: number | null,
  nearestSimilarity: number | null,
): number | null {
  if (withinSimilarity === null || nearestSimilarity === null) return null;
  return withinSimilarity - nearestSimilarity;
}

export type SeparationClass = "win" | "warn" | "bad";

export interface SeparationVerdict {
  readonly separation: number;
  /** The precomputed midrank, 0..1, over MEASURABLE loci only. */
  readonly percentile: number;
  readonly verdictClass: SeparationClass;
  readonly label: string;
}

/**
 * Three bands, one parallel construction, so a reader compares one thing.
 *
 * ⚠ **The wording qualifies the separation BETWEEN this locus and its nearest rival — not the
 * quality of the locus**, which the geometry card beneath shows is excellent in every one of these
 * cases. Cut at p5 because the zero crossing already sits near p2.5, so `Poor` catches the bottom
 * ~2 % alone and `Unclear` adds a thin sliver.
 *
 * ⛔ Returns `null` where either input is missing — *not measurable*, which the card must say in
 * words and must never render as `0.000`. A singleton is its own medoid and has no separation at
 * all; that is an absence, not a bad score.
 */
export function separationVerdict(
  withinSimilarity: number | null,
  nearestSimilarity: number | null,
  percentile: number | null,
): SeparationVerdict | null {
  const gap = separation(withinSimilarity, nearestSimilarity);
  if (gap === null || percentile === null) return null;
  if (gap < 0) {
    return {
      separation: gap,
      percentile,
      verdictClass: "bad",
      label: "Poor cluster separation",
    };
  }
  if (percentile < 0.05) {
    return {
      separation: gap,
      percentile,
      verdictClass: "warn",
      label: "Unclear cluster separation",
    };
  }
  return { separation: gap, percentile, verdictClass: "win", label: "Clean cluster separation" };
}

/**
 * `p12` — a percentile as the card writes it.
 *
 * ⚠ Floored at 1, never 0: `p0` reads as "no data" beside every other tile that uses `—` for
 * exactly that, and the bottom of a midrank is a real rank rather than an absence.
 */
export function percentileLabel(percentile: number): string {
  return `p${Math.max(1, Math.round(percentile * 100))}`;
}

/** A signed number the card prints with its sign, e.g. `+0.412` / `-0.008`. */
export function signedFixed(value: number, digits = 3): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

/** Copies per genome — `null` where the locus has no genomes to divide by. */
export function copiesPerGenome(geneCount: number, genomeCount: number): number | null {
  return genomeCount > 0 ? geneCount / genomeCount : null;
}
