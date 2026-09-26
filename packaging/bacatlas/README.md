# BacAtlas

**A locus-centred atlas of bacterial pangenomes.**

> ⚠ **This release reserves the name.** It ships no pipeline and no data. The work is real and in
> progress; this package exists so that what is published later is published under the name the
> project is already called. Watch
> [github.com/abelsond-cam/bacatlas](https://github.com/abelsond-cam/bacatlas).

## What it is

A bacterial pangenome is usually presented around one reference genome, with everything else hung
off it. That works until the interesting thing is a gene the reference does not have.

BacAtlas presents the pangenome as **loci** instead. A locus is a position in the genome, and what
fills it: the structurally homologous genes found there across a species — however far their
sequences have diverged — together with how consistently each neighbouring position is occupied. You
search for a gene, and you get the neighbourhood it lives in.

Two genes that occupy the same position and are homologous in structure are **syntelogs**. Homology
here means similar *structure*, inferred from protein-language-model embeddings, not sequence
identity: syntelogs routinely differ far more in sequence than any identity threshold would group.
That is the whole point — an identity threshold cannot see a conserved role filled by a divergent
gene, and those are the genes that carry resistance and virulence.

## How it is built

| piece | what it does |
|---|---|
| **Bacformer** | a genome language model over a genome's proteins, giving each gene a context-aware embedding |
| **Nuna** | the clustering method — groups genes into loci by homology *and* genomic context, at a scale graph-based pangenome tools do not reach |
| **BacAtlas** | the atlas itself: the loci, their evidence, and the browser that serves them |

BacAtlas is the atlas; **Nuna** is the clustering method inside it.

## Status

Early. The method clears its correctness gate on *Escherichia coli* and *Klebsiella pneumoniae*, and
a browser over both is running. Reproducibility against Panaroo, and the scale-up beyond the probe
cohort, are in progress. Nothing here is peer-reviewed yet — treat it as a working draft.

## Licence

BSD 3-Clause. © 2026 David Abelson.
