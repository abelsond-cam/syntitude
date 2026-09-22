<script setup lang="ts">
/**
 * "View your own genomes" — the accounts placeholder, the add-genomes step, and what was added.
 *
 * ⭐ **A native `<dialog>`, opened with `showModal()`** — it brings the backdrop, the focus trap and
 * Escape with it, and none of that is worth hand-writing. It cannot be a URL: the hash on this page
 * is the locus label (`lib/locusHashRoute.ts`). When accounts exist this becomes a real route.
 *
 * ⛔ **It says what is NOT built, on the first screen a reader meets.** Accounts, saving, the BakRep
 * download and the ESM-C → Bacformer forward pass are all described as what the service does and
 * marked "to be completed" — David wants collaborators to see the whole shape, without being able to
 * mistake the sketch for the service.
 *
 * ⚠ The file is read with `File.text()` in the browser. Nothing is uploaded, nothing is saved, and it
 * is gone on reload — which the first screen also says.
 */
import { computed, ref, watch } from "vue";

import type { SpeciesEntry } from "@/stores/speciesCatalogueStore";
import { useOwnGenomesStore, type LineOutcome } from "@/stores/ownGenomesStore";
import { MAXIMUM_LINES } from "@/lib/parseAccessionList";

const props = defineProps<{
  speciesKey: string | null;
  species: readonly SpeciesEntry[];
}>();

const own = useOwnGenomesStore();

/**
 * ⭐ **The GPU figure is measured** (David, 2026-09-22: "I thought ESM and bacformer single forward
 * was around 15 seconds per genome. Can we please check this"). It is — CSD3 job 36053709, one
 * A100, bf16, the pinned ESM-C + Bacformer path over three probe genomes: **median 14.3 s per
 * genome**, of which Bacformer is 0.12–0.47 s and ESM-C is all the rest. Rounded to 15 on purpose:
 * the three spanned 13–23 s (the first pays CUDA warm-up), so a decimal would claim a precision the
 * measurement does not have. ⚠ It is the HuggingFace attention path — the run warns faESM is not
 * installed — so a tuned service is faster than what is quoted here, never slower.
 *
 * ⚠ **The CPU figure is still provisional** and says so on screen. CSD3 job 36055321 (32 icelake
 * cores, fp32) is measuring it; the laptop run it was going to come from was called off. Both
 * numbers and the jobs they came from are recorded in nuna's `PROJECT_STATE.md` §6.
 */
const GPU_SECONDS_PER_GENOME = 15;
const CPU_MINUTES_PER_GENOME = 45;
const CPU_TIMING_IS_MEASURED = false;

const element = ref<HTMLDialogElement | null>(null);

/** ⚠ Guarded: jsdom has no `showModal`, and a test that mounts this must not blow up on it. */
watch(
  () => own.isOpen,
  (open) => {
    const dialog = element.value;
    if (dialog === null) return;
    if (open && typeof dialog.showModal === "function" && !dialog.open) dialog.showModal();
    if (!open && typeof dialog.close === "function" && dialog.open) dialog.close();
  },
);

/** Escape and the backdrop close the dialog themselves; the store has to hear about it. */
function onClose(): void {
  own.close();
}

const speciesName = computed(
  () => props.species.find((entry) => entry.key === props.speciesKey)?.scientific_name ?? "this catalogue",
);

/** The rosters are loaded when the reader reaches the step that needs them, never before. */
watch(
  () => [own.isOpen, own.step] as const,
  ([open, step]) => {
    if (!open || step !== "add") return;
    if (own.isLoadingRosters || Object.keys(own.modelledBySpecies).length > 0) return;
    void own.loadRosters(
      props.species.map((entry) => ({ key: entry.key, scientificName: entry.scientific_name })),
    );
  },
);

async function onFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file === undefined) return;
  own.setFile(file.name, await file.text());
}

const rows = computed(() =>
  own.lines.map((line) => ({ line, outcome: own.outcomeFor(line, props.speciesKey) })),
);

/** ⚠ Counted from the outcomes, never from the line count: a repeat is not a genome. */
const showable = computed(() => rows.value.filter((row) => row.outcome.kind === "to-be-completed").length);

const MARK: Readonly<Record<LineOutcome["kind"], string>> = {
  "not-an-accession": "✗",
  repeat: "–",
  "modelled-here": "–",
  "modelled-elsewhere": "→",
  "to-be-completed": "○",
  unchecked: "?",
};

function sentenceFor(outcome: LineOutcome): string {
  switch (outcome.kind) {
    case "not-an-accession":
      return "not a BioSample — one per line, SAMN…, SAMEA… or SAMD…";
    case "repeat":
      return "the same genome again";
    case "modelled-here":
      return `already one of the 100 genomes ${speciesName.value} was modelled from — use “Anchor to a genome”`;
    case "modelled-elsewhere":
      return `one of the 100 modelled genomes of ${outcome.scientificName} — switch species to anchor it`;
    case "to-be-completed":
      return "a BioSample we do not hold yet — with an account it would be fetched from BakRep and placed (to be completed)";
    case "unchecked":
      return "the modelled genome list did not load, so this was not checked";
  }
}
</script>

