/**
 * How one arrangement is described against the commonest one — the single line under every row in
 * the arrangement browser and in the A0 card.
 *
 * ⛔ **The comparison happens in the DISPLAYED frame, not the recorded one.** Each row is mirrored
 * by its own recorded reverse-complement composed with the reader's walk direction, and only then
 * compared column by column. Comparing the recorded vectors instead reports a difference at every
 * position of an inverted arrangement whose neighbours the reader can plainly see are the same —
 * which is the opposite of what the line is for (`app.js:297-315`).
 *
 * ⚠ **Only the occupant's identity is compared, never its strand.** A neighbour transcribed the
 * other way round is the same neighbour, and `viewVec` has already flipped every strand bit on a
 * mirrored row, so reading strand here would report a difference at all ten positions of exactly
 * the rows the mirroring exists to make comparable. Two absent slots are equal to each other.
 *
 * ⚠ **`inverted` reads the arrangement's INTRINSIC recorded flip, not the display mirror.** It is a
 * property of the data — a badge on the row — so it must not appear and disappear as the reader
 * walks the other way. This reproduces the published page exactly, including that the badge is
 * absolute rather than relative to rank 1: where rank 1 is itself recorded reverse-complemented,
 * a second inverted row is still badged `inverted` though the two are drawn the same way up.
 */

import {
  type NeighbourSlot,
  displayMirrorApplied,
  displaySlots,
  labelSlotFor,
  signedOffsetForLabelSlot,
  slotsInDisplayOrder,
} from "./slotSpaces";
import type { WalkDirection } from "./walkDirection";

/**
 * The shape this module needs of an arrangement. Structural rather than an import of
 * `api/types`, so `lib/` keeps no dependency on the wire contract — the arrow already points the
 * other way, `api/types` importing {@link NeighbourSlot} from here.
 */
export interface DisplayableArrangement {
  readonly rank: number;
  readonly is_recorded_reverse_complement: boolean;
  readonly slots: readonly NeighbourSlot[];
}

/** How many differing positions are named one by one before the line gives a count instead. */
export const NAMED_DIFFERENCE_LIMIT = 3;

/** `A-1`, `A+3` — the offset as the track labels it. */
export function offsetLabel(signedOffset: number): string {
  return `A${signedOffset > 0 ? "+" : ""}${signedOffset}`;
}

/**
 * Which display columns two arrangements differ at, named in **label** space.
 *
 * ⚠ Label space, not observed space: the line has to name the offsets the reader can see on the
 * track, or it points at positions the track is not showing. Under a reversed walk that also means
 * the labels come out descending — `A+5` first — because the leftmost column is then `A+5`.
 */
export function differingOffsetLabels(
  base: DisplayableArrangement,
  candidate: DisplayableArrangement,
  direction: WalkDirection,
): string[] {
  const baseView = viewOf(base, direction);
  const candidateView = viewOf(candidate, direction);
  const labels: string[] = [];
  for (const display of displaySlots()) {
    if ((baseView[display]?.locus ?? null) !== (candidateView[display]?.locus ?? null)) {
      labels.push(offsetLabel(signedOffsetForLabelSlot(labelSlotFor(display, direction))));
    }
  }
  return labels;
}

/**
 * The one-line description of `candidate` against `base`, or `null` where there is nothing to say
 * — `base` missing, or `candidate` being rank 1 itself, which callers render as "commonest
 * arrangement" rather than as an empty line.
 */
export function arrangementDifference(
  base: DisplayableArrangement | null | undefined,
  candidate: DisplayableArrangement,
  direction: WalkDirection,
): string | null {
  if (base === null || base === undefined || candidate.rank === 0) return null;
  const differing = differingOffsetLabels(base, candidate, direction);
  const order = candidate.is_recorded_reverse_complement ? "inverted" : null;
  if (differing.length === 0) {
    return order === null ? "same neighbours" : "inverted · same neighbours";
  }
  const where =
    differing.length > NAMED_DIFFERENCE_LIMIT
      ? `differs at ${differing.length} positions`
      : `differs at ${differing.join(", ")}`;
  return order === null ? where : `${order} · ${where}`;
}

/** The arrangement whose rank is 1 — found by RANK, never taken as `listed[0]`. */
export function commonestArrangement<T extends DisplayableArrangement>(
  arrangements: readonly T[],
): T | null {
  return arrangements.find((arrangement) => arrangement.rank === 0) ?? null;
}

function viewOf(
  arrangement: DisplayableArrangement,
  direction: WalkDirection,
): readonly NeighbourSlot[] {
  return slotsInDisplayOrder(
    arrangement.slots,
    displayMirrorApplied(arrangement.is_recorded_reverse_complement, direction),
  );
}
