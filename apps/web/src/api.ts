import type { ActiveCapability, CapabilityCandidate, CapabilityGraphDetail, CareerGraphDirectory, CareerGraphJobDetail, CareerSpectrumPayload, CategoryCandidate, DataOverviewPayload, DataTableDetail, Evidence, GovernanceSummary, GraphPayload, GraphPayloadV2, JobDetail, JobSummary, NormalizationCandidate, Page, VectorizationRun } from "./types";

const API_PREFIX = "/api/v1";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.message ?? `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

async function mutate<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new Error(result?.message ?? `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getDataOverview(signal?: AbortSignal) {
    return request<DataOverviewPayload>("/data-overview", signal);
  },
  getDataTable(tableName: string, page = 1, pageSize = 25, signal?: AbortSignal) {
    const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
    return request<DataTableDetail>(`/data-overview/tables/${encodeURIComponent(tableName)}?${params}`, signal);
  },
  getGovernanceSummary(signal?: AbortSignal) {
    return request<GovernanceSummary>("/capability-governance/summary", signal);
  },
  getCapabilityCandidates(signal?: AbortSignal) {
    return request<{ items: CapabilityCandidate[] }>("/capability-governance/pending/capabilities?limit=500", signal);
  },
  getActiveCapabilities(signal?: AbortSignal) {
    return request<{ items: ActiveCapability[] }>("/capability-governance/capabilities?limit=1000", signal);
  },
  getCategoryCandidates(signal?: AbortSignal) {
    return request<{ items: CategoryCandidate[] }>("/capability-governance/pending/categories?limit=500", signal);
  },
  getNormalizationCandidates(signal?: AbortSignal) {
    return request<{ items: NormalizationCandidate[] }>("/capability-governance/pending/normalizations?limit=500", signal);
  },
  reviewCapabilityCandidate(candidateId: number, body: Record<string, unknown>) {
    return mutate<{ id: number; status: string; resolvedCapabilityId: number | null }>(
      `/capability-governance/capabilities/${candidateId}/review`,
      body,
    );
  },
  reviewCategoryCandidate(candidateId: number, body: Record<string, unknown>) {
    return mutate<{ id: number; status: string; resolvedCategoryId: number | null }>(
      `/capability-governance/categories/${candidateId}/review`,
      body,
    );
  },
  reviewNormalizationCandidate(reviewId: number, body: Record<string, unknown>) {
    return mutate<{ id: number; status: string }>(
      `/capability-governance/normalizations/${reviewId}/review`,
      body,
    );
  },
  listJobs(query = "", pageSize = 30, signal?: AbortSignal) {
    const params = new URLSearchParams({ q: query, pageSize: String(pageSize) });
    return request<Page<JobSummary>>(`/jobs?${params}`, signal);
  },
  getJob(jobId: number, signal?: AbortSignal) {
    return request<JobDetail>(`/jobs/${jobId}`, signal);
  },
  getNeighborhood(nodeKey: string, signal?: AbortSignal) {
    // Keep the first screen readable while retaining the complete skill/evidence
    // counts in the inspector. The backend ranks required/high-weight relations
    // first, so this is a deliberate visual budget rather than data deletion.
    const params = new URLSearchParams({ node: nodeKey, depth: "1", maxNodes: "28", maxEdges: "48" });
    return request<GraphPayload>(`/graph/neighborhood?${params}`, signal);
  },
  getOverview(signal?: AbortSignal) {
    return request<GraphPayload>("/graph/overview?aggregation=job&maxNodes=500&maxEdges=1000", signal);
  },
  listEvidence(filters: { mappingId?: number; jobId?: number }, signal?: AbortSignal) {
    const params = new URLSearchParams({ pageSize: "20" });
    if (filters.mappingId) params.set("mappingId", String(filters.mappingId));
    if (filters.jobId) params.set("jobId", String(filters.jobId));
    return request<Page<Evidence>>(`/evidence?${params}`, signal);
  },
  getCapabilityGraph(signal?: AbortSignal) {
    return request<GraphPayloadV2>("/capability-graph/tree?depth=3", signal);
  },
  getCapabilityGraphDetail(capabilityId: number, signal?: AbortSignal) {
    return request<CapabilityGraphDetail>(`/capability-graph/capabilities/${capabilityId}`, signal);
  },
  getCareerGraph(nodeKey?: string, neighborLimit = 14, signal?: AbortSignal) {
    const params = new URLSearchParams({ neighborLimit: String(neighborLimit) });
    if (nodeKey) params.set("node", nodeKey);
    return request<GraphPayloadV2>(`/career-graph/overview?${params}`, signal);
  },
  getCareerGraphDirectory(signal?: AbortSignal) {
    return request<CareerGraphDirectory>("/career-graph/directory", signal);
  },
  getCareerGraphJobDetail(jobId: number, signal?: AbortSignal) {
    return request<CareerGraphJobDetail>(`/career-graph/jobs/${jobId}`, signal);
  },
  getCareerSpectrum(signal?: AbortSignal) {
    return request<CareerSpectrumPayload>("/career-spectrum", signal);
  },
  createVectorizationRun(job: Record<string, string>) {
    return mutate<{ runId: number; status: string }>("/vectorization/runs", { source: "manual", job });
  },
  getVectorizationRun(runId: number, signal?: AbortSignal) {
    return request<VectorizationRun>(`/vectorization/runs/${runId}`, signal);
  },
  decideMatch(body: Record<string, unknown>) {
    return mutate<{ decisionId: number; status: string }>("/job-match-decisions", body);
  },
};
