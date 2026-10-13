// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { revalidateTag } from "next/cache";
import { FEC_DATA_TAG } from "@/api/cacheTags";
import { POST } from "../route";

const SECRET = "test-secret";

function post(authorization?: string) {
  const headers = authorization ? { authorization } : undefined;
  return POST(
    new Request("http://localhost/api/revalidate", { method: "POST", headers }),
  );
}

describe("POST /api/revalidate", () => {
  beforeEach(() => vi.stubEnv("REVALIDATE_SECRET", SECRET));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.mocked(revalidateTag).mockClear();
  });

  it("revalidates the FEC data tag with stale-while-revalidate", async () => {
    const res = await post(`Bearer ${SECRET}`);

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ revalidated: true });
    expect(revalidateTag).toHaveBeenCalledExactlyOnceWith(FEC_DATA_TAG, "max");
  });

  it.each([
    ["no header", undefined],
    ["a wrong secret", "Bearer wrong-secret"],
    ["a secret prefix", `Bearer ${SECRET.slice(0, -1)}`],
    ["a non-Bearer scheme", `Basic ${SECRET}`],
  ])("rejects %s with 401", async (_, authorization) => {
    const res = await post(authorization);

    expect(res.status).toBe(401);
    expect(revalidateTag).not.toHaveBeenCalled();
  });

  it("fails closed with 500 when the secret isn't configured", async () => {
    vi.stubEnv("REVALIDATE_SECRET", "");

    const res = await post("Bearer ");

    expect(res.status).toBe(500);
    expect(revalidateTag).not.toHaveBeenCalled();
  });
});
