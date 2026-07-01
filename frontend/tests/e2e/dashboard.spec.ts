import { expect, test } from "@playwright/test";

import { mockDashboardApi } from "./helpers/api";
import { assertNoConsoleErrors, trackConsoleErrors } from "./helpers/console";

test.describe("Dashboard", () => {
  test("renders diagnostic operations data without console errors", async ({ page }) => {
    const errors = trackConsoleErrors(page);
    await mockDashboardApi(page);

    await page.goto("/");

    await expect(page.getByRole("heading", { name: /diagnostic operations/i })).toBeVisible();
    await expect(page.getByText("Avery Johnson").first()).toBeVisible();
    await expect(page.getByText("refrigerator.png")).toBeVisible();
    await expect(page.getByText(/with jordan lee/i)).toBeVisible();
    assertNoConsoleErrors(errors);
  });
});
