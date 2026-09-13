import { describe, expect, it } from "vitest";

import {
  COLLAPSE_TIERS,
  PFAM_VERDICTS,
  collapseTierVerdict,
  pfamAccessionsIn,
  pfamEntryUrl,
  pfamVerdict,
} from "./evidenceVocabulary";

describe("the collapse tier", () => {
  it("reads the named tiers straight out of the vocabulary", () => {
    expect(collapseTierVerdict("pfam_not_alignable")).toBe(COLLAPSE_TIERS["pfam_not_alignable"]);
    expect(collapseTierVerdict("esm_homology")?.tone).toBe("win");
  });

  it("⚠ parses the PARAMETRIC mmseq tiers rather than looking them up", () => {
    expect(collapseTierVerdict("mmseq@0.98")?.label).toBe("holds together at 98% identity");
    expect(collapseTierVerdict("mmseq@0.98")?.tone).toBe("neutral");
  });

  it("⭐ changes what it SAYS below 0.5, not just how loudly", () => {
    const low = collapseTierVerdict("mmseq@0.4");
    expect(low?.tone).toBe("warn");
    expect(low?.note).toContain("far below any pangenome tool's floor (Panaroo 70%, Roary 95%)");
    expect(collapseTierVerdict("mmseq@0.5")?.tone).toBe("warn");
    expect(collapseTierVerdict("mmseq@0.51")?.tone).toBe("neutral");
    expect(collapseTierVerdict("mmseq@0.7")?.note).toContain("Ordinary sequence homology");
  });

  it("⛔ carries an UNKNOWN tier through rather than dropping it", () => {
    // The token is a real measurement; showing nothing would say the evidence was never looked at.
    const unknown = collapseTierVerdict("some_future_tier");
    expect(unknown?.label).toBe("some_future_tier");
    expect(unknown?.tone).toBe("neutral");
    expect(unknown?.note).toBe("");
  });

  it("shows no chip where there is no tier", () => {
    expect(collapseTierVerdict(null)).toBeNull();
    expect(collapseTierVerdict("")).toBeNull();
  });

  it("⚠ still carries the RETIRED `no_homology` token, because old catalogues have it", () => {
    expect(collapseTierVerdict("no_homology")).not.toBeNull();
  });
});

describe("⛔ the Pfam verdict needs COVERAGE behind it", () => {
  it("shows nothing when no gene here carries a domain", () => {
    // A verdict issued without coverage behind it is the exact failure `no_coverage` prevents.
    expect(pfamVerdict("single", 0)).toBeNull();
    expect(pfamVerdict("single", null)).toBeNull();
    expect(pfamVerdict(null, 40)).toBeNull();
  });

  it("shows the audit's own class where there is", () => {
    expect(pfamVerdict("single", 40)).toBe(PFAM_VERDICTS["single"]);
    expect(pfamVerdict("disjoint", 1)?.tone).toBe("bad");
  });

  it("⚠ calls `nested` PARTIAL ANNOTATION and never a disagreement", () => {
    const nested = pfamVerdict("nested", 40);
    expect(nested?.tone).toBe("neutral");
    expect(nested?.label).toBe("partial annotation");
    expect(nested?.note).toContain("Absent evidence, not conflicting evidence");
  });

  it("⛔ gives `no_coverage` no chip at all — it is not a verdict", () => {
    expect(PFAM_VERDICTS["no_coverage"]).toBeUndefined();
    expect(pfamVerdict("no_coverage", 40)).toBeNull();
  });

  it("⚠ only `disjoint` is the conflict", () => {
    const bad = Object.entries(PFAM_VERDICTS).filter(([, verdict]) => verdict.tone === "bad");
    expect(bad.map(([key]) => key)).toEqual(["disjoint"]);
  });
});

describe("⛔ a Pfam accession is cut at the dot before it is looked up", () => {
  it("strips the version, which is how the reference is keyed", () => {
    expect(pfamAccessionsIn("PF00126.29,PF03466")).toEqual(["PF00126", "PF03466"]);
  });

  it("handles one, none, and stray whitespace", () => {
    expect(pfamAccessionsIn("PF01381")).toEqual(["PF01381"]);
    expect(pfamAccessionsIn(" PF01381 , PF00126 ")).toEqual(["PF01381", "PF00126"]);
    expect(pfamAccessionsIn(null)).toEqual([]);
    expect(pfamAccessionsIn("")).toEqual([]);
  });
});

describe("⭐ a Pfam chip links to InterPro where there is one", () => {
  it("prefers the integrated record", () => {
    expect(pfamEntryUrl("PF00126", "IPR000847")).toBe(
      "https://www.ebi.ac.uk/interpro/entry/InterPro/IPR000847/",
    );
  });

  it("⚠ falls back to the Pfam entry where the family has no integrated entry", () => {
    // "" is an ABSENCE here, and building a URL out of it would 404 on every clanless family.
    expect(pfamEntryUrl("PF01327", "")).toBe(
      "https://www.ebi.ac.uk/interpro/entry/pfam/PF01327/",
    );
  });
});
