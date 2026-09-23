import { describe, it, expect } from "vitest";
import {
  transformToHierarchy,
  getPositiveSortedSpenders,
  getOfficeBounds,
  getDefaultRange,
  type CandidatesByOffice,
  type RaceNode,
  type CandidateNode,
} from "@/utils/transformToHierarchy";
import type { CandidateSpending, OfficeCode } from "@/types/spending";

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
    makeCandidate(`${office}${i}`, office, {
      inside: totalSpending,
      totalSpending,
    }),
  );
}

function byOffice(partial: Partial<CandidatesByOffice>): CandidatesByOffice {
  return { P: [], S: [], H: [], ...partial };
}

function namedChildren(race: RaceNode): CandidateNode[] {
  return race.children;
}

describe("transformToHierarchy", () => {
  it("always produces three race nodes in order: Presidential, Senate, House", () => {
    const result = transformToHierarchy(byOffice({}));
    expect(result.name).toBe("root");
    expect(result.children.map((r) => r.name)).toEqual([
      "Presidential",
      "Senate",
      "House",
    ]);
    expect(result.children.map((r) => r.code)).toEqual(["P", "S", "H"]);
  });

  it("names a single positive-spending candidate", () => {
    const candidate = makeCandidate("C001", "P", { totalSpending: 100 });
    const result = transformToHierarchy(byOffice({ P: [candidate] }));
    const named = namedChildren(result.children[0]);
    expect(named).toHaveLength(1);
    expect(named[0].name).toBe("C001");
  });

  it("defaults to the top DEFAULT_MAX_NAMED_PER_OFFICE candidates when no activeRange is given", () => {
    const spends = Array.from({ length: 50 }, (_, i) => 5000 - i * 10);
    const candidates = makeCandidatesForOffice("H", spends);
    const result = transformToHierarchy(byOffice({ H: candidates }));
    const house = result.children[2];
    const named = namedChildren(house);
    expect(named).toHaveLength(30);
    expect(named.map((c) => c.name)).toEqual(
      Array.from({ length: 30 }, (_, i) => `H${i}`),
    );
  });

  it("respects an explicit activeRange for the matching office", () => {
    const spends = [500, 400, 300, 200, 100];
    const candidates = makeCandidatesForOffice("H", spends);
    const result = transformToHierarchy(byOffice({ H: candidates }), {
      office: "H",
      range: { min: 200, max: 400 },
    });
    const house = result.children[2];
    const named = namedChildren(house);
    expect(named.map((c) => c.name)).toEqual(["H1", "H2", "H3"]);
  });

  it("range boundaries are inclusive on both ends", () => {
    const spends = [500, 400, 300, 200, 100];
    const candidates = makeCandidatesForOffice("H", spends);
    const result = transformToHierarchy(byOffice({ H: candidates }), {
      office: "H",
      range: { min: 200, max: 400 },
    });
    const named = namedChildren(result.children[2]);
    expect(named.map((c) => c.name)).toContain("H1"); // exactly at max
    expect(named.map((c) => c.name)).toContain("H3"); // exactly at min
  });

  it("an activeRange for a different office doesn't affect this office's default", () => {
    const spends = Array.from({ length: 40 }, (_, i) => 5000 - i * 10);
    const candidates = makeCandidatesForOffice("H", spends);
    const result = transformToHierarchy(byOffice({ H: candidates }), {
      office: "S",
      range: { min: 0, max: 1 },
    });
    const house = result.children[2];
    expect(namedChildren(house)).toHaveLength(30);
  });

  it("never names a candidate with total_spending <= 0, even inside the selected range", () => {
    const candidates = [
      makeCandidate("P1", "P", { totalSpending: 500_000 }),
      makeCandidate("P2", "P", { totalSpending: 0 }),
      makeCandidate("P3", "P", { totalSpending: -100 }),
    ];
    const result = transformToHierarchy(byOffice({ P: candidates }), {
      office: "P",
      range: { min: -1000, max: 1_000_000 },
    });
    const named = namedChildren(result.children[0]);
    expect(named.map((c) => c.name)).toEqual(["P1"]);
  });

  it("trueTotal always reflects every positive-spending candidate, regardless of activeRange", () => {
    const spends = [500, 400, 300, 200, 100];
    const candidates = makeCandidatesForOffice("H", spends);
    const trueTotal = spends.reduce((a, b) => a + b, 0);

    const full = transformToHierarchy(byOffice({ H: candidates }), {
      office: "H",
      range: { min: 100, max: 500 },
    }).children[2];
    expect(full.trueTotal).toBe(trueTotal);
    expect(namedChildren(full)).toHaveLength(5);

    const narrowed = transformToHierarchy(byOffice({ H: candidates }), {
      office: "H",
      range: { min: 200, max: 400 },
    }).children[2];
    // trueTotal is unaffected by narrowing the visible range...
    expect(narrowed.trueTotal).toBe(trueTotal);
    // ...even though fewer candidates are actually rendered.
    expect(namedChildren(narrowed)).toHaveLength(3);
  });

  it("trueTotal excludes non-positive spenders, same as the visible candidates do", () => {
    const candidates = [
      makeCandidate("P1", "P", { totalSpending: 500_000 }),
      makeCandidate("P2", "P", { totalSpending: 0 }),
      makeCandidate("P3", "P", { totalSpending: -100 }),
    ];
    const result = transformToHierarchy(byOffice({ P: candidates }));
    expect(result.children[0].trueTotal).toBe(500_000);
  });

  it("named candidate node has exactly three leaves: Inside, Outside Support, Outside Oppose", () => {
    const candidate = makeCandidate("C004", "H", {
      outsideSupport: 800_000,
      outsideOppose: 300_000,
      inside: 50_000,
    });
    const result = transformToHierarchy(byOffice({ H: [candidate] }));
    const named = namedChildren(result.children[2]).find(
      (c) => c.name === "C004",
    );
    expect(named).toBeDefined();
    expect(named!.children.map((l) => l.name)).toEqual([
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
    const result = transformToHierarchy(byOffice({ P: [candidate] }));
    const named = namedChildren(result.children[0]).find(
      (c) => c.name === "C005",
    );
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

  it("keeps tied candidates in stable input order (Array.sort is stable)", () => {
    const candidates = makeCandidatesForOffice("H", [500, 500, 500]);
    const result = transformToHierarchy(byOffice({ H: candidates }), {
      office: "H",
      range: { min: 500, max: 500 },
    });
    const named = namedChildren(result.children[2]);
    expect(named.map((c) => c.name)).toEqual(["H0", "H1", "H2"]);
  });
});

describe("getPositiveSortedSpenders", () => {
  it("filters out non-positive spending and sorts descending", () => {
    const candidates = [
      makeCandidate("A", "H", { totalSpending: 100 }),
      makeCandidate("B", "H", { totalSpending: 0 }),
      makeCandidate("C", "H", { totalSpending: 300 }),
      makeCandidate("D", "H", { totalSpending: -50 }),
    ];
    const sorted = getPositiveSortedSpenders(candidates);
    expect(sorted.map((c) => c.candidate_id)).toEqual(["C", "A"]);
  });
});

describe("getOfficeBounds", () => {
  it("returns the min and max of a sorted positive roster", () => {
    const sorted = getPositiveSortedSpenders(
      makeCandidatesForOffice("H", [500, 300, 100]),
    );
    expect(getOfficeBounds(sorted)).toEqual({ min: 100, max: 500 });
  });

  it("returns null for an empty roster", () => {
    expect(getOfficeBounds([])).toBeNull();
  });
});

describe("getDefaultRange", () => {
  it("uses the Nth-ranked candidate's spend as the min, and the top spend as max", () => {
    const sorted = getPositiveSortedSpenders(
      makeCandidatesForOffice("H", [500, 400, 300, 200, 100]),
    );
    expect(getDefaultRange(sorted, 3)).toEqual({ min: 300, max: 500 });
  });

  it("uses the last candidate's spend as min when there are fewer than N", () => {
    const sorted = getPositiveSortedSpenders(
      makeCandidatesForOffice("H", [500, 400]),
    );
    expect(getDefaultRange(sorted, 30)).toEqual({ min: 400, max: 500 });
  });

  it("returns null for an empty roster", () => {
    expect(getDefaultRange([], 30)).toBeNull();
  });
});

describe("office code coverage", () => {
  it("each office code produces its own labeled race node", () => {
    const codes: OfficeCode[] = ["P", "S", "H"];
    const result = transformToHierarchy(byOffice({}));
    codes.forEach((code, i) => {
      expect(result.children[i].code).toBe(code);
    });
  });
});
