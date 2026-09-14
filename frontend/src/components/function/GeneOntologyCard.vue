<script setup lang="ts">
/**
 * **GO, one card per namespace** — molecular function, biological process, cellular component.
 *
 * ⛔ **All three, or none.** A namespace with nothing to show still *states* that it has nothing,
 * because `no coverage` and `the members disagree` are different findings and only the second is
 * evidence. A locus with no GO at all is the one case that collapses to a single line, because three
 * identical empty cards say the same thing three times.
 *
 * ⭐ **The terms are GO SLIM classes, not raw terms.** They are folded onto the metagenomics slim
 * *before* the members are compared, because a term and its own child are annotated at different
 * depths rather than in disagreement — comparing raw terms would report a disagreement that is
 * really a difference in annotation detail.
 *
 * ⛔ **Coverage before the verdict, every time.** `no_coverage` gets no chip at all: it is not a
 * verdict, it is the absence of one, and a chip would put it in the same visual position as
 * "classes differ".
 */
import { computed } from "vue";

import type { AnnotationEntry, GeneOntologyNamespace, GoVerdict } from "@/api/types";
import {
  GENE_ONTOLOGY_NAMESPACE_LABEL,
  coverageParts,
  geneOntologyTermUrl,
  geneOntologyVerdict,
} from "@/lib/functionVocabulary";

import CountTable from "../shared/CountTable.vue";

const props = defineProps<{
  namespace: GeneOntologyNamespace;
  annotatedGeneCount: number;
  geneCount: number;
  verdict: GoVerdict | null;
  entries: readonly AnnotationEntry[];
}>();

const label = computed(() => GENE_ONTOLOGY_NAMESPACE_LABEL[props.namespace]);
const chip = computed(() => geneOntologyVerdict(props.verdict));
const coverage = computed(() =>
  coverageParts(props.annotatedGeneCount, props.geneCount, `a ${label.value} term`),
);

const rows = computed(() =>
  props.entries.map((entry) => ({
    key: entry.term,
    count: entry.gene_count,
    term: entry.term,
    // ⚠ The class NAME is the readable half; the accession is what a reader follows. Both, always —
    // `GO:0016020` alone is unreadable and "membrane" alone is unlookupable.
    name: entry.name ?? entry.term,
  })),
);
</script>

<template>
  <div class="card">
    <div class="chip-row func-h">
      <h3 class="sub-head">GO — {{ label }}</h3>
      <span v-if="chip" class="chip" :class="chip.tone">{{ chip.label }}</span>
    </div>
    <p class="muted cover"><b v-if="coverage.emphasis">{{ coverage.emphasis }}</b>{{ coverage.rest }}</p>
    <CountTable v-if="rows.length" :headings="['class', 'GO']" :rows="rows" :total="geneCount">
      <template #cells="{ row }">
        <td>{{ row.name }}</td>
        <td class="acc">
          <a class="acc-link" :href="geneOntologyTermUrl(row.term)" target="_blank" rel="noopener" :title="`${row.term} on AmiGO`">{{ row.term }}</a>
        </td>
      </template>
    </CountTable>
  </div>
</template>
