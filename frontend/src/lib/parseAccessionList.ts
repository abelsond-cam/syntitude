/**
 * The text file a reader brings: **one BioSample accession per line**.
 *
 * ⭐ **BioSample only (David, 2026-09-22)**, and nothing else — no GCA/GCF, no conversion, no
 * secondary accessions. It is the only key that works: BakRep is looked up by BioSample, and the
 * AllTheBacteria assemblies these genomes come from have no assembly accession at all
 * (`assembly_accession` is NULL on all 280 genomes we hold).
 *
 * ⚠ This function decides only what a line IS, never whether we have that genome — that needs the
 * catalogue, and a pure function that reached for it could not be tested on its own. The dialog
 * classifies the accessions it returns.
 *
 * ⚠ Nothing is uploaded: the file is read in the browser with `File.text()`.
 */

/** ⛔ Primary BioSample accessions only. `SRS…`/`ERS…` are secondary and do not resolve in BakRep. */
const BIOSAMPLE = /^SAM(N|EA|D)\d+$/;

/** Long enough for any list a reader pastes, short enough that a wrong file is refused, not chewed. */
export const MAXIMUM_BYTES = 64 * 1024;
export const MAXIMUM_LINES = 200;

export type AccessionLineKind = "biosample" | "repeat" | "not-an-accession";

export interface AccessionLine {
  /** 1-based, as the reader counts them, INCLUDING the comments and blanks that are not listed. */
  readonly lineNumber: number;
  /** ⚠ As the reader wrote it: a line reported back in a case they did not type reads as a bug. */
  readonly text: string;
  /** Upper-cased, for matching. Empty where the line is not an accession at all. */
  readonly accession: string;
  readonly kind: AccessionLineKind;
}

export interface AccessionList {
  readonly lines: readonly AccessionLine[];
  /** Each BioSample once, in the order it first appeared. */
  readonly accessions: readonly string[];
  /** More lines than `MAXIMUM_LINES`: the rest were not read, and the dialog says so. */
  readonly truncated: boolean;
  /** Bigger than `MAXIMUM_BYTES`: read up to the cap, and the dialog says so. */
  readonly tooLarge: boolean;
}

/**
 * Split a file into lines and say what each one is.
 *
 * Blank lines and `#` comments are dropped rather than listed — a reader who commented a line out
 * does not want it reported back. A line's first column is taken (so a CSV or TSV export works) and
 * upper-cased, because accessions are case-insensitive in every source that issues them.
 */
export function parseAccessionList(content: string): AccessionList {
  const tooLarge = content.length > MAXIMUM_BYTES;
  const raw = (tooLarge ? content.slice(0, MAXIMUM_BYTES) : content).split(/\r?\n/);
  const truncated = raw.length > MAXIMUM_LINES;

  const lines: AccessionLine[] = [];
  const accessions: string[] = [];
  const seen = new Set<string>();

  for (const [index, line] of raw.slice(0, MAXIMUM_LINES).entries()) {
    const body = line.split("#")[0] ?? "";
    const first = body.trim().split(/[\s,;\t]+/)[0] ?? "";
    if (first === "") continue;
    const accession = first.toUpperCase();
    const lineNumber = index + 1;
    if (!BIOSAMPLE.test(accession)) {
      lines.push({ lineNumber, text: first, accession: "", kind: "not-an-accession" });
      continue;
    }
    if (seen.has(accession)) {
      lines.push({ lineNumber, text: first, accession, kind: "repeat" });
      continue;
    }
    seen.add(accession);
    accessions.push(accession);
    lines.push({ lineNumber, text: first, accession, kind: "biosample" });
  }

  return { lines, accessions, truncated, tooLarge };
}
