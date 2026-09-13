"""The whole-catalogue sprite: the picture, and the four numbers that make it addressable.

⛔ **The defect this file exists to catch is a picture that is right and a transform that is not.**
Every failure mode here renders perfectly: a mirrored Y, a viewport re-derived one way on the server
and another on the client, a dot drawn at rank order rather than slot order. So the tests below do
not look at the picture — they take the numbers the API serves, project a locus with them exactly as
the client will, and demand that the pixel underneath is actually lit.

⚠ **The PNG is decoded with `zlib` and `struct` alone**, never with the library that wrote it. A
decoder that shares an encoder's assumptions agrees with it about everything, including its bugs.
"""

from __future__ import annotations

import hashlib
import struct
import zlib

import numpy
import pytest

from syntitude_backend.ingest.render_catalogue_scatter_sprite import (
    ALPHA_PER_LOCUS,
    VIEWPORT_MARGIN,
    dust_radius_for,
    project_to_pixels,
    render_catalogue_scatter_sprite,
)


def decode_greyscale_alpha_png(data: bytes):
    """A PNG reader in twenty lines — enough for colour type 4, filter 0, and nothing else."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    position = 8
    compressed = b""
    header = None
    seen = []
    while position < len(data):
        (length,) = struct.unpack(">I", data[position : position + 4])
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        (checksum,) = struct.unpack(">I", data[position + 8 + length : position + 12 + length])
        assert checksum == zlib.crc32(kind + payload) & 0xFFFFFFFF, f"bad CRC on {kind!r}"
        seen.append(kind)
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed += payload
        position += 12 + length
    assert seen[0] == b"IHDR" and seen[-1] == b"IEND", seen
    width, height, depth, colour_type, compression, filter_method, interlace = header
    assert (depth, colour_type, compression, filter_method, interlace) == (8, 4, 0, 0, 0)
    raw = numpy.frombuffer(zlib.decompress(compressed), dtype=numpy.uint8)
    scanlines = raw.reshape(height, width * 2 + 1)
    assert not scanlines[:, 0].any(), "a scanline used a filter this decoder does not implement"
    pixels = scanlines[:, 1:].reshape(height, width, 2)
    return pixels[:, :, 0], pixels[:, :, 1]


def a_small_catalogue(count: int = 400, seed: int = 7):
    """Positions in the quantised int16 range the real map uses."""
    generator = numpy.random.default_rng(seed)
    x = generator.integers(-30_000, 30_000, size=count).astype(numpy.int16)
    y = generator.integers(-30_000, 30_000, size=count).astype(numpy.int16)
    return x, y


# ── the transform, which is the whole contract ─────────────────────────────────────────────────
def test_a_locus_projected_with_the_SERVED_viewport_lands_on_its_own_dust():
    """⛔⛔ **The one that matters.** The sprite is bytes; the six dots are SVG drawn over it.

    They agree only if both use the same transform, and the client has no way to derive it — so the
    renderer serves the numbers it used. This test is the client: it takes only what the API would
    send and checks the pixel underneath every locus is lit.
    """
    x, y = a_small_catalogue()
    sprite = render_catalogue_scatter_sprite(x, y, unplotted_locus_count=0, pixel_size=240)
    _, alpha = decode_greyscale_alpha_png(sprite.image_png)

    scale = sprite.pixel_size / sprite.viewport_span
    pixel_x = (x - sprite.viewport_centre_x) * scale + sprite.pixel_size / 2
    pixel_y = sprite.pixel_size / 2 - (y - sprite.viewport_centre_y) * scale

    lit = alpha[numpy.floor(pixel_y).astype(int), numpy.floor(pixel_x).astype(int)]
    assert lit.min() > 0, (
        f"{int((lit == 0).sum())} of {x.size} loci would be drawn over empty ground — the sprite "
        "and the viewport it published are projections of different numbers"
    )


def test_the_Y_axis_is_FLIPPED_and_a_test_that_only_checked_x_would_not_notice():
    """⚠ The map's y grows upward; a raster's grows downward.

    A renderer that forgets it produces a valid projection of nothing: mirrored, plausible, and
    wrong for every locus at once — so no dot ever looks out of place. Pinned on its own because the
    round trip above would pass a consistently mirrored pair.
    """
    pixel_x, pixel_y = project_to_pixels(
        [0, 0], [-100, 100], centre_x=0, centre_y=0, span=1000, pixel_size=500
    )
    assert pixel_x[0] == pixel_x[1], "x should not move when only y does"
    assert pixel_y[0] > pixel_y[1], "the HIGHER map y must draw at the SMALLER pixel row"


def test_the_viewport_is_the_extent_plus_the_published_margin():
    """`drawGlobal`'s own transform, kept where it can be compared with the page it came from."""
    x = numpy.array([-100, 300], dtype=numpy.int16)
    y = numpy.array([0, 100], dtype=numpy.int16)
    sprite = render_catalogue_scatter_sprite(x, y, unplotted_locus_count=0, pixel_size=120)
    assert sprite.viewport_centre_x == 100.0
    assert sprite.viewport_centre_y == 50.0
    # the WIDER of the two spans, so the picture is square and nothing is stretched
    assert sprite.viewport_span == pytest.approx(400 * VIEWPORT_MARGIN)


