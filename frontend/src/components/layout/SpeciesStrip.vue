<script setup lang="ts">
/**
 * The species picker, the MODEL picker beside it, and the pangenome census. (The mark moved up to
 * the instrument bar on 2026-09-22 — `SiteHeader.vue`.)
 *
 * ⭐ **A switch is a navigation, not a filter** — this page holds one catalogue at a time, so
 * choosing another species, or another model of the same species, leaves this one entirely (the
 * published picker set `location.href`).
 *
 * ⛔ **Both controls emit the same event, because both choose the same thing.** A catalogue is one
 * species × one model, and the page is only ever showing one of them. Picking a species means
 * "that species' default catalogue"; picking a model means "this species, that model". Two emits
 * would have made the parent decide which control had spoken last, and that is a state machine
 * nobody needs.
 */
import type { CatalogueEntry, CatalogueKey, SpeciesCatalogueResponse } from "@/api/types";
import PangenomeCensus from "@/components/census/PangenomeCensus.vue";
import type { SpeciesEntry } from "@/stores/speciesCatalogueStore";

const props = defineProps<{
  species: readonly SpeciesEntry[];
  /** ⚠ The organism, for the left-hand control — NOT the catalogue key. */
  speciesKey: string | null;
  /** The catalogue actually being shown, which is what the model control marks as selected. */
  catalogueKey: CatalogueKey | null;
  /** This species' catalogues. Length one for a species with a single model. */
  catalogues: readonly CatalogueEntry[];
  catalogue: SpeciesCatalogueResponse | null;
}>();

const emit = defineEmits<{ selectCatalogue: [catalogueKey: CatalogueKey] }>();

function onSpeciesChange(event: Event): void {
  const chosen = (event.target as HTMLSelectElement).value;
  const entry = props.species.find((candidate) => candidate.key === chosen);
  // ⚠ A species with nothing published has no catalogue to go to, so the control does not pretend.
  if (entry?.catalogue_key) emit("selectCatalogue", entry.catalogue_key);
}

function onModelChange(event: Event): void {
  const chosen = (event.target as HTMLSelectElement).value;
  if (chosen) emit("selectCatalogue", chosen as CatalogueKey);
}

/**
 * ⚠ Labelled by `model.key` (`nuna5`), not `model.label`, which is the full on-disk parameter
 * string — `nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL`. That belongs in the footer's
 * provenance, where a reader has gone looking for it, not in a control they have to skim.
 */
function modelName(entry: CatalogueEntry): string {
  const steps = entry.model?.step_count;
  const name = entry.model?.key ?? entry.key;
  return steps === null || steps === undefined ? name : `${name} — ${steps} steps`;
}
</script>

<template>
  <section class="species-strip">
    <div class="wrap species-in">
      <label class="species-pick">
        <span class="legend">Choose a microbe to navigate:</span>
        <select id="species" aria-label="Species" :value="speciesKey ?? ''" @change="onSpeciesChange">
          <option v-for="entry in species" :key="entry.key" :value="entry.key">
            {{ entry.scientific_name }}
          </option>
        </select>
      </label>
      <!-- ⛔ HIDDEN, not disabled, when the species holds one catalogue. A disabled control says
           "there is a choice here you may not make"; there is simply no choice, and on every
           catalogue that existed before 2026-09-26 that is still the truth. -->
      <label v-if="catalogues.length > 1" class="species-pick model-pick">
        <span class="legend">Model:</span>
        <select id="model" aria-label="Clustering model" :value="catalogueKey ?? ''" @change="onModelChange">
          <option v-for="entry in catalogues" :key="entry.key" :value="entry.key">
            {{ modelName(entry) }}{{ entry.is_default ? " (default)" : "" }}
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
