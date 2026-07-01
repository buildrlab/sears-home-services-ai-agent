import { describe, expect, it } from "vitest";

import { compactList, formatDateTime, formatFileSize, titleize } from "./format";

describe("format helpers", () => {
  it("formats empty values defensively", () => {
    expect(formatDateTime(null)).toBe("Not set");
    expect(formatFileSize(null)).toBe("Pending");
    expect(compactList([null, undefined, " "])).toBe("Not captured");
  });

  it("formats file sizes for dashboard and upload views", () => {
    expect(formatFileSize(512)).toBe("1 KB");
    expect(formatFileSize(1536)).toBe("2 KB");
    expect(formatFileSize(2.5 * 1024 * 1024)).toBe("2.5 MB");
  });

  it("titleizes status values and compacts populated fields", () => {
    expect(titleize("ready_to_schedule")).toBe("Ready To Schedule");
    expect(compactList(["refrigerator", null, "75201"])).toBe("refrigerator / 75201");
  });

  it("formats valid datetimes without throwing", () => {
    expect(formatDateTime("2026-07-01T18:30:00Z")).not.toBe("Not set");
  });
});
