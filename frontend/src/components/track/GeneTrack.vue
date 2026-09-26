<script setup lang="ts">
/**
 * The track: five genes, the focal gene, five genes, with what lies between them interleaved.
 *
 * ⛔ **An intergenic block is drawn only when an ARRANGEMENT is drawn.** Two marginal modes are not
 * necessarily neighbours in any genome, so the space between them is not an observed gap and drawing
 * one would invent it (`app.js:987`). The fallback track — a locus whose members have no recorded
 * neighbourhood — therefore has no gaps at all, and that is the honest rendering.
 *
 * ⚠ **A gap belongs to a PAIR**, so it cannot be built inside either slot's own component without
 * one of them knowing about the other. The row is assembled here as an explicit list first, and the
 * gaps are interleaved after — which is also what keeps the template free of index arithmetic over
 * three different slot spaces.
 */
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, ref, watch } from "vue";

import type { LocusDetailResponse, NeighbourDisplayRow } from "@/api/types";
import { gapKeyFor, indexGapsByPair } from "@/lib/intergenicGaps";
import {
  SLOT_COUNT,
  type DisplaySlot,
  type NeighbourSlot,
  displaySlots,
  labelSlotFor,
  observedSlotFor,
  signedOffsetForLabelSlot,
} from "@/lib/slotSpaces";
import { useLocusNavigationStore } from "@/stores/locusNavigationStore";
import { useTrackDisplayStore } from "@/stores/trackDisplayStore";

import FocalGeneSlot from "./FocalGeneSlot.vue";
import IntergenicSlot from "./IntergenicSlot.vue";
import NeighbourGeneSlot from "./NeighbourGeneSlot.vue";

const props = defineProps<{
  detail: LocusDetailResponse;
  /** How many genomes the whole collection has, for the coverage axis on each block. */
  collectionGenomeCount: number;
  /** Dimmed while a slower response is in flight — never within the first 150 ms. */
  isDimmed?: boolean;
}>();

const navigation = useLocusNavigationStore();
const track = useTrackDisplayStore();
const { walkDirection, catalogueKey } = storeToRefs(navigation);
const {
  slotsForDisplay,
  displayMirror,
  openPopoverSlot,
  isFocalPopoverOpen,
  drawnArrangement,
  selectedArrangementIndex,
} = storeToRefs(track);

/** Where the focal gene sits among the ten columns: after five of them. */
const FOCAL_AFTER = SLOT_COUNT / 2;

const neighboursByLabel = computed(() => {
  const index = new Map<string, NeighbourDisplayRow>();
  for (const row of props.detail.neighbour_display_rows) index.set(row.label, row);
  return index;
});

const gapsByPair = computed(() => indexGapsByPair(props.detail.intergenic_gaps));

/**
 * ⛔ The IGR tint is ON only where there are scores to tint with (`app.js`: `if (HAS_VAR)`). Without
 * them every gap would be white, which is exactly what a measured, fully conserved neighbourhood
 * looks like — so the class is withheld rather than letting the page claim a measurement it never had.
 */
const hasVarianceScores = computed(() =>
  props.detail.intergenic_gaps.some((gap) => gap.length_variance_score !== null),
);

/**
 * One drawn position. A neighbour carries everything its component needs already resolved — the
 * three slot spaces are collapsed **here**, once, rather than in the template where a wrong one
 * would be invisible.
 */
type RowItem =
  | {
      readonly kind: "neighbour";
      readonly key: string;
      readonly locus: string | null;
      readonly slot: NeighbourSlot;
      readonly display: DisplaySlot;
      readonly labelOffset: number;
      readonly neighbour: NeighbourDisplayRow | null;
      readonly marginal: LocusDetailResponse["offsets"][number] | null;
      readonly isPopoverOpen: boolean;
    }
  | { readonly kind: "focal"; readonly key: string; readonly locus: string };

