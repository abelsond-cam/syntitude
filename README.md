# Syntitude — the Nuna pangenome navigator

The published pages for [Nuna](https://github.com/abelsond-cam/nuna), a pangenome method that groups genes by
the **position they hold in the genome** rather than by the sequence identity they share.

**Live: https://abelsond-cam.github.io/syntitude/**

| page | what it is |
|---|---|
| `index.html` | a redirect to the default catalogue, `kp.html` |
| `ecoli.html` | *Escherichia coli* — 17,531 loci, 489,146 genes, 100 genomes |
| `kp.html` | *Klebsiella pneumoniae* — 15,670 loci, 532,851 genes, 100 genomes |

## This repo holds output, not source

Nothing here is written by hand except `index.html`, `robots.txt` and this file. The species pages are
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

## Reference data

Annotation by **Bakta**; protein families from **UniProt/UniRef50** and **Pfam/InterPro**; functional
classification from the **Gene Ontology** and **NCBI COG**. Gene Ontology and UniProt data are used under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). KEGG orthology accessions are **linked, never
reproduced** — KEGG's terms permit linking freely and redistribution not at all.
