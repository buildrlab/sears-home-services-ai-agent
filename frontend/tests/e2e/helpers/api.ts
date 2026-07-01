import type { Page, Route } from "@playwright/test";

export const session = {
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

export const upload = {
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

export const uploadToken = {
  ...upload,
  id: 91,
  original_filename: null,
  content_type: null,
  byte_size: null,
  status: "pending_upload",
  uploaded_at: null,
};

export const completedUpload = {
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

export async function mockDashboardWorkflowApi(page: Page) {
  const sessions: unknown[] = [structuredClone(session)];
  const uploadsBySession = new Map<number, unknown[]>([[session.id, [structuredClone(upload)]]]);
  const appointments: unknown[] = [
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
  ];

  await page.route("**/diagnostics/sessions", async (route) => {
    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON() as Partial<Record<string, string>>;
      const created = {
        ...structuredClone(session),
        id: 43,
        customer_name: payload.customer_name ?? null,
        customer_email: payload.customer_email ?? null,
        customer_phone: payload.customer_phone ?? null,
        appliance_type: null,
        symptoms: [],
        zip_code: null,
        status: "active",
        events: [],
      };
      sessions.push(created);
      uploadsBySession.set(created.id, []);
      return fulfillJson(route, created, 201);
    }

    return fulfillJson(route, { sessions });
  });

  await page.route("**/appointments", (route) => fulfillJson(route, { appointments }));

  await page.route("**/diagnostics/sessions/*/uploads", (route) => {
    const sessionMatch = /sessions\/(\d+)\/uploads/.exec(route.request().url());
    const sessionId = Number(sessionMatch?.[1]);
    return fulfillJson(route, { uploads: uploadsBySession.get(sessionId) ?? [] });
  });

  await page.route("**/diagnostics/sessions/42/turn", (route) =>
    fulfillJson(route, {
      session: {
        ...session,
        events: [
          ...session.events,
          {
            id: 2,
            role: "assistant",
            content: "Safe checks: confirm the doors are closed and the vents are clear.",
            tool_name: null,
            tool_payload: null,
          },
        ],
      },
      assistant_message: "Safe checks: confirm the doors are closed and the vents are clear.",
      tool_calls: [],
    })
  );

  await page.route("**/diagnostics/sessions/42/upload-link", (route) =>
    fulfillJson(
      route,
      {
        id: 22,
        diagnostic_session_id: 42,
        upload_url: "https://shs.buildrlab.com/uploads/token-123",
        expires_at: "2026-07-01T18:30:00Z",
        email_sent: true,
        status: "pending_upload",
      },
      201
    )
  );

  await page.route("**/diagnostics/uploads/7/analysis", (route) => {
    const analyzed = {
      ...structuredClone(upload),
      status: "analyzed",
      analyzed_at: "2026-07-01T18:04:00Z",
      analysis_summary: "Visible pooling near the refrigerator door suggests a leak path.",
    };
    uploadsBySession.set(42, [analyzed]);
    return fulfillJson(route, analyzed);
  });
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

export async function mockUploadTokenApiOnly(page: Page, token = "token-123") {
  await page.route(`**/uploads/${token}`, (route) => {
    if (route.request().resourceType() === "document") {
      return route.continue();
    }

    return fulfillJson(route, uploadToken);
  });
}

export async function mockExpiredUploadApi(page: Page) {
  await page.route("**/uploads/expired-token", (route) => {
    if (route.request().resourceType() === "document") {
      return route.continue();
    }

    return fulfillJson(route, { detail: "not found" }, 404);
  });
}

export async function mockUploadStorageFailureApi(page: Page) {
  await mockUploadTokenApiOnly(page);
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
    route.fulfill({ status: 500, body: "storage unavailable" })
  );
}

function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}
