import { describe, it, expect } from "vitest";
import { formatDollarsFull } from "@/utils/formatDollars";

describe("formatDollarsFull", () => {
  it("formats non-negative values as whole comma-separated dollars", () => {
    expect(formatDollarsFull(0)).toBe("$0");
    expect(formatDollarsFull(0.5)).toBe("$1");
    expect(formatDollarsFull(999.5)).toBe("$1,000");
    expect(formatDollarsFull(19_000_000)).toBe("$19,000,000");
    expect(formatDollarsFull(5_627_371_073.69)).toBe("$5,627,371,074");
  });

  it("places the minus sign before the dollar sign for negative values", () => {
    expect(formatDollarsFull(-5)).toBe("-$5");
    expect(formatDollarsFull(-1_234_567)).toBe("-$1,234,567");
  });

  it("rounds negative half-dollar values away from zero", () => {
    expect(formatDollarsFull(-0.5)).toBe("-$1");
    expect(formatDollarsFull(-1.5)).toBe("-$2");
    expect(formatDollarsFull(-1_234_567.5)).toBe("-$1,234,568");
  });
});
