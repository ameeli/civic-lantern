import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/mocks/server";
import { listReadyCycles } from "@/api/spending";

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
