/**
 * The three slot spaces of the ±5 track — all integers in 0..9, all valid indices into the same
 * ten-element array, and all meaning different things.
 *
 * ⛔ **This is risk 1 of the rebuild.** `obsSlot`, `labelSlot` and the raw column index are `number`
 * in `app.js`, so nothing there can stop one being passed where another is meant, and the result
 * puts a real count from one position under the gene at another — a picture that still looks like a
 * picture. Here each is a distinct branded type, so that substitution does not compile.
 *
 * | space | what an index means |
 * |---|---|
 * | {@link DisplaySlot} | the column on screen, left to right as the reader sees it |
 * | {@link ObservedSlot} | the position in the **recorded** ±5 vector, as measured |
 * | {@link LabelSlot} | the position whose signed offset **labels** that column |
 *
 * ⭐ **The asymmetry between the last two is the whole point**, and it is not an implementation
 * detail (`app.js:1527-1535`):
 *
 * - **Arrangement flip** — same focal gene, one row drawn backwards so the rows are comparable.
 *   *The column keeps its label*: A−1 stays leftmost, and a footnote says where the counts came
 *   from.
 * - **Walk flip** — the focal gene itself is now read backwards, so the frame really has reversed.
 *   *The label moves with it*: what was A+1 on the right becomes A−1, and the reader keeps walking
 *   one way.
 *
 * So {@link observedSlotFor} takes the **display mirror** (both flips, XOR-composed) while
 * {@link labelSlotFor} takes the **walk direction alone**. Handing either one the other's argument
 * is the bug this module exists to prevent, which is why they do not accept the same type.
 */

import { isReversed, type WalkDirection } from "./walkDirection";

/**
 * The recorded offsets, in recorded order. **Antisymmetric** — `SIGNED_OFFSETS[9 - j]` is always
 * `-SIGNED_OFFSETS[j]` — which is what makes mirroring a column index the same as negating its
 * offset, and is asserted in the tests rather than assumed.
 */
export const SIGNED_OFFSETS = [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5] as const;

/** How many positions a neighbourhood has. Ten: ±5, with no zero — the focal gene is not a slot. */
export const SLOT_COUNT = SIGNED_OFFSETS.length;

declare const displaySlotBrand: unique symbol;
declare const observedSlotBrand: unique symbol;
declare const labelSlotBrand: unique symbol;
declare const displayMirrorBrand: unique symbol;

/** A column on screen, left to right. */
export type DisplaySlot = number & { readonly [displaySlotBrand]: true };
/** A position in the recorded ±5 vector. */
export type ObservedSlot = number & { readonly [observedSlotBrand]: true };
/** The position whose signed offset labels a column. */
export type LabelSlot = number & { readonly [labelSlotBrand]: true };

/**
 * Whether the row being drawn is mirrored — the composition of the arrangement's own recorded
 * reverse-complement with the reader's walk direction. Branded so that a bare boolean, in
 * particular `isReversed(direction)`, cannot be passed to {@link observedSlotFor} by accident.
 */
export type DisplayMirror = boolean & { readonly [displayMirrorBrand]: true };

/** Thrown when an index is not a slot. A silent clamp would draw a real gene in the wrong column. */
export class NotASlotError extends RangeError {
  constructor(value: number, space: string) {
    super(`${value} is not a ${space}: slots are the integers 0..${SLOT_COUNT - 1}`);
    this.name = "NotASlotError";
  }
}

function checked(value: number, space: string): number {
  if (!Number.isInteger(value) || value < 0 || value >= SLOT_COUNT) {
    throw new NotASlotError(value, space);
  }
  return value;
}

/** Narrow a raw column index — from a `v-for`, a dataset attribute — into the display space. */
export function asDisplaySlot(value: number): DisplaySlot {
  return checked(value, "display slot") as DisplaySlot;
}

/** Narrow a raw index into the recorded space. Use where the API gives positions in record order. */
export function asObservedSlot(value: number): ObservedSlot {
  return checked(value, "observed slot") as ObservedSlot;
}

/**
 * The mirroring actually applied to draw one row — `app.js`'s `disp`, and the two flips **cancel**.
 *
 * ⚠ `isRecordedReverseComplement` is INTRINSIC to the arrangement: it is what the badge and the
 * "recorded at" footnote describe, and it is a property of the data. The walk direction is the
 * reader's. Composing them by XOR is what makes a flipped arrangement viewed under a reversed walk
 * draw the right way up.
 */
export function displayMirrorApplied(
  isRecordedReverseComplement: boolean,
  direction: WalkDirection,
): DisplayMirror {
  return (isRecordedReverseComplement !== isReversed(direction)) as DisplayMirror;
}

