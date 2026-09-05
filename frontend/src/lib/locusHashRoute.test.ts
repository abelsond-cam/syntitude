import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";

import { describe, expect, it } from "vitest";

import {
  TRAIL_LIMIT,
  advanceTrail,
  formatLocusHash,
  parseLocusHash,
  sameRoute,
  shadowedReverseRoutes,
} from "./locusHashRoute";
import { FORWARD, REVERSED } from "./walkDirection";

/** The published catalogues label loci with decimal integers; `known` mimics that lookup. */
const CATALOGUE = new Set(["0", "1", "42", "17530"]);
const known = (label: string) => CATALOGUE.has(label);

describe("formatting", () => {
  it("is the bare label when the reader faces forward", () => {
    expect(formatLocusHash({ label: "42", direction: FORWARD })).toBe("#42");
  });

  it("carries a trailing r when the frame is reversed", () => {
    expect(formatLocusHash({ label: "42", direction: REVERSED })).toBe("#42r");
  });

  it("⚠ does NOT percent-encode, because the published page assigns location.hash raw", () => {
    // Encoding here would produce a different URL for the same locus, and the parity suite's
    // round-trip is byte-for-byte against the frozen page.
    expect(formatLocusHash({ label: "a b", direction: FORWARD })).toBe("#a b");
  });
});

describe("parsing", () => {
  it("reads a plain label as forward", () => {
    expect(parseLocusHash("#42", known)).toEqual({ label: "42", direction: FORWARD });
  });

  it("reads a trailing r as reversed", () => {
    expect(parseLocusHash("#42r", known)).toEqual({ label: "42", direction: REVERSED });
  });

  it("tolerates a hash with no leading #", () => {
    expect(parseLocusHash("42", known)).toEqual({ label: "42", direction: FORWARD });
  });

  it("decodes what the browser encoded", () => {
    expect(parseLocusHash("#a%20b", (label) => label === "a b")).toEqual({
      label: "a b",
      direction: FORWARD,
    });
  });

  it("⛔ a label that genuinely ends in r WINS over the direction marker", () => {
    // The whole string is tested first. Stripping before asking would send this reader to a
    // different locus, drawn backwards — and both loci exist, so nothing would look wrong.
    const labels = new Set(["abcr", "abc"]);
    expect(parseLocusHash("#abcr", (label) => labels.has(label))).toEqual({
      label: "abcr",
      direction: FORWARD,
    });
  });

  it("and falls through to the marker when the whole string is not a label", () => {
    const labels = new Set(["abc"]);
    expect(parseLocusHash("#abcr", (label) => labels.has(label))).toEqual({
      label: "abc",
      direction: REVERSED,
    });
  });

  it("returns null for an unknown locus rather than guessing", () => {
    expect(parseLocusHash("#999", known)).toBeNull();
    expect(parseLocusHash("#999r", known)).toBeNull();
  });

  it("returns null for an empty hash", () => {
    expect(parseLocusHash("", known)).toBeNull();
    expect(parseLocusHash("#", known)).toBeNull();
  });

  it("returns null for a bare marker, so `#r` is never locus `''` reversed", () => {
    expect(parseLocusHash("#r", (label) => label === "")).toBeNull();
  });

  it("⚠ survives a malformed escape instead of throwing inside a hashchange listener", () => {
    // An exception here leaves the page on the previous locus with a URL that says otherwise.
    expect(parseLocusHash("#%", known)).toBeNull();
  });

  it("⛔ is not fooled by an inherited object property", () => {
    // `app.js` asks `byLabel[h] == null` against a bare object, so `#constructor` resolves to a
    // truthy inherited property and is treated as a locus. A predicate cannot have the bug.
    expect(parseLocusHash("#constructor", known)).toBeNull();
    expect(parseLocusHash("#__proto__", known)).toBeNull();
  });
});

describe("the round trip", () => {
  it("⭐ holds for every label in the catalogue, in both directions", () => {
    for (const label of CATALOGUE) {
      for (const direction of [FORWARD, REVERSED] as const) {
        const route = { label, direction };
        expect(parseLocusHash(formatLocusHash(route), known)).toEqual(route);
      }
    }
  });

  it("holds for a label ending in r when nothing shadows it", () => {
    const labels = new Set(["abcr"]);
    const isKnown = (label: string) => labels.has(label);
    for (const direction of [FORWARD, REVERSED] as const) {
      const route = { label: "abcr", direction };
      // `abcr` reversed formats as `#abcrr`, which parses back by stripping ONE marker.
      expect(parseLocusHash(formatLocusHash(route), isKnown)).toEqual(route);
    }
  });

  it("⛔ does NOT hold for `abc` reversed when `abcr` is also a locus — and that is the encoding", () => {
    // `#abcr` is both. The whole-string-first rule resolves it toward `abcr`, which is the right
    // call — a locus must always be reachable — but `abc` REVERSED then has no URL at all. This is
    // a property of the published page's hash, which cannot change without breaking saved links,
    // so it is pinned here as a known limit rather than left to be rediscovered as a bug report.
    const labels = new Set(["abcr", "abc"]);
    const isKnown = (label: string) => labels.has(label);
    expect(parseLocusHash(formatLocusHash({ label: "abc", direction: REVERSED }), isKnown)).toEqual({
      label: "abcr",
      direction: FORWARD,
    });
    // Every other route in that catalogue still round-trips.
    for (const route of [
      { label: "abc", direction: FORWARD },
      { label: "abcr", direction: FORWARD },
      { label: "abcr", direction: REVERSED },
    ] as const) {
      expect(parseLocusHash(formatLocusHash(route), isKnown)).toEqual(route);
    }
  });
});

