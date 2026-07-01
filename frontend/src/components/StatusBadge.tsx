import { titleize } from "../format";

const STATUS_STYLES: Record<string, string> = {
  active: "border-info/30 bg-info/10 text-info",
  ready_to_schedule: "border-accent/30 bg-accent-soft text-accent",
  scheduled: "border-success/30 bg-success/10 text-success",
  safety_escalated: "border-danger/30 bg-danger/10 text-danger",
  closed: "border-muted/30 bg-surface-muted text-muted",
  held: "border-warning/40 bg-warning/10 text-warning",
  booked: "border-success/30 bg-success/10 text-success",
  cancelled: "border-danger/30 bg-danger/10 text-danger",
  pending_upload: "border-warning/40 bg-warning/10 text-warning",
  uploaded: "border-info/30 bg-info/10 text-info",
  analysis_pending: "border-info/30 bg-info/10 text-info",
  analyzed: "border-success/30 bg-success/10 text-success",
  failed: "border-danger/30 bg-danger/10 text-danger",
  expired: "border-muted/30 bg-surface-muted text-muted",
};

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex min-h-7 items-center rounded-full border px-2.5 text-xs font-semibold ${STATUS_STYLES[status] ?? "border-border bg-surface-muted text-muted"}`}
    >
      {titleize(status)}
    </span>
  );
}
