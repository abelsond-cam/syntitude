<script setup lang="ts">
/**
 * The **A0 card** — *"which neighbourhood does each member gene sit in?"*
 *
 * ⭐ **A0 does not ask what else is here.** By construction the occupant of A0 is this locus, in
 * every member gene, so a bar of occupants there would read 100 % and say nothing. What is genuinely
 * contested at A0 is the *split*: which whole ±5 neighbourhood each member gene realises. This card
 * is where that accounting closes.
 *
 * ⛔ **The rows are STATIC — this card lists, it does not select** (`app.js:2156`). Picking an
 * arrangement is the switcher's job under the track, and the switcher only ever offers rows the
 * track can actually draw. A card that also selected would have to offer a row past the display cut
 * whose slots the page does not hold, and would then either fetch on a click or silently do nothing.
 *
 * ⚠ **The published card claimed "every one of them listed below"** and was right to: its payload
 * was uncapped at 100 genomes. This one lists what it has and says so — see `arrangementBrowserStore`.
 */
import { computed } from "vue";

import type { Arrangement, Locus } from "@/api/types";
import { arrangementDifference, commonestArrangement } from "@/lib/arrangementDisplay";
import { pluralise, sharePercent } from "@/lib/formatting";
import type { WalkDirection } from "@/lib/walkDirection";

const props = defineProps<{
  locus: Locus;
  /** What to list — the merged set, in rank order. */
  arrangements: readonly Arrangement[];
  /** ⛔ Every arrangement this locus has. Never moved by any cap, and never counted off the list. */
  total: number;
  /** The rank drawn on the track, so its row can say so. `null` where none is drawn. */
  selectedRank: number | null;
  /** ⚓ Which ranks the anchored genome carries here. */
  anchorRanks: readonly number[];
  /**
   * ⛔ Members with **no recorded neighbourhood at all** — the gene reached no window. A fact about
   * the locus, read from the response and never derived by subtraction: deriving it swept in every
   * member sitting past the display cap and told 18,264 *E. coli* genes they had no coordinates
   * when 2,352 do (`c1cb12b`).
   */
  membersWithoutANeighbourhood: number;
  walkDirection: WalkDirection;
  /** How many arrangements are not on this list. */
  arrangementsNotShown: number;
  loadStatus: "idle" | "pending" | "ready" | "failed";
  /** The server's own sentence when the last page failed. */
  loadFailureDetail?: string | null;
}>();

const emit = defineEmits<{ loadMore: [] }>();

const size = computed(() => props.locus.gene_count);

/** ⛔ By RANK, never `arrangements[0]` — a page fetched past the cut has no rank 1 in it. */
const base = computed(() => commonestArrangement(props.arrangements));

const rows = computed(() =>
  props.arrangements.map((arrangement) => ({
    rank: arrangement.rank,
    geneCount: arrangement.gene_count,
    genomeCount: arrangement.genome_count,
    share: size.value > 0 ? arrangement.gene_count / size.value : 0,
    difference:
      arrangementDifference(base.value, arrangement, props.walkDirection) ?? "commonest arrangement",
    isDrawn: arrangement.rank === props.selectedRank,
    isAnchored: props.anchorRanks.includes(arrangement.rank),
    isInverted: arrangement.is_recorded_reverse_complement,
  })),
);

const isComplete = computed(() => props.arrangementsNotShown === 0);

const lede = computed(() => {
  const listing = isComplete.value
    ? "every one of them listed below"
    : `${props.arrangements.length} of them listed below`;
  const pick =
    props.total === 1
      ? "there is nothing to choose between."
      : "pick one in the neighbourhood browser under the track to draw it.";
  return {
    listing: `${props.total === 1 ? " neighbourhood" : " different neighbourhoods"} across its ${size.value} member genes, ${listing}. The bar above draws the commonest few; ${pick}`,
  };
});

