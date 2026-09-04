# `backend/` — the Syntitude API

Postgres + Flask + SQLAlchemy. **Read-only for users**: no login, no accounts, no user writes.
Everything that writes is an offline ingest step.

Design of record: **`docs/design/serving_from_a_database.md`** in the `nuna` repo. Build order and
status: **`PROJECT_STATE.md` §6 and §Layer 6** there. Nothing in this directory carries a status
block.

## Bring it up on a Mac

```bash
brew install postgresql@16 && brew services start postgresql@16
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createdb syntitude_dev
psql -d syntitude_dev -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

uv venv --python 3.13 .venv                    # from the repo root
uv pip install --python .venv/bin/python -e backend

export SYNTITUDE_DATABASE_URL="postgresql+psycopg://$USER@localhost:5432/syntitude_dev"
.venv/bin/python -m syntitude_backend.serve --debug
curl -s localhost:5000/api/v1/health | python3 -m json.tool
```

`pg_trgm` is not optional — it is what preserves the page's **exact substring** search semantics
(`ligase` finds *O-antigen ligase RfaL* mid-string) rather than approximating them with prefixes.

## Configuration

Everything comes from the environment, resolved once at start-up, and a missing value is an
exception then rather than a 404 on one endpoint three weeks later.

| variable | meaning |
|---|---|
| `SYNTITUDE_DATABASE_URL` | required |
| `SYNTITUDE_PROFILE` | `development` (default) or `production` |
| `SYNTITUDE_SQL_ECHO` | `1` to log SQL |
| `SYNTITUDE_ROOT_GFF` | where the gzipped Bakta GFFs live — the **sequence source** |
| `SYNTITUDE_ROOT_ASSEMBLIES` | assembly FASTAs, the fallback if a GFF carries no `##FASTA` |
| `SYNTITUDE_ROOT_EMBEDDINGS` | ESM / Bacformer `.npy`; offline jobs only, never a request |
| `SYNTITUDE_ROOT_ANALYSIS` | audit tables, catalogue maps, assignment TSVs |

An `artifact_pointer` row stores a root **key** plus a relative path, so moving the store is a
config change and never a database migration.

## Layout

| path | what |
|---|---|
| `application_factory.py` | `create_application(configuration) -> Flask`; registers blueprints and decides nothing |
| `configuration.py` | the only module that reads `os.environ` |
| `database.py` | engine, session, declarative base — **and the constraint naming convention** |
| `api/` | one blueprint per resource |
| `services/` | the work; no Flask imports, so it is testable without a request context |
| `serialisers/` | dicts only — no ORM object escapes a serialiser |
| `models/` | SQLAlchemy models, one module per entity group |
| `ingest/` | the **only** writer. Offline. The one place that imports `nuna` |
| `gff/` | the one place a GFF is opened or parsed |
| `queries/` | hand-written SQL for hot paths, each with its `EXPLAIN` checked in |
| `migrations/` | alembic |

## Two rules that are load-bearing

**The serving install must not need `nuna`.** It is a private repo; the med school server has no
access to it and does not need any of it. Only `ingest/` imports it, and only on a machine that
already has the science package. That is why `nuna` is not in `dependencies`.

**The constraint naming convention in `database.py` had to exist before the first migration.**
Without it Postgres invents names, Alembic autogenerate produces a different one on each machine,
and a migration that drops a constraint by name works only for whoever wrote it.

## Loading data

Writes are ours alone and offline; nothing on a request path inserts. The loader needs the cluster
artifacts mirrored locally and `nuna` importable — the serving install needs neither.

```bash
uv pip install --python .venv/bin/python -e backend           # from the repo root
uv pip install --python .venv/bin/python -e ~/developer/nuna  # ingest only; never on the server
uv pip install --python .venv/bin/python scikit-learn         # nuna.eval.metrics imports it at module scope
```

⭐ **The pangenome layer imports `nuna` and the genome layer does not**, and the split is deliberate.
The genome layer needed one 20-line GFF reader, so it vendors it and cross-checks against the
original. The pangenome layer needs `node_order`, `oriented_windows`, `arrangements`,
`neighbour_counts`, `gap_table` and the vendored Pfam/GO/COG tables — the science itself — and a
second implementation of any of those is exactly what this design exists to avoid.

```bash
export SYNTITUDE_DATABASE_URL="postgresql+psycopg://$USER@localhost:5432/syntitude_dev"

# ONE genome layer for both species: contigs, genes, functional labels. Model-INDEPENDENT — a new
# pangenome must never rewrite it. ~180 s for all 280 genomes.
.venv/bin/python -m syntitude_backend.ingest --stage genomes \
  --model-label ecoli_nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL \
  --run-id ecoli_bacformer_clever_exploded_preclusterstrict98pm3b-3b0.5-excl_k100_g100_res0.1_seed0

# then ONE pangenome layer per species: the model registry, the roster, the run and the catalogue.
# ~60 s each, re-runnable — the blast radius is exactly one pangenome.
.venv/bin/python -m syntitude_backend.ingest --stage pangenome --set-key ecoli --species-key ecoli \
  --model-label ecoli_nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL \
  --run-id ecoli_bacformer_clever_exploded_preclusterstrict98pm3b-3b0.5-excl_k100_g100_res0.1_seed0

.venv/bin/python -m syntitude_backend.ingest --stage pangenome --set-key kp --species-key kp \
  --model-label kp_nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL \
  --run-id kp_bacformer_clever_exploded_preclusterkp98pm3b-3b0.5-excl_k100_g100_res0.1_seed0
```

