import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Dashboard } from "./Dashboard";

const session = {
  id: 42,
  external_call_id: "CA123",
  customer_name: "Avery Johnson",
  customer_email: "avery@example.com",
  customer_phone: "+15551234567",
  appliance_type: "refrigerator",
  symptoms: ["leaking"],
  zip_code: "75201",
  status: "ready_to_schedule",
  safety_blocked: false,
  recommended_action: "Schedule a technician.",
  events: [
    {
      id: 1,
      role: "user",
      content: "The refrigerator is leaking.",
      tool_name: null,
      tool_payload: null,
    },
  ],
};

const upload = {
  id: 7,
  diagnostic_session_id: 42,
  storage_bucket: "uploads",
  storage_key: "diagnostic-sessions/42/uploads/photo",
  original_filename: "refrigerator.png",
  content_type: "image/png",
  byte_size: 2048,
  status: "analysis_pending",
  expires_at: "2026-07-01T18:30:00Z",
  uploaded_at: "2026-07-01T18:01:00Z",
  analysis_started_at: null,
  analyzed_at: null,
  analysis_summary: null,
  analysis_result: null,
  failure_reason: null,
};

const appointment = {
  id: 5,
  status: "booked",
  appliance_type: "refrigerator",
  zip_code: "75201",
  issue_summary: "Leaking refrigerator",
  scheduled_start: "2026-07-02T14:00:00Z",
  scheduled_end: "2026-07-02T18:00:00Z",
  hold_expires_at: null,
  confirmation_code: "SHS123",
  customer: {
    id: 9,
    full_name: "Avery Johnson",
    email: "avery@example.com",
    phone: "+15551234567",
  },
  technician: {
    id: 3,
    name: "Jordan Lee",
    email: "jordan@example.com",
  },
};

describe("Dashboard", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders sessions, uploads, events, and appointments", async () => {
    mockDashboardRequests(fetchMock);

    render(<Dashboard />);

    expect(await screen.findByRole("heading", { name: /diagnostic operations/i })).toBeVisible();
    expect(screen.getAllByText("Avery Johnson").length).toBeGreaterThan(0);
    expect(screen.getByText("refrigerator.png")).toBeVisible();
    expect(screen.getByText(/the refrigerator is leaking/i)).toBeVisible();
    expect(screen.getByText(/with jordan lee/i)).toBeVisible();
  });

  it("can send a diagnostic turn and refresh data", async () => {
    mockDashboardRequests(fetchMock);
    const user = userEvent.setup();

    render(<Dashboard />);

    await screen.findAllByText("Avery Johnson");
    await user.type(screen.getByLabelText(/diagnostic turn/i), "Refrigerator leaking in 75201");
    await user.click(screen.getByRole("button", { name: /send turn/i }));

    expect(await screen.findByText(/captured the appliance/i)).toBeVisible();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/diagnostics\/sessions\/42\/turn$/),
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("validates contact details before creating a session", async () => {
    mockDashboardRequests(fetchMock);
    const user = userEvent.setup();

    render(<Dashboard />);

    await screen.findByRole("heading", { name: /diagnostic operations/i });
    await user.click(screen.getByRole("button", { name: /create session/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter an email or phone number for the diagnostic session."
    );
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          requestUrl(input).endsWith("/diagnostics/sessions") && init?.method === "POST"
      )
    ).toBe(false);
  });

  it("shows a dashboard load error", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "backend unavailable" }, 503));
    fetchMock.mockResolvedValueOnce(jsonResponse({ appointments: [] }));

    render(<Dashboard />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Request failed with 503");
  });
});

function mockDashboardRequests(fetchMock: ReturnType<typeof vi.fn<typeof fetch>>) {
  fetchMock.mockImplementation((input, init) => {
    const url = requestUrl(input);
    if (url.endsWith("/diagnostics/sessions")) {
      return Promise.resolve(jsonResponse({ sessions: [session] }));
    }
    if (url.endsWith("/appointments")) {
      return Promise.resolve(jsonResponse({ appointments: [appointment] }));
    }
    if (url.endsWith("/diagnostics/sessions/42/uploads")) {
      return Promise.resolve(jsonResponse({ uploads: [upload] }));
    }
    if (url.endsWith("/diagnostics/sessions/42/turn") && init?.method === "POST") {
      return Promise.resolve(jsonResponse({
        session,
        assistant_message: "I captured the appliance and symptom.",
        tool_calls: [],
      }));
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });
}

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
