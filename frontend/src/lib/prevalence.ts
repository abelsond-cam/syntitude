/**
 * The prevalence bands, in order — the runtime counterpart of `PrevalenceBand`.
 *
 * ⛔ **Five, and the fifth is `rare`.** The contract omitted it while 30 % of loci carried it; a
 * lookup keyed on the band returned `undefined` for those and a switch fell through them. The
 * ordering is the *drawing* order, commonest first, and the shade below is derived from it — so
 * adding a band to the middle re-shades the rest rather than colliding with an existing value.
 */

import type { PrevalenceBand } from "@/api/types";

export const PREVALENCE_BANDS = ["core", "soft_core", "shell", "cloud", "rare"] as const;

/** `soft_core` → `soft core`. The bands are stored with underscores and read without. */
export function prevalenceBandLabel(band: PrevalenceBand): string {
  return band.replace(/_/g, " ");
}

/**
 * A band's shade, 1 at the commonest and 0 at the rarest, for the chip's `--b` custom property.
 *
 * ⚠ Derived from the position rather than written down per band, so the ramp stays monotonic when a
 * band is added — the published page computes it the same way (`app.js:3361`).
 */
export function prevalenceBandShade(band: PrevalenceBand): number {
  const index = PREVALENCE_BANDS.indexOf(band);
  if (index < 0) return 0;
  return 1 - index / (PREVALENCE_BANDS.length - 1);
}
