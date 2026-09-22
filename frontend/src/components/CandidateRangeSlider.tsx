"use client";

import { useMemo, useRef, useState } from "react";
import type { DollarRange } from "@/utils/transformToHierarchy";
import {
  formatDollars,
  formatDollarsFull,
  parseDollarInput,
} from "@/utils/formatDollars";

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

interface CandidateRangeSliderProps {
  /** Absolute min/max total_spending for this office — the slider's fixed track bounds. */
  bounds: DollarRange;
  /** Initial handle positions. Treated as init-only; parent remounts this component (via `key`) to change it. */
  value: DollarRange;
  /** Every positive total_spending value for this office, used to compute the live count. */
  candidateSpends: number[];
  /** Caps how many candidates can ever be in range at once; the handle opposite whichever one is moving gets pulled in to enforce it. */
  maxCandidates?: number;
  /** Fires on drag-release, discrete keyboard steps, and input-box blur/Enter commits — never on every drag tick. */
  onCommit: (range: DollarRange) => void;
}

export default function CandidateRangeSlider({
  bounds,
  value,
  candidateSpends,
  maxCandidates = DEFAULT_MAX_VISIBLE_CANDIDATES,
  onCommit,
}: CandidateRangeSliderProps) {
  const [live, setLive] = useState<DollarRange>(value);
  const liveRef = useRef<DollarRange>(value);
  const draggingRef = useRef<"min" | "max" | null>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  const [minText, setMinText] = useState(formatDollarsFull(value.min));
  const [maxText, setMaxText] = useState(formatDollarsFull(value.max));

  const sortedDescSpends = useMemo(
    () => [...candidateSpends].sort((a, b) => b - a),
    [candidateSpends],
  );

  function clampToCap(range: DollarRange, drivingHandle: "min" | "max") {
    return clampRangeToMaxCandidates(
      range,
      drivingHandle,
      sortedDescSpends,
      maxCandidates,
    );
  }

  const span = Math.max(1, bounds.max - bounds.min);

  function setLiveRange(next: DollarRange) {
    liveRef.current = next;
    setLive(next);
    setMinText(formatDollarsFull(next.min));
    setMaxText(formatDollarsFull(next.max));
  }

  function pct(v: number): number {
    return ((v - bounds.min) / span) * 100;
  }

  function valueFromClientX(clientX: number): number {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return bounds.min;
    const fraction = Math.min(
      1,
      Math.max(0, (clientX - rect.left) / rect.width),
    );
    return bounds.min + fraction * span;
  }

  function onHandlePointerDown(handle: "min" | "max") {
    return (e: React.PointerEvent<HTMLDivElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      draggingRef.current = handle;
    };
  }

  function onHandlePointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const handle = draggingRef.current;
    if (!handle) return;
    const raw = valueFromClientX(e.clientX);
    const current = liveRef.current;
    const next: DollarRange =
      handle === "min"
        ? { min: Math.min(raw, current.max - 1), max: current.max }
        : { min: current.min, max: Math.max(raw, current.min + 1) };
    setLiveRange(clampToCap(next, handle));
  }

  function onHandlePointerUp() {
    if (!draggingRef.current) return;
    draggingRef.current = null;
    onCommit(liveRef.current);
  }

  function onHandleKeyDown(handle: "min" | "max") {
    return (e: React.KeyboardEvent<HTMLDivElement>) => {
      const step = span / 100 || 1;
      let delta = 0;
      if (e.key === "ArrowRight" || e.key === "ArrowUp") delta = step;
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") delta = -step;
      if (!delta) return;
      e.preventDefault();
      const current = liveRef.current;
      const raw: DollarRange =
        handle === "min"
          ? {
              min: clampMin(current.min + delta, current.max, bounds.min),
              max: current.max,
            }
          : {
              min: current.min,
              max: clampMax(current.max + delta, current.min, bounds.max),
            };
      const next = clampToCap(raw, handle);
      setLiveRange(next);
      onCommit(next);
    };
  }

  function handleMinBlur() {
    const parsed = parseDollarInput(minText);
    const snapped =
      parsed === null
        ? liveRef.current.min
        : clampMin(parsed, liveRef.current.max, bounds.min);
    const next = clampToCap(
      { min: snapped, max: liveRef.current.max },
      "min",
    );
    setLiveRange(next);
    onCommit(next);
  }

  function handleMaxBlur() {
    const parsed = parseDollarInput(maxText);
    const snapped =
      parsed === null
        ? liveRef.current.max
        : clampMax(parsed, liveRef.current.min, bounds.max);
    const next = clampToCap(
      { min: liveRef.current.min, max: snapped },
      "max",
    );
    setLiveRange(next);
    onCommit(next);
  }

  const count = candidateSpends.filter(
    (v) => v >= live.min && v <= live.max,
  ).length;

  return (
    <div className="flex flex-col items-center gap-0 font-headline select-none">
      <span className="text-sm font-semibold italic text-breadcrumb-text -mb-4">
        Candidates in range: {count}
      </span>
      <div className="flex justify-between w-full max-w-105 text-xs text-breadcrumb-text">
        <span>{formatDollars(bounds.min)}</span>
        <span>{formatDollars(bounds.max)}</span>
      </div>
      <div className="relative w-full max-w-105 h-5" ref={trackRef}>
        <div className="absolute top-1/2 left-0 right-0 h-1 -translate-y-1/2 border-ink-thin" />
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 bg-(--color-ink)/60 rounded-full"
          style={{
            left: `${pct(live.min)}%`,
            width: `${Math.max(0, pct(live.max) - pct(live.min))}%`,
          }}
        />
        <div
          role="slider"
          tabIndex={0}
          aria-label="Minimum total spending"
          aria-valuemin={bounds.min}
          aria-valuemax={live.max}
          aria-valuenow={live.min}
          className="absolute top-1/2 w-4 h-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-(--color-ink) cursor-grab touch-none"
          style={{ left: `${pct(live.min)}%` }}
          onPointerDown={onHandlePointerDown("min")}
          onPointerMove={onHandlePointerMove}
          onPointerUp={onHandlePointerUp}
          onPointerCancel={onHandlePointerUp}
          onKeyDown={onHandleKeyDown("min")}
        />
        <div
          role="slider"
          tabIndex={0}
          aria-label="Maximum total spending"
          aria-valuemin={live.min}
          aria-valuemax={bounds.max}
          aria-valuenow={live.max}
          className="absolute top-1/2 w-4 h-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-(--color-ink) cursor-grab touch-none"
          style={{ left: `${pct(live.max)}%` }}
          onPointerDown={onHandlePointerDown("max")}
          onPointerMove={onHandlePointerMove}
          onPointerUp={onHandlePointerUp}
          onPointerCancel={onHandlePointerUp}
          onKeyDown={onHandleKeyDown("max")}
        />
      </div>

      <div className="flex justify-between w-full max-w-105 gap-4">
        <input
          aria-label="Minimum total spending amount"
          value={minText}
          onChange={(e) => setMinText(e.target.value)}
          onBlur={handleMinBlur}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          className="border-ink-thin bg-transparent px-2 py-1 text-xs w-1/2 text-center"
        />
        <input
          aria-label="Maximum total spending amount"
          value={maxText}
          onChange={(e) => setMaxText(e.target.value)}
          onBlur={handleMaxBlur}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          className="border-ink-thin bg-transparent px-2 py-1 text-xs w-1/2 text-center"
        />
      </div>
    </div>
  );
}
