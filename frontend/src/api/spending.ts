import { cache } from "react";
import { apiFetch } from "./client";
import type { CandidateSpendingList, ElectionSpending } from "@/types/spending";

export const listElectionSpending = () => {
  return apiFetch<ElectionSpending[]>("/election-spending");
};

export const getElectionSpendingByCycle = cache((cycle: number) => {
  return apiFetch<ElectionSpending>(`/election-spending/${cycle}`);
});

export const listCandidatesSpending = () => {
  return apiFetch<CandidateSpendingList>("/candidate-spending");
};
