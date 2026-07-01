import { expect, test } from "@playwright/test";

import {
  mockExpiredUploadApi,
  mockUploadApi,
  mockUploadStorageFailureApi,
  mockUploadTokenApiOnly,
} from "./helpers/api";
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

  test("shows an expired upload link state without unexpected console errors", async ({
    page,
  }) => {
    const errors = trackConsoleErrors(page, {
      ignoredErrors: [/Failed to load resource: the server responded with a status of 404/i],
    });
    await mockExpiredUploadApi(page);

    await page.goto("/uploads/expired-token");

    await expect(page.getByRole("heading", { name: /upload link unavailable/i })).toBeVisible();
    await expect(page.getByText(/expired or no longer valid/i)).toBeVisible();
    assertNoConsoleErrors(errors);
  });

  test("rejects unsupported files before requesting upload credentials", async ({ page }) => {
    const errors = trackConsoleErrors(page);
    await mockUploadTokenApiOnly(page);
    let presignedRequested = false;
    await page.route("**/uploads/token-123/presigned-post", (route) => {
      presignedRequested = true;
      return route.fulfill({ status: 500, body: "should not be called" });
    });

    await page.goto("/uploads/token-123");
    await page.getByLabel(/appliance image/i).setInputFiles({
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("not an image"),
    });
    await page.getByRole("button", { name: /upload image/i }).click();

    await expect(page.getByText(/choose a jpeg, png, or webp image/i)).toBeVisible();
    expect(presignedRequested).toBe(false);
    assertNoConsoleErrors(errors);
  });

  test("surfaces storage upload failures without unexpected console errors", async ({
    page,
  }) => {
    const errors = trackConsoleErrors(page, {
      ignoredErrors: [/Failed to load resource: the server responded with a status of 500/i],
    });
    await mockUploadStorageFailureApi(page);

    await page.goto("/uploads/token-123");
    await page.getByLabel(/appliance image/i).setInputFiles({
      name: "washer.png",
      mimeType: "image/png",
      buffer: Buffer.from([137, 80, 78, 71]),
    });
    await page.getByRole("button", { name: /upload image/i }).click();

    await expect(page.getByText(/upload service returned an error/i)).toBeVisible();
    assertNoConsoleErrors(errors);
  });
});
