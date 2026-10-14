// Used when the reader's time zone is unknown: the FEC's own filing calendar.
export const FALLBACK_TIME_ZONE = "America/New_York";

function ordinalSuffix(day: number) {
  if (day >= 11 && day <= 13) return "th";
  switch (day % 10) {
    case 1:
      return "st";
    case 2:
      return "nd";
    case 3:
      return "rd";
    default:
      return "th";
  }
}

function dateParts(instant: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).formatToParts(instant);
  return Object.fromEntries(parts.map((p) => [p.type, p.value]));
}

function isValidTimeZone(timeZone: string) {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone });
    return true;
  } catch {
    return false;
  }
}

// "Tuesday, October 13th, 2026": the calendar date at `instant` in `timeZone`.
export function formatMastheadDate(
  instant: Date,
  timeZone: string | null,
): string {
  const zone =
    timeZone && isValidTimeZone(timeZone) ? timeZone : FALLBACK_TIME_ZONE;
  const { weekday, month, day, year } = dateParts(instant, zone);
  return `${weekday}, ${month} ${day}${ordinalSuffix(Number(day))}, ${year}`;
}
