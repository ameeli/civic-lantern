import { describe, it, expect } from "vitest";
import {
  clampMin,
  clampMax,
  clampRangeToMaxCandidates,
} from "@/components/CandidateRangeSlider.utils";

describe("slider validation helpers", () => {
  it("clampMin/clampMax snap to the nearest violated boundary", () => {
    expect(clampMin(-5, 100, 0)).toBe(0);
    expect(clampMin(150, 100, 0)).toBe(99);
    expect(clampMax(500, 100, 200)).toBe(200);
    expect(clampMax(50, 100, 200)).toBe(101);
  });
});

describe("clampRangeToMaxCandidates", () => {
  // 300 distinct values, descending: [300, 299, ..., 1]
  const sortedDesc = Array.from({ length: 300 }, (_, i) => 300 - i);

  it("returns the range unchanged when the count is already within the cap", () => {
    const range = { min: 250, max: 300 }; // 51 candidates
    expect(clampRangeToMaxCandidates(range, "min", sortedDesc, 200)).toEqual(
      range,
    );
  });

  it("pulls max down when driven by min and the count exceeds the cap", () => {
    const range = { min: 1, max: 300 }; // all 300
    const result = clampRangeToMaxCandidates(range, "min", sortedDesc, 200);
    expect(result).toEqual({ min: 1, max: 200 });
    const count = sortedDesc.filter(
      (v) => v >= result.min && v <= result.max,
    ).length;
    expect(count).toBe(200);
  });

  it("pulls min up when driven by max and the count exceeds the cap", () => {
    const range = { min: 1, max: 300 }; // all 300
    const result = clampRangeToMaxCandidates(range, "max", sortedDesc, 200);
    expect(result).toEqual({ min: 101, max: 300 });
    const count = sortedDesc.filter(
      (v) => v >= result.min && v <= result.max,
    ).length;
    expect(count).toBe(200);
  });

  it("respects a custom maxCandidates value", () => {
    const range = { min: 1, max: 300 };
    const result = clampRangeToMaxCandidates(range, "min", sortedDesc, 50);
    expect(result).toEqual({ min: 1, max: 50 });
  });

  it("never inverts the range when values are tied at the boundary", () => {
    const ties = Array.from({ length: 300 }, () => 100);
    const range = { min: 100, max: 100 };
    const result = clampRangeToMaxCandidates(range, "min", ties, 50);
    expect(result.min).toBeLessThan(result.max);
  });
});
