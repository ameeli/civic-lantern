import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { server } from "@/mocks/server";

// next/cache only works inside the Next runtime; outside it, caching is a no-op.
vi.mock("next/cache", () => ({
  cacheLife: vi.fn(),
  cacheTag: vi.fn(),
  revalidateTag: vi.fn(),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// jsdom doesn't implement the Pointer Capture API used by CandidateRangeSlider.
// Node-environment tests (route handlers) have no DOM at all.
if (typeof Element !== "undefined") {
  Element.prototype.setPointerCapture ??= () => {};
  Element.prototype.releasePointerCapture ??= () => {};
}
