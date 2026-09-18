<script setup lang="ts">
/**
 * **The Sequence tab** — one genome's gene(s) at this locus, read from the file Bakta wrote.
 *
 * ⭐ **A sequence is genome-specific, so the tab needs a genome and will not pick one.** With a
 * genome anchored it shows that one — the reader's own choice, and substituting another quietly
 * would be worse than asking. With no anchor it asks, because *"some member's"* is not an answer to
 * *"what is this gene"*.
 *
 * ⛔ **Four different things, and no two of them may look alike:** waiting · failed · *this genome
 * has no gene at this locus* (an ANSWER) · here are the bases. `app.js:4604` — *"a sequence panel
 * that fails silently is one a reader will read as 'this genome has nothing here', which is a
 * different claim and a false one."* Here both of those sentences exist, and they are different
 * sentences.
 */
import { computed } from "vue";

import type { GeneSequenceResponse } from "@/api/types";
import { pluralise } from "@/lib/formatting";

import GeneSequenceCard from "./GeneSequenceCard.vue";

const props = defineProps<{
  displayName: string;
  locusLabel: string;
  /** `null` where no genome is anchored and none has been chosen — the tab then asks for one. */
  sampleId: string | null;
  response: GeneSequenceResponse | null;
  status: "idle" | "pending" | "ready" | "failed";
  failureDetail?: string | null;
  /** The window either side, so every sentence about it quotes one number. */
  flankLength?: number;
}>();

const emit = defineEmits<{ retry: [] }>();

const flankLength = computed(() => props.flankLength ?? 100);
const genes = computed(() => props.response?.genes ?? []);
/** ⭐ ρ > 1: one genome really can hold two genes at one locus, and both are shown. */
const hasGenes = computed(() => genes.value.length > 0);
</script>

<template>
  <!-- ⚠ No `.wrap` of its own: the page's view panel already is one, and a second nests the gutter. -->
  <div>
    <div class="func-head">
      <h2>Sequence</h2>
      <span class="lid">{{ displayName }} ·{{ locusLabel }}</span>
    </div>

    <!-- ⭐ No genome, no guess. -->
    <p v-if="sampleId === null" class="muted">
      Anchor a genome to read its DNA here — a sequence belongs to one genome, and this locus has
      members that differ.
    </p>

    <template v-else>
      <p class="seq-head">
        <b>{{ sampleId }}</b><template v-if="hasGenes"> · {{ pluralise(genes.length, "copy", "copies") }}
        at this locus</template>
      </p>

      <!-- ⛔ Failure, waiting, and "no gene here" are three sentences. -->
      <p v-if="status === 'failed'" class="pop-error" role="alert">
        {{ failureDetail ?? "the sequence did not load" }}
        <button type="button" class="pop-retry" @click="emit('retry')">Try again</button>
      </p>
      <p v-else-if="status !== 'ready' || response === null" class="muted">Reading the annotation file…</p>
      <!-- ⛔ An ANSWER, not a failure: this genome is a member of the catalogue and has no gene at
           this locus, which is a fact about the genome and one a reader came here to learn. -->
      <p v-else-if="!hasGenes" class="muted">
        {{ sampleId }} has no gene at this locus — it is not one of its members.
      </p>
      <!-- ⚠ A `<template v-else>` around the loop, not `v-else` ON it: `v-if` outranks `v-for` in
           Vue 3, so the two on one element compose in an order that is easy to misread and easier
           to break. -->
      <template v-else>
        <GeneSequenceCard
          v-for="gene in genes"
          :key="gene.flat_index"
          :gene="gene"
          :flank-length="flankLength"
        />
      </template>
    </template>
  </div>
</template>
