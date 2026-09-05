/**
 * ⛔ **A failed request and an empty result must never render the same.**
 *
 * The rule generalises from `app.js:4604` — *"a sequence panel that fails silently is one a reader
 * will read as 'this genome has nothing here', which is a different claim and a false one"*. The
 * enforcement is in the type: every API call returns `Result<T>`, **never `T | null`**, so a
 * component physically cannot reach the data without having said what it does when there is none.
 *
 * `T | null` is the shape that permits the bug, because `null` is exactly as falsy as an empty
 * list. This module has no unwrap-or-default, no `.value ?? fallback`, and no way to turn a failure
 * into an absence quietly.
 */

/** The call succeeded. `value` is the parsed body. */
export interface Success<T> {
  readonly ok: true;
  readonly value: T;
}

/**
 * The call did not succeed, and says which way.
 *
 * ⚠ `kind` exists because these are four different sentences to a reader, not four spellings of
 * "something went wrong":
 * - `not_found` — the server answered, and said this locus/species/genome is not here. A real
 *   answer, and the only one a reader can act on.
 * - `network` — the request never reached a server. Retrying may work.
 * - `server` — it reached one and it failed. Retrying probably will not.
 * - `malformed` — it answered, and the body was not what the contract says. That is our bug.
 */
export interface Failure {
  readonly ok: false;
  readonly kind: "not_found" | "network" | "server" | "malformed";
  /** One sentence, safe to show a reader. Never a stack trace. */
  readonly detail: string;
  /** Present when a server answered at all. */
  readonly status?: number;
}

export type Result<T> = Success<T> | Failure;

export function success<T>(value: T): Success<T> {
  return { ok: true, value };
}

export function failure(
  kind: Failure["kind"],
  detail: string,
  status?: number,
): Failure {
  return status === undefined ? { ok: false, kind, detail } : { ok: false, kind, detail, status };
}

/**
 * Map a successful value, leaving a failure alone.
 *
 * ⚠ Deliberately the ONLY combinator here. A `getOrElse` would be the whole bug in one function
 * call, and an `unwrap` that throws moves the decision into a `try` a component will not write.
 */
export function mapResult<T, U>(result: Result<T>, transform: (value: T) => U): Result<U> {
  return result.ok ? success(transform(result.value)) : result;
}

/**
 * A raised {@link Failure}, for the one place a throw is right: a request that was superseded.
 * See `request.ts`.
 */
export class SupersededError extends Error {
  constructor(message = "superseded by a later request") {
    super(message);
    this.name = "SupersededError";
  }
}