<template>
  <dialog ref="element" class="own-dialog" aria-labelledby="own-dialog-title" @close="onClose">
    <div v-if="own.isOpen" class="own-dialog-in">
      <header class="own-dialog-head">
        <h2 id="own-dialog-title">View your own genomes</h2>
        <button type="button" class="own-close" aria-label="Close" @click="own.close()">✕</button>
      </header>

      <!-- ── 1 · accounts, and what the service does ─────────────────────────────────────────── -->
      <section v-if="own.step === 'account'" class="own-step">
        <p class="lede">Accounts and login will be required — to be completed.</p>
        <p class="muted">
          With an account, the genomes you add are saved and are here when you come back.
        </p>
        <p class="muted">
          Each genome is fetched from <b>BakRep</b> — the Bakta annotation of its assembly — every
          protein is embedded with <b>ESM-C</b>, the genome is run through <b>Bacformer</b>, and each
          gene is placed on the locus of its nearest modelled gene. That is about
          <b>{{ GPU_SECONDS_PER_GENOME }} s per genome on a GPU</b> — measured on an A100, and
          almost all of it is ESM-C — or about {{ CPU_MINUTES_PER_GENOME }} minutes on a
          CPU<span v-if="!CPU_TIMING_IS_MEASURED"> (being measured)</span>.
        </p>
        <p class="muted own-caveat">
          Until then this is a demonstration: nothing you add is saved, fetched or computed, and it is
          forgotten when you reload.
        </p>
        <div class="own-actions">
          <button type="button" class="own-button" disabled>Sign in — to be completed</button>
          <button type="button" class="own-button own-go" @click="own.showStep('add')">
            Continue with the demo →
          </button>
        </div>
      </section>

      <!-- ── 2 · add genomes from a text file ────────────────────────────────────────────────── -->
      <section v-else-if="own.step === 'add'" class="own-step">
        <p class="lede">Add genomes · {{ speciesName }}</p>
        <p class="muted">
          A text file with <b>one BioSample per line</b> (SAMN…, SAMEA…, SAMD…). Lines starting with
          <code>#</code> are ignored, and the first column of a CSV or TSV is taken. Up to
          {{ MAXIMUM_LINES }} lines. The file is read here in your browser — nothing is uploaded.
        </p>
        <div class="own-actions">
          <label class="own-button own-file">
            Choose a .txt file
            <input type="file" accept=".txt,.tsv,.csv,text/plain" @change="onFile" />
          </label>
          <span v-if="own.fileName" class="muted own-file-name">{{ own.fileName }}</span>
        </div>

        <p v-if="own.isLoadingRosters" class="muted">Checking your accessions against the catalogue…</p>
        <p v-else-if="own.rosterFailure" class="pop-error" role="alert">
          The modelled genome list did not load — {{ own.rosterFailure.detail }}. Your accessions are
          listed, but they could not be checked against the catalogue.
        </p>

        <ul v-if="rows.length" class="own-lines">
          <li v-for="row in rows" :key="`${row.line.lineNumber}-${row.line.text}`" :class="row.outcome.kind">
            <span class="own-line-n">{{ row.line.lineNumber }}</span>
            <span class="own-line-mark" aria-hidden="true">{{ MARK[row.outcome.kind] }}</span>
            <span class="own-line-id mono">{{ row.line.text }}</span>
            <span class="own-line-say">{{ sentenceFor(row.outcome) }}</span>
          </li>
        </ul>
        <p v-else-if="own.fileName" class="muted">
          No accession in {{ own.fileName }} — every line was blank or a comment.
        </p>

        <p v-if="own.list?.truncated" class="muted alt-desc">
          Only the first {{ MAXIMUM_LINES }} lines were read.
        </p>
        <p v-if="own.list?.tooLarge" class="muted alt-desc">
          That file is larger than 64 kB, so only its beginning was read.
        </p>

        <div class="own-actions">
          <button type="button" class="own-button" @click="own.showStep('account')">← Back</button>
          <button type="button" class="own-button own-go" @click="own.showStep('yours')">
            {{ showable === 1 ? "Show 1 genome" : `Show ${showable} genomes` }} →
          </button>
        </div>
      </section>

      <!-- ── 3 · what was added ──────────────────────────────────────────────────────────────── -->
      <section v-else class="own-step">
        <p class="lede">Your genomes</p>
        <p class="muted own-banner">
          <b>Demonstration.</b> No genome of yours has been placed yet: fetching it from BakRep,
          embedding it and placing each of its genes on the nearest modelled gene's locus is the part
          still to be built. When it is, the genomes you add appear here and can be shown on the
          track beside the 100 this catalogue was modelled from.
        </p>
        <p class="muted">
          Every count elsewhere on this page — prevalence, the bands, the census, the neighbourhoods —
          is the 100 modelled genomes, and stays that way.
        </p>
        <div class="own-actions">
          <button type="button" class="own-button" @click="own.showStep('add')">← Add genomes</button>
          <button type="button" class="own-button own-go" @click="own.close()">Close</button>
        </div>
      </section>
    </div>
  </dialog>
</template>
