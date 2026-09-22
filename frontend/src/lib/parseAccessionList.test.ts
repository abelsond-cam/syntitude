import { describe, expect, it } from "vitest";

import { MAXIMUM_LINES, parseAccessionList } from "./parseAccessionList";

describe("the accession list a reader brings", () => {
  it("takes BioSamples, in the order they first appear", () => {
    const list = parseAccessionList("SAMN05374479\nSAMEA10468708\nSAMD00000344\n");
    expect(list.accessions).toEqual(["SAMN05374479", "SAMEA10468708", "SAMD00000344"]);
    expect(list.lines.map((line) => line.kind)).toEqual(["biosample", "biosample", "biosample"]);
  });

  it("⛔ takes BioSamples and NOTHING else — no assembly accessions, no secondary accessions", () => {
    // David, 2026-09-22: BioSample only. A GCA names the submitter's own assembly, which is a
    // different object from the one BakRep holds, so it is refused rather than quietly converted.
    const list = parseAccessionList("GCA_012642945.1\nGCF_000005845.2\nSRS1571665\nhello\n");
    expect(list.accessions).toEqual([]);
    expect(list.lines.map((line) => line.kind)).toEqual(Array(4).fill("not-an-accession"));
  });

  it("drops blank lines and # comments rather than reporting them back", () => {
    const list = parseAccessionList("# my genomes\n\nSAMN05374479\n\n   \n# done\n");
    expect(list.lines).toHaveLength(1);
    expect(list.lines[0]).toMatchObject({ lineNumber: 3, text: "SAMN05374479", kind: "biosample" });
  });

  it("keeps the reader's OWN line numbers, so a file can be corrected line by line", () => {
    const list = parseAccessionList("# header\nSAMN05374479\nnonsense\n");
    expect(list.lines.map((line) => line.lineNumber)).toEqual([2, 3]);
  });

  it("names a repeat as a repeat, and lists the accession once", () => {
    const list = parseAccessionList("SAMN05374479\nsamn05374479\n");
    expect(list.accessions).toEqual(["SAMN05374479"]);
    expect(list.lines.map((line) => line.kind)).toEqual(["biosample", "repeat"]);
  });

  it("takes the first column of a CSV or TSV export, and matches case-insensitively", () => {
    const list = parseAccessionList("samn05374479,Escherichia coli,2016\nSAMEA10468708\tKp\n");
    expect(list.accessions).toEqual(["SAMN05374479", "SAMEA10468708"]);
  });

  it("⚠ reports each line back AS THE READER WROTE IT, while matching on the upper-cased form", () => {
    // A line echoed in a case nobody typed reads as a bug in the page, not as a note about the file.
    const list = parseAccessionList("samn05374479\nhello\n");
    expect(list.lines.map((line) => line.text)).toEqual(["samn05374479", "hello"]);
    expect(list.lines[0]!.accession).toBe("SAMN05374479");
    expect(list.lines[1]!.accession).toBe("");
  });

  it("⚠ says when it stopped reading, rather than silently taking a prefix", () => {
    const many = Array.from({ length: MAXIMUM_LINES + 5 }, (_line, index) => `SAMN${index}`).join("\n");
    const list = parseAccessionList(many);
    expect(list.truncated).toBe(true);
    expect(list.lines).toHaveLength(MAXIMUM_LINES);

    const huge = parseAccessionList("SAMN05374479\n".repeat(20_000));
    expect(huge.tooLarge).toBe(true);
  });

  it("is empty for an empty file, and says nothing is wrong with it", () => {
    const list = parseAccessionList("");
    expect(list.lines).toEqual([]);
    expect(list.accessions).toEqual([]);
    expect(list.truncated).toBe(false);
    expect(list.tooLarge).toBe(false);
  });
});
