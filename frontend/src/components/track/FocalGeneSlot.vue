<script setup lang="ts">
/**
 * The gene the reader is reading, in the middle of the track.
 *
 * ⭐ **Its bar carries ARRANGEMENTS, not occupants.** The occupant of A0 is the focal locus in every
 * member gene by construction, so a bar of occupants there would read 100 % and say nothing. What is
 * genuinely contested at A0 is which *neighbourhood* each member gene sits in — same grammar as
 * every other bar on the track, "how the member genes split", and it pairs with the switcher
 * directly beneath so the bar shows the split and the buttons pick a slice of it.
 */
import { computed } from "vue";

import type { Arrangement, Locus } from "@/api/types";
import { segmentPercent, slotFit } from "@/lib/trackGeometry";
import type { WalkDirection } from "@/lib/walkDirection";

const props = defineProps<{
  locus: Locus;
  arrangements: readonly Arrangement[];
  selectedIndex: number;
  /** Which ranks the anchored genome carries here, so its row can be marked. */
  anchorRanks: readonly number[];
  /** Members in arrangements the cap left out — a DISPLAY cut. */
  membersInArrangementsNotListed: number;
  /** Members with no recorded window at all — MISSING DATA. A different sentence. */
  membersWithoutANeighbourhood: number;
  walkDirection: WalkDirection;
  isPopoverOpen: boolean;
}>();

const emit = defineEmits<{ togglePopover: []; selectArrangement: [index: number] }>();

const fit = computed(() => slotFit(props.locus.median_gene_length_nt));

/**
 * ⚠ The focal gene's own lane follows the WALK, not any arrangement's flip. The reader is reading
 * this gene backwards or forwards; the arrangement's own mirroring is a property of the row beside
 * it, not of the gene in the middle.
 */
const shownDirection = computed(() => (props.walkDirection === "reversed" ? "rev" : "fwd"));

const size = computed(() => props.locus.gene_count);

const accessibleName = computed(
  () =>
    `${props.locus.display_name} (locus ${props.locus.label}) — ` +
    `${props.arrangements.length} of ${props.arrangements.length + 0} arrangements shown`,
);
</script>

<template>
  <div
    class="slot focal"
    :class="{ narrow: fit.isNarrow, tight: fit.isTight, sel: isPopoverOpen }"
    :data-dir="shownDirection"
    :style="{ width: `${fit.widthPx}px` }"
  >
    <span class="gname" :data-tip="locus.display_name">{{ locus.display_name }}</span>

    <button type="button" class="block focal-block" :data-dir="shownDirection" :aria-label="accessibleName">
      <span class="fill" />
      <template v-if="!fit.isNarrow">
        <span class="lid">·{{ locus.label }}</span>
        <span class="gsub">{{ locus.best_product ?? "—" }}</span>
      </template>
    </button>

    <div class="mid">
      <button
        type="button"
        class="marg-hit"
        :class="{ on: isPopoverOpen }"
        :aria-expanded="isPopoverOpen"
        :aria-label="`Show every arrangement at this locus — ${arrangements.length} shown of ${locus.gene_count} member genes`"
        :data-tip="`${arrangements.length} of ${arrangements.length} arrangements`"
        @click.stop="emit('togglePopover')"
      >
        <span class="marg">
          <i
            v-for="(arrangement, index) in arrangements"
            :key="arrangement.rank"
            :class="{ on: index === selectedIndex, anchored: anchorRanks.includes(arrangement.rank) }"
            :style="{ width: `${segmentPercent(arrangement.gene_count, size)}%` }"
            :data-tip="`arrangement ${arrangement.rank + 1} · ${arrangement.gene_count} of ${size}`"
            @click.stop="emit('selectArrangement', index)"
          />
          <!-- ⛔ TWO remainders, drawn as two segments and never as one. `oth` is members inside
               arrangements the display cap left out; `nowin` is members with no recorded window at
               all. Merging them tells a reader that genes past a display cut have no coordinates,
               which is a different and false claim. -->
          <i
            v-if="membersInArrangementsNotListed > 0"
            class="oth"
            :style="{ width: `${segmentPercent(membersInArrangementsNotListed, size)}%` }"
            :data-tip="`${membersInArrangementsNotListed} of ${size} in arrangements past the display cut`"
          />
          <i
            v-if="membersWithoutANeighbourhood > 0"
            class="nowin"
            :style="{ width: `${segmentPercent(membersWithoutANeighbourhood, size)}%` }"
            :data-tip="`${membersWithoutANeighbourhood} of ${size} member genes have no recorded neighbourhood — no coordinates for the gene, so no window`"
          />
        </span>
      </button>
    </div>
  </div>
</template>
