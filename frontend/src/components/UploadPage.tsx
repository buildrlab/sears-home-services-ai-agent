import {
  AlertTriangle,
  CheckCircle2,
  FileImage,
  LoaderCircle,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  completeUpload,
  createPresignedUpload,
  getUploadByToken,
  uploadFileToStorage,
} from "../api";
import { formatDateTime, formatFileSize } from "../format";
import type { ImageUploadRead, UploadMetadataRequest } from "../types";
import { ALLOWED_IMAGE_TYPES, validateImageFile } from "../uploadValidation";
import { StatusBadge } from "./StatusBadge";

type LoadState = "loading" | "ready" | "uploading" | "success" | "error";

interface UploadPageProps {
  token: string;
}

export function UploadPage({ token }: UploadPageProps) {
  const [upload, setUpload] = useState<ImageUploadRead | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadUpload() {
      setState("loading");
      setMessage(null);

      try {
        const nextUpload = await getUploadByToken(token);
        if (!mounted) {
          return;
        }
        setUpload(nextUpload);
        setState("ready");
      } catch (error) {
        if (!mounted) {
          return;
        }
        setState("error");
        setMessage(readableUploadError(error));
      }
    }

    void loadUpload();

    return () => {
      mounted = false;
    };
  }, [token]);

  const selectedFileMessage = useMemo(() => {
    if (!file) {
      return "PNG, JPEG, or WebP up to 10 MB.";
    }

    return `${file.name} / ${formatFileSize(file.size)}`;
  }, [file]);

  async function handleUpload() {
    if (!file) {
      setMessage("Choose an appliance image before uploading.");
      return;
    }

    const validationMessage = validateImageFile(file);
    if (validationMessage) {
      setMessage(validationMessage);
      return;
    }

    const metadata: UploadMetadataRequest = {
      filename: file.name,
      content_type: file.type,
      byte_size: file.size,
    };

    setState("uploading");
    setMessage(null);

    try {
      const presignedUpload = await createPresignedUpload(token, metadata);
      await uploadFileToStorage(presignedUpload, file);
      const completedUpload = await completeUpload(token, metadata);
      setUpload(completedUpload);
      setState("success");
      setMessage("Upload complete.");
    } catch (error) {
      setState("ready");
      setMessage(readableUploadError(error));
    }
  }

  if (state === "loading") {
    return (
      <section className="mx-auto flex min-h-[520px] w-full max-w-3xl items-center justify-center px-4 py-12">
        <div className="flex items-center gap-3 rounded-card border border-border bg-surface px-4 py-3 text-sm text-muted shadow-sm">
          <LoaderCircle className="h-5 w-5 animate-spin text-primary" aria-hidden="true" />
          Loading upload link
        </div>
      </section>
    );
  }

  if (state === "error" || !upload) {
    return (
      <section className="mx-auto flex min-h-[520px] w-full max-w-3xl items-center justify-center px-4 py-12">
        <div className="w-full rounded-card border border-danger/30 bg-surface p-6 shadow-sm">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-1 h-5 w-5 flex-none text-danger" aria-hidden="true" />
            <div>
              <h1 className="text-xl font-semibold text-foreground">Upload link unavailable</h1>
              <p className="mt-2 text-sm leading-6 text-muted">{message}</p>
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto grid w-full max-w-5xl gap-6 px-4 py-8 md:grid-cols-[1fr_320px]">
      <div className="rounded-card border border-border bg-surface p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase text-primary">Sears Home Services</p>
            <h1 className="mt-2 text-2xl font-semibold text-foreground">Appliance image upload</h1>
          </div>
          <StatusBadge status={upload.status} />
        </div>

        <div className="mt-6 rounded-card border border-border bg-surface-muted p-4">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-1 h-5 w-5 flex-none text-accent" aria-hidden="true" />
            <div className="text-sm leading-6 text-muted">
              <p className="font-medium text-foreground">Secure upload link</p>
              <p>Expires {formatDateTime(upload.expires_at)}. Images are accepted only in JPEG, PNG, or WebP format.</p>
            </div>
          </div>
        </div>

        <form
          className="mt-6 grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void handleUpload();
          }}
        >
          <label className="grid gap-2 text-sm font-medium text-foreground">
            Appliance image
            <input
              className="w-full rounded-card border border-border bg-surface px-3 py-3 text-sm file:mr-4 file:rounded-card file:border-0 file:bg-primary file:px-3 file:py-2 file:text-sm file:font-semibold file:text-primary-foreground"
              type="file"
              accept={ALLOWED_IMAGE_TYPES.join(",")}
              onChange={(event) => {
                setFile(event.currentTarget.files?.[0] ?? null);
                setMessage(null);
              }}
            />
          </label>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted">
            <span className="inline-flex min-h-9 items-center gap-2">
              <FileImage className="h-4 w-4 text-accent" aria-hidden="true" />
              {selectedFileMessage}
            </span>
            <button
              className="inline-flex min-h-11 items-center gap-2 rounded-card bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/40"
              type="submit"
              disabled={state === "uploading"}
            >
              {state === "uploading" ? (
                <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <UploadCloud className="h-4 w-4" aria-hidden="true" />
              )}
              Upload image
            </button>
          </div>
        </form>

        {message ? (
          <div
            className={`mt-5 rounded-card border px-4 py-3 text-sm ${
              state === "success"
                ? "border-success/30 bg-success/10 text-success"
                : "border-warning/40 bg-warning/10 text-foreground"
            }`}
            role="status"
          >
            <div className="flex items-center gap-2">
              {state === "success" ? (
                <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
              )}
              {message}
            </div>
          </div>
        ) : null}
      </div>

      <aside className="rounded-card border border-border bg-surface p-5 shadow-sm">
        <h2 className="text-sm font-semibold uppercase text-muted">Upload details</h2>
        <dl className="mt-4 grid gap-4 text-sm">
          <Detail label="Session" value={`#${String(upload.diagnostic_session_id)}`} />
          <Detail label="Filename" value={upload.original_filename ?? "Pending"} />
          <Detail label="Size" value={formatFileSize(upload.byte_size)} />
          <Detail label="Uploaded" value={formatDateTime(upload.uploaded_at)} />
          <Detail label="Analyzed" value={formatDateTime(upload.analyzed_at)} />
        </dl>
        {upload.analysis_summary ? (
          <p className="mt-5 rounded-card border border-accent/30 bg-accent-soft p-3 text-sm leading-6 text-foreground">
            {upload.analysis_summary}
          </p>
        ) : null}
      </aside>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase text-muted">{label}</dt>
      <dd className="mt-1 text-foreground">{value}</dd>
    </div>
  );
}

function readableUploadError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404 || error.status === 410) {
      return "This upload link is expired or no longer valid.";
    }
    return "The upload service returned an error. Try again in a moment.";
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "The upload could not be completed.";
}
