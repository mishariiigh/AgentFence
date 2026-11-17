# AgentFence Dashboard

Next.js 16 + TypeScript + Tailwind CSS frontend for the AgentFence platform.

> **Note:** All metrics shown in this dashboard are clearly labeled
> **demonstration data**. Live integration with the local AgentFence API is a
> planned milestone (see the root `docs/ROADMAP.md`).

## Development

```bash
npm install
npm run dev        # http://localhost:3000
```

## Checks

```bash
npm run lint       # ESLint
npx tsc --noEmit   # TypeScript
npm run build      # production build
```

## Pages

- `/` Overview — posture summary, getting started
- `/scans` Security Scans — scan history format
- `/findings` Findings — structured finding view
- `/arena` Attack Lab — scenario results
- `/policies` Policy Management — rule tables
- `/mcp` MCP Inspection — server config review
- `/reports` Reports — report artifacts
- `/settings` Settings — security defaults and local API info

## API

The dashboard is designed to consume the local API started with
`agentfence dashboard` (default `http://127.0.0.1:8000`):

- `GET /api/v1/health` — health check
- `POST /api/v1/scan` — run a read-only scan of a local path
- `POST /api/v1/mcp/inspect` — inspect an MCP config file (read-only)
