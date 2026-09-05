/**
 * How wide a gene is drawn, and what stops fitting inside it.
 *
 * ⛔ **The width is set INLINE on the slot, not in a stylesheet**, and that is a testability
 * requirement rather than a style choice (`app.js:1198`): *"the JS test harness loads no
 * stylesheet, so an inline width is the only version of this that any test can see."* jsdom
 * computes no layout either, so a width moved into CSS silently blanks every assertion about it.
 * Keep this comment next to whatever sets `style.width`.
 *
 * ⚠ **The SLOT carries the width, not the block.** The occupancy bar and the offset label are the
 * block's siblings and have to line up under it exactly, or the bar stops describing the gene above
 * it.
 */

/**
 * Base pairs per pixel. Chosen so the median gene lands near the 88 px equal slot it replaced — the
 * track keeps its familiar density and only the *differences* between genes appear.
 */
export const BP_PER_PX = 10;

/**
 * ⚠ A floor, not a scale, and a deliberate departure from true scale at the small end: an 80 bp
 * feature drawn honestly is a hairline nobody can click, so it is drawn at the floor and its true
 * length is in the popover.
 */
export const MIN_BLOCK_PX = 6;

/** The seam where two genes meet or overlap: a mark, never a width to scale. */
export const JOINT_PX = 7;

/** Below this a block cannot hold its locus id and product; they move to the popover. */
export const NARROW_PX = 64;

/**
 * Below this a box cannot hold its own name at the normal size, so the label shrinks rather than
 * disappearing. ⚠ A label raked at 60° reaches half its own width to the right, so on a narrower
 * box the full-size name would sit over the next gene — measured at 30 % of loci before the cap
 * came down. **Must stay in step with `--label-max` in the stylesheet**: this is
 * `max-width × cos(60°)` = half of 40 px.
 */
export const LABEL_MIN_PX = 20;

/**
 * The fallback where no length is known. ⚠ `null` here is *not measured*, and it must not be read
 * as a zero-length gene — a gene of zero length is not a thing, and drawing one at the floor would
 * assert a measurement nobody made.
 */
export const NO_LENGTH_PX = 88;

/** The drawn width of a gene whose members have this median length. */
export function widthForGeneLength(medianGeneLengthNt: number | null | undefined): number {
  if (medianGeneLengthNt === null || medianGeneLengthNt === undefined || medianGeneLengthNt <= 0) {
    return NO_LENGTH_PX;
  }
  return Math.max(MIN_BLOCK_PX, Math.round(medianGeneLengthNt / BP_PER_PX));
}

/** What a slot of this width can no longer hold. Both thresholds, named. */
export interface SlotFit {
  readonly widthPx: number;
  /** Too narrow for the locus id and product — they move to the popover. */
  readonly isNarrow: boolean;
  /** Too narrow even for the gene's own name at full size — the label shrinks. */
  readonly isTight: boolean;
}

export function slotFit(medianGeneLengthNt: number | null | undefined): SlotFit {
  const widthPx = widthForGeneLength(medianGeneLengthNt);
  return {
    widthPx,
    isNarrow: widthPx < NARROW_PX,
    isTight: widthPx < LABEL_MIN_PX,
  };
}

/**
 * The width of a slot with **no occupant** — a contig end.
 *
 * ⛔ It keeps the fallback width and the forward lane on purpose. A contig end is an *absence*, and
 * putting it in a direction lane would assert a transcription direction nothing observed.
 */
export function widthForAbsentOccupant(): number {
  return NO_LENGTH_PX;
}

/**
 * One segment of a marginal bar, as a percentage of the position's observed members.
 *
 * ⚠ The denominator is `observedMemberCount` — the members with a gene here **at all** — and not
 * the locus size. A share against the locus size would read low at every contig-edge position for a
 * reason that has nothing to do with what occupies it.
 */
export function segmentPercent(memberCount: number, observedMemberCount: number): number {
  if (observedMemberCount <= 0) return 0;
  return (100 * memberCount) / observedMemberCount;
}
