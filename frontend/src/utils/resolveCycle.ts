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

  const parsed = Number(requestedCycle);
  if (!Number.isInteger(parsed)) return fallback;

  return readyCycles.includes(parsed) ? parsed : fallback;
}
