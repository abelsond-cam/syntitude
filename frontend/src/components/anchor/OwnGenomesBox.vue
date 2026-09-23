<script setup lang="ts">
/**
 * "+ Add my own genome" — the second of the two boxes under "Anchor to:" in the switcher's gutter.
 *
 * ⭐ **It is the anchor box's sibling, not its replacement** (David, 2026-09-22): the anchor box keeps
 * its job and its ⚓; this one brings genomes the model was never built from. The two are the two
 * answers to one question, which is why they now sit under one header (David, 2026-09-23). Both are
 * grey until something is chosen, and **only one can be chosen at a time** — choosing here releases
 * the anchor, because the track draws one genome.
 *
 * ⛔ **A placed genome never wears the anchor's colour.** The anchored-modelled state is orange; a
 * placed genome takes the green `--projected` accent with a dotted border, and the word "placed"
 * rides beside the accession — so hue is never the only thing carrying the difference. A reader must
 * not be able to mistake a genome the model never saw for one it was built from.
 *
 * ⚠ The `+` is the mark, in the same place as the anchor's ⚓ and the same grey, so the two boxes read
 * as one pair of controls rather than two unrelated widgets.
 */
import { computed } from "vue";

import { useAnchorGenomeStore } from "@/stores/anchorGenomeStore";
import { useOwnGenomesStore } from "@/stores/ownGenomesStore";

const props = defineProps<{ speciesKey: string | null }>();

const own = useOwnGenomesStore();
const anchor = useAnchorGenomeStore();
// ⚠ Both boxes are in flow inside `.arr-gutter`, so when the anchor box is REMOVED — which is what
// happens where the catalogue cannot answer an anchor — this one simply takes its place.

/** The genomes placed on the catalogue now open; empty until the dialog has fetched them. */
const placed = computed(() => own.placedFor(props.speciesKey));

/** ⚠ True only for a PROJECTED anchor. An anchored modelled genome leaves this box grey. */
const chosen = computed(() => (anchor.isProjected ? anchor.sampleId : null));

/**
 * Opening the dialog on the step that answers the reader's question: "yours" once something has been
 * placed on this catalogue, otherwise the accounts page that says what is not built.
 */
function open(): void {
  own.open(placed.value.length > 0 ? "yours" : "account");
}

function release(): void {
  anchor.clearAnchor();
}
</script>

<template>
  <div id="own-genomes-wrap" class="own-genomes">
    <button
      type="button"
      class="own-genomes-box"
      :class="{ on: chosen !== null }"
      :aria-pressed="chosen !== null"
      @click="open()"
    >
      <span class="own-genomes-mark" aria-hidden="true">+</span>
      <span v-if="chosen === null" class="own-genomes-label">Add my own genome</span>
      <!-- ⛔ The word "placed" rides with the accession wherever it is shown: the colour is a cue,
           never the claim. -->
      <span v-else class="own-genomes-label">
        <span class="mono">{{ chosen }}</span> · placed
      </span>
    </button>
    <button
      v-if="chosen !== null"
      type="button"
      class="own-genomes-release"
      title="Stop showing this genome"
      @click="release()"
    >
      ✕
    </button>
  </div>
</template>
