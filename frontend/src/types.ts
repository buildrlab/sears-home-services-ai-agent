export type AppointmentStatus = "held" | "booked" | "cancelled";

export interface CustomerRead {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
}

export interface TechnicianSummaryRead {
  id: number;
  name: string;
  email: string;
}

export interface AppointmentRead {
  id: number;
  status: AppointmentStatus;
  appliance_type: string;
  zip_code: string;
  issue_summary: string | null;
  scheduled_start: string;
  scheduled_end: string;
  hold_expires_at: string | null;
  confirmation_code: string | null;
  customer: CustomerRead;
  technician: TechnicianSummaryRead;
}

export interface AppointmentListResponse {
  appointments: AppointmentRead[];
}

export type DiagnosticSessionStatus =
  | "active"
  | "ready_to_schedule"
  | "scheduled"
  | "safety_escalated"
  | "closed";

export type DiagnosticEventRole = "user" | "assistant" | "tool" | "system";

export interface DiagnosticEventRead {
  id: number;
  role: DiagnosticEventRole;
  content: string;
  tool_name: string | null;
  tool_payload: Record<string, unknown> | null;
}

export interface DiagnosticSessionRead {
  id: number;
  external_call_id: string | null;
  customer_name: string | null;
  customer_email: string | null;
  customer_phone: string | null;
  appliance_type: string | null;
  symptoms: string[];
  zip_code: string | null;
  status: DiagnosticSessionStatus;
  safety_blocked: boolean;
  recommended_action: string | null;
  events: DiagnosticEventRead[];
}

export interface DiagnosticSessionListResponse {
  sessions: DiagnosticSessionRead[];
}

export interface DiagnosticSessionCreate {
  external_call_id?: string;
  customer_name?: string;
  customer_email?: string;
  customer_phone?: string;
}

export interface DiagnosticTurnResponse {
  session: DiagnosticSessionRead;
  assistant_message: string;
  tool_calls: { name: string; arguments: Record<string, unknown> }[];
}

export type ImageUploadStatus =
  | "pending_upload"
  | "uploaded"
  | "analysis_pending"
  | "analyzed"
  | "failed"
  | "expired";

export interface ImageUploadRead {
  id: number;
  diagnostic_session_id: number;
  storage_bucket: string;
  storage_key: string;
  original_filename: string | null;
  content_type: string | null;
  byte_size: number | null;
  status: ImageUploadStatus;
  expires_at: string;
  uploaded_at: string | null;
  analysis_started_at: string | null;
  analyzed_at: string | null;
  analysis_summary: string | null;
  analysis_result: Record<string, unknown> | null;
  failure_reason: string | null;
}

export interface ImageUploadListResponse {
  uploads: ImageUploadRead[];
}

export interface UploadMetadataRequest {
  filename: string;
  content_type: string;
  byte_size: number;
}

export interface PresignedUploadResponse {
  upload_id: number;
  method: "POST";
  url: string;
  fields: Record<string, string>;
  max_byte_size: number;
  expires_at: string;
  storage_key: string;
}

export interface UploadLinkResponse {
  id: number;
  diagnostic_session_id: number;
  upload_url: string;
  expires_at: string;
  email_sent: boolean;
  status: ImageUploadStatus;
}

export interface DashboardData {
  sessions: DiagnosticSessionRead[];
  appointments: AppointmentRead[];
  uploadsBySession: Record<number, ImageUploadRead[]>;
}
