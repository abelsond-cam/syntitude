import { describe, expect, it } from "vitest";

import {
  type DisplayableArrangement,
  arrangementDifference,
  commonestArrangement,
  differingOffsetLabels,
  offsetLabel,
} from "./arrangementDisplay";
import { SIGNED_OFFSETS, type NeighbourSlot } from "./slotSpaces";
import { FORWARD, REVERSED } from "./walkDirection";

const NEIGHBOURS: readonly string[] = ["10", "11", "12", "13", "14", "15", "16", "17", "18", "19"];

function slotsFrom(loci: readonly (string | null)[], sameStrand = true): NeighbourSlot[] {
  return loci.map((locus, index) => ({
    signed_offset: SIGNED_OFFSETS[index] as number,
    locus,
    absence_reason: locus === null ? ("contig_end" as const) : null,
    same_strand: locus === null ? null : sameStrand,
  }));
}

function arrangement(
  rank: number,
  loci: readonly (string | null)[],
  options: { flip?: boolean; sameStrand?: boolean } = {},
): DisplayableArrangement {
  return {
    rank,
    is_recorded_reverse_complement: options.flip ?? false,
    slots: slotsFrom(loci, options.sameStrand ?? true),
  };
}

const BASE = arrangement(0, NEIGHBOURS);

/** The same ten neighbours, recorded backwards — i.e. genuinely reverse-complemented. */
const REVERSED_RECORDING: readonly string[] = [...NEIGHBOURS].reverse();

describe("offsetLabel", () => {
  it("signs a downstream offset and leaves an upstream one as it is", () => {
    expect([offsetLabel(-5), offsetLabel(-1), offsetLabel(1), offsetLabel(5)]).toEqual([
      "A-5",
      "A-1",
      "A+1",
      "A+5",
    ]);
  });
});

describe("⛔ the comparison is made in the DISPLAYED frame", () => {
  it("calls an inverted row with the same neighbours the SAME neighbours", () => {
    // The whole reason a flipped row is drawn reverse-complemented: read in one frame the rows
    // become comparable. Comparing the recorded vectors instead reports all ten positions differing
    // at a row the reader can see is identical.
    const inverted = arrangement(1, REVERSED_RECORDING, { flip: true });
    expect(arrangementDifference(BASE, inverted, FORWARD)).toBe("inverted · same neighbours");
  });

  it("still finds a real difference inside an inverted row", () => {
    const changed = [...REVERSED_RECORDING];
    changed[5] = "99"; // recorded slot 5 -> display slot 4 -> label A-1
    const inverted = arrangement(1, changed, { flip: true });
    expect(arrangementDifference(BASE, inverted, FORWARD)).toBe("inverted · differs at A-1");
  });

  it("⚠ ignores STRAND entirely — a neighbour transcribed the other way is the same neighbour", () => {
    // `slotsInDisplayOrder` flips every strand bit on a mirrored row, so reading strand here would
    // report all ten positions differing at exactly the rows the mirroring exists to make comparable.
    const opposed = arrangement(1, NEIGHBOURS, { sameStrand: false });
    expect(arrangementDifference(BASE, opposed, FORWARD)).toBe("same neighbours");
  });

  it("treats two absences as equal, and an absence against an occupant as a difference", () => {
    const withHole = [...NEIGHBOURS] as (string | null)[];
    withHole[0] = null;
    const bothMissing = arrangement(0, withHole);
    expect(arrangementDifference(bothMissing, arrangement(1, withHole), FORWARD)).toBe(
      "same neighbours",
    );
    expect(arrangementDifference(BASE, arrangement(1, withHole), FORWARD)).toBe("differs at A-5");
  });
});

