import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createDiagnosticSession,
  listDiagnosticSessions,
  loadDashboardData,
  uploadFileToStorage,
} from "./api";

describe("api client", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("unwraps list responses and sends JSON mutation headers", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ sessions: [{ id: 1, events: [] }] }))
      .mockResolvedValueOnce(jsonResponse({ id: 2, events: [] }, 201));

    await expect(listDiagnosticSessions()).resolves.toEqual([{ id: 1, events: [] }]);
    await expect(
      createDiagnosticSession({ customer_email: "caller@example.test" })
    ).resolves.toEqual({ id: 2, events: [] });

    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://127.0.0.1:8000/diagnostics/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ customer_email: "caller@example.test" }),
      })
    );
    const headers = fetchMock.mock.calls[1]?.[1]?.headers;
    expect(headers).toBeInstanceOf(Headers);
    expect((headers as Headers).get("Content-Type")).toBe("application/json");
  });

  it("preserves error status and JSON detail", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "not found" }, 404));

    await expect(listDiagnosticSessions()).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      detail: { detail: "not found" },
    });
  });

  it("handles non-json error responses", async () => {
    fetchMock.mockResolvedValueOnce(new Response("gateway timeout", { status: 504 }));

    await expect(listDiagnosticSessions()).rejects.toMatchObject({ status: 504 });
  });

  it("uploads storage form fields and throws on storage failure", async () => {
    const file = new File(["image"], "image.png", { type: "image/png" });
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await uploadFileToStorage(
      {
        upload_id: 1,
        method: "POST",
        url: "https://s3.example.test/upload",
        fields: { key: "object-key", policy: "policy" },
        max_byte_size: 1024,
        expires_at: "2026-07-01T18:30:00Z",
        storage_key: "object-key",
      },
      file
    );

    const [, init] = fetchMock.mock.calls[0] ?? [];
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);

    fetchMock.mockResolvedValueOnce(new Response("failed", { status: 500 }));
    await expect(
      uploadFileToStorage(
        {
          upload_id: 1,
          method: "POST",
          url: "https://s3.example.test/upload",
          fields: {},
          max_byte_size: 1024,
          expires_at: "2026-07-01T18:30:00Z",
          storage_key: "object-key",
        },
        file
      )
    ).rejects.toMatchObject({ status: 500 });
  });

  it("loads dashboard sessions, appointments, and uploads together", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ sessions: [{ id: 42, events: [] }] }))
      .mockResolvedValueOnce(jsonResponse({ appointments: [{ id: 9 }] }))
      .mockResolvedValueOnce(jsonResponse({ uploads: [{ id: 7 }] }));

    await expect(loadDashboardData()).resolves.toEqual({
      sessions: [{ id: 42, events: [] }],
      appointments: [{ id: 9 }],
      uploadsBySession: { 42: [{ id: 7 }] },
    });
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
