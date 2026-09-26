"""Open a GFF whether or not it is gzipped — by magic number, never by suffix.

Lifted deliberately from ``nuna.tl.probe.extract_strand.open_text`` rather than imported: the
serving install must not depend on ``nuna`` (a private repo the med school server has no access
to). ``tests/test_gff_matches_nuna.py`` asserts the two agree, so this is a pinned copy rather
than a second implementation left to drift.

⚠ The suffix lies on this cohort. A staging job died on ``BadGzipFile: Not a gzipped file
(b'##')`` — ``##`` being the GFF header itself.
"""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import IO

GZIP_MAGIC = b"\x1f\x8b"


def open_gff_text(path: Path) -> IO[str]:
    """Open ``path`` as text, transparently decompressing if it is really gzipped."""
    with open(path, "rb") as probe:
        is_gzipped = probe.read(2) == GZIP_MAGIC
    return gzip.open(path, "rt") if is_gzipped else open(path)
