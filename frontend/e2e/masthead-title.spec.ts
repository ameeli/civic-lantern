import { test, expect } from "@playwright/test";

// Common phone widths; the masthead title wrapped below ~400px and overlapped the date.
for (const width of [320, 375, 390, 430]) {
  test(`masthead title stays on one line above the date at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const title = page.locator(".text-masthead");
    await expect(title).toBeVisible();
    await page.evaluate(() => document.fonts.ready);

    const layout = await title.evaluate((h1) => {
      const range = document.createRange();
      range.selectNodeContents(h1);
      const lineTops = new Set(
        [...range.getClientRects()].map((r) => Math.round(r.top)),
      );
      const date = [...document.querySelectorAll("span")].find(
        (s) => /day, /.test(s.textContent ?? "") && s.offsetParent !== null,
      )!;
      return {
        lines: lineTops.size,
        // getBoundingClientRect includes the title's scaleY transform.
        titleBottom: h1.getBoundingClientRect().bottom,
        dateTop: date.getBoundingClientRect().top,
        scrollWidth: document.documentElement.scrollWidth,
      };
    });

    expect(layout.lines).toBe(1);
    expect(layout.titleBottom).toBeLessThanOrEqual(layout.dateTop);
    expect(layout.scrollWidth).toBeLessThanOrEqual(width);
  });
}
