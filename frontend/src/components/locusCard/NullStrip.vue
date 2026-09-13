<script setup lang="ts">
/**
 * The random-pair baseline, drawn as a density, with this locus's two ticks on it.
 *
 * ⭐ **One LINEAR cosine axis, 0..1, identical in both representations**, so the two are read the
 * same way. The filled tick sits far right of the random-pair hump in BOTH — the clustering is
 * extremely good against chance — and the only thing that varies is the GAP between the two ticks,
 * which is how clearly the locus is bounded.
 *
 * ⚠ **Without this strip a reader cannot tell whether an ESM `nearest other` of 0.94 is close or
 * far**: ESM's random pairs already sit at ~0.645 and Bacformer's at ~0.065, so the same number
 * means opposite things in the two representations.
 *
 * ⚠ Built from spans rather than a canvas so it inherits the page's theme tokens and needs no
 * `getComputedStyle` — which is also what lets a jsdom test assert on it.
 */
import { computed } from "vue";

const props = defineProps<{
  /** The histogram's lower edge, its bin width, and its counts — all three or nothing. */
  binLowerEdge: number | null;
  binWidth: number | null;
  binCounts: readonly number[] | null;
  meanCosine: number | null;
  /** This locus's own members' similarity to its medoid. */
  withinSimilarity: number;
  /** Its medoid's similarity to the nearest other locus's. */
  nearestSimilarity: number;
}>();

/**
 * ⛔ Only the 0..1 half of the axis is drawn. A medoid pair below 0 is vanishingly rare and would
 * spend half the width saying nothing.
 */
const bars = computed(() => {
  const counts = props.binCounts;
  const lower = props.binLowerEdge;
  const width = props.binWidth;
  if (counts === null || lower === null || width === null || width <= 0) return null;
  const zero = Math.max(0, Math.round((0 - lower) / width));
  const kept = counts.slice(zero);
  const max = kept.reduce((highest, count) => Math.max(highest, count), 0);
  return kept.map((count, index) => ({
    key: zero + index,
    // ⚠ Inline height for the same reason the track's widths are inline: jsdom computes no layout,
    // so a stylesheet version of this is invisible to every test.
    heightPercent: max > 0 ? Math.round((100 * count) / max) : 0,
  }));
});

function clampedPercent(value: number): string {
  return `${(100 * Math.max(0, Math.min(1, value))).toFixed(1)}%`;
}
</script>

<template>
  <div v-if="bars" class="nullstrip">
    <div class="nd">
      <i v-for="bar in bars" :key="bar.key" :style="{ height: `${bar.heightPercent}%` }" />
    </div>
    <span
      class="nt inter"
      :style="{ left: clampedPercent(nearestSimilarity) }"
      :title="`nearest other locus: ${nearestSimilarity.toFixed(3)}`"
    />
    <span
      class="nt intra"
      :style="{ left: clampedPercent(withinSimilarity) }"
      :title="`this locus's own members: ${withinSimilarity.toFixed(3)}`"
    />
    <div class="nsfoot">
      <!-- ⛔ `null` here means the baseline was not measured, and the label says nothing rather than
           printing a number the data does not have. -->
      <span>random pairs {{ meanCosine === null ? "" : meanCosine.toFixed(3) }}</span>
      <span class="r">cosine similarity → 1</span>
    </div>
  </div>
</template>
