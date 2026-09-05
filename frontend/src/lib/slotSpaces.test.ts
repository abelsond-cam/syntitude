import { describe, expect, it } from "vitest";

import {
  NotASlotError,
  SIGNED_OFFSETS,
  SLOT_COUNT,
  asDisplaySlot,
  displayMirrorApplied,
  displaySlots,
  labelSlotFor,
  marginalDisplayMirror,
  type NeighbourSlot,
  observedSlotFor,
  signedOffsetForLabelSlot,
  slotsInDisplayOrder,
  strandRelationAsShown,
} from "./slotSpaces";
import { FORWARD, REVERSED } from "./walkDirection";

/** A neighbourhood whose every slot is identifiable, so a mis-mapping cannot look like a match. */
function neighbourhood(overrides: Partial<Record<number, Partial<NeighbourSlot>>> = {}): NeighbourSlot[] {
  return SIGNED_OFFSETS.map((signed_offset, position) => ({
    signed_offset,
    locus: `L${position}`,
    absence_reason: null,
    // Alternating, so reversing the ORDER alone would still produce the right bits and the test
    // would pass while the strand flip was missing.
    same_strand: position % 2 === 0,
    ...(overrides[position] ?? {}),
  })) as NeighbourSlot[];
}

const FLIPPED_ROW = true;
const UPRIGHT_ROW = false;

describe("the offsets themselves", () => {
  it("are ten, with no zero — the focal gene is not a slot", () => {
    expect(SLOT_COUNT).toBe(10);
    expect(SIGNED_OFFSETS).not.toContain(0);
  });

  it("⭐ are ANTISYMMETRIC, which is what makes mirroring a column the same as negating an offset", () => {
    // `labelSlotFor` mirrors the index and the page then reads OFFSETS at it. That is only the same
    // thing as "the label becomes A−1" because of this property, so it is asserted, not assumed.
    for (let position = 0; position < SLOT_COUNT; position++) {
      expect(SIGNED_OFFSETS[SLOT_COUNT - 1 - position]).toBe(-SIGNED_OFFSETS[position]!);
    }
  });
});

describe("the display mirror composes the two flips", () => {
  it("cancels when both apply", () => {
    // A flipped arrangement read under a reversed walk is drawn the right way up.
    expect(displayMirrorApplied(FLIPPED_ROW, REVERSED)).toBe(false);
    expect(displayMirrorApplied(UPRIGHT_ROW, FORWARD)).toBe(false);
  });

  it("applies when exactly one does", () => {
    expect(displayMirrorApplied(FLIPPED_ROW, FORWARD)).toBe(true);
    expect(displayMirrorApplied(UPRIGHT_ROW, REVERSED)).toBe(true);
  });

  it("with no arrangement drawn, only the walk contributes", () => {
    // The `a ? a.disp : walkFlip` branch — a locus whose members have no recorded neighbourhood
    // falls back to the marginal, which has no flip of its own.
    expect(marginalDisplayMirror(REVERSED)).toBe(true);
    expect(marginalDisplayMirror(FORWARD)).toBe(false);
  });
});

describe("⛔ the observed space and the label space are NOT the same mapping", () => {
  it("an arrangement flip moves the gene but KEEPS the label", () => {
    // The reader is looking at the same focal gene; one row is drawn backwards so the rows are
    // comparable. A−1 stays leftmost.
    const mirror = displayMirrorApplied(FLIPPED_ROW, FORWARD);
    const leftmost = asDisplaySlot(0);
    expect(observedSlotFor(leftmost, mirror)).toBe(9);
    expect(signedOffsetForLabelSlot(labelSlotFor(leftmost, FORWARD))).toBe(-5);
  });

  it("a walk flip moves BOTH — the frame itself has reversed", () => {
    // What was A+1 on the right becomes A−1, and the reader keeps walking one way.
    const mirror = displayMirrorApplied(UPRIGHT_ROW, REVERSED);
    const leftmost = asDisplaySlot(0);
    expect(observedSlotFor(leftmost, mirror)).toBe(9);
    expect(signedOffsetForLabelSlot(labelSlotFor(leftmost, REVERSED))).toBe(5);
  });

  it("⭐ so the two disagree on exactly the flipped-arrangement case, and that is the point", () => {
    const disagreements = displaySlots().filter(
      (display) =>
        // Widened deliberately — see the note on the sibling test below.
        (observedSlotFor(display, displayMirrorApplied(FLIPPED_ROW, FORWARD)) as number) !==
        (labelSlotFor(display, FORWARD) as number),
    );
    // Every column: the gene comes from the far end while the label does not move at all.
    expect(disagreements).toHaveLength(SLOT_COUNT);
  });

  it("and agree when the walk alone is what mirrors", () => {
    const agreements = displaySlots().filter(
      (display) =>
        // ⭐ The two casts are the point: `vue-tsc` REFUSES `ObservedSlot === LabelSlot` outright
        // ("no overlap"), which is the whole defence — a component cannot make this comparison by
        // accident. Only a test that is deliberately asking whether the numbers coincide may
        // widen them, and it says so here rather than reaching for `as any`.
        (observedSlotFor(display, displayMirrorApplied(UPRIGHT_ROW, REVERSED)) as number) ===
        (labelSlotFor(display, REVERSED) as number),
    );
    expect(agreements).toHaveLength(SLOT_COUNT);
  });

  it("both are involutions — mirroring twice is the identity", () => {
    for (const display of displaySlots()) {
      const mirror = displayMirrorApplied(FLIPPED_ROW, FORWARD);
      const once = observedSlotFor(display, mirror);
      expect(observedSlotFor(asDisplaySlot(once), mirror)).toBe(display);
    }
  });
});

