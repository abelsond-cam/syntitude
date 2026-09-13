/**
 * What the neighbourhood map is showing: which representation, and which zoom.
 *
 * ⭐ **Both survive a walk, and that is the point of them being here.** Which arrangement is drawn
 * and which popover is open are properties of *this locus* and reset on every step
 * (`trackDisplayStore`); which space the reader is looking at and how far out they are zoomed are
 * properties of *the reader*, and resetting them on every step would undo their choice forty times
 * in a forty-step walk.
 *
 * ⚠ Neither fetches anything. The six-point geometry rides in the locus response and the catalogue
 * sprite is one immutable image the browser has already cached, so switching either is zero round
 * trips — like every other control on this page.
 */

import { defineStore } from "pinia";
import { ref } from "vue";

import type { Representation } from "@/api/types";

/**
 * ⛔ Two zooms, not three. The published page had three crops of one gene UMAP; measured on the
 * shipped fit, a locus's five nearest loci landed a **median 18.5 % of the map apart**, so the
 * innermost crop showed six specks scattered over the whole picture. *"The 'nearest' are spread
 * over the whole catalogue view and it thus indicates the examination of 'these loci' is completely
 * meaningless"* (David, 2026-08-19). They are now two different pictures rather than two crops:
 * a per-locus MDS fit, and the catalogue.
 */
export const MAP_ZOOMS = ["near", "global"] as const;
export type MapZoom = (typeof MAP_ZOOMS)[number];

export const MAP_ZOOM_LABEL: Readonly<Record<MapZoom, string>> = {
  near: "these loci",
  global: "whole catalogue",
};

export const useNeighbourhoodMapStore = defineStore("neighbourhoodMap", () => {
  /**
   * ⚠ Bacformer first, matching the published page's own tab order — the two representations pick
   * **different loci** (their separations agree at only ρ ≈ 0.47), so the default is a real choice
   * about which question the map opens on: context, not sequence.
   */
  const representation = ref<Representation>("bacformer");

  /** `near` to start, as the published page did: the fit of these six is the locus's own picture. */
  const zoom = ref<MapZoom>("near");

  function selectRepresentation(next: Representation): void {
    representation.value = next;
  }

  /**
   * ⛔ **Absolute, never a toggle.** The same rule as `setWalkDirection`, for the same reason: a
   * toggle called twice from two places — a click and a keyboard shortcut, say — lands back where it
   * started while every call site believes it moved.
   */
  function setZoom(next: MapZoom): void {
    zoom.value = next;
  }

  return { representation, zoom, selectRepresentation, setZoom };
});
