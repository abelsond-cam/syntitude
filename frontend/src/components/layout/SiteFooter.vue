<script setup lang="ts">
/**
 * The footer: what this catalogue is, how its model was built, what the audit counted against it,
 * and whose data it shows.
 *
 * ⭐ **Every number here is read from the model's own output and its audit — nothing re-derived**,
 * which is the promise its first sentence makes. The audit headline is QUOTED under the keys the
 * report used, in a closed `<details>`: a reader who wants to know what was counted against this
 * model must be able to find it, but a stranger landing here wants a locus, not a scorecard.
 *
 * ⚠ **Attribution is binding**, not a courtesy: GO and UniProt are CC BY 4.0. KEGG appears only as a
 * linked accession — its terms permit linking and not redistribution, which is why no KO is named.
 */
import { computed } from "vue";

import type { SpeciesCatalogueResponse } from "@/api/types";
import AuditResidualLists from "@/components/footer/AuditResidualLists.vue";

const props = defineProps<{ catalogue: SpeciesCatalogueResponse }>();
const emit = defineEmits<{ go: [locusLabel: string] }>();

/**
 * The graded headline in the order a reader needs it (`render_page._HEADLINE_ROWS`): how big, what was
 * found against it, what was rescued. Each is formatted exactly as the published footer formatted it.
 */
const HEADLINE_ROWS: readonly (readonly [string, string, (value: number) => string])[] = [
  ["clusters graded", "n_clusters_total", (value) => value.toLocaleString()],
  ["genes", "n_genes_total", (value) => value.toLocaleString()],
  ["synteny only — no homology by mmseqs", "synteny_only_n_clusters", (value) => `${value.toLocaleString()} clusters`],
  ["synteny only, as a gene rate", "synteny_only_gene_rate", (value) => `${(value * 100).toFixed(4)}%`],
  ["Pfam conflict", "pfam_conflict_n_clusters", (value) => `${value.toLocaleString()} clusters`],
  // NOT "of which": the denominator is different — Pfam judges only loci with ≥ 2 annotated members.
  ["loci Pfam can judge (≥2 annotated members)", "pfam_judgeable_n_clusters", (value) => `${value.toLocaleString()} clusters`],
  ["UniRef50 family split across loci", "split_gene_rate_excl_singletons", (value) => `${(value * 100).toFixed(2)}% of genes`],
  ["rescued by ESM homology", "n_clusters_esm_rescued", (value) => `${value.toLocaleString()} clusters`],
];

const provenance = computed(() => {
  const pangenome = props.catalogue.pangenome;
  const rows: [string, string][] = props.catalogue.provenance_rows.map(([label, value]) => [label, value]);
  rows.push(["model", pangenome.run_id]);
  rows.push(["built", pangenome.built_at ?? "—"]);
  if (pangenome.git_sha) rows.push(["code", pangenome.git_sha]);
  return rows;
});

const headline = computed(() =>
  HEADLINE_ROWS.flatMap(([label, key, format]) => {
    const value = props.catalogue.audit_headline[key];
    if (value === undefined || value === null) return [];
    return [[label, typeof value === "number" ? format(value) : String(value)] as const];
  }),
);

const omitted = computed(() => {
  const reasons = Object.values(props.catalogue.pangenome.omitted_sections);
  return reasons.length ? `Not shown on this build: ${reasons.join("; ")}.` : "";
});
</script>

<template>
  <footer class="foot">
    <div class="wrap">
      <p>
        Prototype built from a single <em>{{ catalogue.species.scientific_name }}</em> clustering. Every
        number on this page is read from that model's own output and its accessory-fidelity audit — nothing
        is re-derived for display.
      </p>
      <dl>
        <div v-for="([label, value], index) in provenance" :key="index">
          <dt>{{ label }}</dt>
          <dd>{{ value }}</dd>
        </div>
      </dl>
      <details v-if="headline.length" class="foot-detail">
        <summary>Accessory-fidelity audit — what was counted against this model</summary>
        <dl>
          <div v-for="[label, value] in headline" :key="label">
            <dt>{{ label }}</dt>
            <dd>{{ value }}</dd>
          </div>
        </dl>
        <p class="muted">
          Read verbatim from the accessory audit. <b>Synteny only</b> means no homology mmseqs, Pfam or ESM
          could find — the members were grouped on genomic context. That names the evidence, not a mistake:
          many are good calls, and the way to tell is the evidence beside each one. Clusters rescued by Pfam
          or by ESM are homologous and are not counted here.
        </p>
      </details>
      <AuditResidualLists
        :species-key="catalogue.species.key"
        :audit="catalogue.audit_headline"
        @go="emit('go', $event)"
      />
      <p v-if="omitted" class="muted">{{ omitted }}</p>
      <p class="muted">
        Reference data: gene and protein annotation by <b>Bakta</b>; protein families from
        <a href="https://www.uniprot.org/">UniProt / UniRef50</a> and
        <a href="https://www.ebi.ac.uk/interpro/">Pfam / InterPro</a>; functional classification from the
        <a href="https://geneontology.org/">Gene Ontology</a> and
        <a href="https://www.ncbi.nlm.nih.gov/research/cog">NCBI COG</a>;
        <a href="https://www.genome.jp/kegg/">KEGG</a> orthology accessions are linked, not reproduced. Gene
        Ontology and UniProt data are used under
        <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.
      </p>
    </div>
  </footer>
</template>
