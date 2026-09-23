<script setup lang="ts">
/**
 * The **neighbourhood browser** under the track — the control the A0 card's lede points at.
 *
 * ⭐ **This is where an arrangement is PICKED**, and it offers only rows the track can actually
 * draw: the response's `listed`, which is the commonest few **plus whichever the anchored genome
 * carries**, however rare that one is. The A0 card lists every arrangement and selects none; this
 * selects and lists few. Conflating the two counts is how the published page came to claim that
 * four arrangements were all there were (`app.js:1775-1778`).
 *
 * ⛔ **Two marks, not one.** `.on` is *"this is drawn"*; ⚓ is *"this is yours"*. They are usually
 * the same button, and the case where they are not — a manual pick overriding the anchor at this
 * locus — is precisely when the reader has to be able to see both.
 *
 * ⚠ **The buttons come first, the sentences after.** The fan from the focal gene points at the
 * buttons, so they must be the first thing under it; a paragraph above would push them a line
 * further from the locus they belong to and break that line (David, 2026-08-23/25).
 *
 * ⛔ **Two ROOT elements, and no wrapper around them.** `#arrangements.arr-switch` and `.arr-notes` are
 * siblings in the page's grid: `app.css` places the switch at column 2, row 2 — between the anchor
 * control's gutter and the key's — and the notes at `grid-row: 3`, `grid-column: 1 / -1`. A wrapping
 * `<div>` would make them a grid of one and silently drop both placements. The split is structural,
 * not cosmetic: the option row is a grid row of its own so the anchor control beside it can sit
 * vertically centred ON the buttons, and anything appended into the row's box would grow it and pull
 * that control off centre again (`app.js:1780-1782`).
 *
 * ⚠ **The row lives INSIDE `.arr-switch`**, exactly as the published page built it
 * (`app.js:1783`, `host.appendChild(row)`). An earlier version put `.arr-row` at the root on its own;
 * nothing places `.arr-row` in the grid, so it auto-flowed into the 260 px anchor gutter and the
 * buttons stacked into a column down the left of the page — plausible, and wrong, and invisible to
 * every test until the page was rendered beside the published one.
 */
import { computed } from "vue";

import type { Arrangement, Locus, ProjectedCopy } from "@/api/types";
import { arrangementDifference, commonestArrangement } from "@/lib/arrangementDisplay";
import { sharePercent } from "@/lib/formatting";
import type { WalkDirection } from "@/lib/walkDirection";

const props = defineProps<{
  locus: Locus;
  /** The rows the track holds slots for — offer nothing else. */
  arrangements: readonly Arrangement[];
  /** ⛔ Every arrangement this locus has. The sentence counts this; the row draws the above. */
  total: number;
  selectedIndex: number;
  anchorRanks: readonly number[];
  /** The anchored genome's name, or `null` for no anchor — in which case there is no anchor line. */
  anchorGenomeName: string | null;
  /**
   * ⛔ Whether every genome present reaches an arrangement. Chooses between two different claims
   * about an anchored genome that carries none, and only one of them is ever true.
   */
  membershipIsComplete: boolean;
  /**
   * ⛔ A genome PLACED on this model after it was built, not one of its members. Its genes sit on
   * the loci of their nearest modelled genes, so it MATCHES an arrangement rather than being
   * counted in one — and the sentence has to say so, or a reader learns that their genome is part
   * of a model it was never in. `null` when the anchored genome is a member, or when there is none.
   */
  projectedCopies: readonly ProjectedCopy[] | null;
  walkDirection: WalkDirection;
}>();

const emit = defineEmits<{ select: [index: number] }>();

const size = computed(() => props.locus.gene_count);
const base = computed(() => commonestArrangement(props.arrangements));

const options = computed(() =>
  props.arrangements.map((arrangement, index) => ({
    index,
    rank: arrangement.rank,
    genomeCount: arrangement.genome_count,
    share: size.value > 0 ? arrangement.gene_count / size.value : 0,
    isDrawn: index === props.selectedIndex,
    isAnchored: props.anchorRanks.includes(arrangement.rank),
    isInverted: arrangement.is_recorded_reverse_complement,
    difference:
      arrangementDifference(base.value, arrangement, props.walkDirection) ?? "commonest arrangement",
    tooltip:
      `${arrangement.gene_count} of ${size.value} member genes, in ` +
      `${arrangement.genome_count} genomes` +
      (arrangement.is_recorded_reverse_complement ? " — displayed reverse-complemented" : ""),
  })),
);

/**
 * ⚠ Summed over what is DRAWN, not over every arrangement. Every arrangement exists in the
 * database, so summing them all would print "100 % of its genes" at every locus — a true sentence
 * that tells the reader nothing about the buttons in front of them, which is the only thing this
 * line exists to qualify.
 */
const coverage = computed(() => {
  const covered = props.arrangements.reduce((total, one) => total + one.gene_count, 0);
  const verb = props.arrangements.length === 1 ? "accounts for" : "account for";
  return `The ${props.arrangements.length} here ${verb} ${sharePercent(size.value > 0 ? covered / size.value : 0)} of its genes.`;
});

/**
 * ⚠ The single-arrangement locus needs the anchor line MOST — it is the shape a locus an anchored
 * genome does not carry usually has — so this branch cannot simply drop it.
 */
