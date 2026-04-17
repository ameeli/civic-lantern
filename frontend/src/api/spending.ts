import { cache } from "react";
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

export const listElectionSpending = () => {
  return apiFetch<ElectionSpending[]>("/election-spending");
};

export const getElectionSpendingByCycle = cache((cycle: number) => {
  return apiFetch<ElectionSpending>(`/election-spending/${cycle}`);
});

export const getCandidatesSpendings = () => {};
