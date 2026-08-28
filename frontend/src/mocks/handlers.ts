import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("*/election-spending/cycles", () =>
    HttpResponse.json([2026, 2024]),
  ),
];
