/**
 * Resolves which cycle the page should show: the requested cycle if it's
 * ready, otherwise the newest ready cycle. Extracted as a pure function
 * because Vitest doesn't support rendering async Server Components
 * (page.tsx), so this is the testable seam for the fallback logic.
 */
export function resolveCycle(
  requestedCycle: string | string[] | undefined,
  readyCycles: number[],
): number | undefined {
  const fallback = readyCycles[0];

  if (typeof requestedCycle !== "string") return fallback;

  // Reject anything but a plain run of digits before parsing — Number()
  // is too permissive for a URL param (coerces "", " ", "+2024", "2024e0"
  // to valid-looking numbers), which would otherwise pass as "structurally
  // valid" instead of falling through to the fallback like other garbage.
  if (!/^\d+$/.test(requestedCycle)) return fallback;

  const parsed = Number(requestedCycle);
  return readyCycles.includes(parsed) ? parsed : fallback;
}
