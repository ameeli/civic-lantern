import { describe, it, expect } from "vitest";
import { transformToHierarchy } from "@/utils/transformToHierarchy";
import type { CandidateSpending } from "@/types/spending";

const THRESHOLD = 1_000_000;

function makeCandidate(
  id: string,
  office: string | null,
  outsideSupport: number,
  outsideOppose: number,
  inside: number,
): CandidateSpending {
  return {
    candidate_id: id,
    cycle: 2024,
    inside_receipts: null,
    inside_disbursements: inside,
    outside_support: outsideSupport,
    outside_oppose: outsideOppose,
    influence_ratio: null,
    vulnerability_factor: null,
    candidate: office
      ? {
          candidate_id: id,
          name: id,
          state: null,
          office,
          district: null,
          party: null,
          incumbent_challenge: null,
        }
      : null,
  };
}

describe("transformToHierarchy", () => {
  it("always produces three race nodes in order: Presidential, Senate, House", () => {
    const result = transformToHierarchy([], THRESHOLD);
    expect(result.name).toBe("root");
    expect(result.children.map((r) => r.name)).toEqual([
      "Presidential",
      "Senate",
      "House",
    ]);
  });

  it("places an above-threshold candidate as a named node", () => {
    const candidate = makeCandidate("C001", "P", 600_000, 600_000, 100_000);
    const result = transformToHierarchy([candidate], THRESHOLD);
    const presidential = result.children[0];
    const named = presidential.children.filter((c) => "children" in c);
    expect(named).toHaveLength(1);
    expect(named[0].name).toBe("C001");
  });

  it("does not place a below-threshold candidate as a named node", () => {
    const candidate = makeCandidate("C002", "P", 400_000, 400_000, 100_000);
    const result = transformToHierarchy([candidate], THRESHOLD);
    const presidential = result.children[0];
    const named = presidential.children.filter((c) => "children" in c);
    expect(named).toHaveLength(0);
  });

  it("rolls below-threshold spending into Others value", () => {
    const candidate = makeCandidate("C003", "S", 200_000, 100_000, 50_000);
    const result = transformToHierarchy([candidate], THRESHOLD);
    const senate = result.children[1];
    const others = senate.children.find((c) => c.name === "Others");
    // Others value = inside + outside_support + outside_oppose
    expect(others).toBeDefined();
    expect((others as { value: number }).value).toBe(350_000);
  });

  it("named candidate node has exactly three leaves: Inside, Outside Support, Outside Oppose", () => {
    const candidate = makeCandidate("C004", "H", 800_000, 300_000, 50_000);
    const result = transformToHierarchy([candidate], THRESHOLD);
    const house = result.children[2];
    const named = house.children.find(
      (c) => "children" in c && c.name === "C004",
    );
    expect(named).toBeDefined();
    const leaves = (named as { children: { name: string }[] }).children;
    expect(leaves.map((l) => l.name)).toEqual([
      "Inside",
      "Outside Support",
      "Outside Oppose",
    ]);
  });

  it("leaf values match the candidate spending fields", () => {
    const candidate = makeCandidate("C005", "P", 700_000, 500_000, 80_000);
    const result = transformToHierarchy([candidate], THRESHOLD);
    const presidential = result.children[0];
    const named = presidential.children.find(
      (c) => "children" in c && c.name === "C005",
    ) as { children: { name: string; value: number }[] } | undefined;
    expect(named).toBeDefined();
    expect(named!.children.find((l) => l.name === "Inside")!.value).toBe(
      80_000,
    );
    expect(
      named!.children.find((l) => l.name === "Outside Support")!.value,
    ).toBe(700_000);
    expect(
      named!.children.find((l) => l.name === "Outside Oppose")!.value,
    ).toBe(500_000);
  });

  it("skips candidates with null office", () => {
    const candidate = makeCandidate("C006", null, 2_000_000, 0, 0);
    const result = transformToHierarchy([candidate], THRESHOLD);
    for (const race of result.children) {
      const named = race.children.filter((c) => "children" in c);
      expect(named).toHaveLength(0);
    }
  });

  it("skips candidates with an unrecognised office code", () => {
    const candidate = makeCandidate("C007", "X", 2_000_000, 0, 0);
    const result = transformToHierarchy([candidate], THRESHOLD);
    for (const race of result.children) {
      const named = race.children.filter((c) => "children" in c);
      expect(named).toHaveLength(0);
    }
  });
});