# ── what the pixels mean ───────────────────────────────────────────────────────────────────────
def test_one_locus_alone_is_the_PUBLISHED_alpha_exactly():
    """⭐ The continuity property: where dust does not overlap this sprite IS the published canvas.

    `drawGlobal` filled every disc as one merged path, so its dust is a flat 55 % silhouette. This
    renderer composites each locus separately — which diverges only where discs overlap, and must
    agree exactly where they do not, or the two pictures are simply different pictures.
    """
    x = numpy.array([-1000, 1000], dtype=numpy.int16)
    y = numpy.array([-1000, 1000], dtype=numpy.int16)
    sprite = render_catalogue_scatter_sprite(x, y, unplotted_locus_count=0, pixel_size=600)
    _, alpha = decode_greyscale_alpha_png(sprite.image_png)
    assert set(numpy.unique(alpha).tolist()) == {0, round(255 * ALPHA_PER_LOCUS)}


def test_overlapping_dust_DARKENS_which_is_the_deliberate_divergence():
    """⚠ The published page's flat silhouette becomes a solid square at 889,160 loci.

    So `n` overlapping loci composite to `1 − 0.45ⁿ` here. Stated as a test rather than a comment,
    because it is the one place this sprite is not a reproduction.
    """
    coincident = numpy.zeros(4, dtype=numpy.int16)
    spread = numpy.array([0, 0, 0, 20_000], dtype=numpy.int16)
    sprite = render_catalogue_scatter_sprite(
        coincident, spread, unplotted_locus_count=0, pixel_size=200
    )
    _, alpha = decode_greyscale_alpha_png(sprite.image_png)
    three_deep = round(255 * (1 - (1 - ALPHA_PER_LOCUS) ** 3))
    assert alpha.max() == three_deep
    assert three_deep > round(255 * ALPHA_PER_LOCUS)


def test_the_grey_plane_is_FLAT_because_the_colour_is_the_page_s_decision():
    """⛔ A sprite baked in the light theme's rule colour is wrong on the dark ground.

    The server does not know the viewer's theme and cannot; two sprites is two artifacts that can
    disagree. So this carries coverage only, which is also all it measures.
    """
    x, y = a_small_catalogue(50)
    sprite = render_catalogue_scatter_sprite(x, y, unplotted_locus_count=0, pixel_size=120)
    grey, alpha = decode_greyscale_alpha_png(sprite.image_png)
    assert not grey.any()
    assert alpha.any()


def test_the_dust_radius_is_the_published_formula_at_any_sprite_size():
    assert dust_radius_for(600) == pytest.approx(1.1)
    assert dust_radius_for(1200) == pytest.approx(2.2)
    # ⚠ The floor, which is what keeps a small sprite from rendering nothing at all.
    assert dust_radius_for(100) == pytest.approx(0.8)


