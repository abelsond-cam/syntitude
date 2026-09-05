/**
 * The `/api/v1` contract, as TypeScript. **Mirrors `serialisers/` exactly** — a change on either
 * side is breaking, which is the analogue of *"a change here is breaking for `app.js`"*.
 *
 * ⚠ **`null` means NOT MEASURED and `0` means MEASURED ZERO, throughout.** Every nullable number
 * below is nullable for that reason and not for tidiness, so `v-if` on any of them is wrong: a
 * measured zero is falsy, and for gap variance it is the *majority* case — 80–90 % of gaps vary not
 * at all. White on the track has to mean "identical in every genome", never "small". Test
 * `!== null`.
 */

import type { NeighbourSlot } from "@/lib/slotSpaces";

export type { NeighbourSlot };

/** Which of the two embeddings a geometric claim is made in. */
export type Representation = "esm" | "bacformer";

/** How common a locus is across the collection. */
export type PrevalenceBand = "core" | "soft_core" | "shell" | "cloud";

/** The three GO namespaces, spelled as the API spells them. */
export type GeneOntologyNamespace =
  | "molecular_function"
  | "biological_process"
  | "cellular_component";

/**
 * ⛔ `no_coverage` is a VALUE, not an absence. Fewer than two annotated members is neither
 * agreement nor disagreement, and counting it as either invents a finding.
 */
export type GoVerdict = "agree" | "disagree" | "no_coverage";

export interface AnnotationEntry {
  readonly rank: number;
  readonly term: string;
  /** `null` where the vocabulary has no name to give — KEGG ids are present and never named. */
  readonly name: string | null;
  readonly gene_count: number;
  readonly gene_ontology_namespace?: GeneOntologyNamespace;
}

export interface UnirefFamily {
  readonly rank: number;
  readonly uniref50_accession: string;
  readonly gene_count: number;
  readonly modal_product: string | null;
  readonly modal_architecture: string | null;
  readonly pfam_annotated_gene_count: number;
  readonly modal_symbol: string | null;
  /** ⚠ A COUNT, not a list. The card shows the modal plus "+N" and cannot name the others. */
  readonly distinct_symbol_count: number;
}

export interface Arrangement {
  readonly rank: number;
  readonly gene_count: number;
  readonly genome_count: number;
  /**
   * ⚠ INTRINSIC to the arrangement — what the badge and the "recorded at" footnote describe. It is
   * NOT display mirroring, and composing the two is `displayMirrorApplied`'s job.
   */
  readonly is_recorded_reverse_complement: boolean;
  /** Ten, always, in RECORDED order. */
  readonly slots: readonly NeighbourSlot[];
}

export interface OffsetOccupant {
  readonly rank: number;
  readonly locus: string | null;
  readonly gene_count: number;
  readonly same_strand_gene_count: number;
}

export interface OffsetMarginal {
  readonly signed_offset: number;
  /** The honest denominator: members with a gene at this position at all. */
  readonly observed_member_count: number;
  /** ⛔ A DISPLAY cut — the occupants past the exported top-N. */
  readonly observed_not_listed: number;
  /** ⛔ MISSING DATA — members with no gene here, typically a contig end. A different sentence. */
  readonly members_without_an_observation: number;
  readonly occupants: readonly OffsetOccupant[];
}

export interface IntergenicGap {
  /** ⛔ Keyed by LABELS, never by index — the published page's index lookup missed 7,379 of 22,838. */
  readonly flanking_loci: readonly [string | null, string | null];
  readonly observed_genome_count: number;
  /** ⛔ SIGNED. Negative means the two genes OVERLAP; 18.8 % of adjacencies do. */
  readonly median_signed_length_nt: number | null;
  readonly quartile1_signed_length_nt: number | null;
  readonly quartile3_signed_length_nt: number | null;
  readonly minimum_signed_length_nt: number | null;
  readonly maximum_signed_length_nt: number | null;
  /** ⛔ `null` = not measured, `0.0` = every genome agrees. */
  readonly length_variance_score: number | null;
  readonly modal_length_nt: number | null;
  readonly distinct_named_feature_count: number;
  /** ⚠ Only `mn == mx` certifies this. `q1 == q3` is the weaker middle-half claim. */
  readonly every_genome_agrees: boolean;
}

