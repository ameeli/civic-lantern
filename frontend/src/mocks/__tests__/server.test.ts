import { describe, expect, it, vi } from "vitest";

// vitest.setup.ts starts the mock server in "error" mode; msw silently ignores
// an option it doesn't recognise, so check the behaviour, not the config.
describe("mock server", () => {
  it("reports an unmocked request as an error, not a warning", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    await fetch("http://unmocked.test/endpoint").catch(() => {});

    const logged = (spy: typeof error) => spy.mock.calls.flat().join(" ");
    expect(logged(error)).toMatch(/without a matching request handler/);
    expect(logged(warn)).not.toMatch(/without a matching request handler/);
  });
});
