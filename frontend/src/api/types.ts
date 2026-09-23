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

/**
 * How common a locus is across the collection — **five** bands, `prevalence.categorise`'s own.
 *
 * ⛔ `rare` was missing from this union while 9,877 of 33,201 loci — **30 %** — carry it. TypeScript
 * cannot catch that: the value arrives as a string and only a lookup keyed on the band, or an
 * exhaustive switch, ever notices, and then as `undefined` at render time rather than as an error.
 * `apiContract.test.ts` now asserts the union covers every band the real responses carry.
 *
 * ⚠ The order below is the order the bands are *drawn* in, commonest first. `PREVALENCE_BANDS` in
 * `lib/prevalence` is the runtime copy; the two are pinned to each other by a test.
 */
export type PrevalenceBand = "core" | "soft_core" | "shell" | "cloud" | "rare";

/** The three GO namespaces, spelled as the API spells them. */
export type GeneOntologyNamespace =
  | "molecular_function"
  | "biological_process"
  | "cellular_component";

/**
 * ⛔ `no_coverage` is a VALUE, not an absence. Fewer than two annotated members is neither
 * agreement nor disagreement, and counting it as either invents a finding.
 */
/**
 * ⛔⛔ **The Pfam ladder, not a yes/no** — and this type said `"agree" | "disagree" | "no_coverage"`
 * until the function tab was built against it.
 *
 * The server stores and sends `GeneOntologyAgreementVerdict`, six values, because GO agreement means
 * the same thing Pfam agreement does and one vocabulary serves both. Nothing caught the error: no
 * component read `go_verdicts` until now, and when one did every chip would have rendered blank —
 * `VERDICTS["single"]` is `undefined` in a table keyed on `"agree"` — with the page showing a locus
 * whose members agree as a locus with no verdict at all.
 *
 * ⚠ `no_coverage` is a VALUE, never a null: fewer than two annotated members is neither agreement
 * nor disagreement and must not be counted as either.
 */
export type GoVerdict =
  | "no_coverage"
  | "single"
  | "same_domains"
  | "nested"
  | "overlapping"
  | "disjoint";

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
  /**
   * ⚠ **Nullable in the schema**, though populated for all 38,672 crosstab rows in the two loaded
   * catalogues. Typed as the column allows rather than as this data happens to be: a contract that
   * promises non-null where the schema permits null is a latent crash one ingest away, and the card
   * must test `!== null` — a measured **zero** here is the loudest case, a family where no gene is
   * annotated at all.
   */
  readonly pfam_annotated_gene_count: number | null;
  /** ⚠ `null` for 20,600 of 38,672 rows — over half the families carry no modal symbol. */
  readonly modal_symbol: string | null;
  /** ⚠ A COUNT, not a list. The card shows the modal plus "+N" and cannot name the others. */
  readonly distinct_symbol_count: number | null;
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

/**
 * One Pfam-A family, resolved server-side from the vendored public reference.
 *
 * ⚠ **Every field is a string and `""` means the table HAD no value** — never that the key is
 * missing. The vendored reader pads short rows rather than skipping them, so a caller tests
 * membership of the map, not the truthiness of `short_name`.
 */
export interface PfamFamilyReference {
  /** `Sigma70_r2` — what the chip says when it has one. */
  readonly short_name: string;
  readonly description: string;
  /**
   * ⭐ Preferred over the Pfam entry for the link: it is the integrated record, and the page a
   * reader following a domain actually wants. `""` where there is no integrated entry.
   */
  readonly interpro_accession: string;
  readonly interpro_name: string;
  /**
   * ⚠ `""` is CLANLESS and is **not** an identity. Only ~46 % of families are in a clan, so
   * treating `""` as a shared clan would make any two clanless families look like the same
   * superfamily — the common case, not the corner.
   */
  readonly clan_accession: string;
  readonly clan_name: string;
}

