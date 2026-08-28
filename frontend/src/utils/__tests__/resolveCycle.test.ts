import { describe, it, expect } from "vitest";
import { resolveCycle } from "@/utils/resolveCycle";

describe("resolveCycle", () => {
  it("returns the requested cycle when it's ready", () => {
    expect(resolveCycle("2024", [2026, 2024])).toBe(2024);
  });

  it("falls back to the newest ready cycle when no param is present", () => {
    expect(resolveCycle(undefined, [2026, 2024])).toBe(2026);
  });

  it("falls back when the requested cycle is structurally valid but not ready", () => {
    expect(resolveCycle("2022", [2026, 2024])).toBe(2026);
  });

  it("falls back when the requested value is non-numeric garbage", () => {
    expect(resolveCycle("not-a-cycle", [2026, 2024])).toBe(2026);
  });

  it("falls back when the param is an array (repeated query key)", () => {
    expect(resolveCycle(["2024", "2026"], [2026, 2024])).toBe(2026);
  });

  it("returns undefined when there are no ready cycles at all", () => {
    expect(resolveCycle("2024", [])).toBeUndefined();
    expect(resolveCycle(undefined, [])).toBeUndefined();
  });

  it("falls back on an empty string rather than coercing it to 0", () => {
    expect(resolveCycle("", [2026, 2024])).toBe(2026);
  });

  it("falls back on a whitespace-only string", () => {
    expect(resolveCycle("   ", [2026, 2024])).toBe(2026);
  });

  it("falls back on a value with leading/trailing whitespace or a sign", () => {
    expect(resolveCycle(" 2024 ", [2026, 2024])).toBe(2026);
    expect(resolveCycle("+2024", [2026, 2024])).toBe(2026);
  });
});
