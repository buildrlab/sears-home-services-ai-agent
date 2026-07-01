import { describe, expect, it } from "vitest";

import { extractUploadToken } from "./routes";

describe("extractUploadToken", () => {
  it("extracts upload tokens from supported upload routes", () => {
    expect(extractUploadToken("/uploads/token-123")).toBe("token-123");
    expect(extractUploadToken("/upload/token-123/")).toBe("token-123");
    expect(extractUploadToken("/uploads/token%20with%20space")).toBe("token with space");
  });

  it("ignores unrelated or nested routes", () => {
    expect(extractUploadToken("/")).toBeNull();
    expect(extractUploadToken("/diagnostics/token-123")).toBeNull();
    expect(extractUploadToken("/uploads/token-123/extra")).toBeNull();
  });
});
