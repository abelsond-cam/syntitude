<script setup lang="ts">
/**
 * The five nearest OTHER loci in one representation — the evidence for the `nearest other cluster`
 * row, listed directly beneath it.
 *
 * ⭐ **It is the navigation**: a locus you can see you are confusable with is one you want to open.
 *
 * ⚠ **A different five in each representation** — their separations correlate at only ρ ≈ 0.47 — so
 * this list is rendered once per representation inside the block it belongs to, never once for the
 * card. ⛔ And only on the **median** view: it ranks by a median over gene pairs, which is the
 * quantity that view shows, and sitting under the weakest-member rows it would read as a shortlist
 * of that member's rivals, which it is not.
 *
 * ⛔ **No colour swatch.** The list is what survived the neighbourhood map, whose legend keyed
 * colours to dots; with no picture left to key to, a swatch is decoration that reads as meaning.
 *
 * ⚠ **RAGGED**: a locus whose shortlist held fewer than five simply has fewer rows, and the server
 * drops a neighbour its own fan-out could not resolve rather than sending a null address. A row that
 * still fails to resolve here is dropped for the same reason — a blank, walkable row is worse than
 * one fewer row.
 */
import { computed } from "vue";

import type { NearestLocus, NeighbourDisplayRow } from "@/api/types";

const props = defineProps<{
  nearestLoci: readonly NearestLocus[];
  /**
   * ⛔⛔ The fan-out rows, indexed by `catalogue_ordinal` — the SAME key space a nearest-locus row
   * addresses, and not the surrogate `neighbour_locus_id` the offset occupants use. Both are small
   * integers over the same range, so resolving through the other index names one locus where
   * another belongs, on a list that still looks entirely right (`2b99bb4`).
   */
  neighbours: readonly NeighbourDisplayRow[];
}>();

const emit = defineEmits<{ walk: [locusLabel: string] }>();

const byOrdinal = computed(() => {
  const index = new Map<number, NeighbourDisplayRow>();
  for (const row of props.neighbours) index.set(row.catalogue_ordinal, row);
  return index;
});

const rows = computed(() =>
  props.nearestLoci.flatMap((nearest) => {
    const row = byOrdinal.value.get(nearest.catalogue_ordinal);
    if (row === undefined) return [];
    return [
      {
        rank: nearest.rank,
        label: row.label,
        displayName: row.display_name,
        // the locus NUMBER is not what tells you whether a neighbour belongs here — the product is
        product: row.best_product,
        similarity: nearest.cross_similarity,
      },
    ];
  }),
);
</script>

<template>
  <div v-if="rows.length" class="sim-key">
    <button
      v-for="row in rows"
      :key="row.rank"
      type="button"
      class="sim-row"
      :title="`walk to ${row.displayName} — locus ${row.label}`"
      @click="emit('walk', row.label)"
    >
      <span class="nm">{{ row.displayName }}</span>
      <span v-if="row.product" class="desc">{{ row.product }}</span>
      <span class="cos">{{ row.similarity.toFixed(3) }}</span>
    </button>
  </div>
</template>
