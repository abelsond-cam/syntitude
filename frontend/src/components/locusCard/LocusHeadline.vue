<script setup lang="ts">
/**
 * What this locus IS, and how good it is — the card the `--anchor` accent ties to the focal block
 * on the track, so it is visible at a glance which gene is being described.
 *
 * ⭐ **Two rows of three tiles: the first says WHAT, the second says HOW GOOD.** Shares, not
 * fractions — the denominator is the same on every locus, so printing it six times a page adds
 * nothing a reader has to hold. Member genes, named genes and the family count are all stated
 * better lower down and are deliberately absent here.
 *
 * ⛔ **Separation is the only tile that is a RANK**, because it is the only one whose spread is
 * worth ranking. Cohesion is measured against the random-pair baseline instead: almost every locus
 * in these catalogues is cohesive, so ranking cohesion against its peers says the opposite of the
 * truth. See `lib/locusStatistics`.
 */
import { computed } from "vue";

import type { Locus, MapProjection } from "@/api/types";
import { sharePercent } from "@/lib/formatting";
import {
  cohesion,
  copiesPerGenome,
  percentileLabel,
  separationVerdict,
  signedFixed,
  similarityFromDistance,
} from "@/lib/locusStatistics";
import { prevalenceBandLabel, prevalenceBandShade } from "@/lib/prevalence";

const props = defineProps<{
  locus: Locus;
  /** How many genomes the whole collection has — the denominator for "of genomes". */
  collectionGenomeCount: number;
  /**
   * The per-representation random-pair baselines, keyed by representation. ⚠ Without them cohesion
   * has no meaning: ESM's random pairs sit at ~0.645 and Bacformer's at ~0.065.
   */
  mapProjections: readonly MapProjection[];
  /** How many loci the separation midrank was taken over — the other half of "p12 of 12,104 loci". */
  separationMeasurableLocusCount: number | null;
}>();

const nullMeanFor = computed(() => {
  const means = new Map<string, number | null>();
  for (const projection of props.mapProjections) {
    means.set(projection.representation, projection.null_mean_cosine);
  }
  return means;
});

function withinSimilarity(representation: "esm" | "bacformer"): number | null {
  return similarityFromDistance(props.locus.geometry[representation].within_medoid_distance);
}

function cohesionFor(representation: "esm" | "bacformer"): number | null {
  return cohesion(withinSimilarity(representation), nullMeanFor.value.get(representation) ?? null);
}

/**
 * ⚠ The separation tile reads **Bacformer**, the context axis — the same representation the track
 * is built on. The published page tiles that one and not ESM, and the geometry card below shows
 * both.
 */
const verdict = computed(() =>
  separationVerdict(
    withinSimilarity("bacformer"),
    similarityFromDistance(props.locus.geometry.bacformer.nearest_medoid_distance),
    props.locus.geometry.bacformer.separation_percentile,
  ),
);

const separationTitle = computed(() => {
  const value = verdict.value;
  if (value === null) return undefined;
  const over =
    props.separationMeasurableLocusCount === null
      ? "the measurable loci"
      : `${props.separationMeasurableLocusCount.toLocaleString()} loci`;
  return (
    `${value.label} — Bacformer separation ${signedFixed(value.separation)} ` +
    `(own members − nearest other), ranked against ${over}`
  );
});

/** ⛔ `—` where a number was never measured. Never `0`, which is a measurement. */
function orDash(value: number | null, format: (value: number) => string): string {
  return value === null ? "—" : format(value);
}

const copies = computed(() => copiesPerGenome(props.locus.gene_count, props.locus.genome_count));

const tiles = computed(() => [
  {
    key: "prevalence",
    value: orDash(
      props.collectionGenomeCount > 0 ? props.locus.genome_count / props.collectionGenomeCount : null,
      (share) => sharePercent(share),
    ),
    caption: "of genomes",
  },
  { key: "copies", value: orDash(copies.value, (rho) => rho.toFixed(2)), caption: "copies per genome" },
  {
    key: "a5",
    value: orDash(props.locus.evidence.syntenic_a5, (a5) => a5.toFixed(2)),
    caption: "synteny A5",
  },
  {
    key: "bacformer-cohesion",
    value: orDash(cohesionFor("bacformer"), (value) => sharePercent(value)),
    caption: "synteny cohesion",
  },
  {
    key: "esm-cohesion",
    value: orDash(cohesionFor("esm"), (value) => sharePercent(value)),
    caption: "ESM cohesion",
  },
  {
    key: "separation",
    value: verdict.value === null ? "—" : percentileLabel(verdict.value.percentile),
    caption: "cluster separation",
    toneClass: verdict.value === null ? null : `sep-${verdict.value.verdictClass}`,
    title: separationTitle.value,
  },
]);

/**
 * ⚠ The caveat sits BESIDE the name, not in the typography. A name rendered in a different weight
 * to say "inferred" just looks broken; a sentence says what it means.
 */
const inferredNote = computed(() => {
  switch (props.locus.display_name_source) {
    case "product":
      return "inferred from the Bakta product — not a Bakta gene name";
    case "pfam_architecture":
      // The accession the name was read out of — `soleArch`'s single architecture.
      return `inferred from ${props.locus.display_name_source_accession ?? "Pfam"} — not a Bakta gene name`;
    // ⛔ `label` gets NO note, and that is not an oversight. There the display name IS the locus id,
    // so there is no name to caveat: a line saying "inferred from label" would invent a claim about
    // a name nothing inferred. 16,551 of 33,201 loci are in this case.
    case "label":
    case "bakta_symbol":
    default:
      return null;
  }
});
</script>

<template>
  <div class="card focus-card">
    <div class="locus-head">
      <h1 class="locus-name">{{ locus.display_name }}</h1>
      <span
        class="band"
        :style="{ '--b': prevalenceBandShade(locus.prevalence_band).toFixed(2) }"
      >{{ prevalenceBandLabel(locus.prevalence_band) }}</span>
      <span class="locus-id">locus {{ locus.label }}</span>
    </div>

    <p v-if="inferredNote" class="inferred-note">{{ inferredNote }}</p>
    <p v-if="locus.best_product" class="lede">{{ locus.best_product }}</p>

    <div class="tiles">
      <div v-for="tile in tiles" :key="tile.key" class="tile" :class="tile.toneClass" :title="tile.title">
        <div class="v">{{ tile.value }}</div>
        <div class="k">{{ tile.caption }}</div>
      </div>
    </div>
  </div>
</template>
