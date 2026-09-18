/**
 * One function per endpoint. **No component builds a URL**, so a route change is one edit here.
 *
 * ⭐ Every response is immutable for a build — writes are ours alone and offline — so the browser's
 * own HTTP cache does the work, and the client adds no invalidation logic because nothing can
 * invalidate. That is the single largest payoff of the read-only scope, and it is why prefetching
 * on `pointerenter` is free rather than a risk.
 */

import { API_BASE_URL, requestJson } from "./request";
import type { Result } from "./result";
import type {
  ArrangementPageResponse,
  AuditResidualsResponse,
  FunctionResponse,
  GenomeListResponse,
  GeneSequenceResponse,
  LocusDetailResponse,
  Representation,
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
  options: { anchorSampleId?: string; signal?: AbortSignal } = {},
): Promise<Result<LocusDetailResponse>> {
  return requestJson<LocusDetailResponse>(
    `species/${encodeURIComponent(speciesKey)}/loci/${labelSegment(locusLabel)}`,
    {
      ...(options.signal ? { signal: options.signal } : {}),
      ...(options.anchorSampleId ? { query: { anchor: options.anchorSampleId } } : {}),
    },
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
 * ⭐ The whole-catalogue scatter sprite — the only endpoint here that is not JSON, so it is a URL
 * rather than a fetch: the browser loads it as an image and gets decoding, caching and progressive
 * paint for free.
 *
 * ⚠ **The digest goes in the query string on purpose.** Its ETag is the content hash rather than the
 * pangenome id, because an image is cached hard and for a long time by caches we do not control; a
 * URL that carries the digest can never describe different bytes, so the cache entry is permanent
 * and a re-render is picked up immediately.
 */
export function catalogueScatterSpriteUrl(
  speciesKey: string,
  representation: Representation,
  contentDigest: string,
): string {
  const base = API_BASE_URL.replace(/\/$/, "");
  return (
    `${base}/species/${encodeURIComponent(speciesKey)}/map/` +
    `${encodeURIComponent(representation)}/scatter.png?v=${encodeURIComponent(contentDigest)}`
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
