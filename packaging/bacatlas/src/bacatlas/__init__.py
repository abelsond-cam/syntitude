"""BacAtlas — a locus-centred atlas of bacterial pangenomes.

This release **reserves the name**. It carries no pipeline and no data: the clustering method
(*Nuna*) and the browser that serves it are still being written, and this package exists so that
what is published later is published under the name the work is already called.

What BacAtlas is, so that the name means something before the code arrives: a pangenome is usually
presented as one reference genome with its neighbours hung off it. BacAtlas presents it as **loci** —
each position in the genome, the structurally homologous genes that fill it across a species however
far their sequences have diverged, and how consistently each neighbouring position is occupied.

See the project for what exists today: https://github.com/abelsond-cam/bacatlas
"""

__version__ = "0.0.1"

#: What a later release will be built on. Recorded here so the relationship is legible from the
#: package itself rather than only from the repository: BacAtlas is the atlas, Nuna is the
#: clustering method inside it, and Bacformer is the genome language model underneath both.
__components__ = ("nuna", "bacformer")


def about() -> str:
    """One line on what this package is, and honestly what it is not yet."""
    return (
        f"BacAtlas {__version__} — a placeholder reserving the name. "
        "No pipeline is shipped yet; see https://github.com/abelsond-cam/bacatlas"
    )
