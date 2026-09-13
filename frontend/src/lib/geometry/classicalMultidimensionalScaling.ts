/**
 * Classical MDS on a handful of points — the **local** neighbourhood map.
 *
 * ⭐ **This is a fit, not a crop, and that distinction is the reason it exists.** The map used to be
 * one UMAP over every gene in the catalogue, with three crops of it as three zoom levels. Measured
 * on the shipped fit, a locus's five nearest loci landed a **median 18.5 % of the map apart**, so the
 * "these loci" crop showed six specks scattered over the whole picture. David, 2026-08-19: *"the
 * 'nearest' are spread over the whole catalogue view and it thus indicates the examination of 'these
 * loci' is completely meaningless."* That reading was right — UMAP preserves local neighbourhoods,
 * not global distance, and no caption rescues a crop of one.
 *
 * Six loci have a 6×6 distance matrix, and classical MDS on six points is a 6×6 eigenproblem. It is
 * solved here, per locus, on demand, from the 15 cosines the API resolves — sub-millisecond, and it
 * must re-run on every representation or zoom switch with no round trip, which is why it stayed
 * client-side when almost everything else moved to Python.
 *
 * ⭐ **`kept` is what stops the picture over-claiming.** Classical MDS is exact for a configuration
 * that is genuinely planar; `kept` is the share of the positive eigenvalue mass the two drawn axes
 * hold, so the card can say what fraction of their variance the plane keeps rather than implying it
 * keeps all of it.
 */

/** How many sweeps the Jacobi rotation is allowed before it gives up. */
const MAX_SWEEPS = 60;
/** Below this total off-diagonal mass the matrix is diagonal enough to read eigenvalues off. */
const OFF_DIAGONAL_TOLERANCE = 1e-22;
/** A rotation smaller than this changes nothing a float64 can see. */
const NEGLIGIBLE_ROTATION = 1e-18;

export interface Eigen {
  /** Eigenvalues, in the matrix's own order — NOT sorted. */
  readonly values: readonly number[];
  /** Eigenvectors in columns: `vectors[row * n + column]`. */
  readonly vectors: readonly number[];
}

/**
 * Cyclic Jacobi eigendecomposition of a symmetric `n × n` matrix, row-major.
 *
 * ⚠ **Mutates a copy, never the caller's array.** The rotation is in-place by construction, and the
 * published page passed its only copy in — fine there because it built the matrix immediately
 * before, and a trap for anyone who reuses one.
 *
 * No library: six points is a 6×6 problem, and a dependency for it would be larger than the page.
 */
export function jacobiEigen(matrix: readonly number[], n: number): Eigen {
  if (matrix.length !== n * n) {
    throw new RangeError(`a ${n}×${n} matrix has ${n * n} entries, not ${matrix.length}`);
  }
  const a = [...matrix];
  const v = new Array<number>(n * n).fill(0);
  for (let i = 0; i < n; i++) v[i * n + i] = 1;

  for (let sweep = 0; sweep < MAX_SWEEPS; sweep++) {
    let off = 0;
    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) off += (a[p * n + q] as number) ** 2;
    }
    if (off < OFF_DIAGONAL_TOLERANCE) break;

    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) {
        const apq = a[p * n + q] as number;
        if (Math.abs(apq) < NEGLIGIBLE_ROTATION) continue;
        const theta = ((a[q * n + q] as number) - (a[p * n + p] as number)) / (2 * apq);
        const t =
          theta === 0
            ? 1
            : (theta > 0 ? 1 : -1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;
        for (let i = 0; i < n; i++) {
          const aip = a[i * n + p] as number;
          const aiq = a[i * n + q] as number;
          a[i * n + p] = c * aip - s * aiq;
          a[i * n + q] = s * aip + c * aiq;
        }
        for (let i = 0; i < n; i++) {
          const api = a[p * n + i] as number;
          const aqi = a[q * n + i] as number;
          a[p * n + i] = c * api - s * aqi;
          a[q * n + i] = s * api + c * aqi;
        }
        for (let i = 0; i < n; i++) {
          const vip = v[i * n + p] as number;
          const viq = v[i * n + q] as number;
          v[i * n + p] = c * vip - s * viq;
          v[i * n + q] = s * vip + c * viq;
        }
      }
    }
  }

  const values = new Array<number>(n);
  for (let i = 0; i < n; i++) values[i] = a[i * n + i] as number;
  return { values, vectors: v };
}

