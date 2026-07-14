export interface ElectionSpending {
  cycle: number;
  candidate_count: number;
  total_inside_receipts: number | null;
  total_inside_disbursements: number | null;
  total_outside_support: number | null;
  total_outside_oppose: number | null;
  global_influence_ratio: number | null;
}

export interface CandidateInfo {
  candidate_id: string;
  name: string | null;
  state: string | null;
  office: string | null;
  district: string | null;
  party: string | null;
  incumbent_challenge: string | null;
}

export interface CandidateSpending {
  candidate_id: string;
  cycle: number;
  inside_receipts: number | null;
  inside_disbursements: number | null;
  outside_support: number | null;
  outside_oppose: number | null;
  influence_ratio: number | null;
  vulnerability_factor: number | null;
  candidate: CandidateInfo | null;
}

export interface CandidateSpendingList {
  items: CandidateSpending[];
  total_count: number;
  limit: number;
  offset: number;
}

export type SpendingSortBy =
  | "cycle"
  | "inside_receipts"
  | "inside_disbursements"
  | "outside_support"
  | "outside_oppose"
  | "outside_total"
  | "influence_ratio"
  | "vulnerability_factor";

export interface CandidateSpendingParams {
  cycle?: number;
  limit?: number;
  offset?: number;
  sort_by?: SpendingSortBy;
  order?: "asc" | "desc";
}
