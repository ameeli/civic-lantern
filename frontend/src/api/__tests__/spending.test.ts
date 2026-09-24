import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/mocks/server";
import { fetchAllCandidatesForOffice, listReadyCycles } from "@/api/spending";
import type { CandidateSpending } from "@/types/spending";

describe("listReadyCycles", () => {
  it("returns the ready cycles from the default handler", async () => {
    const result = await listReadyCycles();
    expect(result).toEqual([2026, 2024]);
  });

  it("returns an empty list when no cycles are ready yet", async () => {
    server.use(
      http.get("*/election-spending/cycles", () => HttpResponse.json([])),
    );

    const result = await listReadyCycles();
    expect(result).toEqual([]);
  });
});

function makeCandidate(id: string): CandidateSpending {
  return {
    candidate_id: id,
    cycle: 2024,
    inside_receipts: null,
    inside_disbursements: 100,
    outside_support: 0,
    outside_oppose: 0,
    total_spending: 100,
    influence_ratio: null,
    vulnerability_factor: null,
    candidate: null,
  };
}

describe("fetchAllCandidatesForOffice", () => {
  it("returns everything in one request when total_count fits in a single page", async () => {
    const items = [makeCandidate("A"), makeCandidate("B")];
    server.use(
      http.get("*/candidate-spending", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("office")).toBe("S");
        return HttpResponse.json({
          items,
          total_count: items.length,
          limit: 1000,
          offset: 0,
        });
      }),
    );

    const result = await fetchAllCandidatesForOffice(2024, "S");
    expect(result.map((c) => c.candidate_id)).toEqual(["A", "B"]);
  });

  it("loops on offset until total_count is reached", async () => {
    const page1 = [makeCandidate("A"), makeCandidate("B")];
    const page2 = [makeCandidate("C")];
    const handler = vi.fn(({ request }: { request: Request }) => {
      const offset = Number(new URL(request.url).searchParams.get("offset"));
      const items = offset === 0 ? page1 : page2;
      return HttpResponse.json({ items, total_count: 3, limit: 2, offset });
    });
    server.use(http.get("*/candidate-spending", handler));

    const result = await fetchAllCandidatesForOffice(2024, "H");
    expect(result.map((c) => c.candidate_id)).toEqual(["A", "B", "C"]);
    expect(handler).toHaveBeenCalledTimes(2);
  });

  it("stops if a page comes back empty, even if total_count claims more", async () => {
    server.use(
      http.get("*/candidate-spending", () =>
        HttpResponse.json({
          items: [],
          total_count: 10,
          limit: 1000,
          offset: 0,
        }),
      ),
    );

    const result = await fetchAllCandidatesForOffice(2024, "P");
    expect(result).toEqual([]);
  });
});
