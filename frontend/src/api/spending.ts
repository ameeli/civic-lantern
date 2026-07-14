import { cache } from "react";
import { apiFetch } from "./client";
import type {
  CandidateSpendingList,
  CandidateSpendingParams,
  ElectionSpending,
} from "@/types/spending";

export const listElectionSpending = () => {
  return apiFetch<ElectionSpending[]>("/election-spending");
};

export const getElectionSpendingByCycle = cache((cycle: number) => {
  return apiFetch<ElectionSpending>(`/election-spending/${cycle}`);
});

export const listCandidatesSpending = (params: CandidateSpendingParams = {}) => {
  const query = new URLSearchParams();
  if (params.cycle !== undefined) query.set("cycle", String(params.cycle));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.sort_by !== undefined) query.set("sort_by", params.sort_by);
  if (params.order !== undefined) query.set("order", params.order);
  const qs = query.toString();
  return apiFetch<CandidateSpendingList>(
    `/candidate-spending${qs ? `?${qs}` : ""}`,
  );
};