describe("the strand relation is the one the reader SEES", () => {
  it("inverts under a mirrored row and passes through otherwise", () => {
    expect(strandRelationAsShown(true, displayMirrorApplied(FLIPPED_ROW, FORWARD))).toBe(false);
    expect(strandRelationAsShown(true, displayMirrorApplied(UPRIGHT_ROW, FORWARD))).toBe(true);
    expect(strandRelationAsShown(false, displayMirrorApplied(UPRIGHT_ROW, REVERSED))).toBe(true);
    // Both flips cancel, so the recorded relation is also the shown one.
    expect(strandRelationAsShown(false, displayMirrorApplied(FLIPPED_ROW, REVERSED))).toBe(false);
  });
});

describe("slotsInDisplayOrder", () => {
  it("leaves an upright row exactly as recorded, and copies rather than aliases it", () => {
    const slots = neighbourhood();
    const shown = slotsInDisplayOrder(slots, displayMirrorApplied(UPRIGHT_ROW, FORWARD));
    expect(shown).toEqual(slots);
    expect(shown).not.toBe(slots);
  });

  it("reverses the order AND flips every strand bit", () => {
    const slots = neighbourhood();
    const shown = slotsInDisplayOrder(slots, displayMirrorApplied(FLIPPED_ROW, FORWARD));
    expect(shown.map((slot) => slot.locus)).toEqual([
      "L9", "L8", "L7", "L6", "L5", "L4", "L3", "L2", "L1", "L0",
    ]);
    expect(shown.map((slot) => slot.same_strand)).toEqual(
      slots.map((slot) => !slot.same_strand).reverse(),
    );
  });

  it("⛔ leaves an absent slot absent — a contig end has no strand to invert", () => {
    const slots = neighbourhood({
      3: { locus: null, absence_reason: "contig_end", same_strand: null },
    });
    const shown = slotsInDisplayOrder(slots, displayMirrorApplied(FLIPPED_ROW, FORWARD));
    const moved = shown[SLOT_COUNT - 1 - 3]!;
    expect(moved.locus).toBeNull();
    expect(moved.absence_reason).toBe("contig_end");
    expect(moved.same_strand).toBeNull();
  });

  it("⛔ does NOT rewrite signed_offset, which stays the RECORDED offset", () => {
    // Rewriting it here would quietly merge the observed and label spaces — the exact failure the
    // module exists against. The column's label comes from `labelSlotFor`, never from the slot.
    const shown = slotsInDisplayOrder(neighbourhood(), displayMirrorApplied(FLIPPED_ROW, FORWARD));
    expect(shown.map((slot) => slot.signed_offset)).toEqual([...SIGNED_OFFSETS].reverse());
  });

  it("⭐ agrees with observedSlotFor, so the two idioms cannot drift apart", () => {
    // `app.js` has both: an arrangement is drawn from a pre-mirrored `view`, while the marginal is
    // indexed live through `obsSlot`. A rewrite that mirrored one and not the other would put a
    // count from one position under a gene from another and still render.
    const slots = neighbourhood();
    for (const flipped of [UPRIGHT_ROW, FLIPPED_ROW]) {
      for (const direction of [FORWARD, REVERSED] as const) {
        const mirror = displayMirrorApplied(flipped, direction);
        const shown = slotsInDisplayOrder(slots, mirror);
        for (const display of displaySlots()) {
          const recorded = slots[observedSlotFor(display, mirror)]!;
          expect(shown[display]!.locus).toBe(recorded.locus);
          expect(shown[display]!.same_strand).toBe(
            recorded.same_strand === null
              ? null
              : strandRelationAsShown(recorded.same_strand, mirror),
          );
        }
      }
    }
  });

  it("refuses a neighbourhood that is not ten slots long", () => {
    const short = neighbourhood().slice(0, 9);
    expect(() => slotsInDisplayOrder(short, displayMirrorApplied(UPRIGHT_ROW, FORWARD))).toThrow(
      RangeError,
    );
  });
});

describe("an index that is not a slot is an error, never a clamp", () => {
  it.each([-1, 10, 1.5, Number.NaN])("rejects %s", (value) => {
    expect(() => asDisplaySlot(value)).toThrow(NotASlotError);
  });

  it("accepts both ends of the range", () => {
    expect(asDisplaySlot(0)).toBe(0);
    expect(asDisplaySlot(SLOT_COUNT - 1)).toBe(9);
  });
});
