<script setup lang="ts">
/**
 * *"What else is ever here?"* — every locus observed at one position, and how the members split.
 *
 * ⛔ **The heading names the column the reader CLICKED; the counts come from the position it is
 * showing.** On a row drawn mirrored those are different offsets, and a panel reading "A−1" beside a
 * block labelled "A+1" looks like different data. When they disagree the panel says so
 * (`app.js:2207-2216`) — and the comparison is made between the two offsets directly, which also
 * covers an arrangement flip and a reversed walk cancelling, where reading the flip alone is wrong.
 *
 * ⭐ **Clicking a row is a WALK, not a jump**, and it carries the orientation **as drawn** — so the
 * frame follows what was on screen. The published page's own marginal list got this wrong once by
 * using the raw recorded bit, and pointed the reader the wrong way under a reversed walk.
 */
import { computed } from "vue";

import type { NeighbourDisplayRow, OffsetMarginal } from "@/api/types";
import { type DisplayMirror, strandRelationAsShown } from "@/lib/slotSpaces";
import { walkDirectionAfterStep, type WalkDirection } from "@/lib/walkDirection";

const props = defineProps<{
  marginal: OffsetMarginal;
  /** The offset the clicked COLUMN is labelled with. */
  labelledOffset: number;
  /** The offset the counts were RECORDED at — equal to the above unless the row is mirrored. */
  recordedOffset: number;
  /** The mirroring applied to the drawn row, for turning recorded strand into shown strand. */
  displayMirror: DisplayMirror;
  /** The locus drawn in the block above, so its row can be marked as the one on the track. */
  drawnLocus: string | null;
  /** Total members of the focal locus — the denominator for "genes: contig ends first". */
  focalGeneCount: number;
  neighboursByLabel: ReadonlyMap<string, NeighbourDisplayRow>;
  /** How many occupants per position the export kept, for the "outside the top N" tail. */
  topNeighbourCount: number | null;
}>();

const emit = defineEmits<{ walk: [locus: string, direction: WalkDirection] }>();

function offsetLabel(offset: number): string {
  return `A${offset > 0 ? "+" : ""}${offset}`;
}

const heading = computed(
  () => `${offsetLabel(props.labelledOffset)} · ${props.labelledOffset < 0 ? "upstream" : "downstream"}`,
);

/** ⚠ Compare the two OFFSETS, not the flip — see the component header. */
const isDrawnMirrored = computed(() => props.recordedOffset !== props.labelledOffset);

const observed = computed(() => props.marginal.observed_member_count);

const rows = computed(() =>
  props.marginal.occupants.map((occupant) => {
    // ⛔ The recorded majority relation, then mirrored for display. Anything handed to
    // `walkDirectionAfterStep` must come through here.
    const recorded = occupant.same_strand_gene_count * 2 >= occupant.gene_count;
    const shownSameStrand = strandRelationAsShown(recorded, props.displayMirror);
    const row = occupant.locus === null ? undefined : props.neighboursByLabel.get(occupant.locus);
    return {
      rank: occupant.rank,
      locus: occupant.locus,
      // ⚠ The locus id is shown beside the name because 1,364 display names in these catalogues are
      // carried by more than one locus — two blocks reading the same name may not be the same node.
      name: row?.display_name ?? occupant.locus ?? "—",
      product: row?.display_name_source ?? null,
      geneCount: occupant.gene_count,
      share: observed.value > 0 ? occupant.gene_count / observed.value : 0,
      shownSameStrand,
      isOnTrack: occupant.locus !== null && occupant.locus === props.drawnLocus,
    };
  }),
);

/**
 * ⛔ The two remainders, as counts and never merged. `observed_not_listed` is a **display** cut —
 * occupants past the exported top-N — while `members_without_an_observation` is **missing data**, a
 * member with no gene here at all. One says "there are more loci here than we list"; the other says
 * "some members have nothing here". Collapsing them makes the page claim something it cannot.
 */
const tail = computed(() => {
  const parts: string[] = [];
  if (props.marginal.observed_not_listed > 0) {
    parts.push(
      `+${props.marginal.observed_not_listed} outside the top` +
        (props.topNeighbourCount === null ? "" : ` ${props.topNeighbourCount}`),
    );
  }
  const missing = props.focalGeneCount - observed.value;
  if (missing > 0) parts.push(`${missing} genes: contig ends first`);
  return parts;
});

function percent(share: number): string {
  return `${(100 * share).toFixed(share < 0.1 ? 1 : 0)}%`;
}
</script>

<template>
  <div class="pop-card position-card">
    <h2>{{ heading }}</h2>
    <p class="pop-meta">
      {{ observed }} of {{ focalGeneCount }} member genes<template v-if="isDrawnMirrored">
        · ↺ recorded at {{ offsetLabel(recordedOffset) }}</template>
    </p>

    <button
      v-for="row in rows"
      :key="row.rank"
      type="button"
      class="alt"
      :class="{ 'on-track': row.isOnTrack }"
      :disabled="row.locus === null"
      :title="`Recentre on ${row.name} (locus ${row.locus})`"
      @click="row.locus && emit('walk', row.locus, walkDirectionAfterStep(row.shownSameStrand))"
    >
      <div>
        <div class="alt-name">
          {{ row.name }}
          <!-- The arrow is the SHOWN relation, so it agrees with the block on the track. -->
          <span class="strand">{{ row.shownSameStrand ? "→" : "←" }}</span>
          <span class="lid">·{{ row.locus }}</span>
        </div>
        <div class="alt-desc">{{ row.product ?? `locus ${row.locus}` }}</div>
      </div>
      <div class="alt-n">{{ row.geneCount }} · {{ percent(row.share) }}</div>
    </button>

    <p v-if="tail.length" class="pop-tail">{{ tail.join(" · ") }}</p>
  </div>
</template>
