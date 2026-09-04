"""The species registry — two rows today, and the vocabulary that stops a load silently halving.

⛔ **THREE VOCABULARIES NAME THE SAME ORGANISM, AND NO TWO OF THEM AGREE.**

    the browser key    `ecoli` · `kp`          `published.tsv`, the URL, `species_key`
    the parquets       `ecoli` · `kpneumoniae` `{BS}_meta.parquet`'s `species` column
    the scientific     `Escherichia coli` · `Klebsiella pneumoniae`

Joining the first two as if they were one string is not a hypothetical: it matches every *E. coli*
genome and **no Klebsiella genome at all**, so a 280-genome load silently becomes a 122-genome load
that looks entirely successful. The map below is the only permitted translation, and it is
exhaustive — an unrecognised value raises rather than being dropped.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from syntitude_backend.models.pathogen_species import PathogenSpecies

#: The parquets' `species` value → the browser's `species_key`. ⛔ Exhaustive by design.
SPECIES_KEY_BY_PARQUET_VALUE = {
    "ecoli": "ecoli",
    "kpneumoniae": "kp",
}

#: `species_key` → (scientific name, NCBI taxonomy id). The two the browser publishes today.
PUBLISHED_SPECIES = {
    "ecoli": ("Escherichia coli", 562),
    "kp": ("Klebsiella pneumoniae", 573),
}


def species_key_for_parquet_value(value: str) -> str:
    """Translate `{BS}_meta.parquet`'s `species` into the browser's key, or raise saying so."""
    try:
        return SPECIES_KEY_BY_PARQUET_VALUE[value]
    except KeyError:
        raise KeyError(
            f"the parquets name a species {value!r} that has no browser key. Add it to "
            f"SPECIES_KEY_BY_PARQUET_VALUE — known: {sorted(SPECIES_KEY_BY_PARQUET_VALUE)}. It is "
            "raised rather than skipped because a dropped species looks exactly like a successful "
            "load of a smaller cohort."
        ) from None


def ingest_pathogen_species(session: Session, species_keys: list[str] | None = None) -> dict[str, int]:
    """Ensure a row per species; return `{species_key: pathogen_species_id}`.

    Idempotent by `species_key`, and it never updates an existing row's `published_pangenome_id` —
    that pointer is flipped by `publish_pangenome`, in its own transaction, and an ingest that
    touched it here could unpublish a live catalogue as a side effect of loading a new one.
    """
    wanted = species_keys or list(PUBLISHED_SPECIES)
    existing = {
        row.species_key: row.pathogen_species_id
        for row in session.execute(
            select(PathogenSpecies).where(PathogenSpecies.species_key.in_(wanted))
        ).scalars()
    }
    for species_key in wanted:
        if species_key in existing:
            continue
        scientific_name, taxonomy_id = PUBLISHED_SPECIES[species_key]
        row = PathogenSpecies(
            species_key=species_key, scientific_name=scientific_name, ncbi_taxonomy_id=taxonomy_id
        )
        session.add(row)
        session.flush()
        existing[species_key] = row.pathogen_species_id
    return existing
