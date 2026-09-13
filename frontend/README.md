# Frontend — Admin Panel

React 18 + TypeScript + Vite admin panel for the volunteer management system.
See the [root README](../README.md) for full project context, architecture, and features.

## Stack

- React 18 + TypeScript, Vite
- Tailwind CSS v4 + shadcn/ui
- TanStack Query v5 for server state
- React Router v7
- Recharts for analytics

## Run locally

```bash
npm install
npm run dev
```

Opens at http://127.0.0.1:5173. The dev server proxies API calls to the backend
at http://localhost:8000 by default — override with `VITE_API_BASE_URL` in a
local `.env` file (see [.env.example](./.env.example)).

The backend must be running for auth and data. See the [root README](../README.md#backend-setup)
for backend setup.

## Feature layout

Each feature under `src/features/` is self-contained (components, hooks,
API client, types). Shared UI primitives live in `src/components/`. Cross-cutting
concerns (auth context, tenant filter, API client) live in `src/context/` and `src/lib/`.
