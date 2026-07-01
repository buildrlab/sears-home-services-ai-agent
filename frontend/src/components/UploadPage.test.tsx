import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { validateImageFile } from "../uploadValidation";
import { UploadPage } from "./UploadPage";

const uploadResponse = {
  id: 91,
  diagnostic_session_id: 12,
  storage_bucket: "uploads",
  storage_key: "diagnostic-sessions/12/uploads/file",
  original_filename: null,
  content_type: null,
  byte_size: null,
  status: "pending_upload",
  expires_at: "2026-07-01T18:30:00Z",
  uploaded_at: null,
  analysis_started_at: null,
  analyzed_at: null,
  analysis_summary: null,
  analysis_result: null,
  failure_reason: null,
};

const completedUploadResponse = {
  ...uploadResponse,
  original_filename: "washer.png",
  content_type: "image/png",
  byte_size: 1024,
  status: "analysis_pending",
  uploaded_at: "2026-07-01T18:01:00Z",
};

describe("UploadPage", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows an invalid token state", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "not found" }, 404));

    render(<UploadPage token="expired-token" />);

    expect(await screen.findByRole("heading", { name: /upload link unavailable/i })).toBeVisible();
    expect(screen.getByText(/expired or no longer valid/i)).toBeVisible();
  });

  it("validates unsupported file types before requesting upload credentials", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(uploadResponse));

    render(<UploadPage token="token-123" />);

    await screen.findByRole("heading", { name: /appliance image upload/i });
    const fileInput = screen.getByLabelText(/appliance image/i);
    Object.defineProperty(fileInput, "files", {
      value: [new File(["not an image"], "notes.txt", { type: "text/plain" })],
      configurable: true,
    });
    fireEvent.change(fileInput);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /upload image/i }));

    expect(screen.getByText(/choose a jpeg, png, or webp image/i)).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).includes("presigned-post"))
    ).toBe(false);
  });

  it("uploads an image through a presigned storage form", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = requestUrl(input);

      if (url.endsWith("/uploads/token-123") && !init?.method) {
        return Promise.resolve(jsonResponse(uploadResponse));
      }

      if (url.endsWith("/uploads/token-123/presigned-post")) {
        return Promise.resolve(jsonResponse({
          upload_id: 91,
          method: "POST",
          url: "https://s3.example.test/upload",
          fields: { key: "diagnostic-sessions/12/uploads/file", policy: "policy" },
          max_byte_size: 10_485_760,
          expires_at: "2026-07-01T18:30:00Z",
          storage_key: "diagnostic-sessions/12/uploads/file",
        }));
      }

      if (url === "https://s3.example.test/upload") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }

      if (url.endsWith("/uploads/token-123/complete")) {
        return Promise.resolve(jsonResponse(completedUploadResponse));
      }

      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    const user = userEvent.setup();

    render(<UploadPage token="token-123" />);

    await screen.findByRole("heading", { name: /appliance image upload/i });
    await user.upload(
      screen.getByLabelText(/appliance image/i),
      new File([new Uint8Array([137, 80, 78, 71])], "washer.png", { type: "image/png" })
    );
    await user.click(screen.getByRole("button", { name: /upload image/i }));

    expect(await screen.findByText(/upload complete/i)).toBeVisible();
    const storageCall = fetchMock.mock.calls.find(([input]) => requestUrl(input) === "https://s3.example.test/upload");
    expect(storageCall?.[1]?.method).toBe("POST");
    expect(storageCall?.[1]?.body).toBeInstanceOf(FormData);
  });
});

describe("validateImageFile", () => {
  it("accepts supported images", () => {
    expect(validateImageFile(new File(["x"], "image.webp", { type: "image/webp" }))).toBeNull();
  });

  it("rejects oversized files", () => {
    const file = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "large.png", {
      type: "image/png",
    });

    expect(validateImageFile(file)).toMatch(/smaller than 10 mb/i);
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function requestUrl(input: Parameters<typeof fetch>[0]): string {
  if (typeof input === "string") {
    return input;
  }

  if (input instanceof URL) {
    return input.href;
  }

  return input.url;
}
