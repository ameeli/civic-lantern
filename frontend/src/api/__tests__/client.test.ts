import { afterEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/mocks/server";
import { apiFetch } from "@/api/client";

describe("apiFetch", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("sends the backend API key as a bearer token to API_URL", async () => {
    let request: Request | undefined;
    server.use(
      http.get("http://localhost:3000/mock-api/ping", ({ request: r }) => {
        request = r;
        return HttpResponse.json({ ok: true });
      }),
    );

    expect(await apiFetch("/ping")).toEqual({ ok: true });
    expect(request?.headers.get("authorization")).toBe(
      "Bearer test-backend-key",
    );
  });

  it.each(["API_URL", "BACKEND_API_KEY"])(
    "fails loudly instead of calling the backend when %s is unset",
    async (name) => {
      vi.stubEnv(name, "");
      const handler = vi.fn(() => HttpResponse.json({}));
      server.use(http.get("*/ping", handler));

      await expect(apiFetch("/ping")).rejects.toThrow(`${name} is not set`);
      expect(handler).not.toHaveBeenCalled();
    },
  );
});
