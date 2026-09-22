<script setup lang="ts">
/**
 * The species picker and the pangenome census. (The mark moved up to the instrument bar on
 * 2026-09-22 — `SiteHeader.vue`.)
 *
 * ⭐ **A switch is a navigation, not a filter** — this page holds one catalogue at a time, so choosing
 * another species leaves this one entirely (the published picker set `location.href`).
 */
import type { SpeciesCatalogueResponse } from "@/api/types";
import PangenomeCensus from "@/components/census/PangenomeCensus.vue";
import type { SpeciesEntry } from "@/stores/speciesCatalogueStore";

defineProps<{
  species: readonly SpeciesEntry[];
  speciesKey: string | null;
  catalogue: SpeciesCatalogueResponse | null;
}>();

const emit = defineEmits<{ selectSpecies: [speciesKey: string] }>();

function onChange(event: Event): void {
  const value = (event.target as HTMLSelectElement).value;
  if (value) emit("selectSpecies", value);
}
</script>

<template>
  <section class="species-strip">
    <div class="wrap species-in">
      <label class="species-pick">
        <span class="legend">Choose a microbe to navigate:</span>
        <select id="species" aria-label="Species" :value="speciesKey ?? ''" @change="onChange">
          <option v-for="entry in species" :key="entry.key" :value="entry.key">
            {{ entry.scientific_name }}
          </option>
        </select>
      </label>
      <div class="pangenome">
        <span class="legend">Pangenome</span>
        <PangenomeCensus v-if="catalogue !== null" :catalogue="catalogue" />
      </div>
    </div>
  </section>
</template>
