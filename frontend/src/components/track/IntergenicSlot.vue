<script setup lang="ts">
/**
 * What sits between two adjacent genes — **and it is two different objects, not one.**
 *
 * ⛔ A `region` is a real intergenic span. A `seam` is two genes *meeting* or overlapping, which is
 * **not a region at all** (David, 2026-08-21): nothing about it may read as one, so it is drawn as a
 * mark of fixed width rather than scaled, and its own class name says which it is. 18.8 % of
 * adjacent pairs overlap, so the seam is the ordinary case rather than the exotic one.
 *
 * ⚠ Both are excluded by name from every count of *genes* on the track. The ±5 window is five genes
 * either side, and a count that swept these up would stop being able to notice that definition
 * moving.
 */
import { computed } from "vue";

import type { IntergenicGap } from "@/api/types";
import { type GapAppearance, gapAppearance } from "@/lib/intergenicGaps";
import { BP_PER_PX, JOINT_PX, MIN_BLOCK_PX } from "@/lib/trackGeometry";

const props = defineProps<{ gap: IntergenicGap | undefined }>();

const appearance = computed<GapAppearance>(() => gapAppearance(props.gap));

const widthPx = computed(() =>
  appearance.value.kind === "region"
    ? Math.max(MIN_BLOCK_PX, Math.round(appearance.value.lengthNt / BP_PER_PX))
    : JOINT_PX,
);

/**
 * ⛔ Tested with `!== null`, never for truthiness. `0.0` is a **measured** zero — every genome
 * agrees — and it is the majority case; `v-if` on the number itself would treat the commonest and
 * most informative value as missing data, and white on the track would stop meaning "identical in
 * every genome".
 */
const variance = computed(() => props.gap?.length_variance_score ?? null);
const isMeasured = computed(() => variance.value !== null);

const tip = computed(() => {
  const gap = props.gap;
  if (gap === undefined || appearance.value.kind === "none") return "not measured";
  const spread = gap.every_genome_agrees
    ? "identical in every genome"
    : // ⚠ `q1 == q3` means the MIDDLE HALF agrees; only `mn == mx` certifies the strong claim, and
      // saying the strong one here would be a claim the data does not support.
      `median over ${gap.observed_genome_count} genomes`;
  return appearance.value.kind === "seam"
    ? `${appearance.value.overlapNt} bases of overlap · ${spread}`
    : `${appearance.value.lengthNt} bases · ${spread}`;
});
</script>

<template>
  <div
    v-if="appearance.kind !== 'none'"
    class="slot"
    :class="appearance.kind === 'seam' ? 'joint' : 'gap'"
    :style="{ width: `${widthPx}px` }"
  >
    <button
      type="button"
      class="block"
      :class="[appearance.kind === 'seam' ? 'seam' : 'igr', { unmeasured: !isMeasured }]"
      :style="isMeasured ? { '--v': variance!.toFixed(3) } : undefined"
      :data-tip="tip"
      :aria-label="
        appearance.kind === 'seam'
          ? `two genes meeting: ${tip}`
          : `intergenic region: ${tip}`
      "
    >
      <span class="fill" />
    </button>
  </div>
</template>