export interface MdsFit {
  /** One `[x, y]` per point, in the order the distance matrix gave them. */
  readonly positions: readonly (readonly [number, number])[];
  /**
   * ⭐ The share of the positive eigenvalue mass the two drawn axes hold — 1 for a genuinely planar
   * configuration. The card prints it so the picture never claims more than the projection earned.
   */
  readonly kept: number;
}

/**
 * Classical MDS: double-centre the squared distances, take the top two eigenvectors.
 *
 * ⚠ `kept` divides by the **positive** eigenvalue mass only. A distance matrix that is not quite
 * Euclidean produces small negative eigenvalues, and counting those in the denominator would let a
 * badly non-planar configuration report a *higher* kept fraction than a good one.
 */
export function classicalMds(distances: readonly number[], n: number): MdsFit {
  if (distances.length !== n * n) {
    throw new RangeError(`a ${n}×${n} matrix has ${n * n} entries, not ${distances.length}`);
  }
  if (n === 0) return { positions: [], kept: 1 };

  const squared = distances.map((distance) => distance * distance);
  const rowMeans = new Array<number>(n).fill(0);
  let grandMean = 0;
  for (let i = 0; i < n; i++) {
    let sum = 0;
    for (let j = 0; j < n; j++) sum += squared[i * n + j] as number;
    rowMeans[i] = sum / n;
    grandMean += sum;
  }
  grandMean /= n * n;

  const centred = new Array<number>(n * n);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      centred[i * n + j] =
        -0.5 * ((squared[i * n + j] as number) - (rowMeans[i] as number) - (rowMeans[j] as number) + grandMean);
    }
  }

  const { values, vectors } = jacobiEigen(centred, n);
  const order = Array.from({ length: n }, (_unused, index) => index).sort(
    (left, right) => (values[right] as number) - (values[left] as number),
  );
  let positiveMass = 0;
  for (const value of values) if (value > 0) positiveMass += value;

  const first = Math.max(0, values[order[0] as number] as number);
  const second = n > 1 ? Math.max(0, values[order[1] as number] as number) : 0;
  const positions: [number, number][] = [];
  for (let i = 0; i < n; i++) {
    positions.push([
      (vectors[i * n + (order[0] as number)] as number) * Math.sqrt(first),
      n > 1 ? (vectors[i * n + (order[1] as number)] as number) * Math.sqrt(second) : 0,
    ]);
  }
  return { positions, kept: positiveMass > 0 ? (first + second) / positiveMass : 1 };
}

/**
 * Cosine **distance** → the true Euclidean distance between two unit vectors: `√(2d)`.
 *
 * ⭐ **This conversion is what makes classical MDS exact rather than approximate**, and it is also
 * what lets a ring be compared with a gap: the ring on each locus is its own members' median
 * distance from its centre, in these same units, so a ring that reaches a neighbour means the
 * locus's spread reaches it — which is the whole question the map is asked.
 *
 * ⚠ Clamped at zero: a cosine of 1 stored to finite precision can round to a distance just below
 * zero, and `Math.sqrt` of that is `NaN` — a point that then vanishes from the picture entirely.
 */
export function chordDistance(cosineDistance: number): number {
  return Math.sqrt(Math.max(0, 2 * cosineDistance));
}

