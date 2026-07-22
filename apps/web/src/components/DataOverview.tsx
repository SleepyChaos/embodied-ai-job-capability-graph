import { useEffect, useState } from "react";

import { api } from "../api";
import type { DatabaseStats, TableDetail, TableSummary } from "../types";

const GROUP_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  career: { bg: "bg-primary/10", text: "text-primary", border: "border-primary/30" },
  capability: { bg: "bg-success/10", text: "text-success", border: "border-success/30" },
  company: { bg: "bg-warning/10", text: "text-warning", border: "border-warning/30" },
};

export function DataOverview() {
  const [stats, setStats] = useState<DatabaseStats | null>(null);
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [expandedTable, setExpandedTable] = useState<string | null>(null);
  const [tableDetail, setTableDetail] = useState<TableDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api.getStats(controller.signal),
      api.listTables(controller.signal),
    ])
      .then(([s, t]) => {
        setStats(s);
        setTables(t);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const handleTableClick = async (tableName: string) => {
    if (expandedTable === tableName) {
      setExpandedTable(null);
      setTableDetail(null);
      return;
    }
    setExpandedTable(tableName);
    setDetailLoading(true);
    try {
      const detail = await api.getTable(tableName);
      setTableDetail(detail);
    } catch {
      setTableDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleGroup = (group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  const groupedTables = tables.reduce<Record<string, TableSummary[]>>((acc, table) => {
    if (!acc[table.group]) acc[table.group] = [];
    acc[table.group].push(table);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-on-surface-variant">加载中...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Stats Header */}
      <div className="flex items-center gap-6">
        <div>
          <h2 className="text-2xl font-semibold text-on-surface">数据总览</h2>
          <p className="mt-1 text-sm text-on-surface-variant">
            {stats?.total_tables ?? 0} 张表 · {stats?.total_records ?? 0} 条记录
          </p>
        </div>
        <div className="flex gap-3">
          {stats?.groups.map((g) => {
            const colors = GROUP_COLORS[g.group] ?? GROUP_COLORS.career;
            return (
              <div
                key={g.group}
                className={`rounded-lg border px-4 py-2 ${colors.bg} ${colors.border}`}
              >
                <div className={`text-xs font-medium ${colors.text}`}>{g.label}</div>
                <div className="text-lg font-semibold text-on-surface">
                  {g.table_count} 表 / {g.record_count} 条
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Table Groups */}
      {Object.entries(groupedTables).map(([group, groupTables]) => {
        const colors = GROUP_COLORS[group] ?? GROUP_COLORS.career;
        const groupInfo = stats?.groups.find((g) => g.group === group);
        const isCollapsed = collapsedGroups.has(group);

        return (
          <section key={group} className="space-y-3">
            {/* Group Header */}
            <button
              onClick={() => toggleGroup(group)}
              className="flex w-full items-center gap-3 rounded-lg bg-surface p-4 shadow-card transition-shadow hover:shadow-float"
            >
              <div className={`h-8 w-1 rounded-full ${colors.bg.replace("/10", "")}`} />
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-on-surface">
                  {groupInfo?.label ?? group}
                </h3>
                <p className="text-sm text-on-surface-variant">
                  {groupTables.length} 张表 · {groupInfo?.record_count ?? 0} 条记录
                </p>
              </div>
              <svg
                className={`h-5 w-5 text-on-surface-variant transition-transform ${isCollapsed ? "" : "rotate-180"}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Table Cards */}
            {!isCollapsed && (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {groupTables.map((table) => (
                  <div key={table.name}>
                    <button
                      onClick={() => handleTableClick(table.name)}
                      className={`w-full rounded-lg border bg-surface p-4 text-left shadow-card transition-all hover:shadow-float ${
                        expandedTable === table.name
                          ? `border-l-4 ${colors.border.replace("/30", "")}`
                          : "border-outline-variant"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="font-medium text-on-surface">{table.display_name}</div>
                          <div className="mt-0.5 font-mono text-xs text-on-surface-variant">
                            {table.name}
                          </div>
                        </div>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}>
                          {table.row_count}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-on-surface-variant line-clamp-2">
                        {table.description}
                      </p>
                    </button>

                    {/* Expanded Detail */}
                    {expandedTable === table.name && (
                      <div className="mt-2 rounded-lg border border-outline-variant bg-surface-container/40 p-4">
                        {detailLoading ? (
                          <div className="py-4 text-center text-sm text-on-surface-variant">
                            加载中...
                          </div>
                        ) : tableDetail ? (
                          <div className="space-y-4">
                            {/* Columns */}
                            <div>
                              <h4 className="mb-2 text-sm font-medium text-on-surface">列定义</h4>
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="border-b border-outline-variant text-left text-on-surface-variant">
                                      <th className="pb-2 pr-4 font-medium">列名</th>
                                      <th className="pb-2 pr-4 font-medium">类型</th>
                                      <th className="pb-2 font-medium">说明</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {tableDetail.columns.map((col) => (
                                      <tr key={col.name} className="border-b border-outline-variant/50">
                                        <td className="py-1.5 pr-4 font-mono text-xs text-on-surface">
                                          {col.name}
                                          {col.pk && <span className="ml-1 text-primary">*</span>}
                                        </td>
                                        <td className="py-1.5 pr-4 text-xs text-on-surface-variant">
                                          {col.type}
                                        </td>
                                        <td className="py-1.5 text-xs text-on-surface-variant">
                                          {col.description || "-"}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            {/* Data Preview */}
                            {tableDetail.data.length > 0 && (
                              <div>
                                <h4 className="mb-2 text-sm font-medium text-on-surface">
                                  数据预览（前 {tableDetail.data.length} 条）
                                </h4>
                                <div className="max-h-60 overflow-auto rounded border border-outline-variant">
                                  <table className="w-full text-xs">
                                    <thead className="sticky top-0 bg-surface-container">
                                      <tr className="text-left text-on-surface-variant">
                                        {tableDetail.columns.slice(0, 6).map((col) => (
                                          <th key={col.name} className="px-3 py-2 font-medium">
                                            {col.name}
                                          </th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {tableDetail.data.map((row, i) => (
                                        <tr key={i} className="border-t border-outline-variant/50">
                                          {tableDetail.columns.slice(0, 6).map((col) => (
                                            <td key={col.name} className="px-3 py-1.5 text-on-surface">
                                              {formatCellValue(row[col.name])}
                                            </td>
                                          ))}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="py-4 text-center text-sm text-on-surface-variant">
                            加载失败
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") {
    if (value.length > 50) return value.slice(0, 50) + "...";
    return value;
  }
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}
