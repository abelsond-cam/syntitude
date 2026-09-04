"""Decode a published Syntitude catalogue — the frozen oracle every parity suite compares against.

⛔ **This is a READER, never an ingest input.** The two live pages are the correctness oracle for the
rebuild precisely because the database is built from the *source artifacts* independently. A decoder
used to populate the database would make the acceptance test circular: it would prove the payload
round-trips through itself, which was never in doubt.

⛔ **Nothing here is clever.** It is a deliberately literal transcription of
`schemas/locus_browser.schema.md` and of `app.js`'s own decode, so a disagreement between the
database and the page is attributable to one of them rather than to a third interpretation invented
here. Where the schema states a rule, the rule is quoted next to the line that implements it.

**The five meanings of `-1`**, which is the single easiest thing to get wrong in this format, and the
reason a serialiser that maps every `-1` to `None` is right twice and destroys three:

===========================  ======================================================================
where                        what it means
===========================  ======================================================================
a `strings.*` index          absent — no symbol, no product, no architecture
`arr.vec`                    **the contig ends here** — a real observation, not missing data
`map_reps.near`              a neighbour outside this catalogue: drops its **slot**, not its rank
`nodes` float columns        never `-1`; absent is JSON `null` and means *not measured*
`x`/`y` (`nowhere`)          **`-32768`**, not `-1` at all — `0,0` would be a place on the map
===========================  ======================================================================
"""

from __future__ import annotations

import base64
import json
import sys
from array import array
from dataclasses import dataclass
from functools import cached_property
from itertools import accumulate
from pathlib import Path

#: The signed offsets, in payload order. `0` is deliberately absent — it is the focal locus.
OFFSETS = (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)

#: `catalogue_map.COS6_PAIRS` on one side and `app.js::COS6_PAIRS` on the other. ⛔ Reorder either
#: alone and every published payload is mislabelled, with a picture that still looks like a picture.
COS6_PAIRS = tuple((a, b) for a in range(6) for b in range(a + 1, 6))

#: `map_reps.x`/`y` sentinel for a locus with no medoid. Outside the ±32,500 quantisation range.
NOWHERE = -32768

#: `arr.vec` slot value where the contig ends. ⚠ A VALUE, not a wildcard.
CONTIG_END = -1


def _run_starts(counts: list[int]) -> list[int]:
    """Prefix-sum a run-length array into start offsets. ⚠ *Run lengths, not offsets* is the format."""
    return [0, *accumulate(counts)]


def _b64_int16(blob: str) -> array:
    values = array("h")
    values.frombytes(base64.b64decode(blob))
    if sys.byteorder != "little":  # pragma: no cover — the payload is little-endian by contract
        values.byteswap()
    return values


def _b64_int32(blob: str) -> array:
    values = array("i")
    values.frombytes(base64.b64decode(blob))
    if sys.byteorder != "little":  # pragma: no cover
        values.byteswap()
    return values


@dataclass(frozen=True)
class AnnotationRow:
    """One (locus, vocabulary, term) row, in rank order."""

    rank: int
    term: str
    gene_count: int
    #: `lists.go` only — 0/1/2 for molecular function / biological process / cellular component.
    namespace: int | None = None
    #: `lists.u50` only — the family cross-tab's five extra columns.
    modal_product: str | None = None
    modal_architecture: str | None = None
    pfam_annotated_count: int | None = None
    modal_symbol: str | None = None
    distinct_symbol_count: int | None = None


@dataclass(frozen=True)
class Arrangement:
    """One whole ±5 neighbourhood at one locus — the JOINT view."""

    rank: int
    gene_count: int
    genome_count: int
    is_flipped: bool
    #: Ten `locus_index * 2 + same_strand` codes, or `-1` where the contig ends. **As recorded.**
    slot_codes: tuple[int, ...]
    #: Indices into `meta.genomes`, ascending. ⚠ A genome at ρ>1 appears in TWO arrangements at one
    #: locus, so the sum of these over a locus may exceed `nodes.genomes[i]` while their union
    #: equals it.
    genome_ordinals: tuple[int, ...]

    def displayed_slot(self, display_index: int) -> int:
        """The slot code the page draws at `display_index`.

        ⛔ *"On a flipped row, display slot j holds the gene recorded at slot 9 − j, so its count and
        its bar must be read from that slot."* This is `app.js::obsSlot()`. Reversing the codes
        without also complementing the strand bit — or complementing `-1` — is the bug this method
        exists to prevent being written twice.
        """
        if not self.is_flipped:
            return self.slot_codes[display_index]
        code = self.slot_codes[len(self.slot_codes) - 1 - display_index]
        return code if code == CONTIG_END else (code ^ 1)


