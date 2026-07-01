import {
  Activity,
  CalendarCheck,
  FileImage,
  LoaderCircle,
  Mail,
  PhoneCall,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type SyntheticEvent,
} from "react";
import type { LucideIcon } from "lucide-react";

import {
  analyzeUpload,
  createDiagnosticSession,
  createUploadLink,
  loadDashboardData,
  processDiagnosticTurn,
} from "../api";
import { compactList, formatDateTime, formatFileSize } from "../format";
import type { DashboardData, DiagnosticSessionCreate, ImageUploadRead } from "../types";
import { StatusBadge } from "./StatusBadge";

const EMPTY_DATA: DashboardData = {
  sessions: [],
  appointments: [],
  uploadsBySession: {},
};

export function Dashboard() {
  const [data, setData] = useState<DashboardData>(EMPTY_DATA);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newSession, setNewSession] = useState({
    customer_name: "",
    customer_email: "",
    customer_phone: "",
  });
  const [turnMessage, setTurnMessage] = useState("");
  const [uploadEmail, setUploadEmail] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const nextData = await loadDashboardData();
      setData(nextData);
      setSelectedSessionId((current) => {
        if (current && nextData.sessions.some((session) => session.id === current)) {
          return current;
        }

        return nextData.sessions[0]?.id ?? null;
      });
    } catch (refreshError) {
      setError(readableDashboardError(refreshError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void refresh();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [refresh]);

  const selectedSession = useMemo(
    () => data.sessions.find((session) => session.id === selectedSessionId) ?? null,
    [data.sessions, selectedSessionId]
  );
  const selectedUploads = selectedSession
    ? data.uploadsBySession[selectedSession.id] ?? []
    : [];
  const totalUploads = Object.values(data.uploadsBySession).reduce(
    (total, uploads) => total + uploads.length,
    0
  );

  async function handleCreateSession(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice(null);
    const payload: DiagnosticSessionCreate = cleanPayload(newSession);

    if (!payload.customer_email && !payload.customer_phone) {
      setError("Enter an email or phone number for the diagnostic session.");
      return;
    }

    try {
      const session = await createDiagnosticSession(payload);
      setNewSession({ customer_name: "", customer_email: "", customer_phone: "" });
      setNotice(`Created session #${String(session.id)}.`);
      await refresh();
      setSelectedSessionId(session.id);
    } catch (createError) {
      setError(readableDashboardError(createError));
    }
  }

  async function handleDiagnosticTurn(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedSession || !turnMessage.trim()) {
      return;
    }

    try {
      const response = await processDiagnosticTurn(selectedSession.id, turnMessage.trim());
      setTurnMessage("");
      setNotice(response.assistant_message);
      await refresh();
    } catch (turnError) {
      setError(readableDashboardError(turnError));
    }
  }

  async function handleUploadLink(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedSession || !uploadEmail.trim()) {
      return;
    }

    try {
      const response = await createUploadLink(selectedSession.id, uploadEmail.trim());
      setUploadEmail("");
      setNotice(
        response.email_sent
          ? `Upload link sent: ${response.upload_url}`
          : `Upload link created, but email delivery needs attention: ${response.upload_url}`
      );
      await refresh();
    } catch (uploadError) {
      setError(readableDashboardError(uploadError));
    }
  }

  async function handleAnalyze(upload: ImageUploadRead) {
    try {
      const analyzedUpload = await analyzeUpload(upload.id);
      setNotice(
        analyzedUpload.analysis_summary ?? `Upload #${String(upload.id)} analysis finished.`
      );
      await refresh();
    } catch (analysisError) {
      setError(readableDashboardError(analysisError));
    }
  }

  return (
    <main className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase text-primary">Reviewer dashboard</p>
          <h1 className="mt-2 text-2xl font-semibold text-foreground">Diagnostic operations</h1>
        </div>
        <button
          className="inline-flex min-h-11 items-center gap-2 rounded-card border border-border bg-surface px-4 text-sm font-semibold shadow-sm hover:bg-surface-muted focus:outline-none focus:ring-2 focus:ring-primary/30"
          type="button"
          onClick={() => {
            void refresh();
          }}
          disabled={loading}
        >
          {loading ? (
            <LoaderCircle className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
          ) : (
            <RefreshCw className="h-4 w-4 text-primary" aria-hidden="true" />
          )}
          Refresh
        </button>
      </header>

      <section className="grid gap-3 sm:grid-cols-3">
        <MetricCard icon={PhoneCall} label="Sessions" value={data.sessions.length} />
        <MetricCard icon={CalendarCheck} label="Appointments" value={data.appointments.length} />
        <MetricCard icon={FileImage} label="Uploads" value={totalUploads} />
      </section>

      {error ? (
        <div className="rounded-card border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-foreground" role="alert">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="rounded-card border border-accent/30 bg-accent-soft px-4 py-3 text-sm text-foreground" role="status">
          {notice}
        </div>
      ) : null}

      <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <div className="grid gap-6">
          <form className="rounded-card border border-border bg-surface p-5 shadow-sm" onSubmit={handleCreateSession}>
            <h2 className="text-base font-semibold text-foreground">New session</h2>
            <div className="mt-4 grid gap-3">
              <TextField
                label="Customer name"
                value={newSession.customer_name}
                onChange={(value) => {
                  setNewSession((current) => ({ ...current, customer_name: value }));
                }}
              />
              <TextField
                label="Customer email"
                type="email"
                value={newSession.customer_email}
                onChange={(value) => {
                  setNewSession((current) => ({ ...current, customer_email: value }));
                }}
              />
              <TextField
                label="Customer phone"
                type="tel"
                value={newSession.customer_phone}
                onChange={(value) => {
                  setNewSession((current) => ({ ...current, customer_phone: value }));
                }}
              />
            </div>
            <button
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-card bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/40"
              type="submit"
            >
              <PhoneCall className="h-4 w-4" aria-hidden="true" />
              Create session
            </button>
          </form>

          <div className="rounded-card border border-border bg-surface p-5 shadow-sm">
            <h2 className="text-base font-semibold text-foreground">Sessions</h2>
            <div className="mt-4 grid gap-2">
              {loading ? <LoadingRow label="Loading sessions" /> : null}
              {!loading && data.sessions.length === 0 ? (
                <p className="text-sm text-muted">No sessions yet.</p>
              ) : null}
              {data.sessions.map((session) => (
                <button
                  className={`rounded-card border p-3 text-left transition hover:border-primary/50 ${
                    session.id === selectedSessionId
                      ? "border-primary bg-primary/5"
                      : "border-border bg-surface"
                  }`}
                  type="button"
                  key={session.id}
                  onClick={() => {
                    setSelectedSessionId(session.id);
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-foreground">
                        {session.customer_name ?? `Session #${String(session.id)}`}
                      </p>
                      <p className="mt-1 text-sm text-muted">
                        {compactList([session.appliance_type, session.zip_code])}
                      </p>
                    </div>
                    <StatusBadge status={session.status} />
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="grid gap-6">
          <section className="rounded-card border border-border bg-surface p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-foreground">Session detail</h2>
                <p className="mt-1 text-sm text-muted">
                  {selectedSession
                    ? compactList([
                        selectedSession.customer_email,
                        selectedSession.customer_phone,
                        selectedSession.external_call_id,
                      ])
                    : "Select a session"}
                </p>
              </div>
              {selectedSession ? <StatusBadge status={selectedSession.status} /> : null}
            </div>

            {selectedSession ? (
              <>
                <dl className="mt-5 grid gap-4 sm:grid-cols-3">
                  <Detail label="Appliance" value={selectedSession.appliance_type ?? "Not captured"} />
                  <Detail
                    label="Symptoms"
                    value={
                      selectedSession.symptoms.length > 0
                        ? selectedSession.symptoms.join(", ")
                        : "Not captured"
                    }
                  />
                  <Detail label="ZIP" value={selectedSession.zip_code ?? "Not captured"} />
                </dl>

                <form className="mt-5 grid gap-3" onSubmit={handleDiagnosticTurn}>
                  <label className="grid gap-2 text-sm font-medium text-foreground">
                    Diagnostic turn
                    <textarea
                      className="min-h-24 rounded-card border border-border bg-surface px-3 py-2 text-sm leading-6 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      value={turnMessage}
                      onChange={(event) => {
                        setTurnMessage(event.currentTarget.value);
                      }}
                      placeholder="Refrigerator is leaking in 75201"
                    />
                  </label>
                  <button
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-card bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/40"
                    type="submit"
                    disabled={!turnMessage.trim()}
                  >
                    <Send className="h-4 w-4" aria-hidden="true" />
                    Send turn
                  </button>
                </form>
              </>
            ) : (
              <p className="mt-5 text-sm text-muted">No diagnostic session selected.</p>
            )}
          </section>

          <section className="grid gap-6 xl:grid-cols-2">
            <div className="rounded-card border border-border bg-surface p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <FileImage className="h-5 w-5 text-accent" aria-hidden="true" />
                <h2 className="text-base font-semibold text-foreground">Uploads</h2>
              </div>
              {selectedSession ? (
                <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={handleUploadLink}>
                  <label className="grid flex-1 gap-2 text-sm font-medium text-foreground">
                    Upload email
                    <input
                      className="min-h-10 rounded-card border border-border bg-surface px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      type="email"
                      value={uploadEmail}
                      onChange={(event) => {
                        setUploadEmail(event.currentTarget.value);
                      }}
                      placeholder="caller@example.com"
                    />
                  </label>
                  <button
                    className="mt-auto inline-flex min-h-10 items-center justify-center gap-2 rounded-card bg-accent px-4 text-sm font-semibold text-white hover:bg-accent/90 focus:outline-none focus:ring-2 focus:ring-accent/40"
                    type="submit"
                    disabled={!uploadEmail.trim()}
                  >
                    <Mail className="h-4 w-4" aria-hidden="true" />
                    Send link
                  </button>
                </form>
              ) : null}

              <div className="mt-4 grid gap-3">
                {selectedUploads.length === 0 ? (
                  <p className="text-sm text-muted">No uploads for this session.</p>
                ) : null}
                {selectedUploads.map((upload) => (
                  <div className="rounded-card border border-border bg-surface-muted p-3" key={upload.id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-foreground">
                          {upload.original_filename ?? `Upload #${String(upload.id)}`}
                        </p>
                        <p className="mt-1 text-sm text-muted">
                          {formatFileSize(upload.byte_size)} / expires {formatDateTime(upload.expires_at)}
                        </p>
                      </div>
                      <StatusBadge status={upload.status} />
                    </div>
                    {upload.analysis_summary ? (
                      <p className="mt-3 text-sm leading-6 text-foreground">{upload.analysis_summary}</p>
                    ) : null}
                    {["uploaded", "analysis_pending"].includes(upload.status) ? (
                      <button
                        className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-card border border-border bg-surface px-3 text-sm font-semibold hover:bg-surface-muted focus:outline-none focus:ring-2 focus:ring-primary/30"
                        type="button"
                        onClick={() => {
                          void handleAnalyze(upload);
                        }}
                      >
                        <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
                        Run analysis
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-card border border-border bg-surface p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <CalendarCheck className="h-5 w-5 text-primary" aria-hidden="true" />
                <h2 className="text-base font-semibold text-foreground">Appointments</h2>
              </div>
              <div className="mt-4 grid gap-3">
                {data.appointments.length === 0 ? (
                  <p className="text-sm text-muted">No appointments yet.</p>
                ) : null}
                {data.appointments.map((appointment) => (
                  <div className="rounded-card border border-border bg-surface-muted p-3" key={appointment.id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-foreground">
                          {appointment.customer.full_name}
                        </p>
                        <p className="mt-1 text-sm text-muted">
                          {appointment.appliance_type} / {appointment.zip_code}
                        </p>
                      </div>
                      <StatusBadge status={appointment.status} />
                    </div>
                    <p className="mt-3 text-sm text-foreground">
                      {formatDateTime(appointment.scheduled_start)} with {appointment.technician.name}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="rounded-card border border-border bg-surface p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-accent" aria-hidden="true" />
              <h2 className="text-base font-semibold text-foreground">Diagnostic events</h2>
            </div>
            <div className="mt-4 grid gap-3">
              {selectedSession?.events.length === 0 ? (
                <p className="text-sm text-muted">No events recorded.</p>
              ) : null}
              {selectedSession?.events.map((event) => (
                <div className="rounded-card border border-border bg-surface-muted p-3" key={event.id}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase text-primary">{event.role}</p>
                    {event.tool_name ? (
                      <span className="rounded-full border border-border bg-surface px-2 py-1 text-xs text-muted">
                        {event.tool_name}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-foreground">{event.content}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-card border border-border bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-muted">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
        </div>
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft text-accent">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "email" | "tel" | "text";
}) {
  return (
    <label className="grid gap-2 text-sm font-medium text-foreground">
      {label}
      <input
        className="min-h-10 rounded-card border border-border bg-surface px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        type={type}
        value={value}
        onChange={(event) => {
          onChange(event.currentTarget.value);
        }}
      />
    </label>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-card border border-border bg-surface-muted p-3">
      <dt className="text-xs font-semibold uppercase text-muted">{label}</dt>
      <dd className="mt-1 text-sm text-foreground">{value}</dd>
    </div>
  );
}

function LoadingRow({ label }: { label: string }) {
  return (
    <div className="inline-flex items-center gap-2 text-sm text-muted">
      <LoaderCircle className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
      {label}
    </div>
  );
}

function cleanPayload(values: {
  customer_name: string;
  customer_email: string;
  customer_phone: string;
}): DiagnosticSessionCreate {
  return {
    customer_name: values.customer_name.trim() || undefined,
    customer_email: values.customer_email.trim() || undefined,
    customer_phone: values.customer_phone.trim() || undefined,
  };
}

function readableDashboardError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return "The dashboard request failed.";
}
