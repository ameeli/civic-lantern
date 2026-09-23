import { test, expect } from "@playwright/test";
import { formatDollars, formatDollarsFull } from "@/utils/formatDollars";

const API_BASE = "http://127.0.0.1:8000/api/v1";
const CYCLE = 2024;
const OFFICE = "S";

async function fetchSenateDefaultRange() {
  const res = await fetch(
    `${API_BASE}/candidate-spending?cycle=${CYCLE}&office=${OFFICE}&sort_by=total_spending&order=desc&limit=1000`,
  );
  const body = (await res.json()) as {
    items: { total_spending: number }[];
    total_count: number;
  };
  const spends = body.items.map((i) => i.total_spending).sort((a, b) => b - a);
  return {
    max: spends[0],
    defaultMin: spends[Math.min(30, spends.length) - 1],
    trueTotal: spends.reduce((a, b) => a + b, 0),
    count: body.total_count,
  };
}

test.describe("Candidate spending pack chart: dollar-range slider", () => {
  test("chart loads with three office bubbles and no console errors", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto(`/?cycle=${CYCLE}`);
    // Depth-3 spending leaves reuse office color classes (e.g. "Outside Support"
    // also renders fill-office-house), so scope to the currently visible layer.
    await expect(
      page.locator('circle.fill-office-senate[opacity="0.7"]'),
    ).toBeVisible();
    await expect(
      page.locator('circle.fill-office-house[opacity="0.7"]'),
    ).toBeVisible();
    await expect(
      page.locator('circle.fill-office-president[opacity="0.7"]'),
    ).toBeVisible();

    expect(errors).toEqual([]);
  });

  test("drilling into Senate hides other offices' candidates (only Senate's own subtree is visible)", async ({
    page,
  }) => {
    await page.goto(`/?cycle=${CYCLE}`);
    await page.locator("circle.fill-office-senate").click();
    await expect(page.getByText("Candidates in range: 30")).toBeVisible();

    // Only Senate's 30 default candidates should render — not President's or
    // House's, even though they share the same depth in the hierarchy.
    await expect(page.locator('circle[opacity="0.7"]')).toHaveCount(30);
    await expect(
      page.locator('circle.fill-office-house[opacity="0.7"]'),
    ).toHaveCount(0);
    await expect(
      page.locator('circle.fill-office-president[opacity="0.7"]'),
    ).toHaveCount(0);
  });

  test("drilling into Senate shows the slider with the correct default range and count", async ({
    page,
  }) => {
    const expected = await fetchSenateDefaultRange();

    await page.goto(`/?cycle=${CYCLE}`);
    await page.locator("circle.fill-office-senate").click();

    // Breadcrumb reflects the drill-in.
    await expect(page.getByRole("navigation").getByText("Senate", { exact: true })).toBeVisible();

    // Slider appears with the default top-30 range.
    await expect(page.getByText(/Candidates in range: 30/)).toBeVisible();

    const maxLabel = formatDollars(expected.max);
    const minInput = page.getByLabel("Minimum total spending amount");
    const maxInput = page.getByLabel("Maximum total spending amount");

    // Both the SVG candidate label and the slider's static end label can show
    // the same top-spend figure, so scope to the plain (non-SVG) label.
    await expect(page.locator("span", { hasText: maxLabel })).toBeVisible();
    await expect(minInput).toHaveValue(formatDollarsFull(expected.defaultMin));
    await expect(maxInput).toHaveValue(formatDollarsFull(expected.max));
  });

  test("dragging the min handle narrows the visible candidates without losing zoom", async ({
    page,
  }) => {
    await page.goto(`/?cycle=${CYCLE}`);
    await page.locator("circle.fill-office-senate").click();
    await expect(page.getByText("Candidates in range: 30")).toBeVisible();

    const totalBefore = await page.locator('circle[opacity="0.7"]').count();
    expect(totalBefore).toBe(30);

    const handle = page.getByRole("slider", { name: "Minimum total spending" });
    await handle.scrollIntoViewIfNeeded();
    const box = await handle.boundingBox();
    if (!box) throw new Error("slider handle has no bounding box");

    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    // Drag the min handle a fixed distance right, narrowing the range.
    await page.mouse.move(box.x + 150, box.y + box.height / 2, { steps: 10 });
    await page.mouse.up();

    // The chart rebuilds on release, but stays zoomed into Senate.
    await expect(
      page.getByRole("navigation").getByText("Senate", { exact: true }),
    ).toBeVisible();

    const countAfterText = await page
      .getByText(/Candidates in range: \d+/)
      .textContent();
    expect(countAfterText).not.toBe("Candidates in range: 30");

    const countAfter = Number(countAfterText?.match(/\d+/)?.[0]);
    expect(countAfter).toBeLessThan(30);

    // The count label updates synchronously from the slider's own state, but
    // the actual SVG rebuild happens a tick later via the parent's effect —
    // poll rather than taking a one-shot count.
    await expect(page.locator('circle[opacity="0.7"]')).toHaveCount(
      countAfter,
    );
  });

  test("Senate's office-bubble size is unaffected by narrowing its slider range", async ({
    page,
  }) => {
    await page.goto(`/?cycle=${CYCLE}`);
    const senateCircle = page.locator("circle.fill-office-senate");
    const radiusBefore = await senateCircle.getAttribute("r");

    await senateCircle.click();
    await expect(page.getByText(/Candidates in range: \d+/)).toBeVisible();

    const handle = page.getByRole("slider", { name: "Minimum total spending" });
    await handle.scrollIntoViewIfNeeded();
    const box = await handle.boundingBox();
    if (!box) throw new Error("slider handle has no bounding box");
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + 150, box.y + box.height / 2, { steps: 10 });
    await page.mouse.up();

    // Zoom back out to root and compare the office bubble's radius.
    await page.getByRole("navigation").getByText("All Races", { exact: true }).click();
    await expect(page.locator("circle.fill-office-senate")).toBeVisible();

    // The zoom-out animates for 750ms before the range resets and the chart
    // rebuilds, so poll until the radius settles rather than sampling mid-tween.
    await expect
      .poll(async () =>
        Number(
          await page.locator("circle.fill-office-senate").getAttribute("r"),
        ),
      )
      .toBeCloseTo(Number(radiusBefore), 1);
  });
});
