import type { ActiveCapability, CapabilityCandidate, CapabilityGraphDetail, CareerCluster, CareerClusterCandidate, CareerClusteringStatus, CareerGraphDirectory, CareerGraphJobDetail, CareerSpectrumPayload, CategoryCandidate, DataOverviewPayload, DataTableDetail, Evidence, GovernanceSummary, GraphPayload, GraphPayloadV2, JDPipelineJob, JDPipelineStatus, JDPipelineSummary, JobDetail, JobSummary, NormalizationCandidate, Page, VectorizationRun } from "./types";

const API_PREFIX = "/api/v1";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  try {
    const response = await fetch(`${API_PREFIX}${path}`, {
      headers: { Accept: "application/json" },
      signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.message ?? `请求失败（${response.status}）`);
    }
    return response.json() as Promise<T>;
  } catch (error: any) {
    if (error.name === "AbortSignal" || error.name === "AbortError") {
      throw error;
    }
    if (error.message === "Failed to fetch" || error.name === "TypeError") {
      throw new Error("无法连接后端服务，请检查后端 API 是否启动或正在处理密集高并发任务。");
    }
    throw error;
  }
}

async function mutate<T>(path: string, body: unknown): Promise<T> {
  try {
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
  } catch (error: any) {
    if (error.message === "Failed to fetch" || error.name === "TypeError") {
      throw new Error("无法连接后端服务，请稍后重试。");
    }
    throw error;
  }
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
  getCareerClusteringStatus(signal?: AbortSignal) {
    return request<CareerClusteringStatus>("/career-clustering/status", signal);
  },
  getCareerClusterCandidates(signal?: AbortSignal) {
    return request<{ items: CareerClusterCandidate[] }>("/career-clustering/candidates?limit=500", signal);
  },
  getCareerClusters(signal?: AbortSignal) {
    return request<{ items: CareerCluster[] }>("/career-clustering/clusters?limit=1000", signal);
  },
  runCareerClusteringBatch(limit = 5) {
    return mutate<{ items: { careerUnitId: number; status: string; decision?: string; error?: string }[]; count: number }>(
      `/career-clustering/batch?limit=${limit}`,
      {},
    );
  },
  reviewCareerClusterCandidate(candidateId: number, body: Record<string, unknown>) {
    return mutate<{ id: number; status: string; resolvedClusterId: number | null }>(
      `/career-clustering/candidates/${candidateId}/review`,
      body,
    );
  },
  getJDPipelineSummary(signal?: AbortSignal) {
    return request<JDPipelineSummary>("/jd-pipeline/summary", signal);
  },
  getJDPipelineJobs(filters: {
    query?: string;
    source?: string;
    capabilityStatus?: JDPipelineStatus | "";
    careerStatus?: JDPipelineStatus | "";
    page?: number;
    pageSize?: number;
  }, signal?: AbortSignal) {
    const params = new URLSearchParams({
      page: String(filters.page ?? 1),
      pageSize: String(filters.pageSize ?? 30),
    });
    if (filters.query) params.set("q", filters.query);
    if (filters.source) params.set("source", filters.source);
    if (filters.capabilityStatus) params.set("capabilityStatus", filters.capabilityStatus);
    if (filters.careerStatus) params.set("careerStatus", filters.careerStatus);
    return request<{ items: JDPipelineJob[]; page: { page: number; pageSize: number; total: number } }>(
      `/jd-pipeline/jobs?${params}`,
      signal,
    );
  },
  processJDPipeline(careerUnitIds: number[], action: "capability" | "career" | "both") {
    return mutate<{ items: { careerUnitId: number; status: string; capability: string; career: string; capabilityError?: string; careerError?: string }[]; count: number }>(
      "/jd-pipeline/process",
      { careerUnitIds, action },
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
