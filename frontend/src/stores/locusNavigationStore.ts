/**
 * Where the reader is, how they got there, and what is on screen while a request is in flight.
 *
 * ⛔ **Three loading states, never conflated.** Each answers a different question and merging any
 * two of them produces a page that lies:
 * - `pending` — nothing to show. The track renders a **skeleton in its own shape**, so the page
 *   does not jump when the response lands.
 * - `refreshing` — the previous locus stays drawn, and dims only after {@link DIM_AFTER_MS}, so a
 *   cached or fast response never flashes.
 * - `failed` — and it must never look like an empty result. See `api/result.ts`.
 *
 * ⭐ **Walk direction is display state and fetches nothing.** The API response does not depend on
 * it, so flipping the frame is zero round trips — as it must be, because the reader flips it
 * mid-walk and a request there would make the track stutter for no new information.
 */

import { defineStore, storeToRefs } from "pinia";
import { computed, ref } from "vue";

import { fetchLocus } from "@/api/client";
import { LANES } from "@/api/request";
import type { Failure } from "@/api/result";
import type { LocusDetailResponse } from "@/api/types";
import {
  type LocusRoute,
  advanceTrail,
  formatLocusHash,
  parseLocusHash,
} from "@/lib/locusHashRoute";
import { FORWARD, type WalkDirection } from "@/lib/walkDirection";

import { useAnchorGenomeStore } from "./anchorGenomeStore";
import { locusCacheKey, useLocusDetailCacheStore } from "./locusDetailCacheStore";

/**
 * How long a refresh stays undimmed. ⚠ Not a design preference: below this a response that was
 * already cached, or that came back fast, would flash the track grey and back for no reason a
 * reader could name.
 */
export const DIM_AFTER_MS = 150;

/**
 * ⛔ `previous` on `failed` is a genuine absence — there was no earlier locus — and is NOT the same
 * as a failed request. It is what lets the page keep the last good track on screen beside the
 * error, instead of clearing to nothing and implying the catalogue is empty.
 */
export type LocusView =
  | { readonly status: "idle" }
  | { readonly status: "pending" }
  | { readonly status: "refreshing"; readonly previous: LocusDetailResponse; readonly isDimmed: boolean }
  | { readonly status: "ready"; readonly value: LocusDetailResponse }
  | { readonly status: "failed"; readonly failure: Failure; readonly previous: LocusDetailResponse | null };

