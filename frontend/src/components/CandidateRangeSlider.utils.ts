import type { DollarRange } from "@/utils/transformToHierarchy";

export function clampMin(v: number, max: number, rangeMin: number): number {
  return Math.min(Math.max(v, rangeMin), max - 1);
}

export function clampMax(v: number, min: number, rangeMax: number): number {
  return Math.max(Math.min(v, rangeMax), min + 1);
}

export const DEFAULT_MAX_VISIBLE_CANDIDATES = 200;

/** Count of values >= v in a descending-sorted array, via binary search. */
function countAtLeast(sortedDesc: number[], v: number): number {
  let lo = 0;
  let hi = sortedDesc.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (sortedDesc[mid] >= v) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Count of values > v in a descending-sorted array, via binary search. */
function countMoreThan(sortedDesc: number[], v: number): number {
  let lo = 0;
  let hi = sortedDesc.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (sortedDesc[mid] > v) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/**
 * If `range` currently spans more than `maxCandidates` values, pulls the
 * handle opposite `drivingHandle` in until it doesn't — e.g. dragging min
 * down toward $0 past the cap pulls max down with it, live, rather than
 * letting the candidate count balloon.
 */
export function clampRangeToMaxCandidates(
  range: DollarRange,
  drivingHandle: "min" | "max",
  sortedDescSpends: number[],
  maxCandidates: number = DEFAULT_MAX_VISIBLE_CANDIDATES,
): DollarRange {
  const p = countAtLeast(sortedDescSpends, range.min);
  const s = countMoreThan(sortedDescSpends, range.max);
  const count = Math.max(0, p - s);
  if (count <= maxCandidates) return range;

  if (drivingHandle === "min") {
    const targetIndex = p - maxCandidates;
    const newMax = sortedDescSpends[targetIndex];
    if (newMax === undefined) return range;
    return { min: range.min, max: Math.max(newMax, range.min + 1) };
  }

  const targetIndex = s + maxCandidates - 1;
  const newMin = sortedDescSpends[targetIndex];
  if (newMin === undefined) return range;
  return { min: Math.min(newMin, range.max - 1), max: range.max };
}
