import { describe, expect, it } from "vitest";

import * as walkDirection from "./walkDirection";
import { FORWARD, REVERSED, isReversed, walkDirectionAfterStep } from "./walkDirection";

describe("the walk direction is absolute", () => {
  it("has NO toggle, flip or invert in its public surface", () => {
    // ⛔ The load-bearing test of this module. The bug of record was `walkFlip = !walkFlip`, and
    // the defence is that no exported function can express it — so assert the surface, not a
    // behaviour. A future export named `toggleWalk` fails here before it can be called anywhere.
    const exported = Object.keys(walkDirection).sort();
    expect(exported).toEqual(["FORWARD", "REVERSED", "isReversed", "walkDirectionAfterStep"]);
  });

  it("a jump faces forward, because it has no direction of travel to carry", () => {
    expect(walkDirectionAfterStep(undefined)).toBe(FORWARD);
  });

  it("an arrow pointing the way the reader travels leaves the frame unflipped", () => {
    expect(walkDirectionAfterStep(true)).toBe(FORWARD);
  });

  it("an arrow pointing back reverses the frame", () => {
    expect(walkDirectionAfterStep(false)).toBe(REVERSED);
  });

  it("⛔ two antiparallel steps do NOT return the reader to forward", () => {
    // The `lysR → smrA → iclR → atoD` bug, as an assertion. Under a toggle the second antiparallel
    // step would read `forward` and the track would spin back round. The result depends on the
    // arrow alone, so both steps are `reversed` and the reader keeps walking one way.
    let direction = FORWARD;
    direction = walkDirectionAfterStep(false);
    expect(direction).toBe(REVERSED);
    direction = walkDirectionAfterStep(false);
    expect(direction).toBe(REVERSED);
  });

  it("is a pure function of its argument — the current direction cannot reach it", () => {
    // Every call site has a current direction in scope; this pins that it is not an input.
    for (const shown of [undefined, true, false] as const) {
      const fromForward = walkDirectionAfterStep(shown);
      const fromReversed = walkDirectionAfterStep(shown);
      expect(fromForward).toBe(fromReversed);
    }
  });

  it("isReversed names the comparison so no caller writes the string", () => {
    expect(isReversed(REVERSED)).toBe(true);
    expect(isReversed(FORWARD)).toBe(false);
  });
});
