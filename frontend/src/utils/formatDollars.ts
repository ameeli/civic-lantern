/** Abbreviated dollar figure for display, e.g. $238.9M, $19K, $50. */
export function formatDollars(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${Math.round(v)}`;
}

/** Full comma-formatted dollar figure for editable inputs, e.g. $19,000,000. */
export function formatDollarsFull(v: number): string {
  return `$${Math.round(v).toLocaleString("en-US")}`;
}

/** Parses a user-typed dollar string (ignoring $, commas, etc.) into a number, or null if empty. */
export function parseDollarInput(text: string): number | null {
  const digits = text.replace(/[^0-9]/g, "");
  return digits === "" ? null : Number(digits);
}
