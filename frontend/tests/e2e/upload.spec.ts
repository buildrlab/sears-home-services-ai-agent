import { expect, test } from "@playwright/test";

import { mockUploadApi } from "./helpers/api";
import { assertNoConsoleErrors, trackConsoleErrors } from "./helpers/console";

test.describe("Upload page", () => {
  test("uploads an appliance image without console errors", async ({ page }) => {
    const errors = trackConsoleErrors(page);
    await mockUploadApi(page);

    await page.goto("/uploads/token-123");
    await expect(page.getByRole("heading", { name: /appliance image upload/i })).toBeVisible();

    await page.getByLabel(/appliance image/i).setInputFiles({
      name: "washer.png",
      mimeType: "image/png",
      buffer: Buffer.from([137, 80, 78, 71]),
    });
    await page.getByRole("button", { name: /upload image/i }).click();

    await expect(page.getByText(/upload complete/i)).toBeVisible();
    await expect(page.getByText("washer.png", { exact: true })).toBeVisible();
    assertNoConsoleErrors(errors);
  });
});