/**
 * ⛔ **The two remainders, and they are two.**
 *
 * The first is a **display cut** — member genes sitting inside arrangements this card is not
 * listing. The second is **missing data** — member genes that reached no window at all. Merging
 * them tells a reader that genes past a scroll boundary have no coordinates, which is a different
 * claim and a false one.
 *
 * The display cut is derived here rather than taken from the response, because the response's own
 * `members_in_arrangements_not_listed` was computed against the capped list and stops being true
 * the moment a page arrives. The identity it uses is the serialiser's own:
 * `gene_count − members_without_a_neighbourhood` is the number of members that DO sit in some
 * arrangement, so subtracting the ones listed here leaves exactly the ones that do not.
 */
const membersInArrangementsNotShown = computed(() => {
  const listed = props.arrangements.reduce((total, a) => total + a.gene_count, 0);
  return Math.max(0, size.value - props.membersWithoutANeighbourhood - listed);
});

const tail = computed(() => {
  const parts: string[] = [];
  if (membersInArrangementsNotShown.value > 0) {
    parts.push(
      `${membersInArrangementsNotShown.value} member genes sit in arrangements not listed here`,
    );
  }
  if (props.membersWithoutANeighbourhood > 0) {
    // ⚠ The published page's own words, kept for parity, and demonstrably the wrong REASON: these
    // genes are biconditionally the ones alone on their contig, not the ones missing coordinates
    // (`nuna/docs/interesting_loci.md` §6). Rewording it is David's call and is open.
    parts.push(
      `${props.membersWithoutANeighbourhood} member genes have no recorded neighbourhood — ` +
        "no coordinates for the gene, so no window",
    );
  }
  return parts;
});
</script>

<template>
  <div class="pop-card focal-card">
    <h2>A0 · this locus</h2>
    <p class="pop-meta">
      {{ size }} member genes · {{ pluralise(total, "neighbourhood") }}
    </p>

    <p class="pop-lede">This locus sits in <b>{{ total }}</b>{{ lede.listing }}</p>

    <!-- ⚠ The rows scroll, not the card: a card that scrolled as a whole would carry its heading
         and its close control away, and the reader would be left inside a list with no way out. -->
    <div class="arr-scroll">
      <div
        v-for="row in rows"
        :key="row.rank"
        class="alt alt-static"
        :class="{ 'alt-on': row.isDrawn, anchored: row.isAnchored }"
      >
        <div>
          <div class="alt-name">
            <!-- ⚓ Not in the published card, and added deliberately: at an anchored locus whose
                 genome sits in #37 this list is the only place that fact is visible at all. -->
            <span v-if="row.isAnchored" class="arr-anch-mark" title="your anchored genome carries this arrangement">⚓</span>
            #{{ row.rank + 1 }}<template v-if="row.isDrawn"> — drawn above</template>
            <span v-if="row.isInverted" class="arr-inv" title="Displayed reversed: the same neighbourhood with this locus inverted relative to it">↺</span>
          </div>
          <div class="alt-desc">{{ row.difference }}</div>
        </div>
        <div class="alt-n">{{ row.geneCount }} · {{ sharePercent(row.share) }}</div>
      </div>
    </div>

    <!-- ⛔ Failure, waiting and "there is no more" are three different sentences. A page that failed
         must never render as a list that ended. -->
    <p v-if="loadStatus === 'failed'" class="pop-error" role="alert">
      {{ loadFailureDetail ?? "the rest of the list did not load" }}
      <button type="button" class="pop-retry" @click="emit('loadMore')">Try again</button>
    </p>
    <button
      v-else-if="!isComplete"
      type="button"
      class="arr-more"
      :disabled="loadStatus === 'pending'"
      @click="emit('loadMore')"
    >
      {{ loadStatus === "pending" ? "Loading…" : `Show more — ${arrangementsNotShown} not listed` }}
    </button>

    <p v-if="tail.length" class="pop-tail">{{ tail.join(" · ") }}</p>
  </div>
</template>
