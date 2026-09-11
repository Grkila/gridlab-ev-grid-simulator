export const projectCoordinate = (lon: number, lat: number): [number, number] => [(lon - 19.825) * 78, -(lat - 45.265) * 111];
export type RoadPath = { points: [number, number][]; distances: number[]; length: number };

export function buildRoadPath(coordinates: number[][]): RoadPath {
  const points: [number, number][] = [];
  const distances: number[] = [];
  let length = 0;
  for (const coordinate of coordinates) {
    const point = projectCoordinate(coordinate[0], coordinate[1]);
    const previous = points.at(-1);
    const distance = previous ? Math.hypot(point[0] - previous[0], point[1] - previous[1]) : 0;
    if (previous && distance < 1e-9) continue;
    length += distance;
    points.push(point);
    distances.push(length);
  }
  return { points, distances, length };
}

// Arc-length interpolation stays on each road segment, including sharp turns.
// Curved splines would cut corners and move cars through neighboring blocks.
export function sampleRoadPath(path: RoadPath, distance: number) {
  if (path.length === 0 || path.points.length < 2) return { x: path.points[0]?.[0] || 0, z: path.points[0]?.[1] || 0, heading: 0 };
  const at = ((distance % path.length) + path.length) % path.length;
  let lo = 1, hi = path.distances.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (path.distances[mid] < at) lo = mid + 1; else hi = mid;
  }
  const a = path.points[lo - 1], b = path.points[lo];
  const t = (at - path.distances[lo - 1]) / (path.distances[lo] - path.distances[lo - 1]);
  return { x: a[0] + (b[0] - a[0]) * t, z: a[1] + (b[1] - a[1]) * t, heading: Math.atan2(b[0] - a[0], b[1] - a[1]) };
}
