/**
 * Which species the page is showing, and everything about it that arrives before a locus.
 *
 * ⭐ **A species switch is a navigation, not a filter** (`app.js`, the species picker). One page holds
 * one catalogue: the loci, the anchor genomes and every cache key belong to it, and nothing carries
 * across. So choosing a species resets the navigation store rather than re-filtering it.
 *
 * ⚠ **Three loading states here too, never conflated** — the same rule as the locus view. A species
 * list that failed to load and a deployment with no published species are different claims, and the
 * picker must not make the same face at both.
 */

import { defineStore } from "pinia";
import { computed, ref, shallowRef } from "vue";

import { fetchSpeciesCatalogue, fetchSpeciesList } from "@/api/client";
import type { Failure } from "@/api/result";
import type { SpeciesCatalogueResponse, SpeciesListResponse } from "@/api/types";

import { useAnchorGenomeStore } from "./anchorGenomeStore";
import { useLocusNavigationStore } from "./locusNavigationStore";

export type CatalogueLoad<T> =
  | { readonly status: "idle" }
  | { readonly status: "pending" }
  | { readonly status: "ready"; readonly value: T }
  | { readonly status: "failed"; readonly failure: Failure };

export type SpeciesEntry = SpeciesListResponse["species"][number];

export const useSpeciesCatalogueStore = defineStore("speciesCatalogue", () => {
  const navigation = useLocusNavigationStore();
  const anchor = useAnchorGenomeStore();

  const speciesList = shallowRef<CatalogueLoad<readonly SpeciesEntry[]>>({ status: "idle" });
  const catalogue = shallowRef<CatalogueLoad<SpeciesCatalogueResponse>>({ status: "idle" });
  const speciesKey = ref<string | null>(null);

  /** The loaded catalogue, or `null` — for components that render nothing until it exists. */
  const current = computed<SpeciesCatalogueResponse | null>(() =>
    catalogue.value.status === "ready" ? catalogue.value.value : null,
  );

  /** Only the species that serve something are offered as a destination. */
  const publishedSpecies = computed<readonly SpeciesEntry[]>(() =>
    speciesList.value.status === "ready"
      ? speciesList.value.value.filter((entry) => entry.published)
      : [],
  );

  async function loadSpeciesList(): Promise<void> {
    speciesList.value = { status: "pending" };
    const result = await fetchSpeciesList();
    speciesList.value = result.ok
      ? { status: "ready", value: result.value.species }
      : { status: "failed", failure: result };
  }

  /**
   * Show one species. Resets the navigation (and with it the trail, the cache and the anchor)
   * BEFORE the catalogue arrives, so nothing from the previous species can be drawn under the new
   * one's name while the request is in flight.
   */
  async function selectSpecies(nextSpeciesKey: string): Promise<void> {
    if (speciesKey.value === nextSpeciesKey && catalogue.value.status !== "failed") return;
    speciesKey.value = nextSpeciesKey;
    navigation.setSpecies(nextSpeciesKey);
    catalogue.value = { status: "pending" };
    const result = await fetchSpeciesCatalogue(nextSpeciesKey);
    // ⚠ The reader may have picked another species while this was in flight.
    if (speciesKey.value !== nextSpeciesKey) return;
    if (!result.ok) {
      catalogue.value = { status: "failed", failure: result };
      anchor.setAvailability(false);
      return;
    }
    catalogue.value = { status: "ready", value: result.value };
    // A published pangenome always carries gene membership in the database, so an anchor can always
    // be answered — the published page withheld the box only on payloads that shipped no `arr.gid`.
    anchor.setAvailability(result.value.pangenome.genome_count > 0);
  }

  return {
    speciesList,
    catalogue,
    speciesKey,
    current,
    publishedSpecies,
    loadSpeciesList,
    selectSpecies,
  };
});
