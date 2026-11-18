# AgentFence Dashboard

Next.js 16 + TypeScript + Tailwind CSS frontend for the AgentFence platform.

**Overview, Security Scans, Scan Details, Findings, and MCP Inspection pages
consume live data from the local AgentFence API and its SQLite scan history.**
Attack Lab, Policies, Reports, and Settings remain clearly-labelled
demonstration/planned views until their backend integrations ship.

## Development

```bash
npm install
npm run dev        # http://localhost:3000
```

The dashboard talks to the API at `NEXT_PUBLIC_AGENTFENCE_API`
(default: `http://127.0.0.1:8000` — the API started with `agentfence dashboard`).
To override, create `.env.local`:

```bash
echo 'NEXT_PUBLIC_AGENTFENCE_API=http://127.0.0.1:8001' > .env.local
```

If the API is offline, pages show explicit error states (never silent demo
substitution), and a connection indicator in the header shows API health.

## Checks

```bash
npm run lint       # ESLint
npx tsc --noEmit   # TypeScript
npm run test       # vitest (API client + component states)
npm run build      # production build
```

## Pages

- `/` Overview — live totals from `GET /api/v1/summary` + latest scans
- `/scans` Security Scans — persisted history, run new scans (`POST /api/v1/scan`)
- `/scans/[id]` Scan Details — actual findings from `GET /api/v1/scans/{id}`
- `/findings` Findings — aggregated findings with severity filter
- `/arena` Attack Lab — *demonstration data*
- `/policies` Policy Management — *demonstration data*
- `/mcp` MCP Inspection — live via `POST /api/v1/mcp/inspect`
- `/reports` Reports — *demonstration data*
- `/settings` Settings — security defaults and local API info
