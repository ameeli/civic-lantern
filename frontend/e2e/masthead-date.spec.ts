import { test, expect, type Page } from "@playwright/test";

// Vercel sets this from the reader's IP; tests stand in for a reader there.
const TIME_ZONE_HEADER = "x-vercel-ip-timezone";

// "Wednesday, October 14" for now in `timeZone`, computed independently of the app.
function readerDate(timeZone: string) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone,
      weekday: "long",
      month: "long",
      day: "numeric",
    })
      .formatToParts(new Date())
      .map((p) => [p.type, p.value]),
  );
  return `${parts.weekday}, ${parts.month} ${parts.day}`;
}

async function dateLine(page: Page, timeZone: string) {
  await page.setExtraHTTPHeaders({ [TIME_ZONE_HEADER]: timeZone });
  const before = readerDate(timeZone);
  await page.goto("/");
  const text = await page
    .getByText(/^\w+day, \w+ \d+\w\w, \d{4}$/)
    .first()
    .textContent();
  return { text, expected: [before, readerDate(timeZone)] };
}

test.describe("Masthead date", () => {
  // UTC+14 and UTC-11 are 25 hours apart, so their dates always differ:
  // a masthead that ignores the reader's time zone fails at least one.
  for (const timeZone of ["Pacific/Kiritimati", "Pacific/Pago_Pago"]) {
    test(`shows today's date for a reader in ${timeZone}`, async ({ page }) => {
      const { text, expected } = await dateLine(page, timeZone);
      // Either side of a midnight that falls during the page load is correct.
      const dates = [...new Set(expected)].join("|");
      expect(text).toMatch(new RegExp(`^(${dates})(st|nd|rd|th), \\d{4}$`));
    });
  }
});
