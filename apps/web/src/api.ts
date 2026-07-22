import type {
  CapabilityDetail,
  CapabilityTreeNode,
  ImportBatch,
  ImportResult,
  TableDetail,
  TableGroup,
} from "./types";

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

// ============================================================
// Data Overview APIs
// ============================================================

export interface OverviewStats {
  totalTables: number;
  totalRows: number;
}

export async function fetchOverviewStats(): Promise<OverviewStats> {
  const groups = await fetchTableGroups();
  const totalTables = groups.reduce((sum, g) => sum + g.tables.length, 0);
  const totalRows = groups.reduce(
    (sum, g) => sum + g.tables.reduce((s, t) => s + t.rowCount, 0),
    0
  );
  return { totalTables, totalRows };
}

export async function fetchTableGroups(): Promise<TableGroup[]> {
  const response = await fetch(`${API_PREFIX}/data-overview/tables`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch table groups: ${response.statusText}`);
  }
  const data = await response.json();
  return data.groups || [];
}

export async function fetchTableDetail(
  tableName: string,
  page = 1,
  pageSize = 25
): Promise<TableDetail> {
  const params = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
  });
  return request<TableDetail>(
    `/data-overview/tables/${encodeURIComponent(tableName)}?${params}`
  );
}

// ============================================================
// Import APIs
// ============================================================

export async function uploadXlsx(
  file: File,
  subDirectionId?: number
): Promise<ImportResult> {
  const formData = new FormData();
  formData.append("file", file);

  const params = subDirectionId
    ? `?subDirectionId=${subDirectionId}`
    : "";

  const response = await fetch(`${API_PREFIX}/import/xlsx${params}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.message ?? `上传失败（${response.status}）`);
  }

  return response.json();
}

export async function fetchImportBatches(
  page = 1,
  pageSize = 20
): Promise<{ items: ImportBatch[]; pagination: { total: number } }> {
  const params = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
  });
  return request(`/import/batches?${params}`);
}

export async function fetchImportStatus(batchId: number): Promise<ImportResult> {
  return request<ImportResult>(`/import/status/${batchId}`);
}

// ============================================================
// Career Database APIs
// ============================================================

export async function fetchCareerDirections() {
  return request<{ items: any[] }>("/career-directions");
}

export async function fetchCareerUnits(params: {
  q?: string;
  subDirectionId?: number;
  companyId?: number;
  page?: number;
  pageSize?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set("q", params.q);
  if (params.subDirectionId) searchParams.set("subDirectionId", String(params.subDirectionId));
  if (params.companyId) searchParams.set("companyId", String(params.companyId));
  if (params.page) searchParams.set("page", String(params.page));
  if (params.pageSize) searchParams.set("pageSize", String(params.pageSize));
  return request(`/career-units?${searchParams}`);
}

export async function fetchCareerUnitDetail(unitId: number) {
  return request(`/career-units/${unitId}`);
}

// ============================================================
// Capability Database APIs
// ============================================================

export async function fetchCapabilityDirections() {
  return request<{ items: any[] }>("/capability-directions");
}

export async function fetchCapabilities(params: {
  q?: string;
  categoryId?: number;
  page?: number;
  pageSize?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set("q", params.q);
  if (params.categoryId) searchParams.set("categoryId", String(params.categoryId));
  if (params.page) searchParams.set("page", String(params.page));
  if (params.pageSize) searchParams.set("pageSize", String(params.pageSize));
  return request(`/capabilities?${searchParams}`);
}

export async function fetchCapabilityDetail(capabilityId: number): Promise<CapabilityDetail> {
  return request<CapabilityDetail>(`/capabilities/${capabilityId}`);
}

export async function fetchCapabilityTree(): Promise<CapabilityTreeNode> {
  return request<CapabilityTreeNode>("/capabilities/graph-tree");
}

// ============================================================
// Enterprise Database APIs
// ============================================================

export async function fetchCompanies(params: {
  q?: string;
  page?: number;
  pageSize?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set("q", params.q);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.pageSize) searchParams.set("pageSize", String(params.pageSize));
  return request(`/companies?${searchParams}`);
}

export async function fetchCompanyDetail(companyId: number) {
  return request(`/companies/${companyId}`);
}