describe("⭐ shadowed routes are MEASURED, not assumed away", () => {
  it("names the labels whose reversed route the encoding cannot express", () => {
    expect(shadowedReverseRoutes(["abc", "abcr", "xyz"])).toEqual(["abc"]);
  });

  it("finds nothing when no label is another plus r", () => {
    expect(shadowedReverseRoutes(["0", "1", "42"])).toEqual([]);
  });

  it("chains, so `a` / `ar` / `arr` all report", () => {
    expect(shadowedReverseRoutes(["a", "ar", "arr"])).toEqual(["a", "ar"]);
  });

  it("⛔ the PUBLISHED catalogues have none — checked, and it says so when it cannot check", () => {
    // ⚠ Not-looked-at and no-problem-found must never be the same output. If the catalogue is not
    // on this machine the test names that; it does not pass quietly.
    const catalogues = ["ecoli", "kp"].map((species) =>
      fileURLToPath(new URL(`../../../data/${species}.json`, import.meta.url)),
    );
    const present = catalogues.filter((path) => existsSync(path));
    if (present.length === 0) {
      // eslint-disable-next-line no-console
      console.warn("published catalogues absent — shadowed-route check NOT performed");
      expect(present).toHaveLength(0);
      return;
    }
    expect(present).toHaveLength(2);
    for (const path of present) {
      const labels: string[] = JSON.parse(readFileSync(path, "utf8")).nodes.label;
      expect(labels.length).toBeGreaterThan(10_000);
      expect(shadowedReverseRoutes(labels)).toEqual([]);
    }
  });
});

describe("sameRoute", () => {
  it("distinguishes direction as well as locus", () => {
    expect(sameRoute({ label: "1", direction: FORWARD }, { label: "1", direction: FORWARD })).toBe(true);
    expect(sameRoute({ label: "1", direction: FORWARD }, { label: "1", direction: REVERSED })).toBe(false);
    expect(sameRoute({ label: "1", direction: FORWARD }, { label: "2", direction: FORWARD })).toBe(false);
    expect(sameRoute(null, null)).toBe(true);
    expect(sameRoute(null, { label: "1", direction: FORWARD })).toBe(false);
  });
});

describe("the breadcrumb", () => {
  it("extends when the reader walks on", () => {
    expect(advanceTrail(["a", "b"], "c")).toEqual(["a", "b", "c"]);
  });

  it("⛔ RETREATS rather than growing when the reader goes back", () => {
    // Back fires hashchange, which lands in the same path as a click. Pushing unconditionally made
    // the breadcrumb grow when the reader stepped backwards.
    expect(advanceTrail(["a", "b", "c"], "b")).toEqual(["a", "b"]);
  });

  it("ignores a step onto the locus already being read", () => {
    expect(advanceTrail(["a", "b"], "b")).toEqual(["a", "b"]);
  });

  it("pushes a revisit that is not the previous entry", () => {
    // `a` is in the trail but is not where the reader came from, so this is travel, not a retreat.
    expect(advanceTrail(["a", "b", "c"], "a")).toEqual(["a", "b", "c", "a"]);
  });

  it("starts a trail from empty", () => {
    expect(advanceTrail([], "a")).toEqual(["a"]);
  });

  it("drops the oldest entry past the limit", () => {
    const full = Array.from({ length: TRAIL_LIMIT }, (_unused, index) => `L${index}`);
    const next = advanceTrail(full, "new");
    expect(next).toHaveLength(TRAIL_LIMIT);
    expect(next[0]).toBe("L1");
    expect(next[next.length - 1]).toBe("new");
  });

  it("never mutates the trail it was given", () => {
    const before = ["a", "b", "c"];
    const snapshot = [...before];
    advanceTrail(before, "b");
    advanceTrail(before, "d");
    expect(before).toEqual(snapshot);
  });

  it("⭐ a walk out and back returns the trail to where it started", () => {
    let trail: string[] = ["a"];
    for (const label of ["b", "c", "d"]) trail = advanceTrail(trail, label);
    expect(trail).toEqual(["a", "b", "c", "d"]);
    for (const label of ["c", "b", "a"]) trail = advanceTrail(trail, label);
    expect(trail).toEqual(["a"]);
  });
});
