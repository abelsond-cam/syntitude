<script setup lang="ts">
/**
 * "Syntolog Loci" — the home view: what this locus is, and the evidence for it being one.
 *
 * Two columns, as the published card drew them (`app.js::renderCard`): the ARGUMENT on the left —
 * the headline and the sequence-diversity card — and the REFERENCE column beside it — the embedding
 * geometry, then the neighbourhood map immediately below the numbers it is a picture of.
 */
import { storeToRefs } from "pinia";
import { computed } from "vue";

import type { LocusDetailResponse, Representation, SpeciesCatalogueResponse } from "@/api/types";
import EmbeddingGeometryCard from "@/components/locusCard/EmbeddingGeometryCard.vue";
import LocusHeadline from "@/components/locusCard/LocusHeadline.vue";
import SequenceDiversityCard from "@/components/locusCard/SequenceDiversityCard.vue";
import NeighbourhoodMapCard from "@/components/map/NeighbourhoodMapCard.vue";
import { useLocusNavigationStore } from "@/stores/locusNavigationStore";
import { useNeighbourhoodMapStore } from "@/stores/neighbourhoodMapStore";

const props = defineProps<{
  detail: LocusDetailResponse;
  catalogue: SpeciesCatalogueResponse;
}>();

const navigation = useLocusNavigationStore();
const map = useNeighbourhoodMapStore();
const { representation } = storeToRefs(map);

const projections = computed(() => props.catalogue.map_projections);
const available = computed<readonly Representation[]>(() =>
  projections.value.map((projection) => projection.representation),
);
/**
 * ⚠ The separation TILE reads Bacformer — the context axis the track is built on — so its "of N
 * loci" is Bacformer's measurable count, not ESM's.
 */
const separationCount = computed(
  () =>
    projections.value.find((projection) => projection.representation === "bacformer")
      ?.separation_measurable_locus_count ?? null,
);
</script>

<template>
  <div class="work">
    <div>
      <div id="card">
        <LocusHeadline
          :locus="detail.locus"
          :collection-genome-count="catalogue.pangenome.genome_count"
          :map-projections="projections"
          :separation-measurable-locus-count="separationCount"
        />
        <SequenceDiversityCard
          :locus="detail.locus"
          :families="detail.uniref50_families"
          :symbols="detail.annotations['gene_symbol'] ?? []"
          :pfam-reference="detail.pfam_reference"
          :listed-architecture-count="(detail.annotations['pfam_architecture'] ?? []).length"
        />
      </div>
    </div>
    <aside id="side" class="side">
      <EmbeddingGeometryCard
        :geometry="detail.locus.geometry"
        :map-projections="projections"
        :gene-count="detail.locus.gene_count"
        :separation-measurable-locus-count="separationCount"
      />
      <NeighbourhoodMapCard
        :detail="detail"
        :representation="representation"
        :available-representations="available"
        @walk="navigation.navigateTo($event)"
        @select-representation="map.selectRepresentation($event)"
      />
    </aside>
  </div>
</template>
