"use client";

import { useRef, useState } from "react";
import type { DollarRange } from "@/utils/transformToHierarchy";
import {
  formatDollars,
  formatDollarsFull,
  parseDollarInput,
} from "@/utils/formatDollars";

export function isValidMin(v: number, max: number, rangeMin: number): boolean {
  return v >= rangeMin && v < max;
}

export function isValidMax(v: number, min: number, rangeMax: number): boolean {
  return v > min && v <= rangeMax;
}

export function clampMin(v: number, max: number, rangeMin: number): number {
  return Math.min(Math.max(v, rangeMin), max - 1);
}

export function clampMax(v: number, min: number, rangeMax: number): number {
  return Math.max(Math.min(v, rangeMax), min + 1);
}

interface CandidateRangeSliderProps {
  /** Absolute min/max total_spending for this office — the slider's fixed track bounds. */
  bounds: DollarRange;
  /** Initial handle positions. Treated as init-only; parent remounts this component (via `key`) to change it. */
  value: DollarRange;
  /** Every positive total_spending value for this office, used to compute the live count. */
  candidateSpends: number[];
  /** Fires on drag-release, discrete keyboard steps, and valid/snapped input-box commits — never on every drag tick. */
  onCommit: (range: DollarRange) => void;
}

export default function CandidateRangeSlider({
  bounds,
  value,
  candidateSpends,
  onCommit,
}: CandidateRangeSliderProps) {
  const [live, setLive] = useState<DollarRange>(value);
  const liveRef = useRef<DollarRange>(value);
  const draggingRef = useRef<"min" | "max" | null>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  const [minText, setMinText] = useState(formatDollarsFull(value.min));
  const [maxText, setMaxText] = useState(formatDollarsFull(value.max));

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
    setLiveRange(next);
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
      const next: DollarRange =
        handle === "min"
          ? {
              min: clampMin(current.min + delta, current.max, bounds.min),
              max: current.max,
            }
          : {
              min: current.min,
              max: clampMax(current.max + delta, current.min, bounds.max),
            };
      setLiveRange(next);
      onCommit(next);
    };
  }

  function handleMinChange(e: React.ChangeEvent<HTMLInputElement>) {
    const text = e.target.value;
    setMinText(text);
    const parsed = parseDollarInput(text);
    if (
      parsed !== null &&
      isValidMin(parsed, liveRef.current.max, bounds.min)
    ) {
      const next = { min: parsed, max: liveRef.current.max };
      liveRef.current = next;
      setLive(next);
      onCommit(next);
    }
  }

  function handleMinBlur() {
    const parsed = parseDollarInput(minText);
    const snapped =
      parsed === null
        ? liveRef.current.min
        : clampMin(parsed, liveRef.current.max, bounds.min);
    const next = { min: snapped, max: liveRef.current.max };
    setLiveRange(next);
    onCommit(next);
  }

  function handleMaxChange(e: React.ChangeEvent<HTMLInputElement>) {
    const text = e.target.value;
    setMaxText(text);
    const parsed = parseDollarInput(text);
    if (
      parsed !== null &&
      isValidMax(parsed, liveRef.current.min, bounds.max)
    ) {
      const next = { min: liveRef.current.min, max: parsed };
      liveRef.current = next;
      setLive(next);
      onCommit(next);
    }
  }

  function handleMaxBlur() {
    const parsed = parseDollarInput(maxText);
    const snapped =
      parsed === null
        ? liveRef.current.max
        : clampMax(parsed, liveRef.current.min, bounds.max);
    const next = { min: liveRef.current.min, max: snapped };
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
          onChange={handleMinChange}
          onBlur={handleMinBlur}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleMinBlur();
              e.currentTarget.blur();
            }
          }}
          className="border-ink-thin bg-transparent px-2 py-1 text-xs w-1/2 text-center"
        />
        <input
          aria-label="Maximum total spending amount"
          value={maxText}
          onChange={handleMaxChange}
          onBlur={handleMaxBlur}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleMaxBlur();
              e.currentTarget.blur();
            }
          }}
          className="border-ink-thin bg-transparent px-2 py-1 text-xs w-1/2 text-center"
        />
      </div>
    </div>
  );
}
