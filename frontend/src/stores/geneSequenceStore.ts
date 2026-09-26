/**
 * The Sequence tab's data — **per locus AND per genome**, which is what makes it different.
 *
 * ⭐ Every other panel on this page is a function of the locus alone. This one needs a genome too,
 * because bases belong to a genome: the same locus reads differently in each of its members, and
 * that is the point of the tab. So it keys on the pair, and changing *either* discards.
 *
 * ⚠ **It is the only endpoint that opens a file.** The server parses a gzipped GFF (~1.5–3 MB) to
 * answer it — tens of milliseconds against a tab the reader clicks — so it is never fetched on a
 * walk, and the request is made only when the tab is open and a genome is chosen.
 */

import { defineStore, storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";

import { fetchGeneSequence } from "@/api/client";
import { LANES } from "@/api/request";
import type { Failure } from "@/api/result";
import type { GeneSequenceResponse } from "@/api/types";

import { useAnchorGenomeStore } from "./anchorGenomeStore";
import { useLocusNavigationStore } from "./locusNavigationStore";

export type SequenceLoadStatus = "idle" | "pending" | "ready" | "failed";

export const useGeneSequenceStore = defineStore("geneSequence", () => {
  const navigation = useLocusNavigationStore();
  const { drawable, catalogueKey } = storeToRefs(navigation);
  const { sampleId: anchorSampleId } = storeToRefs(useAnchorGenomeStore());

  const response = ref<GeneSequenceResponse | null>(null);
  const status = ref<SequenceLoadStatus>("idle");
  const lastFailure = ref<Failure | null>(null);
  const isOpen = ref(false);

  /**
   * Which genome's bases to show.
   *
   * ⭐ Defaults to the **anchored** genome, which is the reader's own: having picked a genome to
   * anchor the track to, being shown a different genome's DNA would be a quiet substitution. With no
   * anchor there is no default, and the tab asks rather than choosing one — a gene's sequence is
   * genome-specific, and "some member's" is not an answer to "what is this gene".
   */
  const chosenSampleId = ref<string | null>(null);
  const sampleId = computed(() => chosenSampleId.value ?? anchorSampleId.value ?? null);

  /** ⛔ The pair, because either half changing invalidates the answer. */
  const key = computed(() => {
    const label = drawable.value?.locus.label ?? null;
    return label === null || sampleId.value === null ? null : `${sampleId.value}@${label}`;
  });

  watch(key, (next, previous) => {
    if (next === previous) return;
    discard();
    if (isOpen.value && next !== null) void load();
  });

  function discard(): void {
    LANES.sequence.cancel();
    response.value = null;
    status.value = "idle";
    lastFailure.value = null;
  }

  /** ⛔ Absolute, never a toggle — the same rule as every other open/closed flag here. */
  function setOpen(open: boolean): void {
    isOpen.value = open;
    if (open && status.value === "idle" && key.value !== null) void load();
  }

  /** Pick a genome explicitly. Clearing it falls back to the anchor. */
  function selectGenome(next: string | null): void {
    chosenSampleId.value = next;
  }

  /**
   * ⛔ **Three answers, and they are three.** An empty `genes` list means *this genome has no gene
   * at this locus* — an answer, and the panel says so in those words. A failure is a failure. A tab
   * that has not asked yet is neither. `app.js:4604`: *"a sequence panel that fails silently is one
   * a reader will read as 'this genome has nothing here', which is a different claim and a false
   * one."*
   */
  async function load(): Promise<void> {
    const species = catalogueKey.value;
    const label = drawable.value?.locus.label ?? null;
    const genome = sampleId.value;
    if (species === null || label === null || genome === null || status.value === "pending") return;

    const requested = key.value;
    status.value = "pending";
    lastFailure.value = null;
    const outcome = await LANES.sequence.run((signal) =>
      fetchGeneSequence(species, genome, label, signal),
    );
    if (outcome.superseded) return;
    // ⚠ A backstop against microtask ordering; the lane's cancel in `discard` is what carries this.
    if (key.value !== requested) return;

    if (!outcome.result.ok) {
      lastFailure.value = outcome.result;
      status.value = "failed";
      return;
    }
    response.value = outcome.result.value;
    status.value = "ready";
  }

  return {
    response,
    status,
    lastFailure,
    isOpen,
    sampleId,
    chosenSampleId,
    setOpen,
    selectGenome,
    load,
    discard,
  };
});
