/**
 * Where the popover sits: centred under the bar that opened it, clamped inside its host.
 *
 * ⭐ **Pure arithmetic over rectangles, deliberately.** jsdom computes no layout, so a placement that
 * read the DOM directly could not be tested at all. The caller measures; this decides.
 *
 * ⚠ **A popover that outlives what it points at is worse than no popover.** It follows its bar on
 * scroll and on resize, and everything is measured from live rects rather than cached — the track
 * scrolls horizontally under a panel that does not, so a position computed once detaches from its
 * bar the moment the reader scrolls sideways and then points confidently at the wrong block.
 */

/** The subset of `DOMRect` this needs. Named so a test can build one without a browser. */
export interface Rect {
  readonly left: number;
  readonly top: number;
  readonly bottom: number;
  readonly width: number;
}

/** How far below the bar the popover sits. */
export const POPOVER_GAP_PX = 8;

export interface PopoverPosition {
  readonly leftPx: number;
  readonly topPx: number;
}

/**
 * Position the popover under its anchor, in the host's own coordinates.
 *
 * ⚠ Coordinates are relative to `host`, so horizontal scrolling of the track is already accounted
 * for by the caller's `getBoundingClientRect` and no scroll term appears here.
 *
 * ⛔ Clamped to the host so an edge slot cannot push the panel off screen — and clamped with the
 * lower bound applied LAST, so a popover wider than its host lands at 0 rather than at a negative
 * offset. `Math.min` first would put it off the left edge instead of the right.
 */
export function placePopover(
  anchor: Rect,
  host: Rect & { readonly clientWidth: number },
  popoverWidth: number,
): PopoverPosition {
  const centred = anchor.left - host.left + anchor.width / 2 - popoverWidth / 2;
  const rightmost = host.clientWidth - popoverWidth;
  return {
    leftPx: Math.max(0, Math.min(centred, rightmost)),
    topPx: anchor.bottom - host.top + POPOVER_GAP_PX,
  };
}

/**
 * Which offset a popover's HEADING names, given the observed slot it was opened on.
 *
 * ⛔ The heading has to name the column the reader **clicked**, not the position the counts came
 * from. On a row drawn mirrored those differ, and a panel reading "A−1" beside a block labelled
 * "A+1" looks like different data (`app.js:2207-2216`).
 *
 * Returns both, so a caller can say "recorded at …" exactly when they disagree — which is the only
 * case where the distinction is visible, and covers an arrangement flip and a reversed walk
 * cancelling, where reading the flip alone gets it wrong.
 */
export interface PopoverHeading {
  /** The offset the clicked COLUMN is labelled with. */
  readonly labelledOffset: number;
  /** The offset the counts were RECORDED at. */
  readonly recordedOffset: number;
  /** Whether to print the "↺ recorded at …" note. */
  readonly isDrawnMirrored: boolean;
}
