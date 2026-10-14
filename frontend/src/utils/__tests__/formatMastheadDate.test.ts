import { describe, expect, it } from "vitest";
import {
  FALLBACK_TIME_ZONE,
  formatMastheadDate,
} from "@/utils/formatMastheadDate";

const at = (iso: string) => new Date(iso);

describe("formatMastheadDate", () => {
  it("uses the reader's date, not UTC's, in the US evening", () => {
    // 5:30pm Tuesday in Los Angeles is already Wednesday in UTC.
    const instant = at("2026-10-14T00:30:00Z");
    expect(formatMastheadDate(instant, "America/Los_Angeles")).toBe(
      "Tuesday, October 13th, 2026",
    );
    expect(formatMastheadDate(instant, "UTC")).toBe(
      "Wednesday, October 14th, 2026",
    );
  });

  it("follows daylight saving time on both transitions", () => {
    // Each instant lands on a different day if the wrong UTC offset is used.
    expect(
      formatMastheadDate(at("2026-03-09T07:30:00Z"), "America/Los_Angeles"),
    ).toBe("Monday, March 9th, 2026");
    expect(
      formatMastheadDate(at("2026-11-02T07:30:00Z"), "America/Los_Angeles"),
    ).toBe("Sunday, November 1st, 2026");
  });

  it("handles zones a full day apart", () => {
    const instant = at("2026-10-13T10:30:00Z");
    expect(formatMastheadDate(instant, "Pacific/Kiritimati")).toBe(
      "Wednesday, October 14th, 2026",
    );
    expect(formatMastheadDate(instant, "Pacific/Pago_Pago")).toBe(
      "Monday, October 12th, 2026",
    );
  });

  it.each([null, "", "Not/A_Zone"])(
    "falls back to America/New_York for time zone %j",
    (timeZone) => {
      const instant = at("2026-10-14T00:30:00Z");
      expect(FALLBACK_TIME_ZONE).toBe("America/New_York");
      expect(formatMastheadDate(instant, timeZone)).toBe(
        "Tuesday, October 13th, 2026",
      );
    },
  );

  it.each([
    [1, "Thursday, January 1st, 2026"],
    [2, "Friday, January 2nd, 2026"],
    [3, "Saturday, January 3rd, 2026"],
    [11, "Sunday, January 11th, 2026"],
    [12, "Monday, January 12th, 2026"],
    [13, "Tuesday, January 13th, 2026"],
    [21, "Wednesday, January 21st, 2026"],
    [22, "Thursday, January 22nd, 2026"],
    [23, "Friday, January 23rd, 2026"],
    [31, "Saturday, January 31st, 2026"],
  ])("suffixes day %i correctly", (day, expected) => {
    const iso = `2026-01-${String(day).padStart(2, "0")}T12:00:00Z`;
    expect(formatMastheadDate(at(iso), "UTC")).toBe(expected);
  });
});
