import { describe, expect, it } from "vitest";

import {
  chordDistance,
  chordMatrixFrom,
  classicalMds,
  jacobiEigen,
} from "./classicalMultidimensionalScaling";

/** Pairwise Euclidean distances of a configuration, for checking a fit reproduces its input. */
function distanceMatrixOf(points: readonly (readonly number[])[]): number[] {
  const n = points.length;
  const out = new Array<number>(n * n).fill(0);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const a = points[i] as readonly number[];
      const b = points[j] as readonly number[];
      out[i * n + j] = Math.hypot(...a.map((value, axis) => value - (b[axis] as number)));
    }
  }
  return out;
}

function fittedDistances(fit: ReturnType<typeof classicalMds>): number[] {
  return distanceMatrixOf(fit.positions.map((position) => [...position]));
}

describe("the Jacobi eigensolver", () => {
  it("diagonalises a symmetric matrix into eigenvalues it can be rebuilt from", () => {
    // A · v = λ · v, checked directly rather than against a recorded decomposition.
    const matrix = [4, 1, 1, 1, 3, 0, 1, 0, 2];
    const { values, vectors } = jacobiEigen(matrix, 3);
    for (let column = 0; column < 3; column++) {
      for (let row = 0; row < 3; row++) {
        let product = 0;
        for (let k = 0; k < 3; k++) product += (matrix[row * 3 + k] as number) * (vectors[k * 3 + column] as number);
        expect(product).toBeCloseTo((values[column] as number) * (vectors[row * 3 + column] as number), 9);
      }
    }
  });

  it("gets a diagonal matrix exactly right without rotating at all", () => {
    const { values } = jacobiEigen([3, 0, 0, 0, 7, 0, 0, 0, -2], 3);
    expect(values).toEqual([3, 7, -2]);
  });

  it("⛔ does NOT mutate the caller's matrix", () => {
    // The rotation is in-place by construction, and the published page passed its only copy in.
    const matrix = [4, 1, 1, 3];
    jacobiEigen(matrix, 2);
    expect(matrix).toEqual([4, 1, 1, 3]);
  });

  it("refuses a matrix whose length does not match its stated size", () => {
    expect(() => jacobiEigen([1, 2, 3], 2)).toThrow(RangeError);
  });
});

describe("⭐ classical MDS is EXACT for a planar configuration", () => {
  it("reproduces a square's own distances, and keeps all of its variance", () => {
    const square = [
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
    ];
    const fit = classicalMds(distanceMatrixOf(square), 4);
    expect(fit.kept).toBeCloseTo(1, 9);
    const rebuilt = fittedDistances(fit);
    for (const [index, expected] of distanceMatrixOf(square).entries()) {
      expect(rebuilt[index]).toBeCloseTo(expected, 9);
    }
  });

  it("reproduces six points in a plane — the shape this actually runs on", () => {
    const six = [
      [0, 0],
      [1.2, 0.3],
      [-0.4, 0.9],
      [0.7, -1.1],
      [-1.3, -0.5],
      [0.2, 1.4],
    ];
    const fit = classicalMds(distanceMatrixOf(six), 6);
    expect(fit.kept).toBeCloseTo(1, 9);
    const rebuilt = fittedDistances(fit);
    for (const [index, expected] of distanceMatrixOf(six).entries()) {
      expect(rebuilt[index]).toBeCloseTo(expected, 9);
    }
  });

  it("⭐ reports LESS than all of it for a configuration that is not planar", () => {
    // A regular tetrahedron cannot be drawn in a plane, and the card must be able to say so rather
    // than presenting the projection as the thing itself.
    const tetrahedron = [
      [0, 0, 0],
      [1, 0, 0],
      [0.5, Math.sqrt(3) / 2, 0],
      [0.5, Math.sqrt(3) / 6, Math.sqrt(2 / 3)],
    ];
    const fit = classicalMds(distanceMatrixOf(tetrahedron), 4);
    expect(fit.kept).toBeLessThan(0.9);
    expect(fit.kept).toBeGreaterThan(0.5);
  });

  it("⚠ divides `kept` by the POSITIVE eigenvalue mass only", () => {
    // A non-Euclidean matrix produces negative eigenvalues. Counting them in the denominator would
    // let a badly non-planar configuration report a HIGHER kept fraction than a good one.
    const violatesTriangleInequality = [0, 1, 9, 1, 0, 1, 9, 1, 0];
    const fit = classicalMds(violatesTriangleInequality, 3);
    expect(fit.kept).toBeGreaterThan(0);
    expect(fit.kept).toBeLessThanOrEqual(1);
  });

  it("places one point at the origin and two points on a line", () => {
    expect(classicalMds([0], 1).positions).toEqual([[0, 0]]);
    const pair = classicalMds([0, 2, 2, 0], 2);
    expect(Math.hypot(...pair.positions[0]!.map((v, i) => v - pair.positions[1]![i]!))).toBeCloseTo(2, 9);
  });
});

describe("⭐ the chord distance is what makes the fit exact", () => {
  it("turns a cosine distance into the Euclidean distance between unit vectors", () => {
    // Orthogonal unit vectors are √2 apart; identical ones are 0 apart; opposed ones are 2 apart.
    expect(chordDistance(0)).toBe(0);
    expect(chordDistance(1)).toBeCloseTo(Math.SQRT2, 12);
    expect(chordDistance(2)).toBeCloseTo(2, 12);
  });

  it("⛔ clamps at zero rather than returning NaN", () => {
    // A cosine of 1 stored to finite precision can round to a distance just below zero, and
    // `Math.sqrt` of that is NaN — a point that then vanishes from the picture entirely.
    expect(chordDistance(-1e-9)).toBe(0);
    expect(Number.isNaN(chordDistance(-1))).toBe(false);
  });
});

describe("building the distance matrix from a resolved cosine matrix", () => {
  const measured = [
    [1, 0.9, 0.8],
    [0.9, 1, 0.7],
    [0.8, 0.7, 1],
  ];

  it("keeps every point whose distance to the focal one is measured", () => {
    const built = chordMatrixFrom(measured);
    expect(built?.keptIndices).toEqual([0, 1, 2]);
    expect(built?.distances[1]).toBeCloseTo(chordDistance(1 - 0.9), 12);
  });

  it("⛔ drops an unmeasured point rather than placing it at a cosine of ZERO", () => {
    // Zero is ORTHOGONAL — as far apart as two unit vectors get short of opposition — so
    // substituting it for "not measured" puts a locus at a specific, wrong distance.
    const withGap = [
      [1, 0.9, null],
      [0.9, 1, null],
      [null, null, 1],
    ];
    const built = chordMatrixFrom(withGap);
    expect(built?.keptIndices).toEqual([0, 1]);
    expect(built?.distances).toHaveLength(4);
  });

  it("⛔ refuses the whole fit when an INTERIOR pair is unmeasured", () => {
    // Both points reach the focal locus, so neither can be dropped — but their distance to each
    // other is unknown, and a fit that guessed it would draw a relationship nothing measured.
    const interiorGap = [
      [1, 0.9, 0.8],
      [0.9, 1, null],
      [0.8, null, 1],
    ];
    expect(chordMatrixFrom(interiorGap)).toBeNull();
  });

  it("⛔ returns null rather than a one-point map", () => {
    expect(chordMatrixFrom([[1, null], [null, 1]])).toBeNull();
    expect(chordMatrixFrom([[1]])).toBeNull();
  });
});
