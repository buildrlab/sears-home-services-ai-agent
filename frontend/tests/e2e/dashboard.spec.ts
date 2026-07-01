import { expect, test } from "@playwright/test";

import { mockDashboardApi, mockDashboardWorkflowApi } from "./helpers/api";
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

  test("creates sessions and drives diagnostic, upload, and analysis actions", async ({
    page,
  }) => {
    const errors = trackConsoleErrors(page);
    await mockDashboardWorkflowApi(page);

    await page.goto("/");

    await expect(page.getByRole("heading", { name: /diagnostic operations/i })).toBeVisible();
    await page.getByLabel(/customer name/i).fill("Taylor Smith");
    await page.getByLabel(/customer email/i).fill("taylor@example.com");
    await page.getByRole("button", { name: /create session/i }).click();
    await expect(page.getByRole("status")).toContainText("Created session #43.");

    await page.getByRole("button", { name: /avery johnson/i }).click();
    await page.getByLabel(/diagnostic turn/i).fill("The refrigerator is not cooling in 75201.");
    await page.getByRole("button", { name: /send turn/i }).click();
    await expect(page.getByRole("status")).toContainText("Safe checks:");

    await page.getByLabel(/upload email/i).fill("caller@example.com");
    await page.getByRole("button", { name: /send link/i }).click();
    await expect(page.getByRole("status")).toContainText("Upload link sent:");

    await page.getByRole("button", { name: /run analysis/i }).click();
    await expect(page.getByRole("status")).toContainText("Visible pooling");
    await expect(page.getByText(/visible pooling near the refrigerator door/i).last()).toBeVisible();
    assertNoConsoleErrors(errors);
  });
});
