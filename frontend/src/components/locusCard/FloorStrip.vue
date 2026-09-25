<script setup lang="ts">
/**
 * The random **gene-pair** floor, drawn as a box on a 0..1 cosine axis, with this view's values as
 * ticks on it.
 *
 * ⛔ **This is `similarity_baselines[rep].floor_*`, and NOT the retired `map_projections` null.**
 * That null sampled random pairs of MEDOIDS while every number on this card is a median over GENE
 * pairs; on the published ecoli/Bacformer catalogue the two sit at **0.0651** and **0.0587** —
 * close enough to look interchangeable and not be. The component was renamed from `NullStrip` with
 * the measurement, so nothing in the tree still says "null" while drawing the floor.
 *
 * ⭐ **One LINEAR cosine axis, 0..1, identical in both representations**, so the two are read the
 * same way. ⚠ Without it a reader cannot tell whether an ESM `nearest other cluster` of 0.94 is
 * close or far: ESM's random pairs already sit at ~0.742 and Bacformer's at ~0.059, so the same
 * number means opposite things in the two.
 *
 * ⛔ **A box and a whisker, not a density.** The sample behind the floor is summarised by quartiles
 * rather than binned, so a smooth hump would be a picture making a claim the artifact does not. The
 * spread is what a median alone cannot give: whether a locus's 0.41 sits far outside random or
 * inside its shoulder.
 *
 * ⚠ Built from spans rather than a canvas so it inherits the page's theme tokens and needs no
 * `getComputedStyle` — which is also what lets a jsdom test assert on it.
 */
import { computed } from "vue";

import type { FloorTick } from "@/lib/similarityViews";

const props = defineProps<{
  floorMedian: number | null;
  /** All three or none: `null` where the run's audit JSON was not beside its CSV. */
  floorP25: number | null;
  floorP75: number | null;
  floorP99: number | null;
  ticks: readonly FloorTick[];
}>();

/**
 * ⛔ Only the 0..1 half of the axis is drawn, and every edge is clamped into it. A cosine below 0 is
 * vanishingly rare between real genes and would spend half the width saying nothing — and an
 * unclamped `left` past 100 % pushes the tick out of the card entirely rather than onto its end.
 */
function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function leftPercent(value: number): string {
  // ⚠ One decimal, not zero: two loci 0.5 % apart must not land on the same pixel of the axis.
  return `${(100 * clamp(value)).toFixed(1)}%`;
}

/** The p25–p75 box, or — where the quartiles are absent — a zero-width mark at the median alone. */
const box = computed(() => {
  const median = props.floorMedian;
  if (median === null) return null;
  const low = props.floorP25 ?? median;
  const high = props.floorP75 ?? median;
  return {
    left: leftPercent(low),
    width: `${(100 * Math.max(0, clamp(high) - clamp(low))).toFixed(1)}%`,
  };
});

/**
 * The whisker from p75 out to p99. ⛔ Drawn only where BOTH edges are present: a whisker anchored on
 * the median instead of the box would show a spread wider than the one that was measured.
 */
const whisker = computed(() => {
  const high = props.floorP75;
  const far = props.floorP99;
  if (high === null || far === null) return null;
  return {
    left: leftPercent(high),
    width: `${(100 * Math.max(0, clamp(far) - clamp(high))).toFixed(1)}%`,
  };
});

/** `random gene pairs 0.059 (p25–p75 0.03–0.09)` — the quartile clause only where there are any. */
const caption = computed(() => {
  const median = props.floorMedian;
  if (median === null) return "";
  const low = props.floorP25;
  const high = props.floorP75;
  const spread = low === null || high === null ? "" : ` (p25–p75 ${low.toFixed(2)}–${high.toFixed(2)})`;
  return `random gene pairs ${median.toFixed(3)}${spread}`;
});
</script>

<template>
  <div v-if="box" class="nullstrip">
    <div class="fbox">
      <!-- inline geometry: jsdom computes no layout, so a stylesheet version is untestable -->
      <i class="q" :style="{ left: box.left, width: box.width }" />
      <i v-if="whisker" class="w" :style="{ left: whisker.left, width: whisker.width }" />
      <i class="m" :style="{ left: leftPercent(floorMedian!) }" />
    </div>
    <span
      v-for="tick in ticks"
      :key="tick.label"
      class="nt"
      :class="{ inter: tick.isSecondRow, intra: !tick.isSecondRow }"
      :style="{ left: leftPercent(tick.value) }"
      :title="`${tick.label}: ${tick.value.toFixed(3)}`"
    />
    <div class="nsfoot">
      <span>{{ caption }}</span>
      <span class="r">cosine similarity → 1</span>
    </div>
  </div>
</template>
