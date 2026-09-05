/**
 * The URL is a **hash route**, and it carries exactly two things: which locus, and which way the
 * reader is facing.
 *
 * ⭐ **Hash routing is a decision, not a leftover.** It is what makes the browser's own Back button
 * walk the reader's trail, on a server that needs no rewrite rule to serve a deep link.
 *
 * ⛔ **What stays OUT of the URL**, and each for its own reason:
 * - the **anchor genome** — session state. It is deliberately not in the hash, which already
 *   carries a trailing `r`; putting it there would make every anchor change a history entry
 *   (`app.js:195-200`).
 * - the **selected arrangement** — a default per locus, re-derived on arrival.
 * - the **open popover**, the **view tab** and the **map representation** — none of them is a place.
 *
 * ⚠ Anything added here becomes a history entry and a link someone will send to a colleague, so it
 * has to be something that still means the same thing tomorrow.
 */

import { FORWARD, REVERSED, isReversed, type WalkDirection } from "./walkDirection";

/** Where the reader is: one locus, and which way round they are reading it. */
export interface LocusRoute {
  readonly label: string;
  readonly direction: WalkDirection;
}

/**
 * ⛔ The direction marker. A **single trailing `r`**, and the whole delicacy of parsing lives in the
 * fact that a locus label may itself end in one.
 */
const DIRECTION_MARKER = "r";

/**
 * The hash for a route, `#` included — byte-identical to what the published page writes.
 *
 * ⚠ The label is **not** percent-encoded, because `app.js` assigns `location.hash` raw and lets the
 * browser encode whatever it must. Encoding here would produce a different URL for the same locus
 * and break the parity suite's round-trip on any label outside the unreserved set.
 */
export function formatLocusHash(route: LocusRoute): string {
  return `#${route.label}${isReversed(route.direction) ? DIRECTION_MARKER : ""}`;
}

/**
 * Read a hash back into a route, or `null` if it names no locus in this catalogue.
 *
 * ⛔ **The whole string is tested as a label first.** Labels are node ids, so a trailing `r` is the
 * direction marker *only if what remains is itself a label* — which is what keeps an id that
 * genuinely ends in `r` winning over the marker (`app.js:3765-3767`). Stripping first and asking
 * afterwards would silently redirect such a locus to a different one, drawn backwards.
 *
 * `isKnownLabel` is a predicate rather than a lookup object on purpose: `app.js` asks
 * `byLabel[h] == null` against a bare object, so `#constructor` resolves to a truthy inherited
 * property and is treated as a locus. No real label reaches it — they are decimal integers — but a
 * predicate cannot have the bug at all.
 */
export function parseLocusHash(
  hash: string,
  isKnownLabel: (label: string) => boolean,
): LocusRoute | null {
  let text: string;
  try {
    text = decodeURIComponent(hash.replace(/^#/, ""));
  } catch {
    // A malformed escape is not a locus. `decodeURIComponent('%')` throws, and an unhandled
    // exception in a `hashchange` listener leaves the page on the previous locus with a URL that
    // says otherwise.
    return null;
  }
  if (!text) return null;
  if (isKnownLabel(text)) return { label: text, direction: FORWARD };
  if (text.endsWith(DIRECTION_MARKER)) {
    const stem = text.slice(0, -1);
    if (stem && isKnownLabel(stem)) return { label: stem, direction: REVERSED };
  }
  return null;
}

/**
 * ⛔ **The labels whose reversed route this encoding cannot express.**
 *
 * `#abcr` is ambiguous: it is locus `abcr` faced forward *and* locus `abc` faced backward. The
 * whole-string-first rule in {@link parseLocusHash} resolves it toward `abcr` — the right call,
 * because a locus must always be reachable — but the cost is that `abc` reversed then has no URL,
 * and a reader who lands on it via a walk gets a hash that navigates somewhere else on reload.
 *
 * ⚠ **Neither published catalogue can hit this**: labels are decimal integers, so none ends in `r`
 * and the set below is empty. That is a fact about today's naming, not about the encoding, and the
 * moment a model labels loci by gene symbol it stops being true. So it is *measured* rather than
 * assumed — call this at ingest or at boot and fail loudly, because the alternative is a handful of
 * loci whose links quietly point at their neighbours.
 *
 * Returns the shadowed labels — those `X` for which `X + "r"` is also a label.
 */
export function shadowedReverseRoutes(labels: Iterable<string>): string[] {
  const all = labels instanceof Set ? labels : new Set(labels);
  const shadowed: string[] = [];
  for (const label of all) {
    if (all.has(label + DIRECTION_MARKER)) shadowed.push(label);
  }
  return shadowed.sort();
}

/** Two routes name the same place. */
export function sameRoute(a: LocusRoute | null, b: LocusRoute | null): boolean {
  if (a === null || b === null) return a === b;
  return a.label === b.label && a.direction === b.direction;
}

/**
 * How many steps of the breadcrumb are kept. Beyond this the oldest is dropped — the trail is a
 * reading aid, not a history.
 */
export const TRAIL_LIMIT = 24;

/**
 * Extend the breadcrumb — **and retreat along it rather than growing it when the reader goes back.**
 *
 * ⛔ Back fires `hashchange`, which lands in the same navigation path as a click, so pushing
 * unconditionally made the breadcrumb *grow* when the reader stepped backwards (`app.js:3720-3725`).
 * Stepping onto the entry before the last one is a retreat: pop.
 *
 * Returns a new array; the input is never mutated.
 */
export function advanceTrail(
  trail: readonly string[],
  label: string,
  limit: number = TRAIL_LIMIT,
): string[] {
  const next = trail.slice();
  if (next.length > 1 && next[next.length - 2] === label) {
    next.pop();
  } else if (next[next.length - 1] !== label) {
    next.push(label);
  }
  while (next.length > limit) next.shift();
  return next;
}
