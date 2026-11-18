# AgentFence Dashboard

Next.js 16 + TypeScript + Tailwind CSS frontend for the AgentFence platform.

**Overview, Security Scans, Scan Details, Findings, MCP Inspection, Attack
Lab, Policies, and Reports pages consume live data from the local AgentFence
API and its SQLite history.** Settings remains an informational page.

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

## Local session token (required for mutations)

The API rejects mutating requests (scans, Arena runs, policy evaluation)
without a session token. Generate/setup:

```bash
# token is auto-created by the API at .agentfence/.api-token
cd apps/dashboard
printf 'NEXT_PUBLIC_AGENTFENCE_API=http://127.0.0.1:8000\nNEXT_PUBLIC_AGENTFENCE_TOKEN=%s\n' "$(cat ../../.agentfence/.api-token)" > .env.local
npm run dev
```

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
- `/arena` Attack Lab — live: scenario catalogue, run, results, history
- `/policies` Policy Management — live: catalogue, validate/evaluate, history
- `/mcp` MCP Inspection — live via `POST /api/v1/mcp/inspect`
- `/reports` Reports — live: real scan/Arena/policy data
- `/settings` Settings — security defaults and local API info