export interface NeighbourDisplayRow {
  readonly label: string;
  /**
   * ⛔⛔ **The row's OTHER address, and the MAP needs exactly this one.** An arrangement slot code
   * carries `catalogue_ordinal * 2 + strand`, and `geometry[rep].nearest_locus_ordinals` is in the
   * same space — while the marginal occupants are addressed by `label`. Both are small integers
   * over the same range, so resolving the map's nearest loci through anything else draws one locus
   * where another belongs, on a page that still looks entirely right. That exact merge already cost
   * this project once (`2b99bb4`).
   */
  readonly catalogue_ordinal: number;
  readonly display_name: string;
  /**
   * ⭐ For the MAP legend, not the track. *"The locus NUMBER is not what tells you whether a
   * neighbour belongs here — the product is."* The track has no room for it and does not ask.
   */
  readonly best_product: string | null;
  /**
   * Where this locus sits on the **whole-catalogue UMAP**, per representation — the quantised
   * `map_x`/`map_y` the catalogue sprite was drawn from.
   *
   * ⚠ **Served, no longer drawn.** The page stopped showing the catalogue picture on 2026-09-22
   * (David: *"It isn't helpful"*) and nothing here reads this; it is typed because the server still
   * sends it. ⛔ `null` is *no medoid*, never a position of `0, 0` — which is a PLACE.
   */
  readonly map_position: Readonly<Record<Representation, MapPosition | null>>;
  /**
   * ⭐ The map's RING for this locus, per representation — its own members' median distance from its
   * centre, at true scale. *"A ring reaching a neighbour is a spread that reaches it."*
   *
   * ⚠ A **distance**, as stored, so the client converts with `similarityFromDistance` exactly as
   * the card does. `null` where it was never measured — a singleton is its own medoid.
   */
  readonly within_medoid_distance: Readonly<Record<Representation, number | null>>;
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
    /**
     * ⛔ Whether EVERY genome present reaches an arrangement — a **genome** question, and the only
     * thing that settles which of two sentences the anchor line may say. With no anchored ranks,
     * `true` means *"has no gene at this locus"* and `false` means *"has no recorded neighbourhood
     * at this locus"*; they are different claims and only one is ever true. Measured: **6.26 % of
     * ecoli loci and 3.69 % of kp loci** are incomplete (worst case 64 genomes of 100).
     *
     * ⚠ Not derivable from the two gene remainders above. A genome at ρ > 1 has two genes here, and
     * one of them losing its window leaves the genome fully present in an arrangement.
     */
    readonly membership_is_complete: boolean;
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
    /**
     * ⛔ `catalogue` | `projected` | `null`. A catalogue genome is COUNTED in the arrangements it
     * occupies; a projected genome MATCHES one without being in it, so `arrangement_ranks` stays
     * empty for it and its relation is in `projected_copies`. A client that ignores the kind cannot
     * accidentally render a projected genome as a member — but one that reads `arrangement_ranks`
     * alone would say "no gene at this locus" about a gene that is plainly placed there.
     */
    readonly kind: "catalogue" | "projected" | null;
    readonly projected_copies: readonly ProjectedCopy[];
  };
  readonly offsets: readonly OffsetMarginal[];
  readonly intergenic_gaps: readonly IntergenicGap[];
  /**
   * ⭐ Every Pfam family this response MENTIONS, keyed by **version-stripped** accession. The same
   * move as `neighbour_display_rows`: a bounded block in one round trip, instead of the page
   * carrying an 833 kB vendored reference to render a chip.
   *
   * ⛔ A chip holding `PF00126.29` must cut at the dot before looking itself up, or it silently
   * misses and falls back to a bare accession — which reads as *"this family has no name"* rather
   * than as a failed join.
   */
  readonly pfam_reference: Readonly<Record<string, PfamFamilyReference>>;
  /** ⭐ The 15–303-locus fan-out, answered in THIS response rather than in that many more. */
  readonly neighbour_display_rows: readonly NeighbourDisplayRow[];
  readonly resolved_neighbour_count: number;
}

/**
 * One gene of a PROJECTED genome at this locus — placed after the model was built.
 *
 * ⛔ **`agreeing_neighbours` is meaningless without `available_neighbours`.** A locus with *m*
 * modelled genes can supply at most min(n, m) of the n checkers, so the raw count tracks the
 * locus's SIZE as much as the evidence: measured over the first ten placed genomes, `is_contested`
 * runs at 0.39 % where the locus has ten genes to offer and 42.6 % where it has fewer, reaching
 * 96.3 % at singleton loci. Render them together or not at all.
 */
export interface ProjectedCopy {
  readonly flat_index: number;
  readonly copy_ordinal: number;
  readonly copies_at_locus: number;
  readonly nearest_cosine: number | null;
  readonly agreeing_neighbours: number;
  readonly available_neighbours: number;
  readonly placed_summed_cosine: number | null;
  readonly is_contested: boolean;
  readonly runner_up_summed_cosine: number | null;
  /**
   * ⚠ `false` means the gene is ALONE ON ITS CONTIG and has no ±5 window at all — not that its
   * window matched nothing, which is `matched_arrangement_rank === null` with this `true`. Three
   * outcomes, and collapsing two of them reports a neighbourhood comparison for a gene with no
   * neighbours.
   */
  readonly has_a_neighbourhood: boolean;
  readonly matched_arrangement_rank: number | null;
  readonly matched_arrangement_genome_count: number | null;
}