/**
 * The mirroring applied when **no arrangement is drawn** — a locus whose members have no recorded
 * neighbourhood at all, where the track falls back to the marginal mode. The arrangement's own flip
 * does not exist here, so only the walk contributes (`app.js:1524`, the `a ? a.disp : walkFlip`
 * branch).
 */
export function marginalDisplayMirror(direction: WalkDirection): DisplayMirror {
  return isReversed(direction) as DisplayMirror;
}

/**
 * Which **observed** position a display column is showing.
 *
 * A mirrored row is drawn reverse-complemented, so display column `j` holds the gene recorded at
 * `9 − j` — and the marginal, the share and the click target must all follow **the gene, not the
 * column** (`app.js:1509-1516`).
 */
export function observedSlotFor(display: DisplaySlot, mirror: DisplayMirror): ObservedSlot {
  return (mirror ? SLOT_COUNT - 1 - display : display) as ObservedSlot;
}

/**
 * Which offset a display column is **labelled** with.
 *
 * ⛔ Deliberately **not** {@link observedSlotFor}, and deliberately not a function of the
 * arrangement's flip — see this module's header. Only the walk moves a label.
 */
export function labelSlotFor(display: DisplaySlot, direction: WalkDirection): LabelSlot {
  return (isReversed(direction) ? SLOT_COUNT - 1 - display : display) as LabelSlot;
}

/** The signed offset a label slot carries, e.g. `-1` for "one gene upstream". */
export function signedOffsetForLabelSlot(label: LabelSlot): number {
  const offset = SIGNED_OFFSETS[label];
  if (offset === undefined) throw new NotASlotError(label, "label slot");
  return offset;
}

/**
 * The strand relation a reader **sees**, which is what decides the next frame.
 *
 * ⚠ Every arrow drawn, and every value handed to `walkDirectionAfterStep`, must come through here.
 * The recorded bits are relative to the focal gene's own direction; a row drawn mirrored shows the
 * opposite. Both the popover's marginal list and the no-arrangement fallback once used the raw
 * value and pointed the wrong way (`app.js:1518-1525`).
 */
export function strandRelationAsShown(
  recordedSameStrand: boolean,
  mirror: DisplayMirror,
): boolean {
  return mirror ? !recordedSameStrand : recordedSameStrand;
}

/**
 * One position of a neighbourhood, as the API serves it: resolved, never a packed code.
 *
 * ⛔ `occ(code)` is deleted. A bare `-1` meant five different things and a client that mapped every
 * one of them to `null` would be right twice and destroy three, so absence is a `null` locus **plus
 * a named reason** — and `contig_end` is an *observation*, not missing data.
 */
export interface NeighbourSlot {
  /** The offset this slot was RECORDED at. Not the label — see {@link labelSlotFor}. */
  readonly signed_offset: number;
  readonly locus: string | null;
  readonly absence_reason: "contig_end" | "outside_catalogue" | null;
  /** Relative to the focal gene as recorded; `null` where there is no occupant to relate. */
  readonly same_strand: boolean | null;
}

/**
 * One arrangement's slots in **display** order — `app.js`'s `viewVec`, over resolved slots.
 *
 * Reverses the order and flips every strand bit, leaving an absent slot absent: a contig end has no
 * strand to invert, and inventing one would assert a direction nothing observed.
 *
 * ⚠ `signed_offset` is left **exactly as recorded**. It is not the column's label, and rewriting it
 * here would quietly make the two spaces one — which is the failure this module is built against.
 * Ask {@link labelSlotFor} for the label.
 */
export function slotsInDisplayOrder(
  slots: readonly NeighbourSlot[],
  mirror: DisplayMirror,
): NeighbourSlot[] {
  if (slots.length !== SLOT_COUNT) {
    throw new RangeError(`a neighbourhood has ${SLOT_COUNT} slots, not ${slots.length}`);
  }
  if (!mirror) return slots.slice();
  const out: NeighbourSlot[] = [];
  for (let position = SLOT_COUNT - 1; position >= 0; position--) {
    const slot = slots[position];
    if (slot === undefined) throw new NotASlotError(position, "observed slot");
    out.push(
      slot.same_strand === null ? slot : { ...slot, same_strand: !slot.same_strand },
    );
  }
  return out;
}

/** Every display column, in order. A named helper so no component writes its own `0..9` loop. */
export function displaySlots(): DisplaySlot[] {
  return Array.from({ length: SLOT_COUNT }, (_unused, index) => index as DisplaySlot);
}
