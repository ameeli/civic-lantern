import { cache } from "react";
import { apiFetch } from "./client";
import type {
  CandidateSpending,
  CandidateSpendingList,
  CandidateSpendingParams,
  ElectionSpending,
  OfficeCode,
} from "@/types/spending";

export const listElectionSpending = () => {
  return apiFetch<ElectionSpending[]>("/election-spending");
};

/** Cycles where every spending ingestor has succeeded, newest first. */
export const listReadyCycles = () => {
  return apiFetch<number[]>("/election-spending/cycles");
};

export const getElectionSpendingByCycle = cache((cycle: number) => {
  return apiFetch<ElectionSpending>(`/election-spending/${cycle}`);
});

export const listCandidatesSpending = (
  params: CandidateSpendingParams = {},
) => {
  const query = new URLSearchParams();
  if (params.cycle !== undefined) query.set("cycle", String(params.cycle));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.sort_by !== undefined) query.set("sort_by", params.sort_by);
  if (params.order !== undefined) query.set("order", params.order);
  if (params.office !== undefined) query.set("office", params.office);
  const qs = query.toString();
  return apiFetch<CandidateSpendingList>(
    `/candidate-spending${qs ? `?${qs}` : ""}`,
  );
};

/** Fetches every positive-spending candidate for one office, paginating until complete. */
export const fetchAllCandidatesForOffice = async (
  cycle: number,
  office: OfficeCode,
): Promise<CandidateSpending[]> => {
  const limit = 1000;
  const all: CandidateSpending[] = [];
  let offset = 0;

  while (true) {
    const { items, total_count } = await listCandidatesSpending({
      cycle,
      office,
      sort_by: "total_spending",
      order: "desc",
      limit,
      offset,
    });
    all.push(...items);
    offset += items.length;
    if (items.length === 0 || all.length >= total_count) break;
  }

  return all;
};
