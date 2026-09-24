<script setup lang="ts">
/**
 * Anchor the page to one genome: the track draws ITS neighbourhood at every locus instead of the
 * commonest one, and the Sequence tab shows its bases.
 *
 * ⭐ **One anchor, MOUNTED TWICE** — the switcher's gutter and the top of the Sequence tab. On the
 * published page `setAnchor` walked every mounted box writing the value through, because *"the boxes
 * are two views of one state, not two states that are kept in step"*. Here that sentence is the
 * implementation: both instances read one store and there is nothing to keep in step.
 *
 * ⭐ **The search idiom, deliberately** — input → filter → a list of buttons, ArrowUp/Down/Enter,
 * `mousedown` prevented so blur cannot beat the click, a short close delay on blur. The cursor runs
 * from −1, the "most common arrangement" row, which is ALWAYS first and never hidden behind a ×: it
 * is the off switch, and an off switch a reader has to hunt for is one they conclude does not exist.
 *
 * ⛔ **REMOVED, not disabled, when the catalogue cannot answer an anchor** — the rule the published
 * page set: a control that cannot tell "this genome is not here" from "the page has no idea" must
 * not be offered, because the box would make the same face at both.
 *
 * ⚠ **The genomes are filtered on the server now.** The published page held all of them in
 * `meta.genomes`; at 80,000 genomes that is an array nobody should ship, so a list that was cut says
 * so and says how much it left out.
 */
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";

import { fetchGenomes } from "@/api/client";
import type { Failure } from "@/api/result";
import type { GenomeListResponse } from "@/api/types";
import { useAnchorGenomeStore } from "@/stores/anchorGenomeStore";

const props = defineProps<{
  speciesKey: string | null;
  /** Which mounting this is — it only decides the element ids, never the state. */
  placement: "track" | "sequence";
}>();

/** How many genomes one answer lists before saying it was cut. */
const LIST_LIMIT = 200;
const CLOSE_AFTER_BLUR_MS = 120;

const anchor = useAnchorGenomeStore();
const { sampleId: anchoredSampleId, isAvailable, kind } = storeToRefs(anchor);

/**
 * ⛔ **This box shows only a CATALOGUE anchor.** There is one anchor and both boxes read it, but a
 * genome placed on the model afterwards belongs to the other box — showing its accession here would
 * put it behind the ⚓, which means "one of the modelled genomes", about a genome that is not one.
 * So a projected anchor reads as no anchor here, and the box goes back to its grey empty state.
 */
const sampleId = computed(() => (kind.value === "catalogue" ? anchoredSampleId.value : null));
const isAnchored = computed(() => sampleId.value !== null);

const ids = computed(() =>
  props.placement === "track"
    ? { wrap: "anchor-wrap", box: "anchor-genome", results: "anchor-results" }
    : { wrap: "seq-anchor-wrap", box: "seq-anchor-genome", results: "seq-anchor-results" },
);

const box = ref<HTMLInputElement | null>(null);
const text = ref(sampleId.value ?? "");
const isOpen = ref(false);
const answer = ref<GenomeListResponse | null>(null);
const failed = ref<Failure | null>(null);
/** −1 is the "most common arrangement" row. */
const cursor = ref(-1);
let issued = 0;

// ⭐ Either box setting the anchor rewrites BOTH — they read the same store.
watch(sampleId, (next) => {
  text.value = next ?? "";
});

async function search(query: string): Promise<void> {
  const species = props.speciesKey;
  if (species === null) return;
  const token = ++issued;
  const result = await fetchGenomes(species, query.trim(), { limit: LIST_LIMIT });
  if (token !== issued) return;
  if (result.ok) {
    answer.value = result.value;
    failed.value = null;
  } else {
    answer.value = null;
    failed.value = result;
  }
}

function open(): void {
  isOpen.value = true;
  cursor.value = -1;
  // On focus the box holds the current anchor; listing only that one genome would hide the others,
  // so an unedited box lists everything.
  void search(text.value === sampleId.value ? "" : text.value);
}

function close(): void {
  isOpen.value = false;
  cursor.value = -1;
}

function choose(next: string | null): void {
  anchor.setAnchor(next);
  text.value = next ?? "";
  close();
  box.value?.blur();
}

