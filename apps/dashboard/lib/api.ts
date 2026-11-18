/**
 * Typed API client for the local AgentFence backend.
 *
 * Base URL comes from NEXT_PUBLIC_AGENTFENCE_API and defaults to the local
 * API started with `agentfence dashboard` (http://127.0.0.1:8000).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_AGENTFENCE_API ?? "http://127.0.0.1:8000";

export type Severity =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "info";

export interface FindingDto {
  finding_pk: number;
  scan_id: string;
  rule_id: string;
  title: string;
  description: string;
  severity: Severity;
  file_ref: string | null;
  remediation: string;
  evidence: string | null;
}

export interface ScanSummaryDto {
  scan_id: string;
  created_at: string;
  target_display: string;
  status: string;
  scanner_version: string;
  risk_score: number;
  files_inspected: number;
  total_findings: number;
  critical_findings: number;
  high_findings: number;
  medium_findings: number;
  low_findings: number;
  info_findings: number;
  kind: string;
}

export interface ScanDetailDto {
  scan: ScanSummaryDto;
  findings: FindingDto[];
}

export interface ScanListDto {
  scans: ScanSummaryDto[];
  total: number;
  limit: number;
  offset: number;
}

export interface SummaryDto {
  total_scans: number;
  total_findings: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface ScanStartedDto {
  scan_id: string;
  result: {
    target: string;
    scanner: string;
    files_inspected: number;
    findings: {
      id: string;
      title: string;
      severity: Severity;
      category: string;
      description: string;
      remediation: string;
      file: string | null;
      evidence: string | null;
    }[];
  };
  risk_score: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      ...init,
    });
  } catch {
    throw new ApiError(
      `Cannot reach the AgentFence API at ${API_BASE_URL}. Start it with \`agentfence dashboard\`.`,
      0,
    );
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // keep status-based message
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/api/v1/health"),

  summary: () => request<SummaryDto>("/api/v1/summary"),

  listScans: (params?: {
    limit?: number;
    offset?: number;
    order?: "asc" | "desc";
    severity?: Severity;
  }) => {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    if (params?.order) qs.set("order", params.order);
    if (params?.severity) qs.set("severity", params.severity);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<ScanListDto>(`/api/v1/scans${suffix}`);
  },

  getScan: (scanId: string) =>
    request<ScanDetailDto>(`/api/v1/scans/${encodeURIComponent(scanId)}`),

  runScan: (path: string) =>
    request<ScanStartedDto>("/api/v1/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),

  inspectMcp: (path: string) =>
    request<ScanStartedDto>("/api/v1/mcp/inspect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),
};
