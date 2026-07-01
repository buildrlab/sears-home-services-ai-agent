import type {
  AppointmentListResponse,
  DashboardData,
  DiagnosticSessionCreate,
  DiagnosticSessionListResponse,
  DiagnosticSessionRead,
  DiagnosticTurnResponse,
  ImageUploadListResponse,
  ImageUploadRead,
  PresignedUploadResponse,
  UploadLinkResponse,
  UploadMetadataRequest,
} from "./types";

const configuredApiBaseUrl = (import.meta as { env: { VITE_API_BASE_URL?: string } }).env
  .VITE_API_BASE_URL;
const API_BASE_URL = (configuredApiBaseUrl ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const detail = await safeReadJson(response);
    throw new ApiError(
      `Request failed with ${String(response.status)}`,
      response.status,
      detail
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function safeReadJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

export async function listDiagnosticSessions(): Promise<DiagnosticSessionRead[]> {
  const data = await requestJson<DiagnosticSessionListResponse>("/diagnostics/sessions");
  return data.sessions;
}

export async function createDiagnosticSession(
  payload: DiagnosticSessionCreate
): Promise<DiagnosticSessionRead> {
  return requestJson<DiagnosticSessionRead>("/diagnostics/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function processDiagnosticTurn(
  sessionId: number,
  message: string
): Promise<DiagnosticTurnResponse> {
  return requestJson<DiagnosticTurnResponse>(`/diagnostics/sessions/${String(sessionId)}/turn`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function listAppointments(): Promise<AppointmentListResponse["appointments"]> {
  const data = await requestJson<AppointmentListResponse>("/appointments");
  return data.appointments;
}

export async function listSessionUploads(sessionId: number): Promise<ImageUploadRead[]> {
  const data = await requestJson<ImageUploadListResponse>(
    `/diagnostics/sessions/${String(sessionId)}/uploads`
  );
  return data.uploads;
}

export async function getUploadByToken(token: string): Promise<ImageUploadRead> {
  return requestJson<ImageUploadRead>(`/uploads/${encodeURIComponent(token)}`);
}

export async function createPresignedUpload(
  token: string,
  metadata: UploadMetadataRequest
): Promise<PresignedUploadResponse> {
  return requestJson<PresignedUploadResponse>(
    `/uploads/${encodeURIComponent(token)}/presigned-post`,
    {
      method: "POST",
      body: JSON.stringify(metadata),
    }
  );
}

export async function completeUpload(
  token: string,
  metadata: UploadMetadataRequest
): Promise<ImageUploadRead> {
  return requestJson<ImageUploadRead>(`/uploads/${encodeURIComponent(token)}/complete`, {
    method: "POST",
    body: JSON.stringify(metadata),
  });
}

export async function uploadFileToStorage(
  presignedUpload: PresignedUploadResponse,
  file: File
): Promise<void> {
  const formData = new FormData();

  for (const [name, value] of Object.entries(presignedUpload.fields)) {
    formData.append(name, value);
  }

  formData.append("file", file);

  const response = await fetch(presignedUpload.url, {
    method: presignedUpload.method,
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError("Object storage upload failed", response.status);
  }
}

export async function createUploadLink(
  sessionId: number,
  email: string
): Promise<UploadLinkResponse> {
  return requestJson<UploadLinkResponse>(
    `/diagnostics/sessions/${String(sessionId)}/upload-link`,
    {
      method: "POST",
      body: JSON.stringify({ email }),
    }
  );
}

export async function analyzeUpload(uploadId: number): Promise<ImageUploadRead> {
  return requestJson<ImageUploadRead>(`/diagnostics/uploads/${String(uploadId)}/analysis`, {
    method: "POST",
  });
}

export async function loadDashboardData(): Promise<DashboardData> {
  const [sessions, appointments] = await Promise.all([
    listDiagnosticSessions(),
    listAppointments(),
  ]);
  const uploadPairs = await Promise.all(
    sessions.map(async (session) => [session.id, await listSessionUploads(session.id)] as const)
  );
  const uploadsBySession: Record<number, ImageUploadRead[]> = {};

  for (const [sessionId, uploads] of uploadPairs) {
    uploadsBySession[sessionId] = uploads;
  }

  return {
    sessions,
    appointments,
    uploadsBySession,
  };
}
