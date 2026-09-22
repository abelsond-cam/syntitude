<script setup lang="ts">
/**
 * The locus search — a box, a list of buttons, and an ArrowUp/Down/Enter cursor.
 *
 * ⭐ **The published page's grammar, kept exactly** (`app.js`, "search box"): `mousedown` is
 * prevented on every row so the input's blur cannot beat the click, the list closes on a short delay
 * after blur for the same reason, Escape closes and blurs, and `/` anywhere else on the page focuses
 * the box. The anchor control uses the same idiom deliberately — a second interaction grammar for the
 * same shape of control is a thing readers have to learn twice.
 *
 * ⭐ **The haystack is on the server now**: `pg_trgm` accelerating a literal substring match, so
 * `ligase` still finds *O-antigen ligase RfaL* mid-string. The response says which MODE answered —
 * a 1–2 character query is a prefix match — and the list says so rather than implying the catalogue
 * holds nothing else.
 *
 * ⚠ A failed search renders AS a failure, never as "No locus matches": those are different claims,
 * and only one of them is about the catalogue.
 */
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import { searchLoci } from "@/api/client";
import type { Failure } from "@/api/result";
import type { SearchResponse } from "@/api/types";
import { prevalenceBandLabel } from "@/lib/prevalence";

const props = defineProps<{
  speciesKey: string | null;
  /** The collection size, for the "N/100 genomes" figure on each row. */
  collectionGenomeCount: number | null;
}>();

const emit = defineEmits<{ go: [locusLabel: string] }>();

/** The page's own cap on the dropdown (`app.js::search(…, 40)`). */
const RESULT_LIMIT = 40;
/** Long enough to skip the keystrokes of a word being typed, short enough to feel immediate. */
const DEBOUNCE_MS = 120;
/** The blur-before-click guard (`app.js`: `setTimeout(closeResults, 120)`). */
const CLOSE_AFTER_BLUR_MS = 120;

const input = ref<HTMLInputElement | null>(null);
const query = ref("");
const answer = ref<SearchResponse | null>(null);
const failed = ref<Failure | null>(null);
const cursor = ref(-1);

let debounce: ReturnType<typeof setTimeout> | null = null;
let issued = 0;

function close(): void {
  answer.value = null;
  failed.value = null;
  cursor.value = -1;
}

async function run(text: string): Promise<void> {
  const species = props.speciesKey;
  const trimmed = text.trim();
  const token = ++issued;
  if (species === null || trimmed === "") {
    close();
    return;
  }
  const result = await searchLoci(species, trimmed, { limit: RESULT_LIMIT });
  // ⚠ A later keystroke has already asked a newer question; this answer is to an old one.
  if (token !== issued) return;
  if (!result.ok) {
    answer.value = null;
    failed.value = result;
    cursor.value = -1;
    return;
  }
  failed.value = null;
  answer.value = result.value;
  cursor.value = result.value.hits.length ? 0 : -1;
}

watch(query, (text) => {
  if (debounce !== null) clearTimeout(debounce);
  debounce = setTimeout(() => {
    debounce = null;
    void run(text);
  }, DEBOUNCE_MS);
});

function choose(label: string): void {
  close();
  query.value = "";
  issued += 1;
  emit("go", label);
}

/** Whether the answer on screen is to the text in the box — not to what was typed before it. */
function answerIsCurrent(): boolean {
  return debounce === null && answer.value !== null && answer.value.query.trim() === query.value.trim();
}

async function onKeydown(event: KeyboardEvent): Promise<void> {
  if (event.key === "Escape") {
    close();
    input.value?.blur();
    return;
  }
  if (event.key === "Enter" && query.value.trim() !== "" && !answerIsCurrent()) {
    // ⛔ Enter acts on the text in the box. The published page searched synchronously; here the answer
    // trails the typing by a debounce and a round trip, and Enter pressed inside that gap chose a hit
    // for the PREVIOUS query — `rfa` → `rfaL`, Enter, landed on rfaC. Ask now, then choose.
    event.preventDefault();
    if (debounce !== null) {
      clearTimeout(debounce);
      debounce = null;
    }
    await run(query.value);
    const first = answer.value?.hits[0];
    if (first !== undefined) choose(first.label);
    return;
  }
  const hits = answer.value?.hits ?? [];
  if (!hits.length) return;
  if (event.key === "ArrowDown") {
    cursor.value = (cursor.value + 1) % hits.length;
    event.preventDefault();
  } else if (event.key === "ArrowUp") {
    cursor.value = (cursor.value - 1 + hits.length) % hits.length;
    event.preventDefault();
  } else if (event.key === "Enter" && cursor.value >= 0) {
    const hit = hits[cursor.value];
    if (hit !== undefined) choose(hit.label);
  }
}

function onBlur(): void {
  setTimeout(close, CLOSE_AFTER_BLUR_MS);
}

/**
 * `/` focuses the search from anywhere — except from inside another text box. ⚠ Both anchor boxes
 * are excluded too, or typing the `/` in an accession would throw focus out of the anchor box
 * mid-word (`app.js`, the "/" handler).
 */
function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key !== "/") return;
  const active = document.activeElement;
  if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) return;
  input.value?.focus();
  event.preventDefault();
}

onMounted(() => document.addEventListener("keydown", onDocumentKeydown));
onBeforeUnmount(() => {
  document.removeEventListener("keydown", onDocumentKeydown);
  if (debounce !== null) clearTimeout(debounce);
});

function metaFor(genomeCount: number, band: string): string {
  const denominator = props.collectionGenomeCount === null ? "" : `/${props.collectionGenomeCount}`;
  return `${genomeCount}${denominator} genomes · ${prevalenceBandLabel(band as never)}`;
}
</script>

<template>
  <div class="search">
    <input
      id="q"
      ref="input"
      v-model="query"
      type="search"
      autocomplete="off"
      spellcheck="false"
      placeholder="Search a gene name, product or UniRef50 — press /"
      aria-label="Search loci"
      @keydown="onKeydown"
      @blur="onBlur"
    />
    <div id="results" class="results" role="listbox">
      <div v-if="failed !== null" class="hit-none pop-error" role="alert">
        <div>The search did not complete — {{ failed.detail }}.</div>
      </div>
      <template v-else-if="answer !== null">
        <div v-if="answer.hits.length === 0" class="hit-none">
          <div>No locus matches “{{ answer.query.trim() }}”.</div>
          <div class="alt-desc">
            Names here are Bakta symbols, which are not always the name you know — the O-antigen ligase
            is filed as rfaL, not waaL. Product text and UniRef50 accessions are searched too.
          </div>
        </div>
        <button
          v-for="(hit, index) in answer.hits"
          :key="hit.label"
          type="button"
          class="hit"
          role="option"
          :aria-selected="index === cursor ? 'true' : 'false'"
          @mousedown.prevent
          @click="choose(hit.label)"
        >
          <span class="hit-name">{{ hit.display_name }}</span>
          <span class="hit-desc">{{ hit.best_product ?? "—" }}</span>
          <span class="hit-meta">{{ metaFor(hit.genome_count, hit.prevalence_band) }}</span>
        </button>
        <!-- ⚠ Said, not implied: a prefix match searched less of the haystack, and a capped list is
             not the whole answer. -->
        <div v-if="answer.mode === 'prefix' && answer.hits.length" class="hit-none alt-desc">
          Two characters or fewer match the start of a name only — type a third to search inside names
          and products.
        </div>
        <div v-if="answer.truncated" class="hit-none alt-desc">
          Showing the first {{ answer.hits.length }} — type more to narrow it.
        </div>
      </template>
    </div>
  </div>
</template>
