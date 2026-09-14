"""Regenerate frontend/tests/fixtures/api_locus_responses.json from the live API.

Three loci chosen for what they EXERCISE: one ordinary, one with members past the arrangement cap,
one whose members have no recorded neighbourhood. Run from `backend/` with SYNTITUDE_DATABASE_URL
set and both catalogues loaded.
"""
import json, pathlib
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from syntitude_backend.application_factory import create_application
from syntitude_backend.configuration import Configuration
from syntitude_backend.models.locus import Locus

app = create_application(Configuration.from_environment())
engine = create_engine(app.config["SYNTITUDE"].database_url, future=True)
with Session(engine) as session:
    ordinary = session.execute(
        select(Locus.node_label).where(
            Locus.pangenome_id == 1, Locus.total_arrangement_count.between(2, 5)
        ).order_by(Locus.member_gene_count.desc()).limit(1)
    ).scalar_one()
    over_cap = session.execute(
        select(Locus.node_label).where(Locus.pangenome_id == 1, Locus.total_arrangement_count > 12)
        .order_by(Locus.total_arrangement_count.desc()).limit(1)
    ).scalar_one()
    no_window = session.execute(
        select(Locus.node_label).where(
            Locus.pangenome_id == 1,
            Locus.member_gene_count > Locus.arrangement_member_gene_count,
        ).order_by((Locus.member_gene_count - Locus.arrangement_member_gene_count).desc()).limit(1)
    ).scalar_one()

client = app.test_client()
out = {"recorded_from": "the API test client", "loci": {}}

# ⭐ The species response too, for the catalogue map: the sprite's viewport comes from THIS endpoint
# and the loci's positions from the other, so the pair is the only thing that can show them
# disagreeing — and a disagreement is a picture that still looks like a picture.
species = client.get("/api/v1/species/ecoli")
assert species.status_code == 200, species.status_code
out["species"] = species.get_json()

# ⭐ The Sequence tab, for a MINUS-strand gene — the case where the flank orientation can be wrong
# and still look entirely plausible. Plus a genome that has no gene at that locus, because "no gene
# here" is an ANSWER and must be a recorded shape rather than an assumption.
from syntitude_backend.models.gene import Gene, GeneLocusMembership  # noqa: E402
from syntitude_backend.models.genome import Genome  # noqa: E402

with Session(engine) as session:
    minus = session.execute(
        select(Genome.sample_id, Locus.node_label)
        .select_from(Gene)
        .join(
            GeneLocusMembership,
            (GeneLocusMembership.genome_id == Gene.genome_id)
            & (GeneLocusMembership.flat_index == Gene.flat_index),
        )
        .join(Genome, Genome.genome_id == Gene.genome_id)
        .join(Locus, Locus.locus_id == GeneLocusMembership.locus_id)
        .where(
            GeneLocusMembership.pangenome_id == 1,
            Gene.strand == "-",
            Gene.start_position > 500,
            Gene.length_nt > 900,
        )
        .order_by(Gene.genome_id, Gene.flat_index)
        .limit(1)
    ).one()
    absent_genome = session.execute(
        select(Genome.sample_id).where(
            Genome.genome_id.not_in(
                select(GeneLocusMembership.genome_id)
                .join(Locus, Locus.locus_id == GeneLocusMembership.locus_id)
                .where(Locus.node_label == minus.node_label, Locus.pangenome_id == 1)
            )
        ).limit(1)
    ).scalar_one()

out["sequences"] = {}
for name, sample in (("minus_strand", minus.sample_id), ("no_gene_here", absent_genome)):
    reply = client.get(
        f"/api/v1/species/ecoli/genomes/{sample}/loci/{minus.node_label}/sequence"
    )
    assert reply.status_code == 200, (name, reply.status_code)
    out["sequences"][name] = {
        "sample_id": sample,
        "locus_label": minus.node_label,
        "response": reply.get_json(),
    }
    print(f"  sequence   {name:<14s} {sample} @ {minus.node_label} -> "
          f"{len(reply.get_json()['genes'])} gene(s)")

# ⭐ And the sprite BYTES, so the front-end suite can close the loop the backend closes on its own
# side: take the coordinate the real component renders, and read the pixel under it in the real
# picture. Without this the two projections are verified independently and never against each other.
FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures"
for representation in ("bacformer", "esm"):
    sprite = client.get(f"/api/v1/species/ecoli/map/{representation}/scatter.png")
    assert sprite.status_code == 200, (representation, sprite.status_code)
    target = FIXTURES / f"catalogue_scatter_ecoli_{representation}.png"
    target.write_bytes(sprite.data)
    print(f"  sprite     {representation:<10s} {len(sprite.data):,} B -> {target.name}")
# ⭐ A fourth case for the Function tab: a locus carrying EC *and* KEGG *and* all three GO
# namespaces, because the thin EC/KEGG card and the three-namespace split are exactly the parts a
# typical locus does not exercise — 22% of loci mention no Pfam at all and most carry no EC.
with Session(engine) as session:
    function_rich = session.execute(
        select(Locus.node_label).where(
            Locus.pangenome_id == 1,
            Locus.ec_annotated_member_count > 0,
            Locus.kegg_annotated_member_count > 0,
            Locus.go_annotated_member_count_molecular_function > 0,
            Locus.go_annotated_member_count_biological_process > 0,
            Locus.go_annotated_member_count_cellular_component > 0,
        ).order_by(Locus.member_gene_count.desc()).limit(1)
    ).scalar_one()

for name, label in (("ordinary", ordinary), ("over_cap", over_cap), ("no_window", no_window),
                    ("function_rich", function_rich)):
    response = client.get(f"/api/v1/species/ecoli/loci/{label}")
    assert response.status_code == 200, (name, label, response.status_code)
    # ⛔ The function block too, and for EVERY case — it is a second endpoint, so nothing but a
    # recorded pair can show the two disagreeing about the same locus.
    function = client.get(f"/api/v1/species/ecoli/loci/{label}/function")
    assert function.status_code == 200, (name, label, function.status_code)
    out["loci"][name] = {
        "label": label,
        "response": response.get_json(),
        "function": function.get_json(),
    }

path = pathlib.Path(__file__).resolve()
target = pathlib.Path("/Users/davidabelson/developer/syntitude/frontend/tests/fixtures/api_locus_responses.json")
target.write_text(json.dumps(out, indent=1) + "\n")
print("wrote", target)
for name, entry in out["loci"].items():
    arr = entry["response"]["arrangements"]
    blank = sum(
        1 for a in arr["listed"] for s in a["slots"]
        if s["absence_reason"] == "outside_catalogue"
    )
    print(f"  {name:10s} locus {entry['label']:>6s} listed={len(arr['listed'])} total={arr['total']} "
          f"past_cap={arr['members_in_arrangements_not_listed']} no_window={arr['members_without_a_neighbourhood']} "
          f"unresolved_slots={blank}")
