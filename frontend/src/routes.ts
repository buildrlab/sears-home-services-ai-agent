export function extractUploadToken(path: string): string | null {
  const normalizedPath = path.replace(/\/$/, "");
  const match = /^\/uploads?\/([^/]+)$/.exec(normalizedPath);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}
