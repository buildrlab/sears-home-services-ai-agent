import { Dashboard } from "./components/Dashboard";
import { UploadPage } from "./components/UploadPage";
import { extractUploadToken } from "./routes";

interface AppProps {
  path?: string;
}

export function App({ path = window.location.pathname }: AppProps) {
  const uploadToken = extractUploadToken(path);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <nav className="border-b border-border bg-surface">
        <div className="mx-auto flex min-h-16 w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4">
          <a className="text-base font-semibold text-foreground" href="/">
            Sears Home Services AI Agent
          </a>
          <div className="flex items-center gap-2 text-sm font-medium text-muted">
            <a className="rounded-card px-3 py-2 hover:bg-surface-muted" href="/">
              Dashboard
            </a>
          </div>
        </div>
      </nav>
      {uploadToken ? <UploadPage token={uploadToken} /> : <Dashboard />}
    </div>
  );
}
