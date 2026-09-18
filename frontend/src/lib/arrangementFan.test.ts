import { describe, expect, it } from "vitest";

import { NO_FAN, arrangementFan, type FanRect } from "./arrangementFan";

function rect(left: number, top: number, width: number, height = 20): FanRect {
  return { left, top, width, right: left + width, bottom: top + height };
}

const WRAPPER = rect(100, 500, 1000, 200);

describe("the arrangement fan", () => {
  it("leaves the gene and arrives at each option VERTICALLY — never a diagonal across the track", () => {
    const fan = arrangementFan(rect(580, 300, 40), WRAPPER, [{ rect: rect(300, 560, 100), isOn: true }], null);
    // x0 = 580 + 20 − 100 = 500; x1 = 300 + 50 − 100 = 250; y1 = 60; control points at 55 % of the drop.
    expect(fan.curves[0]!.d).toBe("M500 0 C500 33 250 33 250 60");
    expect(fan.height).toBe(60);
    expect(fan.width).toBe(1000);
  });

  it("marks exactly the drawn arrangement's curve", () => {
    const fan = arrangementFan(
      rect(580, 300, 40),
      WRAPPER,
      [
        { rect: rect(300, 560, 100), isOn: false },
        { rect: rect(450, 560, 100), isOn: true },
      ],
      null,
    );
    expect(fan.curves.map((curve) => curve.isOn)).toEqual([false, true]);
  });

  it("⚠ draws NOTHING when the focal gene has scrolled out of the track", () => {
    const scroller = rect(100, 280, 800, 120);
    const offToTheRight = rect(950, 300, 40);
    expect(arrangementFan(offToTheRight, WRAPPER, [{ rect: rect(300, 560, 100), isOn: true }], scroller)).toEqual(
      NO_FAN,
    );
  });

  it("keeps a visible floor when the options sit right under the gene", () => {
    const fan = arrangementFan(rect(580, 300, 40), WRAPPER, [{ rect: rect(300, 502, 100), isOn: true }], null);
    expect(fan.height).toBe(8);
  });

  it("is nothing at all with nothing to join", () => {
    expect(arrangementFan(rect(580, 300, 40), WRAPPER, [], null)).toEqual(NO_FAN);
  });
});
