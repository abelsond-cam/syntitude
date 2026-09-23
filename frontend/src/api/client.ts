/**
 * One function per endpoint. **No component builds a URL**, so a route change is one edit here.
 *
 * ⭐ Every response is immutable for a build — writes are ours alone and offline — so the browser's
 * own HTTP cache does the work, and the client adds no invalidation logic because nothing can
 * invalidate. That is the single largest payoff of the read-only scope, and it is why prefetching
 * on `pointerenter` is free rather than a risk.
 */

import { requestJson } from "./request";
import type { Result } from "./result";
import type {
  ArrangementPageResponse,
  AuditResidualsResponse,
  FunctionResponse,
  GenomeListResponse,
  GeneSequenceResponse,
  LocusDetailResponse,
  ProjectedGenomesResponse,
  SearchResponse,
  SpeciesCatalogueResponse,
  SpeciesListResponse,
} from "./types";

/**
 * ⛔ A locus label goes into a PATH segment, so it is encoded here rather than interpolated. The
 * API routes it with `<path:locus_label>`, which happily accepts a `/` and would otherwise turn one
 * locus into a 404 on a route nobody wrote.
 */
function labelSegment(locusLabel: string): string {
  return encodeURIComponent(locusLabel);
}

export function fetchSpeciesList(signal?: AbortSignal): Promise<Result<SpeciesListResponse>> {
  return requestJson<SpeciesListResponse>("species", signal ? { signal } : {});
}

export function fetchSpeciesCatalogue(
  speciesKey: string,
  signal?: AbortSignal,
): Promise<Result<SpeciesCatalogueResponse>> {
  return requestJson<SpeciesCatalogueResponse>(
    `species/${encodeURIComponent(speciesKey)}`,
    signal ? { signal } : {},
  );
}

/**
 * ⭐ The hot path. One round trip, and the popover is then **offline**: all ten offset slots, the
 * drawn arrangements, the gaps and the map geometry are in this one response, so opening a popover,
 * switching arrangement, flipping walk direction and switching map representation fetch nothing.
 *
 * `anchorSampleId` names a genome; given one, the arrangement that genome carries is included even
 * if it sits past the display cap — otherwise the reader is told in words that their genome sits in
 * #37 and has no button to go back to it.
 */
export function fetchLocus(
  speciesKey: string,
  locusLabel: string,
  options: { anchorSampleId?: string; projectedSampleId?: string; signal?: AbortSignal } = {},
): Promise<Result<LocusDetailResponse>> {
  // ⛔ `anchor` and `projected` are different parameters because they are different relations: a
  // modelled genome is COUNTED in an arrangement, a projected one MATCHES it. The API refuses both
  // at once with a named 400 rather than picking one silently, so this never sends both.
  const query = options.anchorSampleId
    ? { anchor: options.anchorSampleId }
    : options.projectedSampleId
      ? { projected: options.projectedSampleId }
      : undefined;
  return requestJson<LocusDetailResponse>(
    `species/${encodeURIComponent(speciesKey)}/loci/${labelSegment(locusLabel)}`,
    {
      ...(options.signal ? { signal: options.signal } : {}),
      ...(query ? { query } : {}),
    },
  );
}

/**
 * The one place the anchor's KIND becomes a query parameter — `{}` for no anchor.
 *
 * ⚠ Everything that fetches a locus goes through this, so a new call site cannot forget that a
 * projected genome is not fetched with `anchor=`. Sending it that way returns a 404 (it is in no
 * collection), which renders as "this genome has nothing here" — a claim, and a false one.
 */
export function anchorQuery(
  sampleId: string | null,
  kind: "catalogue" | "projected",
): { anchorSampleId?: string; projectedSampleId?: string } {
  if (!sampleId) return {};
  return kind === "projected" ? { projectedSampleId: sampleId } : { anchorSampleId: sampleId };
}

/** Genomes placed on this catalogue after the model was built — never members of it. */
export function fetchProjectedGenomes(
  speciesKey: string,
  signal?: AbortSignal,
): Promise<Result<ProjectedGenomesResponse>> {
  return requestJson<ProjectedGenomesResponse>(
    `species/${encodeURIComponent(speciesKey)}/projected-genomes`,
    { ...(signal ? { signal } : {}) },
  );
}

/** Arrangements past the display cut — the full scroller, paged. */
export function fetchArrangementPage(
  speciesKey: string,
  locusLabel: string,
  offset: number,
  signal?: AbortSignal,
): Promise<Result<ArrangementPageResponse>> {
  return requestJson<ArrangementPageResponse>(
    `species/${encodeURIComponent(speciesKey)}/loci/${labelSegment(locusLabel)}/arrangements`,
    { query: { offset }, ...(signal ? { signal } : {}) },
  );
}

/** The EggNOG tab — fetched on tab open, not on every walk. */
export function fetchLocusFunction(
  speciesKey: string,
  locusLabel: string,
  signal?: AbortSignal,
): Promise<Result<FunctionResponse>> {
  return requestJson<FunctionResponse>(
    `species/${encodeURIComponent(speciesKey)}/loci/${labelSegment(locusLabel)}/function`,
    signal ? { signal } : {},
  );
}

/**
 * The Sequence tab — one genome's gene(s) at one locus, sliced from the original GFF on the server.
 *
 * ⚠ Fetched on tab open and per genome, never on a walk: it is the only endpoint here that opens a
 * file, and nobody wants a genome's bases on every one of forty steps.
 */
export function fetchGeneSequence(
  speciesKey: string,
  sampleId: string,
  locusLabel: string,
  signal?: AbortSignal,
): Promise<Result<GeneSequenceResponse>> {
  return requestJson<GeneSequenceResponse>(
    `species/${encodeURIComponent(speciesKey)}/genomes/${encodeURIComponent(sampleId)}/loci/` +
      `${labelSegment(locusLabel)}/sequence`,
    signal ? { signal } : {},
  );
}

/**
 * Substring search with the page's exact semantics — `pg_trgm` accelerating `ILIKE '%q%'`, so
 * `ligase` still finds *O-antigen ligase RfaL* mid-string. Replaces the resident 3.0 MB haystack.
 */
export function searchLoci(
  speciesKey: string,
  query: string,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<Result<SearchResponse>> {
  return requestJson<SearchResponse>(`species/${encodeURIComponent(speciesKey)}/search`, {
    query: { q: query, limit: options.limit },
    ...(options.signal ? { signal: options.signal } : {}),
  });
}

/**
 * The genomes an anchor can name, filtered server-side — the published page held all of them in
 * `meta.genomes` and filtered in the browser, which at 80,000 genomes is an array nobody should ship.
 * Case-insensitive substring on the sample id, the same semantics as `app.js::anchorSearch`.
 */
export function fetchGenomes(
  speciesKey: string,
  query: string,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<Result<GenomeListResponse>> {
  return requestJson<GenomeListResponse>(`species/${encodeURIComponent(speciesKey)}/genomes`, {
    query: { q: query, limit: options.limit },
    ...(options.signal ? { signal: options.signal } : {}),
  });
}

/** The footer's two residual lists — fetched when the reader opens one, never with the page. */
export function fetchAuditResiduals(
  speciesKey: string,
  signal?: AbortSignal,
): Promise<Result<AuditResidualsResponse>> {
  return requestJson<AuditResidualsResponse>(
    `species/${encodeURIComponent(speciesKey)}/audit/residual-loci`,
    signal ? { signal } : {},
  );
}