/** A genome placed on this catalogue after the model was built — never a member of it. */
export interface ProjectedGenomeEntry {
  readonly sample_id: string;
  readonly rule: string;
  readonly neighbours_searched: number;
  readonly neighbours_reported: number;
  readonly gene_count: number;
  readonly placed_gene_count: number;
  /** ⛔ Four counts that are not the same number — see the backend serialiser. */
  readonly genes_without_a_vector: number;
  readonly genes_without_a_neighbourhood: number;
  readonly contested_gene_count: number;
  readonly distinct_locus_count: number;
  readonly multi_copy_locus_count: number;
  readonly window_matched_gene_count: number;
  /** ⚠ The distribution, not a mean: there is no novelty threshold, so the spread is the signal. */
  readonly nearest_cosine: {
    readonly median: number | null;
    readonly fifth_percentile: number | null;
    readonly minimum: number | null;
  };
  readonly nuna_git_sha: string | null;
}

export interface ProjectedGenomesResponse {
  readonly species_key: string;
  readonly genomes: readonly ProjectedGenomeEntry[];
  /** The sentence the page must repeat wherever these genomes appear. */
  readonly caveat: string;
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

/** A position on the catalogue map, in quantised units — the same integers the sprite was drawn from. */
export type MapPosition = readonly [number, number];

/**
 * The whole-catalogue scatter, as a picture rather than an array — the one part of the map that is
 * O(catalogue). Its BYTES come from `/species/{key}/map/{rep}/scatter.png`; this is everything needed
 * to draw on top of them.
 *
 * ⚠ **Served, no longer drawn.** The page stopped showing the catalogue picture on 2026-09-22 (David:
 * *"It isn't helpful. Just display closest 6 neighbours."*). The server still renders and describes
 * it, so the type still says what arrives.
 */
export interface CatalogueScatterSprite {
  readonly pixel_size: number;
  /**
   * ⛔⛔ **The transform the renderer actually used.** Anything that draws on the picture must use it
   * and never compute its own: a re-derived viewport puts a locus's dot BESIDE its own speck rather
   * than on it, and the picture still looks like a picture.
   */
  readonly viewport_centre: readonly [number, number];
  readonly viewport_span: number;
  /** What one locus looks like on the picture, so the caption can say so. */
  readonly dust_radius_pixels: number;
  readonly alpha_per_locus: number;
  /** ⭐ What is ON the picture — NOT the catalogue size, which is what the published caption quoted. */
  readonly plotted_locus_count: number;
  /** Loci with no medoid: they never reached the map and have no speck. */
  readonly unplotted_locus_count: number;
  /** ⚠ The ETag and the cache-buster — sha256 of the bytes, not the pangenome id. */
  readonly content_digest: string;
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
  /** `null` where this representation has no rendered sprite. Served, no longer drawn — see above. */
  readonly scatter_sprite: CatalogueScatterSprite | null;
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
  /** The footer's `<dl>`, one `[label, value]` pair per row, printed verbatim (`render_page._provenance`). */
  readonly provenance_rows: readonly (readonly [string, string])[];
  /** Loci per band. ⛔ Every band is present — a band with no loci is a measured `0`, never absent. */
  readonly prevalence_census: Readonly<Record<PrevalenceBand, number>>;
  /**
   * ⭐ The SAME catalogue partitioned by GENE. Divided by the genome count it is the census's
   * "per genome" line — a different partition, not a restatement: a third of the loci are singletons
   * while a typical genome carries about fifty singleton genes.
   */
  readonly prevalence_gene_census: Readonly<Record<PrevalenceBand, number>>;
  /** Read verbatim from the audit summary at ingest. Keys absent from an older summary are absent here. */
  readonly audit_headline: Readonly<Record<string, number | string | null>>;
  readonly map_projections: readonly MapProjection[];
  readonly landing_locus: string | null;
  readonly example_loci: readonly string[];
  /** The example chips as drawn: name, and the UniRef50 families the chip quotes. */
  readonly example_locus_rows: readonly ExampleLocusRow[];
}

export interface ExampleLocusRow {
  readonly label: string;
  readonly display_name: string;
  readonly uniref50_family_count: number | null;
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
  /** What the page prints under the name — the number never tells a reader whether a hit is theirs. */
  readonly best_product: string | null;
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

/**
 * One gene copy's bases — the Sequence tab's payload.
 *
 * ⭐ **~5 kB out, where the published page pulled 1.3 MB in.** It had no choice: GitHub Pages
 * applies `Range` to the *compressed* stream, so byte offsets return plausible wrong bytes with a
 * 206 and no error, and the browser had to fetch whole `.nseq` files and decode DNA itself. A server
 * slices the file Bakta wrote, so that custom format is retired rather than ported.
 */
export interface GeneSequence {
  /** ⭐ ρ > 1 puts one genome in a locus twice, so a copy is `n of m` and the page says so. */
  readonly copy_ordinal: number;
  readonly copy_count: number;
  readonly flat_index: number;
  /**
   * ⛔ The contig's own NAME, never `contig_index + 1` — the index enumerates contigs that HAVE a
   * CDS. Measured: the derived name is wrong on 7,696 of 26,878 contigs (28.6 %) and right on the
   * rest, so a page deriving it looks correct seven times in ten and names a real contig the gene is
   * not on for the other three.
   */
  readonly contig_name: string;
  readonly seqid: string;
  /** 1-based inclusive, and the end INCLUDES the stop codon. */
  readonly start_position: number;
  readonly end_position: number;
  readonly strand: "+" | "-";
  /** ⚠ Whether a strand parquet existed at all. A forced `+` must never read as an observation. */
  readonly strand_is_observed: boolean;
  readonly gff_phase: number;
  readonly is_five_prime_partial: boolean;
  readonly length_nt: number;
  readonly protein_length_aa: number | null;
  readonly gene_symbol: string | null;
  readonly product: string | null;
  /** ⚠ Genome-private (`AAOCBP_22210`) and never a gene NAME. */
  readonly locus_tag: string | null;
  readonly coding_sequence: string;
  readonly protein_sequence: string;
  /**
   * ⛔ In the GENE's reading direction, not the contig's. On a minus-strand gene the upstream flank
   * sits at HIGHER contig coordinates and is reverse-complemented with it.
   */
  readonly upstream_flank_sequence: string;
  readonly downstream_flank_sequence: string;
  readonly upstream_flank_is_truncated_by_contig_end: boolean;
  readonly downstream_flank_is_truncated_by_contig_end: boolean;
  /** Contig coordinates the flank came from, 1-based inclusive. `null` where the flank is empty. */
  readonly upstream_flank_span: readonly [number, number] | null;
  readonly downstream_flank_span: readonly [number, number] | null;
  readonly gc_percent: number;
  /** What ingest wrote from the same coordinates — sent so the two can be seen to agree. */
  readonly stored_gc_percent: number | null;
}

export interface GeneSequenceResponse {
  readonly genome: { readonly sample_id: string };
  readonly locus: { readonly label: string };
  /**
   * ⛔ An EMPTY list is the answer *"this genome has no gene at this locus"*, not a failure. A
   * request that failed is a `Failure`, and the two must never render alike.
   */
  readonly genes: readonly GeneSequence[];
}

/**
 * One genome the anchor control can offer.
 *
 * ⚠ **Two counts, because they are two facts.** `locus_count` is the loci where this genome has a
 * gene; `arrangement_locus_count` is the loci where it appears in some recorded neighbourhood — the
 * published page's `genomeCounts()`, which could only see the latter. They differ wherever a gene
 * got no window. Both are per LOCUS: a genome at ρ > 1 is counted once, or the number would exceed
 * the catalogue and mean nothing.
 */
export interface GenomeRow {
  readonly sample_id: string;
  readonly collection_genome_ordinal: number;
  readonly locus_count: number;
  readonly arrangement_locus_count: number;
}

/** `GET /species/{key}/genomes?q=` — replaces the resident `meta.genomes` + `anchorSearch`. */
export interface GenomeListResponse {
  readonly species_key: string;
  readonly query: string;
  readonly genome_count: number;
  /** How many match `q` before the limit — so a truncated list can say how much it left out. */
  readonly matched_genome_count: number;
  readonly truncated: boolean;
  readonly genomes: readonly GenomeRow[];
}

/** One row of the footer's residual lists — the evidence beside the name, to judge before clicking. */
export interface ResidualLocusRow {
  readonly label: string;
  readonly display_name: string;
  readonly prevalence_band: PrevalenceBand;
  readonly gene_count: number;
  readonly uniref50_family_count: number | null;
  /** `null` where Pfam could not judge the locus — not "no architectures". */
  readonly pfam_architecture_count: number | null;
  readonly syntenic_a5: number | null;
  /** ⚠ DISTANCES, as stored; the footer shows similarities and converts once. */
  readonly esm_within_medoid_distance: number | null;
  readonly esm_nearest_medoid_distance: number | null;
}

/**
 * `GET /species/{key}/audit/residual-loci` — ⛔ TWO lists, never merged: grouped on context alone is
 * a statement about the evidence, a Pfam conflict is evidence against the merge, and neither is a
 * verdict. A locus can be in both, and then appears in both.
 */
export interface AuditResidualsResponse {
  readonly grouped_on_context_alone: readonly ResidualLocusRow[];
  readonly pfam_conflicts: readonly ResidualLocusRow[];
}
