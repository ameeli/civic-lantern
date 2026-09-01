import { describe, it, expect } from "vitest";
import { transformToHierarchy } from "@/utils/transformToHierarchy";
import type { CandidateSpending } from "@/types/spending";

const MAX_NAMED = 20;

interface MakeCandidateOptions {
  outsideSupport?: number;
  outsideOppose?: number;
  inside?: number;
  totalSpending?: number;
}

function makeCandidate(
  id: string,
  office: string | null,
  options: MakeCandidateOptions = {},
): CandidateSpending {
  const {
    outsideSupport = 0,
    outsideOppose = 0,
    inside = 0,
    totalSpending = inside + outsideSupport + outsideOppose,
  } = options;

  return {
    candidate_id: id,
    cycle: 2024,
    inside_receipts: null,
    inside_disbursements: inside,
    outside_support: outsideSupport,
    outside_oppose: outsideOppose,
    total_spending: totalSpending,
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

/** Builds candidates for `office`, one per entry in `spends`, named `${office}0`, `${office}1`, ... in input order. */
function makeCandidatesForOffice(
  office: string,
  spends: number[],
): CandidateSpending[] {
  return spends.map((totalSpending, i) =>
    makeCandidate(`${office}${i}`, office, { totalSpending }),
  );
}

describe("transformToHierarchy", () => {
  it("always produces three race nodes in order: Presidential, Senate, House", () => {
    const result = transformToHierarchy([], MAX_NAMED);
    expect(result.name).toBe("root");
    expect(result.children.map((r) => r.name)).toEqual([
      "Presidential",
      "Senate",
      "House",
    ]);
  });

  it("names a single positive-spending candidate", () => {
    const candidate = makeCandidate("C001", "P", { totalSpending: 100 });
    const result = transformToHierarchy([candidate], MAX_NAMED);
    const presidential = result.children[0];
    const named = presidential.children.filter((c) => "children" in c);
    expect(named).toHaveLength(1);
    expect(named[0].name).toBe("C001");
  });

  it("names only the top N candidates per office, rolling the rest into Others", () => {
    const maxNamed = 3;
    const spends = [500, 400, 300, 200, 100];
    const candidates = makeCandidatesForOffice("H", spends);
    const result = transformToHierarchy(candidates, maxNamed);
    const house = result.children[2];

    const named = house.children.filter((c) => "children" in c);
    expect(named.map((c) => c.name)).toEqual(["H0", "H1", "H2"]);

    const others = house.children.find((c) => c.name === "Others");
    expect(others).toBeDefined();
    expect((others as { value: number }).value).toBe(200 + 100);
  });

  it("bounds named circles to N regardless of how many total candidates an office has", () => {
    const spends = Array.from({ length: 50 }, (_, i) => 5000 - i * 10);
    const candidates = makeCandidatesForOffice("H", spends);
    const result = transformToHierarchy(candidates, MAX_NAMED);
    const house = result.children[2];
    const named = house.children.filter((c) => "children" in c);
    expect(named).toHaveLength(MAX_NAMED);
  });

  it("never names a candidate with total_spending <= 0, even with fewer than N candidates in the office", () => {
    const candidates = [
      makeCandidate("P1", "P", { totalSpending: 500_000 }),
      makeCandidate("P2", "P", { totalSpending: 0 }),
      makeCandidate("P3", "P", { totalSpending: -100 }),
    ];
    const result = transformToHierarchy(candidates, MAX_NAMED);
    const presidential = result.children[0];

    const named = presidential.children.filter((c) => "children" in c);
    expect(named.map((c) => c.name)).toEqual(["P1"]);

    const others = presidential.children.find((c) => c.name === "Others");
    expect((others as { value: number }).value).toBe(0 + -100);
  });

  it("rolls below-threshold and zero/negative spending into Others value", () => {
    const candidates = [
      makeCandidate("S1", "S", { totalSpending: 350_000 }),
      makeCandidate("S2", "S", { totalSpending: 0 }),
    ];
    const result = transformToHierarchy(candidates, 1);
    const senate = result.children[1];

    const named = senate.children.filter((c) => "children" in c);
    expect(named.map((c) => c.name)).toEqual(["S1"]);

    const others = senate.children.find((c) => c.name === "Others");
    expect(others).toBeDefined();
    expect((others as { value: number }).value).toBe(0);
  });

  it("keeps tied candidates in stable input order (Array.sort is stable)", () => {
    const maxNamed = 2;
    const candidates = makeCandidatesForOffice("H", [500, 500, 500]);
    const result = transformToHierarchy(candidates, maxNamed);
    const house = result.children[2];

    const named = house.children.filter((c) => "children" in c);
    expect(named.map((c) => c.name)).toEqual(["H0", "H1"]);

    const others = house.children.find((c) => c.name === "Others");
    expect((others as { value: number }).value).toBe(500);
  });

  it("named candidate node has exactly three leaves: Inside, Outside Support, Outside Oppose", () => {
    const candidate = makeCandidate("C004", "H", {
      outsideSupport: 800_000,
      outsideOppose: 300_000,
      inside: 50_000,
    });
    const result = transformToHierarchy([candidate], MAX_NAMED);
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
    const candidate = makeCandidate("C005", "P", {
      outsideSupport: 700_000,
      outsideOppose: 500_000,
      inside: 80_000,
    });
    const result = transformToHierarchy([candidate], MAX_NAMED);
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
    const candidate = makeCandidate("C006", null, { totalSpending: 2_000_000 });
    const result = transformToHierarchy([candidate], MAX_NAMED);
    for (const race of result.children) {
      const named = race.children.filter((c) => "children" in c);
      expect(named).toHaveLength(0);
    }
  });

  it("skips candidates with an unrecognised office code", () => {
    const candidate = makeCandidate("C007", "X", { totalSpending: 2_000_000 });
    const result = transformToHierarchy([candidate], MAX_NAMED);
    for (const race of result.children) {
      const named = race.children.filter((c) => "children" in c);
      expect(named).toHaveLength(0);
    }
  });
});