function onInput(): void {
  isOpen.value = true;
  cursor.value = -1;
  void search(text.value);
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    close();
    box.value?.blur();
    return;
  }
  const hits = answer.value?.genomes ?? [];
  // ⛔ No hits, or an answer to an earlier query: every key below does nothing, as on the published
  // page (`if (!A.hits.length) return;`). Otherwise Enter on "No genome matches" hit the −1 row and
  // CLEARED the reader's anchor — the one thing they were not asking for.
  const answeredQuery = answer.value?.query ?? null;
  const typed = text.value === sampleId.value ? "" : text.value.trim();
  if (hits.length === 0 || answeredQuery !== typed) return;
  if (event.key === "ArrowDown") {
    cursor.value = cursor.value + 1 >= hits.length ? -1 : cursor.value + 1;
    event.preventDefault();
  } else if (event.key === "ArrowUp") {
    cursor.value = cursor.value <= -1 ? hits.length - 1 : cursor.value - 1;
    event.preventDefault();
  } else if (event.key === "Enter") {
    choose(cursor.value < 0 ? null : (hits[cursor.value]?.sample_id ?? null));
    event.preventDefault();
  }
}

function onBlur(): void {
  setTimeout(() => {
    close();
    // A half-typed query that was never chosen is not an anchor; put back the one that is.
    text.value = sampleId.value ?? "";
  }, CLOSE_AFTER_BLUR_MS);
}
</script>

<template>
  <div v-if="isAvailable" :id="ids.wrap" class="arr-anchor" :class="{ on: isAnchored, 'seq-anchor': placement === 'sequence' }">
    <label class="arr-anchor-box" :for="ids.box">
      <input
        :id="ids.box"
        ref="box"
        v-model="text"
        type="search"
        autocomplete="off"
        spellcheck="false"
        placeholder="A genome in BacAtlas"
        :aria-label="placement === 'track' ? 'Anchor the neighbourhood to one genome' : 'Anchor the sequence to one genome'"
        @focus="open"
        @input="onInput"
        @keydown="onKeydown"
        @blur="onBlur"
      />
      <!-- ⚠ U+2693 U+FE0E — the variation selector asks for the TEXT anchor. The bare character can
           draw as a colour emoji, which ignores `color`, and the grey state would never be grey. -->
      <span class="arr-anchor-mark" aria-hidden="true">⚓︎</span>
      <span class="arr-anchor-caret" aria-hidden="true">▾</span>
    </label>
    <!-- ⚠ Clicks stop HERE: the document-level closer dismisses the popover on any outside click,
         and would take this list with it before a click on a row could land. -->
    <div :id="ids.results" class="results anchor-results" role="listbox" @click.stop>
      <template v-if="isOpen">
        <div v-if="failed !== null" class="hit-none pop-error" role="alert">
          The genome list did not load — {{ failed.detail }}.
        </div>
        <template v-else-if="answer !== null">
          <button
            type="button"
            class="anchor-hit clear"
            role="option"
            :aria-selected="cursor === -1 ? 'true' : 'false'"
            @mousedown.prevent
            @click="choose(null)"
          >
            most common arrangement
          </button>
          <div v-if="answer.genomes.length === 0" class="hit-none">
            No genome in this catalogue matches “{{ answer.query }}”.
          </div>
          <button
            v-for="(genome, index) in answer.genomes"
            :key="genome.sample_id"
            type="button"
            class="anchor-hit"
            role="option"
            :aria-selected="index === cursor ? 'true' : 'false'"
            @mousedown.prevent
            @click="choose(genome.sample_id)"
          >
            <span>{{ genome.sample_id }}</span>
            <!-- ⚠ `locus_count` — loci where this genome has a GENE. The published page could only
                 count loci where it appears in a recorded neighbourhood (`arrangement_locus_count`),
                 which undercounts wherever a gene got no window. Per LOCUS either way. -->
            <span class="anchor-n">{{ genome.locus_count.toLocaleString() }} loci</span>
          </button>
          <div v-if="answer.truncated" class="hit-none alt-desc">
            {{ answer.genomes.length }} of {{ answer.matched_genome_count.toLocaleString() }} matching genomes
            — type more of the accession to narrow it.
          </div>
        </template>
      </template>
    </div>
  </div>
</template>
