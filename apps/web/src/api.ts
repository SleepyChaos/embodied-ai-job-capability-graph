import type {
  DatabaseStats,
  ImportHistoryItem,
  ImportResult,
  Page,
  TableDetail,
  TableSummary,
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

export const api = {
  // === Data Overview ===
  getStats(signal?: AbortSignal) {
    return request<DatabaseStats>("/data-overview/stats", signal);
  },
  listTables(signal?: AbortSignal) {
    return request<TableSummary[]>("/data-overview/tables", signal);
  },
  getTable(name: string, page = 1, pageSize = 20, signal?: AbortSignal) {
    const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
    return request<TableDetail>(`/data-overview/tables/${encodeURIComponent(name)}?${params}`, signal);
  },

  // === Import ===
  uploadXlsx(file: File): Promise<ImportResult> {
    const formData = new FormData();
    formData.append("file", file);
    return fetch(`${API_PREFIX}/import/xlsx`, {
      method: "POST",
      body: formData,
    }).then(async (response) => {
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.message ?? `上传失败（${response.status}）`);
      }
      return response.json() as Promise<ImportResult>;
    });
  },
  getImportHistory(signal?: AbortSignal) {
    return request<ImportHistoryItem[]>("/import/history", signal);
  },
};
