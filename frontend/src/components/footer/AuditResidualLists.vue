<script setup lang="ts">
/**
 * Every locus grouped on context alone, and every Pfam conflict — a model's own residuals, on its
 * own page, each one click away.
 *
 * ⛔ **Two lists, never one** (`render_page._failures`). They are different kinds of evidence and
 * neither is a verdict: *grouped on context alone* says no sequence, Pfam or ESM method could join
 * the members; a Pfam conflict says their domain architectures share no clan, which an HMM can get
 * wrong by missing homology ESM sees. One list would state a conflict as a grade.
 *
 * ⚠ **Fetched when a list is first opened.** The COUNTS in each summary come from the audit headline
 * the species response already carries, so a closed list still says how long it is; the rows arrive
 * only if the reader asks for them.
 */
import { computed, ref } from "vue";

import { fetchAuditResiduals } from "@/api/client";
import type { Failure } from "@/api/result";
import type { AuditResidualsResponse, ResidualLocusRow } from "@/api/types";
import { prevalenceBandLabel } from "@/lib/prevalence";

const props = defineProps<{
  speciesKey: string;
  audit: Readonly<Record<string, number | string | null>>;
}>();

const emit = defineEmits<{ go: [locusLabel: string] }>();

const lists = ref<AuditResidualsResponse | null>(null);
const failed = ref<Failure | null>(null);
const isLoading = ref(false);

function count(key: string): number {
  const value = props.audit[key];
  return typeof value === "number" ? value : 0;
}

/** `failure_tiers` is synteny_only + no_homology; both are counted here, as the audit counts them. */
// ⚠ The headline's count until the rows arrive, then the rows' OWN count — the published footer
// printed `len(list)`, and a summary must never promise ten over a list of nine.
const contextAloneCount = computed(
  () =>
    lists.value?.grouped_on_context_alone.length ??
    count("synteny_only_n_clusters") + count("no_homology_n_clusters"),
);
const conflictCount = computed(() => lists.value?.pfam_conflicts.length ?? count("pfam_conflict_n_clusters"));

async function load(event: Event): Promise<void> {
  if (!(event.target as HTMLDetailsElement).open || lists.value !== null || isLoading.value) return;
  isLoading.value = true;
  const result = await fetchAuditResiduals(props.speciesKey);
  isLoading.value = false;
  if (result.ok) {
    lists.value = result.value;
    failed.value = null;
  } else {
    failed.value = result;
  }
}

/** `render_page._goto_rows`: enough evidence beside the name to judge before clicking. */
function evidence(row: ResidualLocusRow): string {
  const bits = [prevalenceBandLabel(row.prevalence_band), `${row.gene_count.toLocaleString()} genes`];
  // ⚠ Omitted when not measured — `?? 0` would have printed a measurement nobody made.
  if (row.uniref50_family_count !== null) bits.push(`${row.uniref50_family_count} UniRef50`);
  if (row.pfam_architecture_count !== null) bits.push(`${row.pfam_architecture_count} architectures`);
  if (row.syntenic_a5 !== null) bits.push(`A5 ${row.syntenic_a5.toFixed(2)}`);
  // ⛔ SIMILARITIES on the wire now, and there is nothing left to convert. These were medoid
  // DISTANCES and this line turned each into `1 − d`; they are the same set-to-set numbers the
  // locus card shows, so a surviving subtraction would print the complement of a real similarity —
  // 0.98 as 0.02 — on the one list whose whole job is to be judged gene by gene.
  const within = row.esm_within_similarity;
  const nearest = row.esm_nearest_similarity;
  if (within !== null && nearest !== null) bits.push(`ESM ${within.toFixed(2)}/${nearest.toFixed(2)}`);
  return bits.join(" · ");
}
</script>

<template>
  <details v-if="contextAloneCount > 0" class="foot-detail" @toggle="load">
    <summary>Every locus grouped on context alone ({{ contextAloneCount.toLocaleString() }})</summary>
    <p class="muted">
      No sequence, Pfam or ESM homology behind the grouping — genomic context is all there was. Worth
      looking at every one: this is where the model is doing something an identity threshold cannot, and
      also where it would go wrong. Each is one click away.
    </p>
    <p v-if="failed !== null" class="pop-error" role="alert">The list did not load — {{ failed.detail }}.</p>
    <p v-else-if="lists === null" class="muted">Loading…</p>
    <div v-else class="goto-list">
      <button
        v-for="row in lists.grouped_on_context_alone"
        :key="row.label"
        type="button"
        class="goto-row"
        @click="emit('go', row.label)"
      >
        <b>{{ row.display_name }}</b> <span class="lid">&middot;{{ row.label }}</span>
        <span class="goto-ev">{{ evidence(row) }}</span>
      </button>
    </div>
  </details>
  <details v-if="conflictCount > 0" class="foot-detail" @toggle="load">
    <summary>Every Pfam conflict ({{ conflictCount.toLocaleString() }})</summary>
    <p class="muted">
      The annotated members carry domain architectures with no clan in common — evidence against the
      merge, but not a verdict: an HMM can miss homology ESM sees, and a locus whose members are all phage
      targets or all pilus variants is <em>expected</em> to look varied. A different domain order and a
      missing domain are both excluded before this count. Judge each against its synteny and its ESM pair.
    </p>
    <p v-if="failed !== null" class="pop-error" role="alert">The list did not load — {{ failed.detail }}.</p>
    <p v-else-if="lists === null" class="muted">Loading…</p>
    <div v-else class="goto-list">
      <button
        v-for="row in lists.pfam_conflicts"
        :key="row.label"
        type="button"
        class="goto-row"
        @click="emit('go', row.label)"
      >
        <b>{{ row.display_name }}</b> <span class="lid">&middot;{{ row.label }}</span>
        <span class="goto-ev">{{ evidence(row) }}</span>
      </button>
    </div>
  </details>
</template>
