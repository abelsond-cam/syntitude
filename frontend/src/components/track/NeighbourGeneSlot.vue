<script setup lang="ts">
/**
 * One position of the ±5 neighbourhood: the gene drawn there, and the bar saying what else ever is.
 *
 * ⛔⛔ **The `style.width` below is INLINE and must stay inline.** `app.js:1198` — *"the JS test
 * harness loads no stylesheet, so an inline width is the only version of this that any test can
 * see."* jsdom computes no layout either, so a width moved into a stylesheet silently blanks around
 * forty DOM assertions: they keep passing while measuring nothing. This is a testability
 * requirement, not a style choice, and it will look like something to tidy up.
 *
 * ⚠ **The SLOT carries the width, not the block.** The occupancy bar and the offset label are the
 * block's siblings and must line up under it exactly, or the bar stops describing the gene above it.
 *
 * ⛔ **`data-dir` is the strand relation AS SHOWN**, already mirrored for display. Anything that
 * draws an arrow, or hands a direction to the walk, must come from the shown value — the published
 * page's marginal list and its no-arrangement fallback both used the raw recorded bit and pointed
 * the wrong way under a reversed walk.
 */
import { computed } from "vue";

import type { NeighbourDisplayRow, OffsetMarginal } from "@/api/types";
import type { NeighbourSlot } from "@/lib/slotSpaces";
import { slotFit, widthForAbsentOccupant } from "@/lib/trackGeometry";

import MarginalBar from "./MarginalBar.vue";

const props = defineProps<{
  /** The slot as DRAWN — mirroring already applied by `slotsInDisplayOrder`. */
  slot: NeighbourSlot;
  /** The occupant's display row, or `null` when the slot is empty or fell outside the catalogue. */
  neighbour: NeighbourDisplayRow | null;
  /** The offset this COLUMN is labelled with. ⚠ Not the slot's recorded offset — see `labelSlotFor`. */
  labelOffset: number;
  /** The marginal for the position this column is SHOWING, in the observed space. */
  marginal: OffsetMarginal | null;
  neighboursByLabel: ReadonlyMap<string, NeighbourDisplayRow>;
  /** How many genomes the whole collection has, for the coverage axis. */
  collectionGenomeCount: number;
  isPopoverOpen: boolean;
}>();

const emit = defineEmits<{ walk: [locus: string, sameStrandAsShown: boolean]; togglePopover: [] }>();

const hasOccupant = computed(() => props.slot.locus !== null && props.slot.same_strand !== null);

/**
 * ⛔ A slot with no occupant keeps the FALLBACK width and the FORWARD lane. A contig end is an
 * absence: putting it in a direction lane would assert a transcription direction nothing observed,
 * and scaling it would assert a length nobody measured.
 */
const fit = computed(() =>
  hasOccupant.value
    ? slotFit(props.neighbour?.median_gene_length_nt)
    : { widthPx: widthForAbsentOccupant(), isNarrow: false, isTight: false },
);

const shownDirection = computed(() => (props.slot.same_strand ? "fwd" : "rev"));

const offsetLabel = computed(() => `A${props.labelOffset > 0 ? "+" : ""}${props.labelOffset}`);

/**
 * TWO ORTHOGONAL AXES on one block, and keeping them independent is the point.
 *
 * `--c` is this occupant's own share of the position, against the divergent genes that hold it in
 * other genomes — so the colour describes the gene **named on the block**, not whichever gene
 * happens to be the positional mode. `--p` is how much of the pangenome this part of the graph
 * covers, a property of the locus rather than the position. Read together: solid deep blue is a
 * gene that always holds a position across the whole pangenome; faint purple is one of several
 * divergent options at a position only part of the species has.
 */
const shareOfPosition = computed<number | null>(() => {
  const marginal = props.marginal;
  if (marginal === null || marginal.observed_member_count === 0 || props.slot.locus === null) {
    return null;
  }
  const mine = marginal.occupants.find((occupant) => occupant.locus === props.slot.locus);
  // ⚠ `null`, not 0. An occupant outside the exported top-N has an UNKNOWN share, not a zero one,
  // and the colour ramp would paint a zero as the most divergent purple it has.
  return mine === undefined ? null : mine.gene_count / marginal.observed_member_count;
});

const coverage = computed(() => {
  if (props.neighbour === null || props.collectionGenomeCount <= 0) return 1;
  return props.neighbour.genome_count / props.collectionGenomeCount;
});

const fillStyle = computed(() => ({
  "--c": (shareOfPosition.value ?? 0).toFixed(3),
  "--p": coverage.value.toFixed(3),
}));

const geneName = computed(() => props.neighbour?.display_name ?? props.slot.locus ?? "—");

const blockTip = computed(() => {
  if (!hasOccupant.value) return `nothing observed at ${offsetLabel.value}`;
  const marginal = props.marginal;
  const share =
    shareOfPosition.value === null
      ? "outside the commonest occupants of this position"
      : `${marginal?.occupants.find((o) => o.locus === props.slot.locus)?.gene_count} of ` +
        `${marginal?.observed_member_count} member genes`;
  const recorded =
    props.slot.signed_offset !== props.labelOffset
      ? `\nRecorded at A${props.slot.signed_offset > 0 ? "+" : ""}${props.slot.signed_offset}` +
        " — this arrangement is drawn reversed, so its counts come from there"
      : "";
  return (
    `${geneName.value} (locus ${props.slot.locus})\n${share}; transcribed ` +
    `${props.slot.same_strand ? "with" : "against"} the focal gene${recorded}`
  );
});

function walk(): void {
  if (props.slot.locus === null || props.slot.same_strand === null) return;
  emit("walk", props.slot.locus, props.slot.same_strand);
}
</script>

<template>
  <div
    class="slot"
    :class="{ narrow: fit.isNarrow, tight: fit.isTight, sel: isPopoverOpen }"
    :data-dir="hasOccupant ? shownDirection : 'fwd'"
    :style="{ width: `${fit.widthPx}px` }"
  >
    <span class="gname" :data-tip="geneName">{{ geneName }}</span>

    <button
      type="button"
      class="block"
      :class="{ empty: !hasOccupant, unknown: hasOccupant && shareOfPosition === null, pale: coverage < 0.45 }"
      :data-dir="hasOccupant ? shownDirection : undefined"
      :disabled="!hasOccupant"
      :data-tip="blockTip"
      :aria-label="`position ${offsetLabel}: ${blockTip.replace(/\n/g, '. ')}. Walk to this locus.`"
      @click="walk"
    >
      <span class="fill" :style="fillStyle" />
      <!-- ⚠ Hidden on a narrow slot rather than clipped: below 64 px a block cannot hold its locus
           id and product, and they move to the popover instead. -->
      <template v-if="hasOccupant && !fit.isNarrow">
        <span class="lid">·{{ slot.locus }}</span>
        <span class="gsub">{{ neighbour?.display_name ?? "—" }}</span>
      </template>
    </button>

    <!-- The bar and the offset label are one unit — the bar says what ELSE sits at this position and
         the label says which position that is — so they sit in the middle band together. -->
    <div class="mid">
      <MarginalBar
        :marginal="marginal"
        :highlight-locus="slot.locus"
        :offset-label="offsetLabel"
        :neighbours-by-label="neighboursByLabel"
        :is-open="isPopoverOpen"
        @toggle="emit('togglePopover')"
      />
    </div>
  </div>
</template>