# ── the counts, and the digest ─────────────────────────────────────────────────────────────────
def test_it_reports_BOTH_counts_because_the_catalogue_size_is_not_what_it_drew():
    """⭐ The published caption said "among all 17,531" — the catalogue size.

    A locus with no medoid never reaches the map CSV, has no geometry row and no speck. The two
    numbers travel together so a page can never quote the wrong one as the denominator.
    """
    x, y = a_small_catalogue(120)
    sprite = render_catalogue_scatter_sprite(x, y, unplotted_locus_count=31, pixel_size=120)
    assert sprite.plotted_locus_count == 120
    assert sprite.unplotted_locus_count == 31


def test_the_digest_is_the_sha256_of_the_bytes_served():
    x, y = a_small_catalogue(60)
    sprite = render_catalogue_scatter_sprite(x, y, unplotted_locus_count=0, pixel_size=120)
    assert sprite.content_digest == hashlib.sha256(sprite.image_png).hexdigest()


def test_an_empty_catalogue_RAISES_rather_than_returning_a_blank_square():
    """⛔ A blank picture reads as "no locus is anywhere", which is a claim and a false one."""
    with pytest.raises(ValueError, match="not a picture"):
        render_catalogue_scatter_sprite(
            numpy.array([], dtype=numpy.int16),
            numpy.array([], dtype=numpy.int16),
            unplotted_locus_count=0,
        )


def test_the_sprite_is_the_same_bytes_every_time_it_is_rendered():
    """⚠ The digest is an ETag, so a renderer that is not deterministic silently breaks caching."""
    x, y = a_small_catalogue(200)
    first = render_catalogue_scatter_sprite(x, y, unplotted_locus_count=0, pixel_size=240)
    second = render_catalogue_scatter_sprite(x, y, unplotted_locus_count=0, pixel_size=240)
    assert first.content_digest == second.content_digest


# ── the size claim, measured rather than asserted from the plan ────────────────────────────────
def clustered_catalogue(count: int, seed: int = 3):
    """Positions in blobs rather than uniform noise — a UMAP output is nothing like white noise."""
    generator = numpy.random.default_rng(seed)
    centres = generator.integers(-28_000, 28_000, size=(60, 2))
    pick = generator.integers(0, 60, size=count)
    x = numpy.clip(centres[pick, 0] + generator.normal(0, 2_400, count), -32_000, 32_000)
    y = numpy.clip(centres[pick, 1] + generator.normal(0, 2_400, count), -32_000, 32_000)
    return x.astype(numpy.int16), y.astype(numpy.int16)


def test_the_sprite_is_bounded_by_its_RESOLUTION_and_not_by_the_catalogue_size():
    """⭐ The endpoint's whole argument, as a property rather than a remembered byte count.

    ⚠ **It does not win today, and saying so is the point.** Measured here: at the published ecoli
    catalogue's 17,531 loci the sprite is ~118 kB against ~70 kB of raw positions, so sending the
    coordinates is *cheaper* now. The crossover is around 30k loci, and at the design target of
    889,160 the positions are 3.56 MB while the sprite is ~0.3 MB — because a sprite is bounded by
    1200² pixels and a coordinate array is not bounded by anything.

    So the assertion is the ratio, not the size: 50× the loci must not cost anything like 50× the
    bytes. A recorded "≤ 150,000 B" would be re-baselined the first time a catalogue grew.
    """
    small_count, large_count = 17_531, 889_160
    small = render_catalogue_scatter_sprite(*clustered_catalogue(small_count), unplotted_locus_count=0)
    large = render_catalogue_scatter_sprite(*clustered_catalogue(large_count), unplotted_locus_count=0)

    locus_growth = large_count / small_count
    sprite_growth = len(large.image_png) / len(small.image_png)
    print(
        f"\n  {small_count:>9,} loci: {len(small.image_png):>9,} B sprite vs {small_count * 4:>9,} B positions"
        f"\n  {large_count:>9,} loci: {len(large.image_png):>9,} B sprite vs {large_count * 4:>9,} B positions"
    )
    assert sprite_growth < locus_growth / 10, (
        f"{locus_growth:.0f}× the loci cost {sprite_growth:.1f}× the bytes — the sprite is growing "
        "with the catalogue, which is the thing it exists not to do"
    )
    assert len(large.image_png) < large_count * 4 / 5, (
        "at the design target the picture must be a large multiple cheaper than the positions, or "
        "there is no reason to render one"
    )
