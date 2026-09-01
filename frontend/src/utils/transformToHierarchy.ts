import type { CandidateSpending } from "@/types/spending";

export interface SpendingLeaf {
  name: string;
  value: number;
  /** For the "Others" leaf: total_spending of the last named candidate, i.e. everything rolled up here is below this amount. */
  cutoff?: number;
}

export interface CandidateNode {
  name: string;
  party: string | null;
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

const DEFAULT_MAX_NAMED_PER_OFFICE = 20;

export function transformToHierarchy(
  candidates: CandidateSpending[],
  maxNamedPerOffice: number = DEFAULT_MAX_NAMED_PER_OFFICE,
): HierarchyRoot {
  const byOffice: Record<string, CandidateSpending[]> = {
    P: [],
    S: [],
    H: [],
  };

  for (const c of candidates) {
    const office = c.candidate?.office;
    if (!office || !(office in byOffice)) continue;
    byOffice[office].push(c);
  }

  const toCandidateNode = (c: CandidateSpending): CandidateNode => ({
    name: c.candidate?.name ?? c.candidate_id,
    party: c.candidate?.party ?? null,
    children: [
      { name: "Inside", value: c.inside_disbursements ?? 0 },
      { name: "Outside Support", value: c.outside_support ?? 0 },
      { name: "Outside Oppose", value: c.outside_oppose ?? 0 },
    ],
  });

  const toRaceNode = (office: string): RaceNode => {
    // Sort explicitly here rather than relying on the caller's incoming
    // sort order, so this function is correct and testable in isolation.
    const spenders = byOffice[office]
      .filter((c) => (c.total_spending ?? 0) > 0)
      .sort((a, b) => (b.total_spending ?? 0) - (a.total_spending ?? 0));

    const named = spenders.slice(0, maxNamedPerOffice);
    const beyondTopN = spenders.slice(maxNamedPerOffice);
    const nonPositive = byOffice[office].filter(
      (c) => (c.total_spending ?? 0) <= 0,
    );

    const othersTotal = [...beyondTopN, ...nonPositive].reduce(
      (sum, c) => sum + (c.total_spending ?? 0),
      0,
    );
    const lastNamed = named[named.length - 1];
    const othersLeaf: SpendingLeaf = {
      name: "Others",
      value: othersTotal,
      ...(lastNamed ? { cutoff: lastNamed.total_spending ?? 0 } : {}),
    };

    return {
      name: OFFICE_LABELS[office],
      children: [...named.map(toCandidateNode), othersLeaf],
    };
  };

  return {
    name: "root",
    children: ["P", "S", "H"].map(toRaceNode),
  };
}
