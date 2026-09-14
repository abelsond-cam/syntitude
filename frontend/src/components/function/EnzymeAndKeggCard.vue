<script setup lang="ts">
/**
 * **EC and KEGG** — thin enough that they share one compact card rather than each getting a table.
 *
 * ⛔ **A KEGG KO is LINKED and NEVER NAMED.** KEGG's terms permit linking freely but not
 * redistributing its content, and embedding ~880 KO descriptions in a published page is
 * redistribution — unlike NCBI's COG, which is a US Government work. One click for the name is the
 * honest trade, and the asymmetry between the two rows here is that licence, not an oversight.
 *
 * ⚠ **The count is SEPARATED from the accession.** Run together it reads as one token: `K15540`
 * beside a count of 77 came back from a reader as the question *"what is K1554077?"*
 */
import { computed } from "vue";

import type { AnnotationEntry, FunctionResponse } from "@/api/types";
import { enzymeCommissionUrl, keggOrthologyUrl } from "@/lib/functionVocabulary";

const props = defineProps<{
  coverage: FunctionResponse["coverage"];
  enzymeEntries: readonly AnnotationEntry[];
  keggEntries: readonly AnnotationEntry[];
}>();

const lines = computed(() =>
  [
    {
      key: "ec",
      label: "EC",
      entries: props.enzymeEntries,
      annotated: props.coverage.ec_annotated_gene_count,
      url: enzymeCommissionUrl,
      title: (term: string) => `EC ${term} on ExPASy`,
    },
    {
      key: "kegg",
      label: "KEGG KO",
      entries: props.keggEntries,
      annotated: props.coverage.kegg_annotated_gene_count,
      url: keggOrthologyUrl,
      title: (term: string) => `${term} on KEGG — the description lives there, not here`,
    },
  ].filter((line) => line.entries.length > 0),
);

const geneCount = computed(() => props.coverage.gene_count);
</script>

<template>
  <!-- ⚠ The whole card is absent when neither vocabulary has anything, rather than present and
       empty: two headings over nothing say less than no card at all. -->
  <div v-if="lines.length" class="card">
    <h3 class="sub-head">EC and KEGG</h3>
    <div v-for="line in lines" :key="line.key" class="kv">
      <span class="k">{{ line.label }}</span>
      <span class="v">
        <template v-for="(entry, index) in line.entries" :key="entry.term">
          <template v-if="index"> · </template>
          <a
            class="acc-link"
            :href="line.url(entry.term)"
            target="_blank"
            rel="noopener"
            :title="line.title(entry.term)"
          >{{ entry.term }}</a>
          <span class="alt-n">×{{ entry.gene_count }}</span>
        </template>
      </span>
      <span class="cov">{{ line.annotated }} of {{ geneCount }} annotated</span>
    </div>
  </div>
</template>
