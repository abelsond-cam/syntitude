/**
 * The **one** async boundary, and the stale-response guard generalised from the page's `seqTok`.
 *
 * `app.js:4118` states the invariant this replaces: *"app.js is otherwise wholly synchronous by
 * choice… so the asynchrony is confined to `withSeq` and never leaks upward."* It cannot stay that
 * way once the catalogue lives in a database, so the discipline moves here instead:
 *
 * ⭐ **Exactly three things fetch**, and each gets its own lane: navigating to a locus, opening the
 * function tab, opening the sequence tab. Everything else the reader can do — switching arrangement,
 * flipping walk direction, opening a popover, changing map representation — is answered out of the
 * response already in hand. If a fourth lane appears, something has been moved off the hot path
 * that belongs on it.
 *
 * ⛔ **A superseded response is not a failure and not an empty result — it is a third thing**, and
 * {@link LaneOutcome} makes a component say so. A reader who walks on twice quickly supersedes their
 * own first request; rendering an error for that, or rendering nothing, are both wrong. The right
 * behaviour is to change nothing at all, and the early return that does it is visible in the code.
 */

import { type Failure, type Result, failure, success } from "./result";

/** ⛔ Same origin by default. A literal origin in source is what makes the next deploy a rewrite. */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

/** Join the base with a path, tolerating a trailing slash on either side. */
export function apiUrl(path: string): string {
  const base = API_BASE_URL.replace(/\/$/, "");
  return `${base}/${path.replace(/^\//, "")}`;
}

/**
 * One GET, parsed, as a {@link Result}.
 *
 * ⚠ Every failure mode is *named* rather than collapsed into a boolean: a 404 is the server
 * answering, and a reader can act on it; a network error is not, and retrying may work.
 */
export async function requestJson<T>(
  path: string,
  options: { signal?: AbortSignal; query?: Record<string, string | number | undefined> } = {},
): Promise<Result<T>> {
  const url = new URL(apiUrl(path), globalThis.location?.origin ?? "http://localhost");
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  // Relative when it can be — the URL object above exists to build the query string safely, not to
  // pin an origin into the request.
  const target = url.origin === (globalThis.location?.origin ?? "http://localhost")
    ? `${url.pathname}${url.search}`
    : url.toString();

  let response: Response;
  try {
    // `exactOptionalPropertyTypes` refuses `signal: undefined` here, and it is right to: an
    // absent key and a key holding `undefined` are different things to `RequestInit`.
    response = await fetch(target, {
      headers: { Accept: "application/json" },
      ...(options.signal ? { signal: options.signal } : {}),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    return failure("network", describe(error, "the request did not reach the server"));
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    return failure(
      "malformed",
      describe(error, "the server's answer was not JSON"),
      response.status,
    );
  }

  if (response.ok) return success(body as T);

  // The API answers a 404 with `{error, detail}` naming which of the species, the pangenome or the
  // locus was missing — so show the server's own sentence rather than inventing one.
  const detail =
    isRecord(body) && typeof body["detail"] === "string"
      ? body["detail"]
      : `the server answered ${response.status}`;
  return failure(response.status === 404 ? "not_found" : "server", detail, response.status);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function describe(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/**
 * What a lane hands back. Superseded is its own case, so it cannot be confused with either an
 * error or an empty answer.
 */
export type LaneOutcome<T> =
  | { readonly superseded: true }
  | { readonly superseded: false; readonly result: Result<T> };

const SUPERSEDED: LaneOutcome<never> = { superseded: true };

/**
 * A single in-flight request, with the one that came before it cancelled.
 *
 * ⚠ The token is checked **after** the await as well as relying on the abort: an abort is a request
 * to stop, not a guarantee the response has not already resolved. Both guards are needed, and the
 * token is the one that is actually sufficient.
 */
export class RequestLane {
  readonly name: string;
  private token = 0;
  private controller: AbortController | null = null;

  constructor(name: string) {
    this.name = name;
  }

  /** Whether a request is in flight. Drives the `refreshing` state, never the `pending` one. */
  get isBusy(): boolean {
    return this.controller !== null;
  }

  async run<T>(work: (signal: AbortSignal) => Promise<Result<T>>): Promise<LaneOutcome<T>> {
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    const issued = ++this.token;
    try {
      const result = await work(controller.signal);
      if (issued !== this.token) return SUPERSEDED;
      return { superseded: false, result };
    } catch (error) {
      if (issued !== this.token) return SUPERSEDED;
      if (error instanceof Error && error.name === "AbortError") return SUPERSEDED;
      return {
        superseded: false,
        result: failure("network", describe(error, "the request failed")) satisfies Failure,
      };
    } finally {
      if (issued === this.token) this.controller = null;
    }
  }

  /** Abandon whatever is in flight — leaving the view as it is, not as an error. */
  cancel(): void {
    this.controller?.abort();
    this.controller = null;
    this.token++;
  }
}

/**
 * ⛔ **The lanes, named here rather than created ad hoc so that adding one is a visible edit to
 * this list and has to be argued for.** Three of them are the hot path's own rule — navigating,
 * opening the EggNOG tab, opening the Sequence tab — and the fourth is argued below.
 *
 * ⭐ **`arrangements` — the argument, made once, so the next lane has to clear the same bar.**
 * The three-lane rule exists to keep the *hot path* one round trip: everything a reader does to
 * the drawn locus — switching arrangement, flipping the frame, opening a popover, changing map
 * representation — is answered from the response already in hand. Paging past the arrangement cut
 * is not on that path. It is a deliberate second act by a reader who has opened the A0 card, and
 * it is the fourth fetch the design named from the start.
 *
 * It cannot ride either of the other lanes, and the reason is supersession rather than tidiness:
 * `RequestLane.run` **cancels whatever that lane is holding**. On `navigation`, asking for the next
 * page of arrangements would abort the reader's own walk; on `function`, opening the EggNOG tab
 * while the scroller loads would abort one of two independent surfaces. Lanes are not a namespace —
 * they are a cancellation domain, and these are three domains.
 *
 * ⚠ Navigating away must still discard an arrangement page in flight, and the lane cannot do that
 * on its own. `arrangementBrowserStore` cancels this lane when the drawn locus changes, and
 * re-checks the label after the await, because a Vue watcher runs after the microtask that resolves
 * the fetch.
 */
export const LANES = {
  navigation: new RequestLane("navigation"),
  function: new RequestLane("function"),
  sequence: new RequestLane("sequence"),
  arrangements: new RequestLane("arrangements"),
} as const;
