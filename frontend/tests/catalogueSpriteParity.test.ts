/**
 * @vitest-environment jsdom
 *
 * ⭐⭐ **The closed loop: the coordinate the COMPONENT renders, against the pixel in the REAL PNG.**
 *
 * The backend proves its own half — 2,000 real loci projected in numpy land on lit dust. The front
 * end proves its own half — the projection matches hand-computed coordinates. But those are *two
 * implementations of one formula, each checked against itself*. If both drifted the same way, or if
 * the front end scaled the sprite into the SVG square differently from how it projects positions
 * into it, every existing test would still pass and every dot would sit beside its own speck.
 *
 * So this suite takes only what a browser has: the recorded locus response, the recorded species
 * response, and the recorded sprite bytes. It mounts the real component, reads the `cx`/`cy` it
 * actually rendered, converts to sprite pixels through the SAME `viewBox`→image mapping the SVG
 * declares, and asks whether that pixel is lit.
 *
 * ⚠ The PNG is decoded with `zlib` alone, not with the code that wrote it.
 */
import { mount } from "@vue/test-utils";
import { inflateSync } from "node:zlib";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

import type { LocusDetailResponse, MapProjection, Representation } from "@/api/types";
import NeighbourhoodMapCard from "@/components/map/NeighbourhoodMapCard.vue";

vi.mock("@/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/client")>()),
  fetchLocus: vi.fn(async () => ({ ok: false, kind: "network", detail: "not used" })),
}));

const FIXTURES = resolve(process.cwd(), "tests/fixtures");
const recorded = JSON.parse(
  readFileSync(resolve(FIXTURES, "api_locus_responses.json"), "utf8"),
) as {
  loci: Record<string, { label: string; response: LocusDetailResponse }>;
  species: { map_projections: MapProjection[] };
};

/** ⛔ The SVG's own square, and it must stay in step with the component's `DRAWN_SIZE`. */
const DRAWN_SIZE = 600;
const CASES = ["ordinary", "over_cap", "no_window"] as const;

/** A minimal greyscale+alpha PNG reader — IHDR, IDAT, filter 0. Nothing else. */
function decodeAlpha(bytes: Buffer): { width: number; height: number; alpha: Uint8Array } {
  expect([...bytes.subarray(0, 8)]).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  let position = 8;
  let width = 0;
  let height = 0;
  const parts: Buffer[] = [];
  while (position < bytes.length) {
    const length = bytes.readUInt32BE(position);
    const kind = bytes.subarray(position + 4, position + 8).toString("ascii");
    const payload = bytes.subarray(position + 8, position + 8 + length);
    if (kind === "IHDR") {
      width = payload.readUInt32BE(0);
      height = payload.readUInt32BE(4);
      // 8-bit greyscale+alpha, no interlace — anything else and the slicing below is nonsense.
      expect([payload[8], payload[9], payload[12]]).toEqual([8, 4, 0]);
    } else if (kind === "IDAT") {
      parts.push(Buffer.from(payload));
    }
    position += 12 + length;
  }
  const raw = inflateSync(Buffer.concat(parts));
  const stride = width * 2 + 1;
  const alpha = new Uint8Array(width * height);
  for (let row = 0; row < height; row += 1) {
    const start = row * stride;
    expect(raw[start]).toBe(0);
    for (let column = 0; column < width; column += 1) {
      alpha[row * width + column] = raw[start + 1 + column * 2 + 1] as number;
    }
  }
  return { width, height, alpha };
}

function projectionFor(representation: Representation): MapProjection {
  const found = recorded.species.map_projections.find(
    (projection) => projection.representation === representation,
  );
  if (found === undefined) throw new Error(`no ${representation} projection in the fixture`);
  return found;
}

function spriteFor(representation: Representation) {
  return decodeAlpha(readFileSync(resolve(FIXTURES, `catalogue_scatter_ecoli_${representation}.png`)));
}

describe("⭐⭐ every dot the component renders sits on dust in the real sprite", () => {
  it("across three real loci and both representations", () => {
    let checked = 0;
    const misses: string[] = [];

    for (const representation of ["bacformer", "esm"] as const) {
      const sprite = spriteFor(representation);
      const descriptor = projectionFor(representation).scatter_sprite;
      expect(descriptor).not.toBeNull();
      // ⛔ The picture the browser gets IS the picture the descriptor describes. Without this the
      // rest of the test could be checking a stale fixture against fresh numbers.
      expect(sprite.width).toBe(descriptor!.pixel_size);
      expect(sprite.height).toBe(descriptor!.pixel_size);

      for (const kind of CASES) {
        const card = mount(NeighbourhoodMapCard, {
          props: {
            detail: recorded.loci[kind]!.response,
            representation,
            availableRepresentations: ["bacformer", "esm"] as const,
            zoom: "global" as const,
            speciesKey: "ecoli",
            projection: projectionFor(representation),
          },
        });
        for (const dot of card.findAll(".map-dot")) {
          // The `<image>` fills the viewBox square, so one user unit is `pixel_size / DRAWN_SIZE`
          // image pixels — the same mapping the SVG itself declares, taken from the same two
          // numbers rather than assumed to be 2.
          const scale = sprite.width / DRAWN_SIZE;
          const column = Math.floor(Number(dot.attributes("cx")) * scale);
          const row = Math.floor(Number(dot.attributes("cy")) * scale);
          checked += 1;
          if ((sprite.alpha[row * sprite.width + column] ?? 0) === 0) {
            misses.push(`${representation}/${kind} at ${column},${row}`);
          }
        }
      }
    }

    // ⛔ Coverage before the verdict: a run that mounted six empty cards would report no misses.
    expect(checked).toBeGreaterThanOrEqual(CASES.length * 2 * 2);
    expect(misses).toEqual([]);
  });

  it("⛔ and would NOTICE — a dot moved by a tenth of the frame lands on nothing", () => {
    // The check above is only worth having if empty ground is actually reachable. Shifting every
    // dot by 60 user units must produce misses, or the sprite is so dense that "on dust" is
    // vacuous and the whole loop proves nothing.
    const sprite = spriteFor("bacformer");
    const card = mount(NeighbourhoodMapCard, {
      props: {
        detail: recorded.loci.ordinary!.response,
        representation: "bacformer" as const,
        availableRepresentations: ["bacformer", "esm"] as const,
        zoom: "global" as const,
        speciesKey: "ecoli",
        projection: projectionFor("bacformer"),
      },
    });
    const scale = sprite.width / DRAWN_SIZE;
    let unlit = 0;
    for (const dot of card.findAll(".map-dot")) {
      const column = Math.floor((Number(dot.attributes("cx")) + 60) * scale);
      const row = Math.floor((Number(dot.attributes("cy")) + 60) * scale);
      if ((sprite.alpha[row * sprite.width + column] ?? 0) === 0) unlit += 1;
    }
    expect(unlit).toBeGreaterThan(0);
  });
});
