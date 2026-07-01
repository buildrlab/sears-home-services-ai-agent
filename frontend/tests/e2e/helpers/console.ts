import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

interface ConsoleTrackerOptions {
  ignoredErrors?: RegExp[];
}

export function trackConsoleErrors(page: Page, options: ConsoleTrackerOptions = {}): string[] {
  const errors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      const text = message.text();
      if (!options.ignoredErrors?.some((pattern) => pattern.test(text))) {
        errors.push(text);
      }
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  return errors;
}

export function assertNoConsoleErrors(errors: string[]) {
  expect(errors).toEqual([]);
}
