/**
 * The reader's direction of travel — **absolute, never a toggle.**
 *
 * ⛔ **This module deliberately exports no toggle, no flip and no invert.** The bug of record
 * (`lysR → smrA → iclR → atoD`) was `walkFlip = !walkFlip` applied on top of a strand relation that
 * had *already* been mirrored for display: the first antiparallel step was right, the second
 * inverted, and the track spun back on itself instead of carrying on along the stream. It rendered
 * perfectly the whole way. Every rewrite reaches for the toggle because "stepping onto a reversed
 * gene flips the frame" reads like one — so the only way to set this state is to say what it
 * becomes, and there is no function here that could express the other thing.
 *
 * The rule, from `app.js:3733-3748`: the strand relation handed in is **the orientation as drawn**,
 * the direction the block's arrow points on screen — not the raw relation recorded in the data.
 */

/** Which way the reader is travelling. `reversed` means the focal gene is read right-to-left. */
export type WalkDirection = "forward" | "reversed";

export const FORWARD: WalkDirection = "forward";
export const REVERSED: WalkDirection = "reversed";

/**
 * The direction after stepping onto a neighbour, given the arrow the reader clicked.
 *
 * - `undefined` — a **jump**, not a walk (search, a chip, a breadcrumb, a deep link). There is no
 *   direction of travel to carry forward, so the new locus faces forward.
 * - `true` — the block points the way the reader is already travelling: the new focal gene is read
 *   forwards, so the frame is unflipped.
 * - `false` — it points back: the new focal gene is read backwards, so the frame reverses.
 *
 * ⚠ The result depends on **nothing but the argument**. It is not a function of the current
 * direction, and it must never become one: `sameStrandAsDrawn` has already been through the
 * display mirroring, so composing it with the current direction mirrors twice.
 */
export function walkDirectionAfterStep(sameStrandAsDrawn: boolean | undefined): WalkDirection {
  return sameStrandAsDrawn === undefined || sameStrandAsDrawn ? FORWARD : REVERSED;
}

/** Whether a direction mirrors the track. Kept as a named function so no caller compares strings. */
export function isReversed(direction: WalkDirection): boolean {
  return direction === REVERSED;
}
