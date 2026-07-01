export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Not set";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) {
    return "Pending";
  }

  if (bytes < 1024 * 1024) {
    return `${String(Math.round(bytes / 1024))} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function titleize(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function compactList(values: (string | null | undefined)[]): string {
  const compacted = values.filter((value): value is string => Boolean(value?.trim()));
  return compacted.length > 0 ? compacted.join(" / ") : "Not captured";
}