@dataclass(frozen=True)
class OffsetOccupant:
    """One candidate neighbour at one signed offset — the MARGINAL view."""

    signed_offset: int
    rank: int
    neighbour_locus_index: int
    gene_count: int
    same_strand_count: int


@dataclass(frozen=True)
class IntergenicGap:
    """One gap, keyed on the SORTED pair of flanking loci."""

    low_locus_index: int
    high_locus_index: int
    observed_genome_count: int
    median_signed_length_nt: int
    quartile1: int | None
    quartile3: int | None
    minimum: int | None
    maximum: int | None
    #: ⚠ NULL = not measured; `0.0` = every genome agrees. The page must not conflate them.
    variance_score: float | None
    modal_length_nt: int | None
    distinct_named_feature_count: int
    features: tuple[tuple[str, str, int], ...]


class Catalogue:
    """A published catalogue, decoded lazily and index-aligned to `nodes`."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.raw = json.loads(self.path.read_text())
        self.schema_version: int = self.raw["schema"]
        self.meta: dict = self.raw["meta"]
        self.strings: dict[str, list[str]] = self.raw["strings"]
        self.nodes: dict[str, list] = self.raw["nodes"]
        self.n_loci: int = self.meta["n_loci"]

        # ⛔ Coverage before anything else. A decoder that quietly returned empty lists for a block
        # this payload does not carry would make every parity suite pass by examining nothing —
        # *not looked at* and *no difference* are indistinguishable in a diff unless something makes
        # them different. This is that something.
        if len(self.nodes["label"]) != self.n_loci:
            raise ValueError(
                f"{self.path.name}: meta.n_loci is {self.n_loci:,} but nodes.label has "
                f"{len(self.nodes['label']):,} entries — the columnar arrays are not index-aligned"
            )

    # ── strings ───────────────────────────────────────────────────────────────────────────────
    def string(self, pool: str, index: int) -> str | None:
        """Resolve an interned index. ⚠ `-1` is **absent**, and is the only negative that appears."""
        if index is None or index < 0:
            return None
        return self.strings[pool][index]

    # ── nodes ─────────────────────────────────────────────────────────────────────────────────
    def label(self, locus_index: int) -> str:
        """⛔ TEXT, always. Node labels look numeric and are not."""
        return str(self.nodes["label"][locus_index])

    @cached_property
    def index_by_label(self) -> dict[str, int]:
        return {str(label): i for i, label in enumerate(self.nodes["label"])}

    def scalar(self, column: str, locus_index: int):
        """One `nodes` column at one locus. ⚠ `None` is *not measured*, never `0.0`."""
        return self.nodes[column][locus_index]

    def band(self, locus_index: int) -> str:
        return self.meta["bands"][self.nodes["band"][locus_index]]

    # ── lists (CSR) ───────────────────────────────────────────────────────────────────────────
    @cached_property
    def _list_starts(self) -> dict[str, list[int]]:
        return {key: _run_starts(block["n"]) for key, block in self.raw["lists"].items()}

    def annotation_rows(self, key: str, locus_index: int) -> list[AnnotationRow]:
        """The `lists.<key>` rows for one locus, in rank order.

        `u50` additionally carries the cross-tab; `go` carries its namespace. ⚠ `nsym` is a COUNT,
        not a list — the page shows the modal plus `+N` and cannot name the others.
        """
        block = self.raw["lists"][key]
        starts = self._list_starts[key]
        lo, hi = starts[locus_index], starts[locus_index + 1]
        pool = "sym" if key == "sym" else key
        rows: list[AnnotationRow] = []
        for rank, position in enumerate(range(lo, hi)):
            extras: dict = {}
            if key == "u50":
                extras = dict(
                    modal_product=self.string("prod", block["prod"][position]),
                    modal_architecture=self.string("pfam", block["arch"][position]),
                    pfam_annotated_count=block["npf"][position],
                    modal_symbol=self.string("sym", block["sym"][position]),
                    distinct_symbol_count=block["nsym"][position],
                )
            elif key == "go":
                extras = dict(namespace=block["ns"][position])
            rows.append(
                AnnotationRow(
                    rank=rank,
                    term=self.strings[pool][block["idx"][position]],
                    gene_count=block["cnt"][position],
                    **extras,
                )
            )
        return rows

    # ── arr — the joint view (CSR, and `gid` rides on `gen`) ──────────────────────────────────
    @cached_property
    def _arrangement_starts(self) -> list[int]:
        return _run_starts(self.raw["arr"]["n"])

    @cached_property
    def _genome_id_starts(self) -> list[int]:
        """⭐ `gid` carries no lengths of its own — prefix-sum `gen` a SECOND time to index it."""
        return _run_starts(self.raw["arr"]["gen"])

    def arrangements(self, locus_index: int) -> list[Arrangement]:
        block = self.raw["arr"]
        starts = self._arrangement_starts
        gid_starts = self._genome_id_starts
        gid = block.get("gid")
        n_offsets = len(self.meta["offsets"])
        out: list[Arrangement] = []
        for rank, position in enumerate(range(starts[locus_index], starts[locus_index + 1])):
            slot_lo = position * n_offsets
            genome_ordinals: tuple[int, ...] = ()
            if gid is not None:
                genome_ordinals = tuple(gid[gid_starts[position] : gid_starts[position + 1]])
            out.append(
                Arrangement(
                    rank=rank,
                    gene_count=block["cnt"][position],
                    genome_count=block["gen"][position],
                    is_flipped=bool(block["flip"][position]),
                    slot_codes=tuple(block["vec"][slot_lo : slot_lo + n_offsets]),
                    genome_ordinals=genome_ordinals,
                )
            )
        return out

    def total_arrangement_count(self, locus_index: int) -> int:
        """⛔ `arr.tot` — never moved by a display cap, and never conflated with the number listed."""
        return self.raw["arr"]["tot"][locus_index]

    # ── ctx — the marginal view ───────────────────────────────────────────────────────────────
    @cached_property
    def _context_starts(self) -> list[int]:
        return _run_starts(self.raw["ctx"]["n"])

    def observed_member_counts(self, locus_index: int) -> tuple[int, ...]:
        """`ctx.obs` — member genes for which each offset EXISTS, counted BEFORE the top-N cut.

        ⛔ This is the denominator that makes "and N others" honest, and `obs < size` is what exposes
        contig-edge truncation. It is not derivable from the occupant rows.
        """
        base = locus_index * len(OFFSETS)
        return tuple(self.raw["ctx"]["obs"][base : base + len(OFFSETS)])

    def offset_occupants(self, locus_index: int) -> list[OffsetOccupant]:
        block = self.raw["ctx"]
        starts = self._context_starts
        out: list[OffsetOccupant] = []
        for slot, signed_offset in enumerate(OFFSETS):
            cell = locus_index * len(OFFSETS) + slot
            for rank, position in enumerate(range(starts[cell], starts[cell + 1])):
                out.append(
                    OffsetOccupant(
                        signed_offset=signed_offset,
                        rank=rank,
                        neighbour_locus_index=block["nid"][position],
                        gene_count=block["cnt"][position],
                        same_strand_count=block["same"][position],
                    )
                )
        return out

    # ── gaps ──────────────────────────────────────────────────────────────────────────────────
    @cached_property
    def intergenic_gaps(self) -> list[IntergenicGap]:
        block = self.raw.get("gaps")
        if not block:
            return []
        feature_starts = _run_starts(block["fn"])
        labels, types = block["labels"], block["types"]
        # ⛔ THE SPARSE TRIPLE INVERTS THE USUAL RULE, AND GETTING IT BACKWARDS IS SILENT.
        # `app.js::gapVarRaw` (:61-65) is the contract, in two clauses:
        #   `if (!HAS_VAR) return null`      — the whole BLOCK absent ⇒ not measured
        #   `i === undefined ? 0 : vd[i]/1000` — a GAP absent from `vi` ⇒ **measured zero**
        # 86.1 % of this catalogue's gaps are absent from `vi`, and every one of them means *every
        # genome agrees* — the majority case, and the one a naive "absent ⇒ None" reading destroys.
        # ⚠ `vd` is the score × 1000 (observed range 0..2000 = 0.0..2.0, clipped), so it is divided
        # here rather than compared raw against a 0..1 threshold somewhere downstream.
        # ⚠ `vmd` (the modal length) is NOT recovered for an absent gap: it was simply not carried.
        # So one absence has two different fates, and they are not interchangeable.
        has_variance = all(key in block for key in ("vi", "vd", "vmd"))
        variance = {i: value / 1000 for i, value in zip(block.get("vi", []), block.get("vd", []), strict=True)}
        modal = dict(zip(block.get("vi", []), block.get("vmd", []), strict=True))
        out: list[IntergenicGap] = []
        for i in range(len(block["a"])):
            lo, hi = feature_starts[i], feature_starts[i + 1]
            out.append(
                IntergenicGap(
                    low_locus_index=block["a"][i],
                    high_locus_index=block["b"][i],
                    observed_genome_count=block["n"][i],
                    median_signed_length_nt=block["nt"][i],
                    quartile1=block.get("q1", [None] * len(block["a"]))[i],
                    quartile3=block.get("q3", [None] * len(block["a"]))[i],
                    minimum=block.get("mn", [None] * len(block["a"]))[i],
                    maximum=block.get("mx", [None] * len(block["a"]))[i],
                    variance_score=(variance.get(i, 0.0) if has_variance else None),
                    modal_length_nt=modal.get(i),
                    distinct_named_feature_count=block["n_feat"][i],
                    features=tuple(
                        (labels[block["flab"][j]], types[block["ftyp"][j]], block["fcnt"][j])
                        for j in range(lo, hi)
                    ),
                )
            )
        return out

    # ── map_reps ──────────────────────────────────────────────────────────────────────────────
    @cached_property
    def _map_entries(self) -> dict[str, dict]:
        return {entry["rep"]: entry for entry in self.raw.get("map_reps", [])}

    def map_position(self, representation: str, locus_index: int) -> tuple[int, int] | None:
        """Quantised `(x, y)`, or `None` where the locus has no medoid.

        ⚠ The sentinel is `-32768`, **not** `-1`: `0,0` would be the middle of the map, which is a
        place, so an absent position gets a value outside the range rather than an origin.
        """
        entry = self._map_entries[representation]
        x = _b64_int16(entry["x"])[locus_index]
        y = _b64_int16(entry["y"])[locus_index]
        return None if x == NOWHERE or y == NOWHERE else (x, y)

    def map_neighbour_slots(self, representation: str, locus_index: int) -> list[tuple[int, int]]:
        """The surviving `(slot_index, neighbour_locus_index)` pairs.

        ⛔ **Slots are not ranks.** A `-1` drops that locus *and its slot*; the surviving slot
        indices are what address `cos6`. Reading by rank instead draws one locus's distances on
        another, and the picture still looks like a picture.
        """
        entry = self._map_entries[representation]
        k = entry["k"]
        near = _b64_int32(entry["near"])[locus_index * k : (locus_index + 1) * k]
        return [(slot + 1, value) for slot, value in enumerate(near) if value >= 0]

    def map_cosine_matrix(self, representation: str, locus_index: int) -> list[list[float | None]]:
        """The 6×6 cosine matrix: focal locus at slot 0, its five nearest at 1–5.

        Unit diagonal, symmetric, and `None` in any row/column whose slot was dropped — because a
        dropped slot is *this locus is not in the catalogue*, not *cosine zero*.
        """
        entry = self._map_entries[representation]
        scale = entry["cos_scale"]
        packed = _b64_int16(entry["cos6"])[locus_index * len(COS6_PAIRS) : (locus_index + 1) * len(COS6_PAIRS)]
        live = {0, *(slot for slot, _ in self.map_neighbour_slots(representation, locus_index))}
        matrix: list[list[float | None]] = [[None] * 6 for _ in range(6)]
        for slot in live:
            matrix[slot][slot] = 1.0
        for (a, b), value in zip(COS6_PAIRS, packed, strict=True):
            if a in live and b in live:
                matrix[a][b] = matrix[b][a] = value / scale
        return matrix

    def null_baseline(self, representation: str) -> dict | None:
        """The random-pair medoid baseline — the axis the geometry card reads its numbers against."""
        return self.raw.get("null", {}).get(representation)


def load_catalogue(path: str | Path) -> Catalogue:
    """Load a published catalogue from disk."""
    return Catalogue(Path(path))
