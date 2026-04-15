import { apiFetch } from "./client";

interface ElectionSpending {
  cycle: number;
  candidate_count: number;
  total_inside_receipts: number | null;
  total_inside_disbursements: number | null;
  total_outside_support: number | null;
  total_outside_oppose: number | null;
  global_influence_ratio: number | null;
}

export function getElectionSpendings() {
  return apiFetch<ElectionSpending[]>("/elections/spending");
}

export function getElectionSpending(cycle: number) {
  return apiFetch<ElectionSpending>(`/elections/spending/${cycle}`);
}