const row = computed<RowItem[]>(() => {
  const slots = slotsForDisplay.value;
  const neighbours = displaySlots().map((display): RowItem => {
    const slot = slots[display] as NeighbourSlot;
    // ⛔ The OBSERVED position this column is showing — the marginal, the share and the click target
    // must all follow the gene, not the column.
    const observed = observedSlotFor(display, displayMirror.value);
    return {
      kind: "neighbour",
      key: `slot-${display}`,
      locus: slot.locus,
      slot,
      display,
      // ⚠ And the LABEL space, which is a different mapping: an arrangement flip keeps the label
      // where it is, a walk flip moves it.
      labelOffset: signedOffsetForLabelSlot(labelSlotFor(display, walkDirection.value)),
      neighbour: slot.locus === null ? null : (neighboursByLabel.value.get(slot.locus) ?? null),
      marginal: props.detail.offsets[observed] ?? null,
      isPopoverOpen: openPopoverSlot.value === observed,
    };
  });
  return [
    ...neighbours.slice(0, FOCAL_AFTER),
    { kind: "focal", key: "focal", locus: props.detail.locus.label },
    ...neighbours.slice(FOCAL_AFTER),
  ];
});

/** The gap between row positions `index - 1` and `index`, if the response carries one. */
function gapBefore(index: number) {
  // ⛔ Only with an arrangement drawn — see the module header.
  if (drawnArrangement.value === null || index === 0) return undefined;
  const previous = row.value[index - 1]?.locus;
  const current = row.value[index]?.locus;
  if (previous == null || current == null) return undefined;
  return gapsByPair.value.get(gapKeyFor(previous, current));
}

/**
 * ⭐ Put the focal gene under the middle of the page (`app.js::centreFocal`, David 2026-08-23), so
 * the switcher centred below it really is beneath it. The focal gene is the middle SLOT, but slots
 * are as wide as their genes, so five long genes on one side push it far off the track's own centre —
 * only a scroll can centre it. Re-run whenever the row is redrawn: a new locus, another arrangement,
 * a flipped walk. The browser clamps it when the track is narrower than its scroller.
 */
const scroller = ref<HTMLDivElement | null>(null);

async function centreFocal(): Promise<void> {
  await nextTick();
  const host = scroller.value;
  const focal = host?.querySelector<HTMLElement>(".slot.focal");
  if (!host || !focal) return;
  host.scrollLeft = focal.offsetLeft + focal.offsetWidth / 2 - host.clientWidth / 2;
}

onMounted(centreFocal);
watch([() => props.detail, selectedArrangementIndex, walkDirection], centreFocal);

/**
 * ⭐ Prefetch on hover. The cursor sits on a block for 150–300 ms before the click, which covers a
 * 4 kB response — and because there are no user writes the cache is a pure function of its key, so
 * a prefetch that is never used costs one request and no correctness risk at all.
 */
function prefetch(locus: string | null): void {
  if (locus === null || catalogueKey.value === null) return;
  track.prefetchNeighbour(catalogueKey.value, locus);
}
</script>

<template>
  <div ref="scroller" class="track-scroll">
    <div
      class="track"
      :class="{ dimmed: isDimmed, 'igr-var': hasVarianceScores }"
      role="list"
      aria-label="gene neighbourhood"
    >
      <template v-for="(item, index) in row" :key="item.key">
        <IntergenicSlot v-if="index > 0" :gap="gapBefore(index)" />

        <FocalGeneSlot
          v-if="item.kind === 'focal'"
          :locus="detail.locus"
          :arrangements="detail.arrangements.listed"
          :total="detail.arrangements.total"
          :selected-index="selectedArrangementIndex"
          :anchor-ranks="detail.anchor.arrangement_ranks"
          :members-in-arrangements-not-listed="detail.arrangements.members_in_arrangements_not_listed"
          :members-without-a-neighbourhood="detail.arrangements.members_without_a_neighbourhood"
          :walk-direction="walkDirection"
          :is-popover-open="isFocalPopoverOpen"
          @toggle-popover="track.toggleFocalPopover()"
          @select-arrangement="track.selectArrangement($event)"
        />

        <NeighbourGeneSlot
          v-else
          :slot="item.slot"
          :neighbour="item.neighbour"
          :label-offset="item.labelOffset"
          :marginal="item.marginal"
          :neighbours-by-label="neighboursByLabel"
          :collection-genome-count="collectionGenomeCount"
          :is-popover-open="item.isPopoverOpen"
          @walk="track.walkTo(item.display)"
          @toggle-popover="track.togglePopoverAt(item.display)"
          @pointerenter="prefetch(item.locus)"
        />
      </template>
    </div>
  </div>
</template>
