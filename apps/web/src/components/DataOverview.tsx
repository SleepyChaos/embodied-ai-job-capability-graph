import { useEffect, useState } from "react";

import { fetchOverviewStats, fetchTableGroups, fetchTableDetail } from "../api";
import type { TableGroup, TableDetail, OverviewStats } from "../types";

const GROUP_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  career: { bg: "bg-primary/10", text: "text-primary", border: "border-primary/30" },
  capability: { bg: "bg-success/10", text: "text-success", border: "border-success/30" },
  company: { bg: "bg-warning/10", text: "text-warning", border: "border-warning/30" },
};

export function DataOverview() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [groups, setGroups] = useState<TableGroup[]>([]);
  const [expandedTable, setExpandedTable] = useState<string | null>(null);
  const [tableDetail, setTableDetail] = useState<TableDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    Promise.all([fetchOverviewStats(), fetchTableGroups()])
      .then(([s, g]) => {
        setStats(s);
        setGroups(g);
      })
      .catch((err) => console.error("Failed to load data:", err))
      .finally(() => setLoading(false));
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
      const detail = await fetchTableDetail(tableName);
      setTableDetail(detail);
    } catch (err) {
      console.error("Failed to load table detail:", err);
      setTableDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleGroup = (groupKey: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupKey)) next.delete(groupKey);
      else next.add(groupKey);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">加载中...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Stats Header */}
      <div className="flex items-center gap-6">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">数据总览</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {stats?.totalTables ?? 0} 张表 · {stats?.totalRows ?? 0} 条记录
          </p>
        </div>
        <div className="flex gap-3">
          {groups.map((g) => {
            const colors = GROUP_COLORS[g.key] ?? GROUP_COLORS.career;
            const totalRows = g.tables.reduce((sum, t) => sum + t.rowCount, 0);
            return (
              <div
                key={g.key}
                className={`rounded-lg border px-4 py-2 ${colors.bg} ${colors.border}`}
              >
                <div className={`text-xs font-medium ${colors.text}`}>{g.name}</div>
                <div className="text-lg font-semibold text-foreground">
                  {g.tables.length} 表 / {totalRows} 条
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Table Groups */}
      {groups.map((group) => {
        const colors = GROUP_COLORS[group.key] ?? GROUP_COLORS.career;
        const isCollapsed = collapsedGroups.has(group.key);

        return (
          <section key={group.key} className="space-y-3">
            {/* Group Header */}
            <button
              type="button"
              onClick={() => toggleGroup(group.key)}
              className="flex w-full items-center gap-2 text-left"
            >
              <span className={`h-4 w-1 rounded ${colors.bg}`} />
              <h3 className="text-lg font-medium text-foreground">{group.name}</h3>
              <span className="text-sm text-muted-foreground">
                ({group.tables.length} 张表)
              </span>
              <svg
                className={`ml-auto h-5 w-5 text-muted-foreground transition-transform ${
                  isCollapsed ? "" : "rotate-180"
                }`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Tables Grid */}
            {!isCollapsed && (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {group.tables.map((table) => (
                  <div key={table.name}>
                    <button
                      type="button"
                      onClick={() => handleTableClick(table.name)}
                      className={`w-full rounded-lg border bg-card p-4 text-left transition-all hover:shadow-md ${
                        expandedTable === table.name
                          ? `border-2 ${colors.border}`
                          : "border-border"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="font-medium text-foreground">{table.name}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {table.description}
                          </div>
                        </div>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}>
                          {table.rowCount}
                        </span>
                      </div>
                    </button>

                    {/* Expanded Detail */}
                    {expandedTable === table.name && (
                      <div className="mt-2 rounded-lg border border-border bg-card p-4">
                        {detailLoading ? (
                          <div className="py-4 text-center text-muted-foreground">加载中...</div>
                        ) : tableDetail ? (
                          <div className="space-y-4">
                            {/* Columns */}
                            <div>
                              <h4 className="mb-2 text-sm font-medium text-foreground">列定义</h4>
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="border-b border-border">
                                      <th className="py-1 pr-4 text-left text-muted-foreground">列名</th>
                                      <th className="py-1 pr-4 text-left text-muted-foreground">类型</th>
                                      <th className="py-1 text-left text-muted-foreground">主键</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {tableDetail.columns.map((col) => (
                                      <tr key={col.name} className="border-b border-border/50">
                                        <td className="py-1 pr-4 font-mono text-xs">{col.name}</td>
                                        <td className="py-1 pr-4 text-xs text-muted-foreground">{col.type}</td>
                                        <td className="py-1 text-xs">{col.primaryKey ? "✓" : ""}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            {/* Data Preview */}
                            {tableDetail.data.length > 0 && (
                              <div>
                                <h4 className="mb-2 text-sm font-medium text-foreground">
                                  数据预览 ({tableDetail.pagination.total} 条)
                                </h4>
                                <div className="max-h-64 overflow-auto">
                                  <table className="w-full text-sm">
                                    <thead>
                                      <tr className="border-b border-border">
                                        {tableDetail.columns.slice(0, 5).map((col) => (
                                          <th key={col.name} className="py-1 pr-2 text-left text-xs text-muted-foreground">
                                            {col.name}
                                          </th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {tableDetail.data.slice(0, 5).map((row, i) => (
                                        <tr key={i} className="border-b border-border/50">
                                          {tableDetail.columns.slice(0, 5).map((col) => (
                                            <td key={col.name} className="py-1 pr-2 text-xs">
                                              {String(row[col.name] ?? "").slice(0, 30)}
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
                          <div className="py-4 text-center text-muted-foreground">加载失败</div>
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
