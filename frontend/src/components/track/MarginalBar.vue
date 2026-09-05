<script setup lang="ts">
/**
 * The marginal, kept as a thin bar under every block: **how ALL member genes split at that
 * position.** The block above it is one arrangement's occupant; this is the whole population behind
 * it, so a contested position is visible without clicking and the two views never have to be
 * confused.
 *
 * ⛔ The bar is the affordance for *"what else is ever here?"* — it is the population, so it opens
 * the population. A position with nothing observed gets a plain bar with nothing to open, and it is
 * still drawn: an absent bar and an empty one say different things.
 */
import { computed } from "vue";

import type { NeighbourDisplayRow, OffsetMarginal } from "@/api/types";
import { segmentPercent } from "@/lib/trackGeometry";

const props = defineProps<{
  marginal: OffsetMarginal | null;
  /** The locus drawn in the block above, so its own segment can be lit. `null` at a contig end. */
  highlightLocus: string | null;
  /** How the position is labelled — `A-1`, `A+3`. Read out in the accessible name. */
  offsetLabel: string;
  neighboursByLabel: ReadonlyMap<string, NeighbourDisplayRow>;
  isOpen: boolean;
}>();

const emit = defineEmits<{ toggle: [] }>();

const observed = computed(() => props.marginal?.observed_member_count ?? 0);
const occupants = computed(() => props.marginal?.occupants ?? []);

/**
 * ⛔ The remainder here is `observed_not_listed` — a **display** cut, the occupants past the
 * exported top-N. It is emphatically not `members_without_an_observation`, which is missing data at
 * a contig edge, and the two must never be drawn as one segment: one says *"there are more loci
 * here than we list"*, the other says *"some members have no gene here at all"*.
 */
const otherSegmentPercent = computed(() =>
  segmentPercent(props.marginal?.observed_not_listed ?? 0, observed.value),
);

function displayName(label: string | null): string {
  if (label === null) return "—";
  return props.neighboursByLabel.get(label)?.display_name ?? label;
}

const accessibleName = computed(() => {
  const count = occupants.value.length;
  return (
    `Show every locus observed at ${props.offsetLabel} — ` +
    `${count} ${count === 1 ? "locus" : "loci"} across ${observed.value} member genes`
  );
});
</script>

<template>
  <!-- ⚠ Nothing observed: a plain bar, no button. There is nothing to open, and offering a control
       that could only ever answer "nothing here" is worse than offering none. -->
  <div v-if="observed === 0" class="marg" />
  <button
    v-else
    type="button"
    class="marg-hit"
    :class="{ on: isOpen }"
    :aria-label="accessibleName"
    :aria-expanded="isOpen"
    :data-tip="`Show every locus observed at ${offsetLabel}`"
    @click.stop="emit('toggle')"
  >
    <span class="marg">
      <i
        v-for="occupant in occupants"
        :key="occupant.rank"
        :class="{ on: occupant.locus !== null && occupant.locus === highlightLocus }"
        :style="{ width: `${segmentPercent(occupant.gene_count, observed)}%` }"
        :data-tip="`${displayName(occupant.locus)} · ${occupant.gene_count} of ${observed}`"
      />
      <i
        v-if="otherSegmentPercent > 0"
        class="oth"
        :style="{ width: `${otherSegmentPercent}%` }"
        :data-tip="`${marginal?.observed_not_listed} of ${observed} in other loci`"
      />
    </span>
  </button>
</template>
