<script setup lang="ts">
/**
 * The instrument bar: the mark, and the locus search.
 *
 * ⭐ **The ship sits here, beside the wordmark (David, 2026-09-22)** — it used to stand on the species
 * strip, centred over the evidence column. Inlined rather than an `<img>` so the stylesheet can size
 * it, and `aria-hidden` because the wordmark beside it already names the site: read aloud, it would
 * announce "Syntitude" twice.
 */
import logoMarkup from "@/assets/logo.svg?raw";
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
      <div class="brand">
        <!-- ⚠ Inlined ONCE on the page: the SVG carries `id`s for its clip paths, and a second copy
             would duplicate them. -->
        <!-- eslint-disable-next-line vue/no-v-html — a checked-in asset, not reader input -->
        <div class="bar-logo" aria-hidden="true" v-html="logoMarkup" />
        <!-- ⚠ One line, as the published template has it: Vue drops whitespace that spans a line break
             between two tags, and split here the rule lost its space ("—NAVIGATE"). -->
        <div class="mark">Syntitude<span>.org</span> <span class="mark-rule">—</span> <span class="mark-sub">Navigate your Pangenome</span></div>
      </div>
      <LocusSearchBox
        :species-key="speciesKey"
        :collection-genome-count="collectionGenomeCount"
        @go="emit('go', $event)"
      />
    </div>
  </header>
</template>