Then **publish** — a separate, explicit step, because the pointer is what the service reads and a
load that is not published changes nothing a reader can see. `--publish` verifies eight things about
the catalogue (locus count against the row count, the landing locus, both map representations, every
locus named …) and refuses to move the pointer if any fails.

```bash
.venv/bin/python -m syntitude_backend.ingest --stage pangenome --publish  ...  # as above
```

## The API

| endpoint | replaces |
|---|---|
| `GET /api/v1/species` | `published.tsv` |
| `GET /api/v1/species/{key}` | `meta`, the census, the footer provenance, `meta.landing`/`examples` |
| `GET /api/v1/species/{key}/loci/{label}` | ⭐ the hot path — `show(i)` minus the function tab |
| `GET …/loci/{label}/arrangements` | `focalCard`'s full scroller, paged |
| `GET …/loci/{label}/function` | `renderFunction`, on tab open |
| `GET /api/v1/species/{key}/search` | `search()` and the 3.0 MB `HAY` |

Measured on the loaded *E. coli* catalogue: the landing locus is **11.8 kB in 36 ms**, and a locus
view is **8 statements whether it resolves 2 neighbours or 49** — the property
`tests/test_api_endpoints.py` asserts, rather than a recorded budget that could be re-baselined.

⭐ **The parity suites need a loaded database.** `tests/test_catalogue_parity.py` (T1, T3a, T5, T7)
reads `SYNTITUDE_DATABASE_URL` and compares every locus against the published catalogue in
`data/{species}.json`. Without that variable, or with the run not loaded, it **skips with the
reason** rather than passing.

⛔ **Do not reconstruct a `run_id`.** The two published ones differ by `strict98` against `kp98`,
not by their species token, and a run id that differed only in a *default-emitted* token would
resolve to a different run and load a catalogue that is wrong about which model produced it. The
triples are checked in at `syntitude_backend/ingest/published_catalogues.py`, with a test that both
resolve against the store.

| variable | meaning |
|---|---|
| `SYNTITUDE_NUNA_DATA_ROOT` | the local artifact mirror (default `~/developer/nuna/data`) |
| `SYNTITUDE_FULL_COHORT=1` | run the alignment gate over all 280 genomes (~85 s) instead of 30 |

The loader reports counts and then **asks the database what it holds**, because a loader that
reports its own writes back confirms itself. A refusal names the genome and the check that caught
it, rolls that genome back, and the run continues.

## Tests

```bash
.venv/bin/python -m pytest backend/tests -q
```

They need the `syntitude_dev` database running; override with `SYNTITUDE_TEST_DATABASE_URL`.

### ⚠ The `nuna` cross-check runs from nuna's venv, not this one

`gff/` carries **pinned copies** of two rules that live in `nuna` — `open_text`'s gzip-by-magic-number
and `genome_sequence.translate_cds` — because the serving install must not depend on a private repo.
A copy is only safe while something fails when it diverges, and that something is
`tests/test_gff_reader_against_nuna.py`. It is **not** run by the command above: `nuna/__init__.py`
pulls anndata, which pulls sklearn, and mirroring that chain into a serving package's test extra to
prove one 20-line function still matches would be the wrong trade. Run it where nuna already lives:

```bash
cd ~/developer/nuna
PYTHONPATH=~/developer/syntitude/backend .venv/bin/python -m pytest \
  ~/developer/syntitude/backend/tests/test_gff_reader_against_nuna.py -q
```

It skips — saying which is missing — if `nuna` is not importable or the probe GFFs have not been
pulled to `~/developer/nuna/data/raw/gff`. **A skip here is not a pass**; if the cross-check cannot
run, the vendored copies are unverified.

## Linting — `ruff check` is enforced, `ruff format` is NOT

```bash
uvx ruff check backend/syntitude_backend backend/tests    # must pass; run before every commit
```

⚠ **Do not run `ruff format` over the tree.** Both are configured in `backend/pyproject.toml`, but only
`check` has ever been applied: **54 of 88 files would be reformatted**, so a formatting pass produces a
diff that is almost entirely unrelated to whatever you were doing and buries it. Format the lines you
touch by hand, to the configured `line-length = 120`.

⚠ **Fix lint findings by hand rather than with `--fix`.** This is the sibling repo's rule and it applies
here for the same reason: `--fix` mutates the tree during a commit, and it once deleted three re-exports
that were pinned by an identity test, turning ten tests red in a commit whose hooks all passed.
