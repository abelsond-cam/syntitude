/**
 * Projecting a locus onto the **whole-catalogue sprite** — with the server's numbers, never ours.
 *
 * ⛔⛔ **This is the one place the sprite and the dots drawn on it can disagree, and the failure is
 * invisible.** The published page could project the six foreground loci itself, because it held
 * every coordinate in the browser and could take their extent. This client holds a *picture*. If it
 * re-derives a viewport — from the projection's `extent`, from the six positions it happens to have,
 * from anything — the focal dot lands *beside* its own speck rather than on it, by a few pixels or
 * by a third of the frame, and the result still looks exactly like a scatter plot with a highlighted
 * point. Nothing on the page could contradict it.
 *
 * So the renderer records the transform it actually used and the API serves it, and these functions
 * take that transform as an argument. There is deliberately no function here that computes one.
 *
 * ⚠ **The units are the quantised `map_x`/`map_y` integers**, the same ones `locus_embedding_geometry`
 * stores and the same ones the renderer consumed — which is what makes this a subtraction and a
 * scale rather than a unit conversion with a place to go wrong.
 */

import type { CatalogueScatterSprite } from "@/api/types";

/** A position on the map, in quantised units. `null` where the locus has no medoid. */
export type MapPosition = readonly [number, number];

/**
 * The transform the sprite was rendered with. Structurally a subset of {@link CatalogueScatterSprite},
 * so a caller cannot pass "some viewport" — only the one that came back with the picture.
 */
export type SpriteViewport = Pick<CatalogueScatterSprite, "viewport_centre" | "viewport_span">;

/**
 * Quantised map coordinates → a point in a `drawnSize` square laid over the sprite.
 *
 * ⛔ **Y is flipped**, because the map's y grows upward and a raster's grows downward. A version
 * that forgets it is a valid projection of nothing: mirrored, plausible, and wrong for every locus
 * at once — so no dot ever looks out of place.
 */
export function projectOntoSprite(
  position: MapPosition,
  viewport: SpriteViewport,
  drawnSize: number,
): [number, number] {
  const scale = drawnSize / viewport.viewport_span;
  return [
    (position[0] - viewport.viewport_centre[0]) * scale + drawnSize / 2,
    drawnSize / 2 - (position[1] - viewport.viewport_centre[1]) * scale,
  ];
}

/**
 * What the global view's caption says about its own coverage.
 *
 * ⭐ **The published caption quoted the catalogue size** — *"where this locus sits among all
 * 17,531"* — and a locus with no medoid never reached the map at all, so it is not on the picture.
 * The two counts are served separately for exactly this sentence, and the second clause appears
 * only when there is something to say.
 */
export function spriteCoverageSentence(sprite: CatalogueScatterSprite): string {
  const plotted = sprite.plotted_locus_count.toLocaleString();
  if (sprite.unplotted_locus_count === 0) return `all ${plotted} loci`;
  return (
    `${plotted} loci — the ${sprite.unplotted_locus_count.toLocaleString()} with no medoid are ` +
    "not on this picture"
  );
}
