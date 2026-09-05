import { describe, expect, it } from "vitest";

import { POPOVER_GAP_PX, type Rect, placePopover } from "./popoverPlacement";

function rect(left: number, top: number, width: number, height = 20): Rect {
  return { left, top, bottom: top + height, width };
}

const host = { ...rect(100, 50, 800), clientWidth: 800 };

describe("the popover sits under the bar that opened it", () => {
  it("is centred on the anchor, in the HOST's coordinates", () => {
    // Anchor centre is at 300+40 = 340 absolute, i.e. 240 within the host; a 100-wide popover
    // therefore starts at 190.
    const position = placePopover(rect(300, 200, 80), host, 100);
    expect(position.leftPx).toBe(190);
  });

  it("sits below the anchor by the gap, not on top of it", () => {
    const position = placePopover(rect(300, 200, 80), host, 100);
    // anchor.bottom (220) − host.top (50) + gap
    expect(position.topPx).toBe(220 - 50 + POPOVER_GAP_PX);
  });

  it("⛔ clamps at the right edge so an edge slot cannot push it off screen", () => {
    const position = placePopover(rect(880, 200, 20), host, 200);
    expect(position.leftPx).toBe(600); // clientWidth 800 − width 200
  });

  it("⛔ clamps at the left edge too", () => {
    const position = placePopover(rect(100, 200, 20), host, 200);
    expect(position.leftPx).toBe(0);
  });

  it("⚠ a popover WIDER than its host lands at 0, not at a negative offset", () => {
    // The clamp order matters: `Math.min` last would put a too-wide panel off the LEFT edge, where
    // it is unreachable, instead of overflowing to the right where it can still be read.
    const position = placePopover(rect(300, 200, 80), host, 1_000);
    expect(position.leftPx).toBe(0);
  });

  it("uses the anchor's live position, so scrolling the track moves it", () => {
    // The track scrolls horizontally under a panel that does not. Two different anchor rects for
    // the same bar must give two different positions, or the popover detaches from its block.
    const before = placePopover(rect(300, 200, 80), host, 100);
    const after = placePopover(rect(220, 200, 80), host, 100);
    expect(after.leftPx).toBe(before.leftPx - 80);
  });
});