describe("the line names the positions the TRACK shows", () => {
  it("names up to three of them, in the order the columns are drawn", () => {
    const changed = [...NEIGHBOURS] as (string | null)[];
    changed[0] = "90";
    changed[4] = "94";
    changed[9] = "99";
    expect(arrangementDifference(BASE, arrangement(1, changed), FORWARD)).toBe(
      "differs at A-5, A-1, A+5",
    );
  });

  it("counts them instead once there are more than three", () => {
    const changed = NEIGHBOURS.map((locus, index) => (index < 4 ? `9${index}` : locus));
    expect(arrangementDifference(BASE, arrangement(1, changed), FORWARD)).toBe(
      "differs at 4 positions",
    );
  });

  it("⭐ a WALK flip moves the label with the gene, so the same change is named the same way", () => {
    // This is the asymmetry the three slot spaces exist for: an arrangement flip keeps the column's
    // label where it is; a walk flip carries it along. A difference at one physical neighbour must
    // therefore keep its name whichever way the reader is walking.
    const changed = [...NEIGHBOURS] as (string | null)[];
    changed[4] = "94";
    const candidate = arrangement(1, changed);
    expect(arrangementDifference(BASE, candidate, FORWARD)).toBe("differs at A-1");
    expect(arrangementDifference(BASE, candidate, REVERSED)).toBe("differs at A-1");
  });

  it("⚠ lists them DESCENDING under a reversed walk, because the leftmost column is then A+5", () => {
    const changed = [...NEIGHBOURS] as (string | null)[];
    changed[4] = "94";
    changed[5] = "95";
    expect(differingOffsetLabels(BASE, arrangement(1, changed), FORWARD)).toEqual(["A-1", "A+1"]);
    expect(differingOffsetLabels(BASE, arrangement(1, changed), REVERSED)).toEqual(["A+1", "A-1"]);
  });
});

describe("⚠ `inverted` is the arrangement's INTRINSIC flip, not the display mirror", () => {
  it("does not appear or disappear as the reader walks the other way", () => {
    const inverted = arrangement(1, REVERSED_RECORDING, { flip: true });
    expect(arrangementDifference(BASE, inverted, REVERSED)).toContain("inverted");
    expect(arrangementDifference(BASE, arrangement(1, NEIGHBOURS), REVERSED)).not.toContain(
      "inverted",
    );
  });

  it("is ABSOLUTE, not relative to rank 1 — reproducing the published page exactly", () => {
    // Both recorded reverse-complemented, so both draw the same way up; the published page still
    // badges the second one, and parity is the governing rule here.
    const flippedBase = arrangement(0, REVERSED_RECORDING, { flip: true });
    const flippedOther = arrangement(1, REVERSED_RECORDING, { flip: true });
    expect(arrangementDifference(flippedBase, flippedOther, FORWARD)).toBe(
      "inverted · same neighbours",
    );
  });
});

describe("nothing to say", () => {
  it("says nothing about rank 1 itself — the caller writes `commonest arrangement`", () => {
    expect(arrangementDifference(BASE, BASE, FORWARD)).toBeNull();
    expect(arrangementDifference(BASE, arrangement(0, REVERSED_RECORDING), FORWARD)).toBeNull();
  });

  it("says nothing when there is no rank 1 to compare against", () => {
    expect(arrangementDifference(null, arrangement(3, NEIGHBOURS), FORWARD)).toBeNull();
  });
});

describe("⛔ the base is found by RANK, never taken as the first element", () => {
  it("picks rank 1 out of a list a display cap has spliced an anchored row into", () => {
    const listed = [arrangement(0, NEIGHBOURS), arrangement(37, NEIGHBOURS)];
    expect(commonestArrangement(listed)?.rank).toBe(0);
  });

  it("returns null rather than a wrong base when rank 1 is genuinely absent", () => {
    // A page fetched at an offset past the cut has no rank 1 in it, and measuring every row against
    // whatever happened to come first would describe differences from a row nobody is looking at.
    expect(commonestArrangement([arrangement(50, NEIGHBOURS)])).toBeNull();
  });
});
