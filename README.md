# Syntitude — the Nuna pangenome navigator

The published pages for [Nuna](https://github.com/abelsond-cam/nuna), a pangenome method that groups genes by
the **position they hold in the genome** rather than by the sequence identity they share.

**Live: https://abelsond-cam.github.io/syntitude/**

| page | what it is |
|---|---|
| `index.html` | a redirect to the default catalogue, `kp.html` |
| `ecoli.html` | *Escherichia coli* — 17,531 loci, 489,146 genes, 100 genomes |
| `kp.html` | *Klebsiella pneumoniae* — 15,670 loci, 532,851 genes, 100 genomes |

## Two things live here now

1. **The static site** — the root: `index.html`, `ecoli.html`, `kp.html`, `data/`, `robots.txt`. This is
   what GitHub Pages serves today, and it is **frozen**: it is the parity oracle for the rebuild and the
   rollback if the rebuild is withdrawn.
2. **The service rebuild** — `backend/` (Flask + SQLAlchemy over Postgres) and `frontend/` (Vue 3 +
   Pinia + Vite), which ARE hand-written source. Design of record: `docs/design/serving_from_a_database.md`
   in `nuna`; status: `PROJECT_STATE.md` there. Nothing in this repo carries a status block.

## The static site holds output, not source

Nothing at the root is written by hand except `index.html`, `robots.txt` and this file. The species pages are
**rendered artifacts** — each is one self-contained HTML file carrying its whole catalogue, generated from a
model's payload by `nuna.tl.locus_browser.render_page`. Do not edit them here; the edit would be silently
overwritten by the next deploy and would not exist in the source repo. Change `nuna` and re-deploy:

    # in ~/developer/nuna
    uv run python -m nuna.tl.locus_browser.publish_site --site ~/developer/syntitude

The method's source is private while unpublished, which is also why the site lives in its own repo: GitHub
Pages cannot build from a private repository on a free plan.

## Not indexed, on purpose

`robots.txt` and a `noindex` meta tag keep these pages out of search results. They are reachable by anyone
with the link — a Pages site is world-readable whatever the repo's visibility — but a research prototype's
numbers change when its model does, and an indexed snapshot outlives the model it describes. To reverse,
delete `robots.txt` **and** the `noindex` meta in `nuna`'s `render_page.py::_DOC`; a cached page cannot be
un-crawled, so both have to go.

## Running with Docker Compose

The service rebuild — `backend/` (the API) and `frontend/` (the Vue app) — runs as three containers on
one host, from `compose.yaml`:

| service | what | |
|---|---|---|
| `db` | `postgres:16` | restored from a `pg_dump -Fc` on its **first** start, or empty |
| `api` | gunicorn over the Flask app | serving dependencies only — never `nuna`, never the `ingest` extra |
| `web` | nginx | the built app, with the API proxied under the same base; the only published port |

It needs Docker Engine 25+ with the Compose v2 plugin, and nothing else: no Python, no Node, no `nuna`.

```bash
cp .env.example .env               # then set SYNTITUDE_DB_PASSWORD (openssl rand -hex 24) and the paths
mkdir -p deploy/dump               # the dump goes here, named syntitude.dump — see below
docker compose up -d --wait        # builds, restores, and returns once all three are healthy
curl -s localhost:8080/api/v1/health
```

Every setting is documented in `.env.example`. ⚠ **Its names are not the containers' names**: Compose lets
the invoking shell override `.env`, and the Mac development setup sets `SYNTITUDE_DATABASE_URL` and
`SYNTITUDE_ROOT_GFF` in the shell for the local server — so `compose.yaml` builds those two from
`SYNTITUDE_DB_*` and `SYNTITUDE_HOST_GFF_DIR` instead of reading them.

**The dump.** Taken on the machine that ran the ingest, never on the server:

```bash
pg_dump -Fc -d syntitude_dev -f deploy/dump/syntitude.dump    # *.dump is gitignored
```

**The restore drill.** A dump is restored only into an EMPTY volume — the postgres image's rule — so a new
dump, or the drill itself, is:

```bash
docker compose down -v                  # ⛔ -v deletes the database volume; that is the point
time docker compose up -d --wait        # restore, ANALYZE, and all three healthy
docker compose logs db | grep syntitude # the restore's own line, with its duration
```

⛔ **A failed restore does not heal on restart.** The volume is no longer empty, so the next start skips the
restore. The restore script leaves a marker when it fails, and the `db` healthcheck refuses to pass while
it exists, so the api never comes up on a half-restored database. The fix is always
`docker compose down -v`, then a good dump.

**No dump** starts an empty database: `/api/v1/health` says `schema_present: false` and every data
endpoint fails until the schema exists. `docker compose run --rm api alembic upgrade head` builds it —
empty, which is useful only for checking the plumbing.

**Sequences.** The Sequence tab reads the gzipped Bakta GFFs, mounted **read-only** from
`SYNTITUDE_HOST_GFF_DIR`. Without it the sequence endpoint answers `503` with a named reason and nothing
else is affected. On Linux the tree must be readable by uid 10001, the api's user.

**A subpath.** For `https://host/syntitude/`, set `SYNTITUDE_PUBLIC_BASE=/syntitude/` and rebuild
(`docker compose up -d --build`) — the base is compiled into the bundle. The API then lives at
`/syntitude/api/v1`, and the institution's reverse proxy must forward `/syntitude/` to this host **with
the prefix intact**. Nothing in the code names a base or an origin; see `frontend/README.md`.

**New code.** `git pull && docker compose up -d --build` rebuilds the api and web images and leaves the
database alone.

## Reference data

Annotation by **Bakta**; protein families from **UniProt/UniRef50** and **Pfam/InterPro**; functional
classification from the **Gene Ontology** and **NCBI COG**. Gene Ontology and UniProt data are used under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). KEGG orthology accessions are **linked, never
reproduced** — KEGG's terms permit linking freely and redistribution not at all.