export interface LocusGeometry {
  readonly within_medoid_distance: number | null;
  readonly nearest_medoid_distance: number | null;
  /**
   * ⛔ A midrank over MEASURABLE loci only, never over the catalogue. `null` reads "not
   * measurable" — a singleton has no within-distance — and must never render as `0.000`.
   */
  readonly separation_percentile: number | null;
  readonly map_position: readonly [number, number] | null;
  readonly nearest_locus_ordinals: readonly number[] | null;
  /**
   * ⛔ Resolved server-side into a 6×6, with `-1` slot-drops already applied. Slots are not ranks:
   * reading by rank draws one locus's distances on another, and it still looks like a picture.
   */
  readonly cosine_matrix: readonly (readonly (number | null)[])[] | null;
}

export interface NeighbourDisplayRow {
  readonly label: string;
  readonly display_name: string;
  readonly display_name_source: string;
  readonly genome_count: number;
  readonly median_gene_length_nt: number | null;
  readonly prevalence_band: PrevalenceBand;
}

export interface Locus {
  readonly label: string;
  readonly catalogue_ordinal: number;
  readonly display_name: string;
  readonly display_name_source: string;
  readonly display_name_source_accession: string | null;
  readonly best_product: string | null;
  readonly bakta_gene_symbol: string | null;
  readonly gene_count: number;
  readonly genome_count: number;
  readonly named_gene_count: number;
  readonly prevalence_band: PrevalenceBand;
  readonly median_gene_length_nt: number | null;
  readonly gene_length_interquartile_range_nt: number | null;
  readonly uniref50: {
    readonly family_count: number;
    /** ⚠ What the card CLAIMS with, while the list shows every family. */
    readonly major_family_count: number;
    readonly labelled_gene_count: number;
    readonly impurity: number | null;
    readonly coverage: number | null;
  };
  readonly pfam: {
    /** ⛔ `gene_count − this` is MISSING COVERAGE, not a competing architecture. */
    readonly annotated_gene_count: number;
    readonly architecture_count: number;
    /** ⛔ The audit's own verdict, READ and never re-derived — the page once disagreed on 2 of 22,624. */
    readonly concordance_class: string | null;
  };
  readonly evidence: {
    readonly syntenic_a5: number | null;
    readonly collapse_tier: string | null;
    readonly collapse_bucket: string | null;
    /** ⚠ "the identity at which the 50 LONGEST members first group" — weaker than the whole locus. */
    readonly resolved_threshold: number | null;
    readonly resolved_threshold_is_capped_at_50_members: boolean;
  };
  readonly geometry: Readonly<Record<Representation, LocusGeometry>>;
  readonly interest_score: number | null;
}

export interface LocusDetailResponse {
  readonly locus: Locus;
  readonly annotations: Readonly<Record<string, readonly AnnotationEntry[]>>;
  readonly uniref50_families: readonly UnirefFamily[];
  readonly arrangements: {
    readonly listed: readonly Arrangement[];
    /** ⛔ Never moved by any display cap, and never conflated with the number listed. */
    readonly total: number;
    /** ⛔ Arrangements the cap left out — a COUNT of arrangements. */
    readonly arrangements_not_listed: number;
    /**
     * ⛔ Members sitting INSIDE those uncapped arrangements. A different remainder from the one
     * below, and the API's own creation: the published payload is uncapped, so this category did
     * not exist there.
     */
    readonly members_in_arrangements_not_listed: number;
    /**
     * ⛔ Members with no recorded neighbourhood **at all** — no coordinates for the gene, so no
     * window. ⚠ Folding this together with the field above tells a reader that 15,912 *E. coli*
     * genes have no coordinates when they simply sit past the display cap.
     */
    readonly members_without_a_neighbourhood: number;
  };
  /**
   * ⛔ Which arrangement RANKS the anchored genome carries — a **list**, because rho > 1 puts one
   * genome in two arrangements at one locus and there is no uniqueness constraint on
   * (locus, genome) anywhere.
   *
   * ⚠ An empty list carries two different facts and `is_anchored` is what separates them: *"your
   * genome has no gene at this locus"* against *"you have not anchored one"*. They are different
   * sentences on the page.
   */
  readonly anchor: {
    readonly is_anchored: boolean;
    readonly arrangement_ranks: readonly number[];
  };
  readonly offsets: readonly OffsetMarginal[];
  readonly intergenic_gaps: readonly IntergenicGap[];
  /** ⭐ The 15–303-locus fan-out, answered in THIS response rather than in that many more. */
  readonly neighbour_display_rows: readonly NeighbourDisplayRow[];
  readonly resolved_neighbour_count: number;
}