const isSingleArrangement = computed(() => props.total <= 1);

/**
 * ⭐ The placed genome's own sentence, and it never uses the member's words.
 *
 * Four cases, each a different claim: it is here and its whole neighbourhood is one the 100 already
 * have; it is here and its neighbourhood is new; it is here but alone on its contig, so it has no
 * neighbourhood to compare at all; or it has no gene at this locus.
 *
 * ⚠ The agreement always carries its denominator. A locus with *m* modelled genes can offer at most
 * min(n, m) checkers, so "9 of 10" and "1 of 1" are different evidence and the bare numerator would
 * make a rare locus look like a doubtful placement.
 */
const placedLine = computed(() => {
  const who = props.anchorGenomeName;
  const copies = props.projectedCopies;
  if (who === null || copies === null) return null;
  if (copies.length === 0) {
    return { who, isMuted: true, rest: " has no gene placed at this locus — the most common neighbourhood is shown instead" };
  }
  const first = copies[0]!;
  const agreement = `${first.agreeing_neighbours} of its ${first.available_neighbours} nearest agree`;
  const cosine = first.nearest_cosine === null ? "" : `nearest modelled gene ${first.nearest_cosine.toFixed(2)}; `;
  const where = !first.has_a_neighbourhood
    ? "it is alone on its contig here, so it has no neighbourhood to compare"
    : first.matched_arrangement_rank === null
      ? "its neighbourhood here is one no modelled genome has"
      : `its neighbourhood here is #${first.matched_arrangement_rank + 1}`;
  const copiesHere = copies.length > 1 ? ` (${copies.length} of its genes are placed here)` : "";
  return {
    who,
    isMuted: false,
    rest: ` — placed after the model was built, not a member: ${where}. ${cosine}${agreement}.${copiesHere}`,
  };
});

const anchorLine = computed(() => {
  if (placedLine.value !== null) return placedLine.value;
  const who = props.anchorGenomeName;
  if (who === null) return null;
  if (props.anchorRanks.length > 0) return { who, isMuted: false, rest: null };
  return {
    who,
    isMuted: true,
    // ⛔ The two absences are different claims and the shorter line must not merge them. `coords` is
    // an inner join in the export, so a gene with no coordinates never reaches a window: at 6.26 %
    // of ecoli loci a genome is counted present and sits in no arrangement, and "has no gene here"
    // is false there. `membership_is_complete` is the only thing that can tell them apart, and it
    // is a genome count — the gene remainders cannot answer it.
    rest: props.membershipIsComplete
      ? " has no gene at this locus — the most common neighbourhood is shown instead"
      : " has no recorded neighbourhood at this locus — the most common is shown instead",
  };
});
</script>

<template>
  <!-- ⛔ Two roots, deliberately — see the header. Never wrap these in an element. -->
  <template v-if="arrangements.length > 0">
    <!-- `.arr-switch:empty` hides itself, so a single-arrangement locus leaves no gap here. -->
    <div id="arrangements" class="arr-switch">
    <div v-if="!isSingleArrangement" class="arr-row" role="group" aria-label="neighbourhood">
      <button
        v-for="option in options"
        :key="option.rank"
        type="button"
        class="arr-opt"
        :class="{ on: option.isDrawn, anchored: option.isAnchored, flip: option.isInverted }"
        :aria-pressed="option.isDrawn"
        :title="option.tooltip"
        @click="emit('select', option.index)"
      >
        <div class="arr-top">
          <span
            v-if="option.isAnchored"
            class="arr-anch-mark"
            :title="`${anchorGenomeName} carries this arrangement`"
          >⚓</span>
          <span class="arr-rank">#{{ option.rank + 1 }}</span>
          <span
            v-if="option.isInverted"
            class="arr-inv"
            :title="`Displayed reversed: this is the same neighbourhood with ${locus.display_name} inverted relative to it. Read in one frame, the arrangements become comparable.`"
          >↺</span>
          <b>{{ option.genomeCount }}</b> genomes<span class="arr-pct">{{ sharePercent(option.share) }}</span>
        </div>
        <div class="arr-diff">{{ option.difference }}</div>
      </button>
    </div>
    </div>

    <!-- Below the row, in its own grid row, so nothing here can move the buttons. -->
    <div class="arr-notes">
      <p v-if="anchorLine" class="arr-anchored" :class="{ muted: anchorLine.isMuted }">
        <template v-if="anchorLine.rest === null">Anchored to <b>{{ anchorLine.who }}</b></template>
        <template v-else><b>{{ anchorLine.who }}</b>{{ anchorLine.rest }}</template>
      </p>

      <p v-if="isSingleArrangement" class="arr-only">
        All <b>{{ arrangements[0]?.genome_count ?? 0 }}</b> genomes put the same genes around this
        locus — one arrangement.
      </p>
      <!-- Coverage before verdict: the denominator a reader needs to judge the buttons sits in one
           place, directly under them. -->
      <p v-else class="arr-head">
        This locus sits in <b>{{ total }}</b> neighbourhoods across
        <b>{{ locus.genome_count }}</b> genomes. {{ coverage }}
      </p>
    </div>
  </template>
</template>