/**
 * The chord distance matrix for a resolved 6×6 cosine matrix, with unmeasured pairs dropped.
 *
 * ⛔ **`null` in the matrix is an absence, not a zero.** A zero cosine is *orthogonal* — as far
 * apart as two unit vectors get short of opposition — so substituting it for "not measured" places
 * a locus at a specific, wrong distance rather than leaving it out. Returns `null` when fewer than
 * two points survive, because a one-point map is not a map.
 */
export function chordMatrixFrom(
  cosineMatrix: readonly (readonly (number | null)[])[],
): { readonly distances: number[]; readonly keptIndices: number[] } | null {
  const size = cosineMatrix.length;
  const keptIndices: number[] = [];
  for (let index = 0; index < size; index++) {
    const row = cosineMatrix[index];
    // A point is usable when its distance to every other kept point is measured; the focal point
    // (index 0) anchors the set, so its row is what decides membership.
    if (row !== undefined && row[0] !== null && row[0] !== undefined) keptIndices.push(index);
  }
  if (keptIndices.length < 2) return null;

  const n = keptIndices.length;
  const distances = new Array<number>(n * n).fill(0);
  for (let a = 0; a < n; a++) {
    for (let b = 0; b < n; b++) {
      if (a === b) continue;
      const cosine = cosineMatrix[keptIndices[a] as number]?.[keptIndices[b] as number];
      // An unmeasured interior pair cannot be invented; the whole fit is refused instead.
      if (cosine === null || cosine === undefined) return null;
      distances[a * n + b] = chordDistance(1 - cosine);
    }
  }
  return { distances, keptIndices };
}


/** A square drawing surface, and where a fitted point lands on it. */
export interface MapViewport {
  /** The world-space centre the view is framed on. */
  readonly centreX: number;
  readonly centreY: number;
  /** The world-space width the view covers, padded. */
  readonly span: number;
  /** World units per drawn unit — the scale a ring's radius is drawn at. */
  readonly scale: number;
}

/** How much empty margin the frame leaves around the outermost ring. */
export const VIEWPORT_PADDING = 1.16;

/**
 * Frame a set of fitted points **and their rings**, at true scale.
 *
 * ⛔ **No rescaling to make mid-range rings visible.** Most loci are far tighter than their nearest
 * rival, and that IS the finding — a ring drawn larger than it is would turn the map's one real
 * question ("does this locus's spread reach its neighbour?") into decoration.
 *
 * ⚠ The bounds include each radius, not just each centre: a ring framed out of view is a spread the
 * reader cannot see reaching anything.
 */
export function fitViewport(
  positions: readonly (readonly [number, number])[],
  radii: readonly number[],
  drawnSize: number,
): MapViewport {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const [index, position] of positions.entries()) {
    const radius = radii[index] ?? 0;
    minX = Math.min(minX, position[0] - radius);
    maxX = Math.max(maxX, position[0] + radius);
    minY = Math.min(minY, position[1] - radius);
    maxY = Math.max(maxY, position[1] + radius);
  }
  if (!Number.isFinite(minX)) {
    return { centreX: 0, centreY: 0, span: 1, scale: drawnSize };
  }
  // ⚠ A floor on the span: six identical loci have zero extent, and dividing by it puts every dot
  // at Infinity — a blank picture rather than the "these are the same point" one it should be.
  const span = Math.max(maxX - minX, maxY - minY, 1e-6) * VIEWPORT_PADDING;
  return {
    centreX: (minX + maxX) / 2,
    centreY: (minY + maxY) / 2,
    span,
    scale: drawnSize / span,
  };
}

/**
 * A fitted point, in drawing coordinates.
 *
 * ⚠ The Y axis is flipped: MDS works in mathematical coordinates where y grows upward, and both SVG
 * and canvas grow downward. Forgetting this mirrors the picture — which looks like a picture.
 */
export function projectOnto(
  point: readonly [number, number],
  viewport: MapViewport,
  drawnSize: number,
): [number, number] {
  return [
    (point[0] - viewport.centreX) * viewport.scale + drawnSize / 2,
    drawnSize / 2 - (point[1] - viewport.centreY) * viewport.scale,
  ];
}
