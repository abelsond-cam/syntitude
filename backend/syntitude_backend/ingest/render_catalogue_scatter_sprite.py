"""The whole-catalogue scatter — rendered once, at ingest, into one PNG.

⭐ **Why this is a picture and not an array.** Every other thing the map needs is a number the API
sends: six positions, fifteen cosines, a ring radius. The dust behind them is the one part that is
O(catalogue): 889,160 loci × two int16 coordinates is 3.5 MB per representation, per page load,
to draw a texture no reader ever reads a value out of. `serving_at_scale.md` priced exactly this and
it is the endpoint's whole reason — *"889k × 4 B is not sendable; a 1200² PNG is ~150 kB"*.

⛔ **The sprite and the six dots drawn on top of it MUST share one viewport, and the sprite is the
one that knows it.** The published page could derive the transform on the fly because it held the
coordinates; a client that holds only the picture cannot, and a client that re-derives the extent
from anything else puts the focal dot next to its own speck rather than on it — a picture that still
looks like a picture. So the renderer writes down the four numbers it actually used
(`viewport_centre_x`, `viewport_centre_y`, `viewport_span`, `pixel_size`) and the API serves them
beside the bytes. Nothing downstream may compute them again.

⚠ **One deliberate divergence from `drawGlobal`, and it is about scale.** The published page issued
`beginPath()`, added every disc as a subpath, and called `fill()` **once** — so overlapping loci are
filled once, at a flat 55 % alpha, and the dust is a *silhouette*. That reads well at 17,531 loci
and becomes a solid grey square at 889,160, which is the size this endpoint exists for. This
renderer instead composites each locus as its own 55 % disc, so a pixel covered `n` times gets
`1 − 0.45ⁿ`. The two agree **exactly** wherever dust does not overlap (`n = 1` → 0.55, the published
value), and diverge only where the published picture had stopped carrying information anyway.

⚠ **It is a COVERAGE mask, not a coloured picture** — greyscale + alpha, with the grey flat at zero.
The page is theme-aware and the server is not: a sprite baked in the light theme's rule colour is
wrong on the dark ground, and a second sprite per theme is two artifacts that can disagree. The
client tints it (`filter: invert()` under the dark theme), so the colour stays the page's decision,
which is what it is.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass

#: `drawGlobal`'s own margin — the extent, then 4 % so the outermost loci are not on the frame.
VIEWPORT_MARGIN = 1.04

def dust_radius_for(pixel_size: int) -> float:
    """`drawGlobal`'s own dust radius, `max(0.8, 1.1 · px / 600)`.

    Kept as a formula rather than a number so the sprite can be re-rendered at another size without
    anyone having to re-decide what dust looks like. The floor is what stops a small sprite from
    rendering nothing at all.
    """
    return max(0.8, 1.1 * pixel_size / 600)


#: The published page's per-locus alpha. ⚠ See the module docstring: the published page applied it
#: to a single merged path, so it never accumulated there and it does here.
ALPHA_PER_LOCUS = 0.55

#: 1200² is the size `serving_at_scale.md` priced. Large enough that the design-target catalogue's
#: dust is texture rather than a blob, small enough to sit inside one cached response.
DEFAULT_PIXEL_SIZE = 1200

#: Loci are stamped in blocks so peak memory stays flat as the catalogue grows: at the design target
#: one array of (889,160 × 17) pixel indices is ~120 MB, and there is no reason to hold it at once.
#: ⚠ This is a memory bound, not a Python loop over rows — every block is still one vectorised pass.
LOCI_PER_BLOCK = 50_000


@dataclass(frozen=True)
class CatalogueScatterSprite:
    """The rendered sprite and everything needed to draw the six foreground dots onto it."""

    image_png: bytes
    pixel_size: int
    #: ⛔ The viewport the renderer ACTUALLY used, in the same quantised units as `map_x`/`map_y`.
    viewport_centre_x: float
    viewport_centre_y: float
    viewport_span: float
    dust_radius_pixels: float
    alpha_per_locus: float
    #: ⭐ The honest denominator. The published caption said "among all 17,531" — the catalogue size
    #: — but a locus with no medoid never reaches the map at all and is not on this picture.
    plotted_locus_count: int
    unplotted_locus_count: int
    content_digest: str


def project_to_pixels(
    x, y, *, centre_x: float, centre_y: float, span: float, pixel_size: int
):
    """World (quantised) coordinates → pixel coordinates, exactly as `drawGlobal` projected them.

    ⛔ **Y is flipped.** The map's `y` grows upward and a raster's grows downward, so a renderer that
    forgets it produces a picture that is a valid projection of nothing — mirrored, plausible, and
    consistently wrong for every locus at once, which is why no dot looks out of place.
    """
    import numpy

    scale = pixel_size / span
    pixel_x = (numpy.asarray(x, dtype=numpy.float64) - centre_x) * scale + pixel_size / 2
    pixel_y = pixel_size / 2 - (numpy.asarray(y, dtype=numpy.float64) - centre_y) * scale
    return pixel_x, pixel_y


def _disc_offsets(radius: float):
    """The integer pixel offsets a disc of this radius covers, as two flat arrays."""
    import numpy

    reach = int(numpy.floor(radius))
    span = numpy.arange(-reach, reach + 1)
    dx, dy = numpy.meshgrid(span, span, indexing="xy")
    inside = (dx * dx + dy * dy) <= radius * radius
    return dx[inside].ravel(), dy[inside].ravel()


def _coverage_counts(pixel_x, pixel_y, *, pixel_size: int, radius: float):
    """How many loci's discs cover each pixel. Returns the `pixel_size²` count grid.

    ⚠ **A locus that lands outside the canvas is a bug, not a rounding case** — the viewport is
    built from the extent of these very points plus 4 %. It is counted and returned rather than
    silently dropped, because "nothing fell off" and "we did not look" must not read the same.
    """
    import numpy

    offset_x, offset_y = _disc_offsets(radius)
    counts = numpy.zeros(pixel_size * pixel_size, dtype=numpy.int32)
    dropped = 0
    for start in range(0, pixel_x.size, LOCI_PER_BLOCK):
        block_x = numpy.floor(pixel_x[start : start + LOCI_PER_BLOCK]).astype(numpy.int64)
        block_y = numpy.floor(pixel_y[start : start + LOCI_PER_BLOCK]).astype(numpy.int64)
        stamp_x = block_x[:, None] + offset_x[None, :]
        stamp_y = block_y[:, None] + offset_y[None, :]
        inside = (stamp_x >= 0) & (stamp_x < pixel_size) & (stamp_y >= 0) & (stamp_y < pixel_size)
        dropped += int(inside.size - inside.sum())
        flat = (stamp_y[inside] * pixel_size + stamp_x[inside]).astype(numpy.int64)
        counts += numpy.bincount(flat, minlength=pixel_size * pixel_size).astype(numpy.int32)
    return counts.reshape(pixel_size, pixel_size), dropped


def _alpha_from_counts(counts, alpha_per_locus: float):
    """`1 − (1−α)ⁿ` — what `n` independent α-discs composite to, as a byte.

    ⭐ At `n = 1` this is exactly the published page's flat 55 %, which is what makes today's sprite
    and the published canvas the same picture wherever the dust is sparse.
    """
    import numpy

    highest = int(counts.max()) if counts.size else 0
    ramp = numpy.rint(
        255.0 * (1.0 - numpy.power(1.0 - alpha_per_locus, numpy.arange(highest + 1)))
    ).astype(numpy.uint8)
    ramp[0] = 0
    return ramp[counts]


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def encode_greyscale_alpha_png(alpha) -> bytes:
    """An 8-bit greyscale+alpha PNG with the grey flat at zero — i.e. a coverage mask.

    ⚠ **Hand-rolled on purpose, and it is ~20 lines.** The alternative is Pillow, a compiled imaging
    stack pulled in to lay out four chunks and call `zlib`; this module writes no pixels a reader
    could not check by hand, and the test decodes it with `zlib` alone rather than trusting the same
    library that wrote it.
    """
    import numpy

    height, width = alpha.shape
    # Colour type 4 = greyscale + alpha. The grey plane is constant zero, so it costs almost nothing
    # compressed, and the client decides the colour.
    pixels = numpy.zeros((height, width, 2), dtype=numpy.uint8)
    pixels[:, :, 1] = alpha
    # Filter byte 0 (None) per scanline: the data is already a near-constant plane plus a sparse
    # one, and an adaptive filter buys little on it while making the format unreadable by hand.
    scanlines = numpy.concatenate(
        [numpy.zeros((height, 1), dtype=numpy.uint8), pixels.reshape(height, width * 2)], axis=1
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 4, 0, 0, 0)
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", header),
            _png_chunk(b"IDAT", zlib.compress(scanlines.tobytes(), 9)),
            _png_chunk(b"IEND", b""),
        )
    )


def render_catalogue_scatter_sprite(
    x,
    y,
    *,
    unplotted_locus_count: int,
    pixel_size: int = DEFAULT_PIXEL_SIZE,
) -> CatalogueScatterSprite:
    """Render every locus's medoid position as one coverage sprite.

    `x`/`y` are the **quantised** map coordinates, the same integers `locus_embedding_geometry`
    stores, so the six dots the client draws on top need no unit conversion to land on their dust.
    """
    import numpy

    x = numpy.asarray(x)
    y = numpy.asarray(y)
    if x.size == 0:
        raise ValueError("a scatter sprite of no loci is a blank square, which is not a picture")

    lowest_x, highest_x = float(x.min()), float(x.max())
    lowest_y, highest_y = float(y.min()), float(y.max())
    # `drawGlobal`'s own transform, kept in its own order of operations.
    span = max(highest_x - lowest_x, highest_y - lowest_y, 1.0) * VIEWPORT_MARGIN
    centre_x = (lowest_x + highest_x) / 2
    centre_y = (lowest_y + highest_y) / 2

    radius = dust_radius_for(pixel_size)
    pixel_x, pixel_y = project_to_pixels(
        x, y, centre_x=centre_x, centre_y=centre_y, span=span, pixel_size=pixel_size
    )
    counts, dropped = _coverage_counts(pixel_x, pixel_y, pixel_size=pixel_size, radius=radius)
    if dropped:
        raise AssertionError(
            f"{dropped} dust pixels fell outside a viewport built from these very points — "
            "the projection and the extent disagree"
        )
    image = encode_greyscale_alpha_png(_alpha_from_counts(counts, ALPHA_PER_LOCUS))
    return CatalogueScatterSprite(
        image_png=image,
        pixel_size=pixel_size,
        viewport_centre_x=centre_x,
        viewport_centre_y=centre_y,
        viewport_span=span,
        dust_radius_pixels=radius,
        alpha_per_locus=ALPHA_PER_LOCUS,
        plotted_locus_count=int(x.size),
        unplotted_locus_count=int(unplotted_locus_count),
        content_digest=hashlib.sha256(image).hexdigest(),
    )
