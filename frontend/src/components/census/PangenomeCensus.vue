<script setup lang="ts">
/**
 * The pangenome in two partitions of the same catalogue: by LOCUS and by GENE.
 *
 * ⭐ They answer different questions, and the older summary only gave the first (`app.js::pangenome`).
 * "17,531 loci, 5,458 of them singletons" says a third of the catalogue is one-offs; "4,891 genes per
 * genome, 55 of them singletons" says a typical genome barely meets them. Both are true, and a reader
 * given only the locus count reasonably concludes the wrong thing about what is in a genome.
 *
 * Bands: `core` + `soft_core` is the HEADLINE core (present in ≥ 95 % of genomes); `shell` + `cloud`
 * is the accessory; `rare` is the singleton band. ⚠ "singletons" on BOTH lines — it is one band, and
 * two names for it across two adjacent lines made a reader work out that they were the same thing
 * (David, 2026-08-23).
 *
 * ⚠ The per-genome figures are genes summed per band ÷ genomes, and the three parts sum to the whole
 * by construction because every gene sits in exactly one locus and every locus in one band. They are
 * served, not re-derived from a resident catalogue — the client no longer holds one.
 */
import { computed } from "vue";

import type { SpeciesCatalogueResponse } from "@/api/types";

const props = defineProps<{ catalogue: SpeciesCatalogueResponse }>();

const loci = computed(() => props.catalogue.prevalence_census);
const genes = computed(() => props.catalogue.prevalence_gene_census);
const genomeCount = computed(() => props.catalogue.pangenome.genome_count);

function whole(value: number): string {
  return Math.round(value).toLocaleString();
}

const locusParts = computed(() => [
  {
    value: (loci.value.core + loci.value.soft_core).toLocaleString(),
    label: "core",
    tip: "present in at least 95% of genomes",
  },
  {
    value: (loci.value.shell + loci.value.cloud).toLocaleString(),
    label: "accessory",
    tip:
      `shell (>=15% of genomes) ${loci.value.shell.toLocaleString()} + ` +
      `cloud (2 genomes to <15%) ${loci.value.cloud.toLocaleString()}`,
  },
  { value: loci.value.rare.toLocaleString(), label: "singletons", tip: "found in exactly one genome" },
]);

const perGenome = computed(() => {
  const n = genomeCount.value;
  if (!n) return null;
  const all = Object.values(genes.value).reduce((total, value) => total + value, 0);
  return [
    { value: whole(all / n), label: "genes", tip: "total genes modelled ÷ genomes" },
    {
      value: whole((genes.value.core + genes.value.soft_core) / n),
      label: "core",
      tip: "genes sitting in loci present in >=95% of genomes",
    },
    {
      value: whole((genes.value.shell + genes.value.cloud) / n),
      label: "accessory",
      tip: "genes sitting in shell or cloud loci",
    },
    {
      value: whole(genes.value.rare / n),
      label: "singletons",
      tip: "genes in loci found in exactly one genome — the same band the locus line counts, seen per genome",
    },
  ];
});
</script>

<template>
  <div id="pangenome-lines">
    <div class="pg-line">
      <span class="pg-stat"><b>{{ genomeCount.toLocaleString() }}</b> genomes</span>
      <span class="pg-sep">·</span>
      <span class="pg-stat"><b>{{ catalogue.pangenome.gene_count.toLocaleString() }}</b> genes modelled</span>
    </div>
    <div class="pg-line pg-sub">
      <b>{{ catalogue.pangenome.locus_count.toLocaleString() }}</b><span class="pg-label"> loci:</span>
      <template v-for="(part, index) in locusParts" :key="part.label">
        <span v-if="index" class="pg-sep">·</span>
        <span class="pg-stat" :data-tip="part.tip"><b>{{ part.value }}</b> {{ part.label }}</span>
      </template>
    </div>
    <div v-if="perGenome !== null" class="pg-line pg-sub">
      <span class="pg-label">per genome:</span>
      <template v-for="(part, index) in perGenome" :key="part.label">
        <span v-if="index" class="pg-sep">·</span>
        <span class="pg-stat" :data-tip="part.tip"><b>{{ part.value }}</b> {{ part.label }}</span>
      </template>
    </div>
  </div>
</template>
