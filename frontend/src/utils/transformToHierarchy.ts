import type { CandidateSpending } from "@/types/spending";

export interface SpendingLeaf {
  name: string;
  value: number;
}

export interface CandidateNode {
  name: string;
  children: SpendingLeaf[];
}

export interface RaceNode {
  name: string;
  children: (CandidateNode | SpendingLeaf)[];
}

export interface HierarchyRoot {
  name: string;
  children: RaceNode[];
}

const OFFICE_LABELS: Record<string, string> = {
  P: "Presidential",
  S: "Senate",
  H: "House",
};

export function transformToHierarchy(
  candidates: CandidateSpending[],
  threshold: number,
): HierarchyRoot {
  const aboveThreshold: Record<string, CandidateSpending[]> = {
    P: [],
    S: [],
    H: [],
  };
  const belowThreshold: Record<string, number> = { P: 0, S: 0, H: 0 };

  for (const c of candidates) {
    const office = c.candidate?.office;
    if (!office || !(office in aboveThreshold)) continue;

    const outsideTotal = (c.outside_support ?? 0) + (c.outside_oppose ?? 0);
    if (outsideTotal >= threshold) {
      aboveThreshold[office].push(c);
    } else {
      belowThreshold[office] += (c.inside_disbursements ?? 0) + outsideTotal;
    }
  }

  const toCandidateNode = (c: CandidateSpending): CandidateNode => ({
    name: c.candidate?.name ?? c.candidate_id,
    children: [
      { name: "Inside", value: c.inside_disbursements ?? 0 },
      { name: "Outside Support", value: c.outside_support ?? 0 },
      { name: "Outside Oppose", value: c.outside_oppose ?? 0 },
    ],
  });

  const toRaceNode = (office: string): RaceNode => ({
    name: OFFICE_LABELS[office],
    children: [
      ...aboveThreshold[office].map(toCandidateNode),
      { name: "Others", value: belowThreshold[office] },
    ],
  });

  return {
    name: "root",
    children: ["P", "S", "H"].map(toRaceNode),
  };
}
