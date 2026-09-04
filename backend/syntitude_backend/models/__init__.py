"""Every SQLAlchemy model, imported here so Alembic autogenerate sees the whole metadata.

⛔ A model not imported here is **invisible to autogenerate**, which produces a migration that
silently omits its table — and the failure surfaces much later, as a missing relation on one
endpoint. Adding a model means adding it to this file.
"""

from syntitude_backend.models.gene import (  # noqa: F401
    Gene,
    GeneFunctionalAnnotation,
    GeneLocusMembership,
    GenomeNoncodingFeature,
)
from syntitude_backend.models.genome import Genome, GenomeAssembly, GenomeContig  # noqa: F401
from syntitude_backend.models.genome_collection import (  # noqa: F401
    GenomeCollection,
    GenomeCollectionBuildReport,
    GenomeCollectionMembership,
)
from syntitude_backend.models.intergenic_gap import IntergenicGap, IntergenicGapFeature  # noqa: F401
from syntitude_backend.models.locus import Locus  # noqa: F401
from syntitude_backend.models.locus_annotation import (  # noqa: F401
    LocusAnnotationEntry,
    LocusUnirefFamilyCrosstab,
)
from syntitude_backend.models.locus_arrangement import LocusArrangement  # noqa: F401
from syntitude_backend.models.locus_embedding_geometry import (  # noqa: F401
    LocusEmbeddingGeometry,
    LocusMapProjection,
)
from syntitude_backend.models.locus_offset_occupant import LocusOffsetOccupant  # noqa: F401
from syntitude_backend.models.nuna_model import NunaModel, NunaModelStep  # noqa: F401
from syntitude_backend.models.pangenome import (  # noqa: F401
    Pangenome,
    PangenomeEvaluation,
    PangenomeInputEdge,
    PangenomeStep,
)
from syntitude_backend.models.pathogen_species import PathogenSpecies  # noqa: F401

__all__ = [
    "Gene",
    "GeneFunctionalAnnotation",
    "GeneLocusMembership",
    "Genome",
    "GenomeAssembly",
    "GenomeCollection",
    "GenomeCollectionBuildReport",
    "GenomeCollectionMembership",
    "GenomeContig",
    "GenomeNoncodingFeature",
    "IntergenicGap",
    "IntergenicGapFeature",
    "Locus",
    "LocusAnnotationEntry",
    "LocusArrangement",
    "LocusEmbeddingGeometry",
    "LocusMapProjection",
    "LocusOffsetOccupant",
    "LocusUnirefFamilyCrosstab",
    "NunaModel",
    "NunaModelStep",
    "Pangenome",
    "PangenomeEvaluation",
    "PangenomeInputEdge",
    "PangenomeStep",
    "PathogenSpecies",
]
