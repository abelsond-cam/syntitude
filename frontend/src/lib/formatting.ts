/**
 * The page's shared number formatting. One rule per number, in one place, so two panels showing
 * the same quantity cannot round it differently.
 */

/**
 * A share of a whole, as a percentage.
 *
 * ⚠ **A deliberate, single divergence from the published page**, written down because an
 * undocumented one is how two "authoritative" renderings come to disagree. `app.js`'s `pct` rounds
 * to whole percent everywhere it is called (`app.js:858`), so an occupant carried by 2 of 500
 * member genes prints as **"2 · 0%"** — a real, listed row reporting zero. Below 10 % this keeps
 * one decimal, so that row reads "2 · 0.4%" instead. Nothing above 10 % changes, which is every
 * number a parity diff of the shipped catalogues actually compares.
 */
export function sharePercent(share: number): string {
  return `${(100 * share).toFixed(share < 0.1 ? 1 : 0)}%`;
}

/** `n` with the singular or plural of `noun`, e.g. `1 neighbourhood` / `3 neighbourhoods`. */
export function pluralise(count: number, noun: string, plural = `${noun}s`): string {
  return `${count} ${count === 1 ? noun : plural}`;
}
