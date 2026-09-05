/**
 * **Parity suite T2, the geometry half — every slot width, against the frozen page.**
 *
 * ⭐ The width is four lines of arithmetic and looks impossible to get wrong, which is exactly why
 * it is measured rather than transcribed. It is what ~40 DOM assertions stand on; it is the one
 * number the page sets **inline** so that a harness which loads no stylesheet can see it at all;
 * and a floor applied at the wrong end, or a `round` where the page has a `Math.max`, produces a
 * track that looks entirely plausible.
 *
 * `tests/js/record_track_geometry.js` in the `nuna` repo boots the published `app.js`, visits 300
 * seeded loci per species and records what it drew. This replays the same lengths through
 * `lib/trackGeometry` and requires the same pixels.
 */

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";

import { describe, expect, it } from "vitest";

import {
  LABEL_MIN_PX,
  MIN_BLOCK_PX,
  NARROW_PX,
  NO_LENGTH_PX,
  slotFit,
  widthForAbsentOccupant,
  widthForGeneLength,
} from "@/lib/trackGeometry";

interface RecordedSlot {
  readonly label: string | null;
  readonly is_focal: boolean;
  readonly has_occupant: boolean;
  readonly length_nt: number | null;
  readonly width: string | null;
  readonly is_narrow: boolean;
  readonly is_tight: boolean;
}

interface RecordedGeometry {
  readonly recorded_from: string;
  readonly has_lengths: boolean;
  readonly visited_loci: number;
  readonly recorded_slots: number;
  readonly visits: readonly { readonly focal_label: string; readonly slots: readonly RecordedSlot[] }[];
}

const SPECIES = ["ecoli", "kp"] as const;

function fixturePath(species: string): string {
  return fileURLToPath(new URL(`./fixtures/track_geometry_${species}.json`, import.meta.url));
}

function load(species: string): RecordedGeometry {
  return JSON.parse(readFileSync(fixturePath(species), "utf8")) as RecordedGeometry;
}

describe("the geometry fixtures", () => {
  it("⛔ names any species whose fixture is missing rather than passing quietly", () => {
    expect(SPECIES.filter((species) => !existsSync(fixturePath(species)))).toEqual([]);
  });

  it.each(SPECIES)("%s recorded what it claims, and the payload HAD lengths", (species) => {
    const recorded = load(species);
    expect(recorded.recorded_from).toBe("app.js");
    // ⚠ Without this the whole suite would pass against a payload with no `len_nt` at all, where
    // every slot falls back to 88 px and the formula is never exercised.
    expect(recorded.has_lengths).toBe(true);
    expect(recorded.visited_loci).toBe(300);
    const slots = recorded.visits.reduce((total, visit) => total + visit.slots.length, 0);
    expect(slots).toBe(recorded.recorded_slots);
    expect(slots).toBe(3_300);
  });

  it.each(SPECIES)("%s covers the cases the formula bends at", (species) => {
    const slots = load(species).visits.flatMap((visit) => visit.slots);
    // A fixture of 3,300 ordinary genes would pass every assertion below while testing no edge.
    expect(slots.filter((slot) => !slot.has_occupant).length).toBeGreaterThan(100);
    expect(slots.filter((slot) => slot.is_narrow).length).toBeGreaterThan(500);
    expect(slots.filter((slot) => slot.is_tight).length).toBeGreaterThan(50);
  });
});

describe.each(SPECIES)("%s — every recorded slot width is reproduced", (species) => {
  const recorded = load(species);
  const slots = recorded.visits.flatMap((visit) => visit.slots);

  it("⭐ the width, for all 3,300 of them", () => {
    const wrong: { slot: RecordedSlot; computed: string }[] = [];
    for (const slot of slots) {
      const computed = slot.has_occupant
        ? widthForGeneLength(slot.length_nt)
        : widthForAbsentOccupant();
      if (`${computed}px` !== slot.width) wrong.push({ slot, computed: `${computed}px` });
    }
    expect(wrong.slice(0, 3)).toEqual([]);
    expect(wrong).toHaveLength(0);
    expect(slots.length).toBe(recorded.recorded_slots);
  });

  it("⭐ and both fit thresholds, which decide what moves to the popover", () => {
    const wrong: RecordedSlot[] = [];
    for (const slot of slots) {
      if (!slot.has_occupant) continue;
      const fit = slotFit(slot.length_nt);
      if (fit.isNarrow !== slot.is_narrow || fit.isTight !== slot.is_tight) wrong.push(slot);
    }
    expect(wrong.slice(0, 3)).toEqual([]);
    expect(wrong).toHaveLength(0);
  });

  it("⛔ a slot with NO occupant takes the fallback width, never a scaled one", () => {
    // A contig end is an absence. Drawing it at the floor would assert a measurement nobody made,
    // and drawing it at zero would make it unclickable and invisible at once.
    const absent = slots.filter((slot) => !slot.has_occupant);
    expect(absent.length).toBeGreaterThan(100);
    for (const slot of absent) expect(slot.width).toBe(`${NO_LENGTH_PX}px`);
  });

  it("the floor really is reached, and is a floor rather than a scale", () => {
    const floored = slots.filter(
      (slot) => slot.has_occupant && slot.length_nt !== null && slot.length_nt < BP_FLOOR_NT,
    );
    for (const slot of floored) expect(slot.width).toBe(`${MIN_BLOCK_PX}px`);
  });
});

/** Below this many bases the true width would be under the floor. `MIN_BLOCK_PX × BP_PER_PX`. */
const BP_FLOOR_NT = MIN_BLOCK_PX * 10;

describe("the boundaries, stated rather than assumed", () => {
  it("⚠ NARROW is a STRICT less-than, so a slot of exactly 64 px is not narrow", () => {
    // Observed in the fixture: a 636 nt gene draws at exactly 64 px and the frozen page does NOT
    // mark it narrow. A `<=` here would move the locus id and product into the popover for a whole
    // band of genes that can hold them.
    expect(slotFit(NARROW_PX * 10).widthPx).toBe(NARROW_PX);
    expect(slotFit(NARROW_PX * 10).isNarrow).toBe(false);
    expect(slotFit(NARROW_PX * 10 - 10).isNarrow).toBe(true);
  });

  it("⚠ TIGHT is a strict less-than too", () => {
    expect(slotFit(LABEL_MIN_PX * 10).isTight).toBe(false);
    expect(slotFit(LABEL_MIN_PX * 10 - 10).isTight).toBe(true);
  });

  it("⛔ a null length is NOT MEASURED and takes the fallback, not the floor", () => {
    // A gene of zero length is not a thing. Falling to the floor would draw a hairline that claims
    // to be a measurement.
    expect(widthForGeneLength(null)).toBe(NO_LENGTH_PX);
    expect(widthForGeneLength(undefined)).toBe(NO_LENGTH_PX);
    expect(widthForGeneLength(0)).toBe(NO_LENGTH_PX);
  });

  it("rounds rather than truncating", () => {
    // 861 nt is 86.1 px and draws at 86; 866 nt is 86.6 and draws at 87. Truncation would lose the
    // second, and the difference compounds across ten slots into a visibly wrong track.
    expect(widthForGeneLength(861)).toBe(86);
    expect(widthForGeneLength(866)).toBe(87);
  });
});
