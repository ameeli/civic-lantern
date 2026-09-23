import type { CandidateSpending, OfficeCode } from "@/types/spending";

export interface DollarRange {
  min: number;
  max: number;
}

export type CandidatesByOffice = Record<OfficeCode, CandidateSpending[]>;

export interface SpendingLeaf {
  name: string;
  value: number;
}

export interface CandidateNode {
  name: string;
  party: string | null;
  children: SpendingLeaf[];
}

export interface RaceNode {
  name: string;
  code: OfficeCode;
  /** Sum of every positive-spending candidate in this office, independent of `children`/`activeRange` — used to size the office bubble. */
  trueTotal: number;
  /** Only the candidates currently within the selected (or default) range. */
  children: CandidateNode[];
}

export interface HierarchyRoot {
  name: string;
  children: RaceNode[];
}

export const DEFAULT_MAX_NAMED_PER_OFFICE = 30;

const OFFICE_LABELS: Record<OfficeCode, string> = {
  P: "Presidential",
  S: "Senate",
  H: "House",
};

const OFFICE_CODES: OfficeCode[] = ["P", "S", "H"];

/** Positive-spending candidates, sorted by total_spending descending. */
export function getPositiveSortedSpenders(
  candidates: CandidateSpending[],
): CandidateSpending[] {
  return candidates
    .filter((c) => (c.total_spending ?? 0) > 0)
    .sort((a, b) => (b.total_spending ?? 0) - (a.total_spending ?? 0));
}

/** The absolute min/max total_spending across a (positive-sorted) roster, or null if empty. */
export function getOfficeBounds(
  sorted: CandidateSpending[],
): DollarRange | null {
  if (sorted.length === 0) return null;
  return {
    min: sorted[sorted.length - 1].total_spending ?? 0,
    max: sorted[0].total_spending ?? 0,
  };
}

/** The default slider range: [Nth-ranked candidate's spend (or the last, if fewer), top spend]. */
export function getDefaultRange(
  sorted: CandidateSpending[],
  maxNamed: number = DEFAULT_MAX_NAMED_PER_OFFICE,
): DollarRange | null {
  if (sorted.length === 0) return null;
  const cutoffIndex = Math.min(maxNamed, sorted.length) - 1;
  return {
    min: sorted[cutoffIndex].total_spending ?? 0,
    max: sorted[0].total_spending ?? 0,
  };
}

function toCandidateNode(c: CandidateSpending): CandidateNode {
  return {
    name: c.candidate?.name ?? c.candidate_id,
    party: c.candidate?.party ?? null,
    children: [
      { name: "Inside", value: c.inside_disbursements ?? 0 },
      { name: "Outside Support", value: c.outside_support ?? 0 },
      { name: "Outside Oppose", value: c.outside_oppose ?? 0 },
    ],
  };
}

export function transformToHierarchy(
  candidatesByOffice: CandidatesByOffice,
  activeRange?: { office: OfficeCode; range: DollarRange },
): HierarchyRoot {
  const toRaceNode = (office: OfficeCode): RaceNode => {
    const sorted = getPositiveSortedSpenders(candidatesByOffice[office] ?? []);
    const range =
      activeRange?.office === office
        ? activeRange.range
        : getDefaultRange(sorted);

    const visible = range
      ? sorted.filter((c) => {
          const spent = c.total_spending ?? 0;
          return spent >= range.min && spent <= range.max;
        })
      : [];

    const trueTotal = sorted.reduce(
      (sum, c) => sum + (c.total_spending ?? 0),
      0,
    );

    return {
      name: OFFICE_LABELS[office],
      code: office,
      trueTotal,
      children: visible.map(toCandidateNode),
    };
  };

  return {
    name: "root",
    children: OFFICE_CODES.map(toRaceNode),
  };
}
