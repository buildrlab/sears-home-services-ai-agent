# Frontend

React frontend for the Sears Home Services voice AI appliance diagnostic agent.

## Stack

- React 19.2.7
- Vite 8.1.2
- TypeScript 6.0.3
- Tailwind CSS v4.3.2
- Vitest 4.1.9
- React Testing Library 16.3.2
- Playwright 1.61.1
- ESLint 10.6.0

## Responsibilities

- Secure appliance image upload page.
- Upload result/status page.
- Minimal reviewer dashboard for call sessions, appointments, uploads, and diagnostic events.
- Functional, polished, responsive UI.

## Configuration

Copy the example environment file when overriding local defaults:

```bash
cp .env.example .env
```

`VITE_API_BASE_URL` defaults to `http://127.0.0.1:8000`.

The frontend handles upload links at `/uploads/<token>`. The backend should use
`UPLOAD_LINK_BASE_URL=http://127.0.0.1:5173/uploads` locally and
`UPLOAD_LINK_BASE_URL=https://shs.buildrlab.com/uploads` on AWS.

## Local Run

```bash
pnpm install
pnpm dev
```

Open `http://127.0.0.1:5173`. If the port is in use, Vite prints the alternate
local URL.

## Testing

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

Component tests cover dashboard rendering, diagnostic turn submission, upload
token errors, file validation, and presigned upload flow. Playwright tests cover
the dashboard and upload page with API mocks and fail on unexpected browser
console errors.

## Infrastructure

Frontend AWS resources are managed from `frontend/infra` using Terraform.
