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
for name, label in (("ordinary", ordinary), ("over_cap", over_cap), ("no_window", no_window)):
    response = client.get(f"/api/v1/species/ecoli/loci/{label}")
    assert response.status_code == 200, (name, label, response.status_code)
    out["loci"][name] = {"label": label, "response": response.get_json()}

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
