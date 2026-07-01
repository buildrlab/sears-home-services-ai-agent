import type { Page, Route } from "@playwright/test";

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

const uploadToken = {
  ...upload,
  id: 91,
  original_filename: null,
  content_type: null,
  byte_size: null,
  status: "pending_upload",
  uploaded_at: null,
};

const completedUpload = {
  ...uploadToken,
  original_filename: "washer.png",
  content_type: "image/png",
  byte_size: 1024,
  status: "analysis_pending",
  uploaded_at: "2026-07-01T18:01:00Z",
};

export async function mockDashboardApi(page: Page) {
  await page.route("**/diagnostics/sessions", (route) =>
    fulfillJson(route, { sessions: [session] })
  );
  await page.route("**/appointments", (route) =>
    fulfillJson(route, {
      appointments: [
        {
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
        },
      ],
    })
  );
  await page.route("**/diagnostics/sessions/42/uploads", (route) =>
    fulfillJson(route, { uploads: [upload] })
  );
}

export async function mockUploadApi(page: Page) {
  await page.route("**/uploads/token-123", (route) => {
    if (route.request().resourceType() === "document") {
      return route.continue();
    }

    return fulfillJson(route, uploadToken);
  });
  await page.route("**/uploads/token-123/presigned-post", (route) =>
    fulfillJson(route, {
      upload_id: 91,
      method: "POST",
      url: "https://s3.example.test/upload",
      fields: { key: "diagnostic-sessions/42/uploads/photo", policy: "policy" },
      max_byte_size: 10_485_760,
      expires_at: "2026-07-01T18:30:00Z",
      storage_key: "diagnostic-sessions/42/uploads/photo",
    })
  );
  await page.route("https://s3.example.test/upload", (route) =>
    route.fulfill({ status: 204, body: "" })
  );
  await page.route("**/uploads/token-123/complete", (route) =>
    fulfillJson(route, completedUpload)
  );
}

function fulfillJson(route: Route, body: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}