export interface ArrangementPageResponse {
  readonly arrangements: readonly Arrangement[];
  readonly offset: number;
  readonly total: number;
}

export interface FunctionResponse {
  readonly annotations: Readonly<Record<string, readonly AnnotationEntry[]>>;
  readonly coverage: {
    readonly gene_count: number;
    readonly cog_annotated_gene_count: number;
    /** ⛔ A COUNT, never a relation — two COG ids in one locus is ordinary above family level. */
    readonly cog_distinct_id_count: number;
    readonly modal_cog_categories: readonly string[] | null;
    readonly ec_annotated_gene_count: number;
    readonly kegg_annotated_gene_count: number;
    readonly go_annotated_gene_count: Readonly<Record<GeneOntologyNamespace, number>>;
  };
  readonly go_verdicts: Readonly<Record<GeneOntologyNamespace, GoVerdict | null>>;
}

export interface ModelStep {
  readonly ordinal: number;
  readonly name: string;
  readonly representation: Representation | null;
  readonly gamma: number | null;
  readonly rho_rule: string | null;
  readonly rho_ceiling: number | null;
  readonly uses_exclusivity: boolean;
  readonly stage_name: string | null;
  readonly stage_detail: string | null;
}

export interface MapProjection {
  readonly representation: Representation;
  readonly method: string;
  readonly requested_metric: string | null;
  readonly extent: readonly [number, number, number, number];
  readonly cosine_scale_factor: number | null;
  /** ⚠ Without this a cosine has no meaning — ESM's random pairs sit at ~0.645, Bacformer's ~0.065. */
  readonly null_mean_cosine: number | null;
  readonly null_bin_lower_edge: number | null;
  readonly null_bin_width: number | null;
  readonly null_bin_counts: readonly number[] | null;
  /** ⭐ The other half of "p12 of 12,104 loci". */
  readonly separation_measurable_locus_count: number | null;
}

export interface SpeciesCatalogueResponse {
  readonly species: { readonly key: string; readonly scientific_name: string };
  readonly pangenome: {
    readonly run_id: string;
    readonly genome_count: number;
    readonly gene_count: number;
    readonly locus_count: number;
    readonly built_at: string | null;
    readonly git_sha: string | null;
    readonly exclusivity_form: string;
    /** ⚠ An absent section is NAMED, so an omission is never mistaken for a measured zero. */
    readonly omitted_sections: Readonly<Record<string, string>>;
  };
  readonly model: {
    readonly key: string;
    readonly label: string | null;
    readonly exclusivity_form: string;
    readonly knn_k: number | null;
    readonly step_count: number | null;
  } | null;
  readonly steps: readonly ModelStep[];
  readonly provenance_rows: readonly unknown[];
  readonly prevalence_census: unknown;
  readonly audit_headline: unknown;
  readonly map_projections: readonly MapProjection[];
  readonly landing_locus: string | null;
  readonly example_loci: readonly string[];
}

export interface SpeciesListResponse {
  readonly species: readonly {
    readonly key: string;
    readonly scientific_name: string;
    readonly ncbi_taxonomy_id: number | null;
    /** ⚠ A species with nothing published is LISTED with `false`, never filtered out. */
    readonly published: boolean;
    readonly genome_count: number | null;
    readonly gene_count: number | null;
    readonly locus_count: number | null;
    readonly model_label: string | null;
  }[];
}

export interface SearchHit {
  readonly label: string;
  readonly display_name: string;
  readonly gene_count: number;
  readonly genome_count: number;
  readonly prevalence_band: PrevalenceBand;
  readonly rank_band: string | null;
}

export interface SearchResponse {
  readonly query: string;
  /**
   * ⚠ Which mode answered. A 1–2 character query cannot use the trigram index and searches less of
   * the haystack; a reader is entitled to know that rather than to conclude the catalogue is empty.
   */
  readonly mode: string;
  readonly truncated: boolean;
  readonly hits: readonly SearchHit[];
}
