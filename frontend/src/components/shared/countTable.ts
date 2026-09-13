/**
 * The count table's contract, in a module of its own.
 *
 * ⚠ It cannot live inside `CountTable.vue`: the `generic="Row extends CountRow"` attribute is
 * resolved before that block's own declarations exist, so a type declared there is not in scope for
 * the constraint that uses it.
 */

/** The widest a share bar may be drawn, in px — the scale the published table uses. */
export const SHARE_BAR_MAX_PX = 46;
/** ⚠ A floor, so a single-gene row is still a visible mark rather than nothing at all. */
export const SHARE_BAR_MIN_PX = 2;

export interface CountRow {
  /** Stable across a re-render — an accession, not an index. */
  readonly key: string;
  readonly count: number;
}

/**
 * ⚠ Returned in px and applied inline (`app.js:1198`): *"the JS test harness loads no stylesheet, so
 * an inline width is the only version of this that any test can see."* jsdom computes no layout
 * either, so moving this into CSS blanks every assertion about it.
 */
export function shareBarWidthPx(count: number, total: number): number {
  if (total <= 0) return SHARE_BAR_MIN_PX;
  return Math.max(SHARE_BAR_MIN_PX, Math.round((SHARE_BAR_MAX_PX * count) / total));
}

/** ⛔ Zero denominator yields a share of 0, never `NaN` — which renders as the word "NaN". */
export function shareOf(count: number, total: number): number {
  return total > 0 ? count / total : 0;
}
