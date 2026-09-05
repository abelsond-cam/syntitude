/**
 * The locus cache — **a pure function of its key, with nothing that can invalidate it.**
 *
 * ⭐ Because there are no user writes, a response is immutable for a build. Nothing goes stale
 * within a session, so this store has no expiry, no revalidation and no invalidation API. That is
 * the single largest payoff of the read-only scope, and it is what makes prefetching on
 * `pointerenter` free: the cursor sits on a block for 150–300 ms before the click, which covers a
 * 4 kB response, and a prefetch that is never used costs one request and no correctness risk.
 *
 * ⛔ **The key includes the anchor**, and that is not defensive. Given an anchor the API includes
 * the arrangement that genome carries *even when it sits past the display cap* — so the same locus
 * has genuinely different responses with and without one. Keying on the label alone would serve a
 * reader who has just set an anchor the response from before they set it, in which their genome's
 * arrangement is missing, and the page would tell them in words that it sits at #37 with no button
 * to go back to it. That is the exact failure the anchor exists to prevent.
 */

import { defineStore } from "pinia";
import { ref, shallowRef } from "vue";

import { fetchLocus } from "@/api/client";
import type { LocusDetailResponse } from "@/api/types";

/** How many locus responses to hold. A walk of 40 steps fits comfortably. */
export const CACHE_LIMIT = 120;

/**
 * ⛔ Include the anchor. See the module header — the response shape depends on it.
 * `null` and the empty string are the same state (no anchor) and must produce the same key, or a
 * control that clears itself to `""` silently doubles the cache.
 */
export function locusCacheKey(
  speciesKey: string,
  locusLabel: string,
  anchorSampleId: string | null,
): string {
  return `${speciesKey} ${locusLabel} ${anchorSampleId || ""}`;
}

export const useLocusDetailCacheStore = defineStore("locusDetailCache", () => {
  /**
   * ⚠ A plain `Map`, deliberately NOT reactive. A locus response is a deep object of ~14 kB and
   * making Vue track every field of every cached one costs proxy creation on the hot path for
   * reactivity nothing reads — components watch the *current* locus in the navigation store, never
   * the cache. `size` is mirrored into a ref for the few places that want to show it.
   */
  const entries = new Map<string, LocusDetailResponse>();
  const size = ref(0);
  /** Which keys have a prefetch in flight, so hovering twice does not fetch twice. */
  const inFlight = shallowRef(new Set<string>());

  function get(key: string): LocusDetailResponse | undefined {
    const found = entries.get(key);
    if (found !== undefined) {
      // Least-recently-used: re-insert so the eviction below drops what a walk has left behind.
      entries.delete(key);
      entries.set(key, found);
    }
    return found;
  }

  function has(key: string): boolean {
    return entries.has(key);
  }

  function put(key: string, value: LocusDetailResponse): void {
    entries.delete(key);
    entries.set(key, value);
    while (entries.size > CACHE_LIMIT) {
      const oldest = entries.keys().next();
      if (oldest.done) break;
      entries.delete(oldest.value);
    }
    size.value = entries.size;
  }

  /**
   * Warm the cache for a locus the reader is hovering. **Never reports anything**: a prefetch that
   * fails must leave no trace, because the reader did not ask for it and the click that follows
   * will make the request again and report properly.
   *
   * ⚠ Runs on no lane. A lane would cancel the navigation the reader is actually waiting on.
   */
  async function prefetch(
    speciesKey: string,
    locusLabel: string,
    anchorSampleId: string | null,
  ): Promise<void> {
    const key = locusCacheKey(speciesKey, locusLabel, anchorSampleId);
    if (entries.has(key) || inFlight.value.has(key)) return;
    inFlight.value.add(key);
    try {
      const result = await fetchLocus(speciesKey, locusLabel, {
        ...(anchorSampleId ? { anchorSampleId } : {}),
      });
      if (result.ok) put(key, result.value);
    } finally {
      inFlight.value.delete(key);
    }
  }

  /** Only for tests and for switching species, where every key changes anyway. */
  function clear(): void {
    entries.clear();
    inFlight.value.clear();
    size.value = 0;
  }

  return { size, get, has, put, prefetch, clear };
});