export const useLocusNavigationStore = defineStore("locusNavigation", () => {
  const cache = useLocusDetailCacheStore();
  const anchor = useAnchorGenomeStore();
  const { sampleId: anchorSampleId } = storeToRefs(anchor);

  const speciesKey = ref<string | null>(null);
  const route = ref<LocusRoute | null>(null);
  const trail = ref<readonly string[]>([]);
  const view = ref<LocusView>({ status: "idle" });

  let dimTimer: ReturnType<typeof setTimeout> | null = null;

  /**
   * The locus currently drawable, whatever the status. ⚠ Deliberately NOT called "the locus": a
   * component that renders this while `status === 'failed'` is showing the *previous* one, and the
   * error panel beside it is what makes that honest.
   */
  const drawable = computed<LocusDetailResponse | null>(() => {
    const current = view.value;
    if (current.status === "ready") return current.value;
    if (current.status === "refreshing") return current.previous;
    if (current.status === "failed") return current.previous;
    return null;
  });

  /** The reader's direction of travel. Display state; changing it fetches nothing. */
  const walkDirection = computed<WalkDirection>(() => route.value?.direction ?? FORWARD);

  const hash = computed(() => (route.value ? formatLocusHash(route.value) : ""));

  function cancelDimTimer(): void {
    if (dimTimer !== null) {
      clearTimeout(dimTimer);
      dimTimer = null;
    }
  }

  function setSpecies(nextSpeciesKey: string): void {
    if (speciesKey.value === nextSpeciesKey) return;
    // Switching species is a full navigation to a different catalogue: every cache key changes,
    // the trail refers to loci that no longer exist, and the anchor's BioSample set is disjoint.
    speciesKey.value = nextSpeciesKey;
    route.value = null;
    trail.value = [];
    view.value = { status: "idle" };
    cache.clear();
    anchor.clearAnchor();
    LANES.navigation.cancel();
    cancelDimTimer();
  }

  /**
   * ⛔ **Absolute, never a toggle** — and there is no toggle action on this store for the same
   * reason `lib/walkDirection` exports none. Fetches nothing.
   */
  function setWalkDirection(direction: WalkDirection): void {
    if (route.value === null || route.value.direction === direction) return;
    route.value = { label: route.value.label, direction };
  }

  /** Go to a locus. `direction` is absolute — compute it with `walkDirectionAfterStep`. */
  async function navigateTo(locusLabel: string, direction: WalkDirection = FORWARD): Promise<void> {
    const species = speciesKey.value;
    if (species === null) throw new Error("navigateTo before setSpecies");

    route.value = { label: locusLabel, direction };
    // ⛔ Retreat rather than growth — Back fires `hashchange`, which lands here exactly as a click
    // does, and pushing unconditionally made the breadcrumb GROW when the reader went backwards.
    trail.value = advanceTrail(trail.value, locusLabel);

    const key = locusCacheKey(species, locusLabel, anchorSampleId.value);
    const cached = cache.get(key);
    if (cached !== undefined) {
      // ⭐ Zero fetch, and zero flash: no pending, no refreshing, no dim timer.
      cancelDimTimer();
      LANES.navigation.cancel();
      view.value = { status: "ready", value: cached };
      return;
    }

    const previous = drawable.value;
    cancelDimTimer();
    if (previous !== null) {
      view.value = { status: "refreshing", previous, isDimmed: false };
      dimTimer = setTimeout(() => {
        const current = view.value;
        if (current.status === "refreshing") {
          view.value = { status: "refreshing", previous: current.previous, isDimmed: true };
        }
      }, DIM_AFTER_MS);
    } else {
      view.value = { status: "pending" };
    }

    const outcome = await LANES.navigation.run((signal) =>
      fetchLocus(species, locusLabel, {
        signal,
        ...(anchorSampleId.value ? { anchorSampleId: anchorSampleId.value } : {}),
      }),
    );
    // ⭐ Superseded: the reader walked on before this landed. Change NOTHING — not the view, not
    // the timer. Rendering an error here, or clearing the track, would both be wrong.
    if (outcome.superseded) return;

    cancelDimTimer();
    if (outcome.result.ok) {
      cache.put(key, outcome.result.value);
      view.value = { status: "ready", value: outcome.result.value };
    } else {
      view.value = { status: "failed", failure: outcome.result, previous };
    }
  }

  /**
   * Apply a URL hash — the browser's Back button and a deep link both arrive here.
   *
   * `isKnownLabel` is supplied by the caller because only it knows the catalogue. An unknown hash
   * returns `false` and the caller decides what to say; this store does not guess a locus.
   */
  async function applyHash(
    rawHash: string,
    isKnownLabel: (label: string) => boolean,
  ): Promise<boolean> {
    const parsed = parseLocusHash(rawHash, isKnownLabel);
    if (parsed === null) return false;
    if (route.value?.label === parsed.label && route.value.direction === parsed.direction) {
      return true;
    }
    await navigateTo(parsed.label, parsed.direction);
    return true;
  }

  /** Re-run the request for the locus already in `route`, after a failure. */
  async function retry(): Promise<void> {
    const current = route.value;
    if (current === null) return;
    await navigateTo(current.label, current.direction);
  }

  return {
    speciesKey,
    route,
    trail,
    view,
    drawable,
    walkDirection,
    hash,
    setSpecies,
    setWalkDirection,
    navigateTo,
    applyHash,
    retry,
  };
});
