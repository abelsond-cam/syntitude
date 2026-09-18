<script setup lang="ts">
/** The instrument bar: the mark, and the locus search. */
import LocusSearchBox from "@/components/search/LocusSearchBox.vue";

defineProps<{
  speciesKey: string | null;
  collectionGenomeCount: number | null;
}>();

const emit = defineEmits<{ go: [locusLabel: string] }>();
</script>

<template>
  <header class="bar">
    <div class="bar-in">
      <div class="mark">
        Syntitude<span>.org</span> <span class="mark-rule">—</span>
        <span class="mark-sub">Navigate your Pangenome</span>
      </div>
      <LocusSearchBox
        :species-key="speciesKey"
        :collection-genome-count="collectionGenomeCount"
        @go="emit('go', $event)"
      />
    </div>
  </header>
</template>
