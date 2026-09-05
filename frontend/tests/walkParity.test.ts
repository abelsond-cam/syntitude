/**
 * **Parity suite T2, first half — the walk, against the frozen page.**
 *
 * `tests/js/record_walks.js` in the `nuna` repo boots the published `app.js` under `node:vm`, drives
 * 500 seeded walks of 40 steps, and records for every step the inputs the reader saw — which column
 * was clicked and which way its arrow pointed — beside the outcome the page chose. This suite
 * replays those inputs through `lib/` and requires the same outcome.
 *
 * ⭐ **This is what makes `lib/` differential rather than self-consistent.** It is graded against
 * 4,688 lines of reference behaviour that actually shipped, not against my reading of them. The
 * second half — driving the same walks through the Vue components and diffing the rendered track —
 * lands with the track component; this half needs no browser and is available now.
 *
 * ⛔ **Every assertion below is preceded by a coverage assertion.** A suite that examined three
 * steps and one that examined nineteen thousand must not look the same, and a fixture that never
 * exercised the distinction being tested must fail rather than pass — hence
 * `discriminatingSteps`, which counts the steps on which a toggle implementation would give a
 * different answer, and refuses to run the comparison if that count is small.
 */

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";

import { describe, expect, it } from "vitest";

import { formatLocusHash, parseLocusHash } from "@/lib/locusHashRoute";
import { FORWARD, REVERSED, walkDirectionAfterStep } from "@/lib/walkDirection";

interface RecordedStep {
  readonly hash_before: string;
  readonly column: number;
  readonly data_dir: "fwd" | "rev";
  readonly target_label: string;
  readonly arrangement: {
    readonly selected_index: number;
    readonly option_count: number;
    readonly focal_dir: string | null;
  };
  readonly hash_after: string;
}

interface RecordedWalks {
  readonly recorded_from: string;
  readonly payload_schema: number | null;
  readonly locus_count: number;
  readonly walked_seeds: number;
  readonly recorded_steps: number;
  readonly walks: readonly { readonly seed_label: string; readonly stopped: string | null; readonly steps: readonly RecordedStep[] }[];
}

const SPECIES = ["ecoli", "kp"] as const;

function fixturePath(species: string): string {
  return fileURLToPath(new URL(`./fixtures/walks_${species}.json`, import.meta.url));
}

function load(species: string): RecordedWalks {
  return JSON.parse(readFileSync(fixturePath(species), "utf8")) as RecordedWalks;
}

describe("the recorded fixtures are present and cover what they claim", () => {
  it("⛔ names any species whose fixture is missing rather than passing quietly", () => {
    const missing = SPECIES.filter((species) => !existsSync(fixturePath(species)));
    expect(missing).toEqual([]);
  });

  it.each(SPECIES)("%s walked 500 seeds and recorded what it walked", (species) => {
    const recorded = load(species);
    expect(recorded.recorded_from).toBe("app.js");
    expect(recorded.walked_seeds).toBe(500);
    expect(recorded.walks).toHaveLength(500);
    // The header's own count must equal what is actually in the file — otherwise a truncated
    // fixture reports full coverage.
    const steps = recorded.walks.reduce((total, walk) => total + walk.steps.length, 0);
    expect(steps).toBe(recorded.recorded_steps);
    expect(steps).toBeGreaterThan(19_000);
  });

  it.each(SPECIES)("%s exercises reversed frames and reversed arrows in quantity", (species) => {
    // A fixture of 20,000 forward steps would pass every assertion below while testing nothing.
    const steps = load(species).walks.flatMap((walk) => walk.steps);
    const reversedArrows = steps.filter((step) => step.data_dir === "rev").length;
    const startedReversed = steps.filter((step) => step.hash_before.endsWith("r")).length;
    expect(reversedArrows).toBeGreaterThan(5_000);
    expect(startedReversed).toBeGreaterThan(5_000);
  });
});

describe.each(SPECIES)("%s — the walk replays through lib/ exactly as the page walked it", (species) => {
  const recorded = load(species);
  const steps = recorded.walks.flatMap((walk) => walk.steps);

  /**
   * Every label the fixture names. ⚠ Real labels are decimal integers, so none ends in `r` and the
   * direction marker is unambiguous over this set — which is asserted rather than assumed, because
   * the parse rule's whole delicacy is what happens when one does.
   */
  const labels = new Set<string>();
  for (const walk of recorded.walks) {
    labels.add(walk.seed_label);
    for (const step of walk.steps) labels.add(step.target_label);
  }
  const known = (label: string) => labels.has(label);

  it("the label set is unambiguous under the direction marker", () => {
    expect([...labels].filter((label) => label.endsWith("r"))).toEqual([]);
    expect(labels.size).toBeGreaterThan(1_000);
  });

  it("⭐ the direction after every step is the one the frozen page chose", () => {
    const disagreements: { step: RecordedStep; expected: string; actual: string }[] = [];
    for (const step of steps) {
      const after = parseLocusHash(step.hash_after, known);
      if (after === null) {
        disagreements.push({ step, expected: "a parsable route", actual: "null" });
        continue;
      }
      const predicted = walkDirectionAfterStep(step.data_dir === "fwd");
      if (predicted !== after.direction) {
        disagreements.push({ step, expected: after.direction, actual: predicted });
      }
    }
    expect(disagreements.slice(0, 3)).toEqual([]);
    expect(disagreements).toHaveLength(0);
    // Coverage, stated: this ran over every recorded step, not a sample.
    expect(steps.length).toBe(recorded.recorded_steps);
  });

  it("⛔ and a TOGGLE would disagree on thousands of them — so the test discriminates", () => {
    // Without this the suite above could pass against an implementation that toggles, on a fixture
    // that happened never to reverse twice. `lysR → smrA → iclR → atoD` is this count being > 0.
    let toggleDisagreements = 0;
    for (const step of steps) {
      const before = parseLocusHash(step.hash_before, known);
      const after = parseLocusHash(step.hash_after, known);
      if (before === null || after === null) continue;
      // What a toggle implementation would produce: flip the current frame on a reversed arrow.
      const toggled =
        step.data_dir === "rev" ? (before.direction === FORWARD ? REVERSED : FORWARD) : before.direction;
      if (toggled !== after.direction) toggleDisagreements++;
    }
    expect(toggleDisagreements).toBeGreaterThan(2_000);
  });

  it("the page navigated to the locus the clicked block named", () => {
    const wrong = steps.filter((step) => parseLocusHash(step.hash_after, known)?.label !== step.target_label);
    expect(wrong.slice(0, 3)).toEqual([]);
    expect(wrong).toHaveLength(0);
  });

  it("⭐ every recorded hash round-trips byte-identically through format/parse", () => {
    const hashes = new Set<string>();
    for (const step of steps) {
      hashes.add(step.hash_before);
      hashes.add(step.hash_after);
    }
    const broken: string[] = [];
    for (const hash of hashes) {
      const route = parseLocusHash(hash, known);
      if (route === null || formatLocusHash(route) !== hash) broken.push(hash);
    }
    expect(broken.slice(0, 3)).toEqual([]);
    expect(broken).toHaveLength(0);
    expect(hashes.size).toBeGreaterThan(1_000);
  });

  it("a walk that stopped early said WHY, and few did", () => {
    const stopped = recorded.walks.filter((walk) => walk.stopped !== null);
    for (const walk of stopped) expect(walk.stopped).toBe("no walkable neighbour");
    // A fixture in which most walks died immediately would satisfy every count above while
    // covering almost no ground.
    expect(stopped.length).toBeLessThan(recorded.walks.length / 10);
  });
});
