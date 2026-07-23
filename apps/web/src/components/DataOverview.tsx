import {
  ClipboardCheck,
  ArrowLeft,
  ArrowRight,
  Braces,
  Columns3,
  Database,
  HardDrive,
  KeyRound,
  Link2,
  Rows3,
  Search,
  Table2,
} from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import { GovernanceReview } from "./GovernanceReview";
import type {
  DataColumn,
  DataOverviewPayload,
  DataTableDetail,
  DataTableSummary,
  DatabaseValue,
} from "../types";

type DetailView = "schema" | "rows";
type DataWorkspace = "browser" | "review";

const numberFormatter = new Intl.NumberFormat("zh-CN");

function initialTable() {
  return new URLSearchParams(location.search).get("table") || "career_units";
}

function initialView(): DetailView {
  return new URLSearchParams(location.search).get("tab") === "rows" ? "rows" : "schema";
}

function initialPage() {
  const value = Number(new URLSearchParams(location.search).get("page") || 1);
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : 1;
}

function initialWorkspace(): DataWorkspace {
  return new URLSearchParams(location.search).get("workspace") === "review" ? "review" : "browser";
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function renderValue(value: DatabaseValue) {
  if (value === null) return <span className="null-value">NULL</span>;
  if (typeof value === "object") return <span className="blob-value">BLOB · {numberFormatter.format(value.bytes)} B</span>;
  if (typeof value === "string" && value.length === 0) return <span className="empty-value">空字符串</span>;
  return String(value);
}

function ColumnConstraints({ column }: { column: DataColumn }) {
  return <div className="constraint-list">
    {column.primaryKeyPosition ? <span className="constraint-badge primary"><KeyRound size={11} />PK{column.primaryKeyPosition > 1 ? column.primaryKeyPosition : ""}</span> : null}
    {column.foreignKeys.length ? <span className="constraint-badge foreign"><Link2 size={11} />FK</span> : null}
    {!column.nullable ? <span className="constraint-badge required">NOT NULL</span> : <span className="constraint-badge nullable">NULL</span>}
    {column.unique ? <span className="constraint-badge unique">UNIQUE</span> : null}
  </div>;
}

function SchemaView({ detail, onSelectTable }: { detail: DataTableDetail; onSelectTable: (tableName: string) => void }) {
  return <div className="schema-view">
    <div className="schema-table-wrap" tabIndex={0} aria-label="字段结构表格，可横向滚动查看全部属性">
      <table className="schema-table">
        <thead><tr><th>#</th><th>字段与中文说明</th><th>声明类型</th><th>键与约束</th><th>默认值</th><th>外键指向</th></tr></thead>
        <tbody>{detail.columns.map((column) => <tr key={column.name}>
          <td>{column.position + 1}</td>
          <td><code>{column.name}</code><small>{column.description}</small></td>
          <td><span className={`type-badge ${column.typeCategory}`}>{column.declaredType || "BLOB"}</span></td>
          <td><ColumnConstraints column={column} /></td>
          <td><code className="default-value">{column.defaultValue ?? "—"}</code></td>
          <td>{column.foreignKeys.length ? column.foreignKeys.map((foreignKey) => <button className="reference-link" type="button" onClick={() => onSelectTable(foreignKey.table)} key={`${foreignKey.table}-${foreignKey.column}`}>
            {foreignKey.table}<strong>.{foreignKey.column ?? "rowid"}</strong>
          </button>) : <span className="muted-dash">—</span>}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <div className="relationship-summary">
      <div><strong>外键关系</strong><span>{detail.foreignKeys.length} 条从本表发出</span></div>
      <div><strong>反向引用</strong><span>{detail.incomingReferences.length} 条指向本表</span></div>
      <div><strong>索引</strong><span>{detail.indexes.length} 个已定义索引</span></div>
    </div>
  </div>;
}

function RowsView({ detail, onPage }: { detail: DataTableDetail; onPage: (page: number) => void }) {
  const totalPages = Math.max(1, Math.ceil(detail.page.total / detail.page.pageSize));
  return <div className="rows-view">
    <div className="data-table-scroll" tabIndex={0} aria-label="数据预览表格，可横向滚动查看全部字段">
      <table className="data-preview-table" style={{ minWidth: Math.max(900, detail.columns.length * 150) }}>
        <thead><tr>{detail.columns.map((column) => <th key={column.name}><span>{column.name}</span><small>{column.declaredType || "BLOB"}{column.primaryKeyPosition ? " · PK" : column.foreignKeys.length ? " · FK" : ""}</small></th>)}</tr></thead>
        <tbody>{detail.rows.map((row, rowIndex) => <tr key={`${detail.page.page}-${rowIndex}`}>
          {detail.columns.map((column) => <td key={column.name}><code title={typeof row[column.name] === "string" ? String(row[column.name]) : undefined}>{renderValue(row[column.name])}</code></td>)}
        </tr>)}</tbody>
      </table>
      {detail.rows.length === 0 ? <div className="data-empty"><Rows3 size={24} /><span>该表当前没有数据</span></div> : null}
    </div>
    <footer className="table-pagination">
      <span>第 {detail.page.page} / {totalPages} 页 · 共 {numberFormatter.format(detail.page.total)} 行</span>
      <div><button type="button" disabled={detail.page.page <= 1} onClick={() => onPage(detail.page.page - 1)} aria-label="上一页"><ArrowLeft size={15} /></button>
      <button type="button" disabled={detail.page.page >= totalPages} onClick={() => onPage(detail.page.page + 1)} aria-label="下一页"><ArrowRight size={15} /></button></div>
    </footer>
  </div>;
}

export function DataOverview() {
  const [overview, setOverview] = useState<DataOverviewPayload | null>(null);
  const [detail, setDetail] = useState<DataTableDetail | null>(null);
  const [selectedTable, setSelectedTable] = useState(initialTable);
  const [view, setView] = useState<DetailView>(initialView);
  const [page, setPage] = useState(initialPage);
  const [query, setQuery] = useState("");
  const [workspace, setWorkspace] = useState<DataWorkspace>(initialWorkspace);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());

  useEffect(() => {
    const controller = new AbortController();
    api.getDataOverview(controller.signal).then((result) => {
      setOverview(result);
      setSelectedTable((current) => result.tables.some((table) => table.name === current)
        ? current
        : result.tables.find((table) => table.name === "career_units")?.name ?? result.tables[0]?.name ?? "");
    }).catch((reason: Error) => {
      if (reason.name !== "AbortError") setError(reason.message);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedTable) return undefined;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setDetail(null);
    api.getDataTable(selectedTable, page, 25, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setDetail(result);
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") setError(reason.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [page, selectedTable]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    params.set("section", "data");
    params.set("table", selectedTable);
    params.set("tab", view);
    if (view === "rows" && page > 1) params.set("page", String(page)); else params.delete("page");
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [page, selectedTable, view]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    params.set("section", "data");
    if (workspace === "review") params.set("workspace", "review"); else params.delete("workspace");
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [workspace]);

  const tableByName = useMemo(() => new Map(overview?.tables.map((table) => [table.name, table]) ?? []), [overview]);
  const visibleGroups = useMemo(() => (overview?.groups ?? []).map((group) => ({
    ...group,
    tables: group.tables.map((name) => tableByName.get(name)).filter((table): table is DataTableSummary => Boolean(table)).filter((table) => (
      !deferredQuery || `${table.name} ${table.displayName} ${table.description}`.toLowerCase().includes(deferredQuery)
    )),
  })).filter((group) => group.tables.length > 0), [deferredQuery, overview, tableByName]);

  const selectTable = (tableName: string) => {
    setSelectedTable(tableName);
    setPage(1);
  };

  return <main className="data-overview-page">
    <header className="data-overview-hero">
      <div><h1>数据总览</h1><p>浏览 SQLite v4 的业务表、字段约束、主外键关系与只读数据样本。</p></div>
      <div className="database-file"><HardDrive size={17} /><span><strong>{overview?.database.fileName ?? "正在连接数据库"}</strong><small>{overview ? `${formatBytes(overview.database.fileSizeBytes)} · schema ${overview.database.schemaVersion}` : "读取元数据中"}</small></span></div>
    </header>

    <nav className="data-workspace-switch" aria-label="数据总览工作区">
      <button type="button" className={workspace === "browser" ? "active" : ""} onClick={() => setWorkspace("browser")}><Database size={15} />数据库浏览</button>
      <button type="button" className={workspace === "review" ? "active" : ""} onClick={() => setWorkspace("review")}><ClipboardCheck size={15} />能力审核<span>{workspace === "review" ? "正在审核" : "候选队列"}</span></button>
    </nav>

    {workspace === "browser" ? <><section className="database-metrics" aria-label="数据库概览指标">
      <div><Table2 size={18} /><span><strong>{overview?.summary.tableCount ?? "—"}</strong><small>业务表</small></span></div>
      <div><Rows3 size={18} /><span><strong>{overview ? numberFormatter.format(overview.summary.totalRows) : "—"}</strong><small>数据行</small></span></div>
      <div><Link2 size={18} /><span><strong>{overview?.summary.relationshipCount ?? "—"}</strong><small>外键关系</small></span></div>
      <div><Database size={18} /><span><strong>{overview?.summary.nonEmptyTableCount ?? "—"}</strong><small>非空表</small></span></div>
    </section>

    <div className="database-browser">
      <aside className="table-directory">
        <div className="directory-heading"><span>数据表目录</span><small>{overview?.tables.length ?? 0}</small></div>
        <label className="table-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索表名或用途" /></label>
        <div className="table-groups">
          {visibleGroups.map((group) => <section key={group.name}><h2>{group.name}<span>{group.tables.length}</span></h2>
            {group.tables.map((table) => <button type="button" className={selectedTable === table.name ? "active" : ""} onClick={() => selectTable(table.name)} key={table.name}>
              <span><strong>{table.displayName}</strong><code>{table.name}</code></span><small>{numberFormatter.format(table.rowCount)}</small>
            </button>)}
          </section>)}
          {visibleGroups.length === 0 ? <div className="directory-empty">没有匹配的数据表</div> : null}
        </div>
      </aside>

      <section className="table-inspector">
        {detail ? <>
          <header className="table-titlebar">
            <div><span>{detail.table.group}</span><h2>{detail.table.displayName}</h2><code>{detail.table.name}</code><p>{detail.table.description}</p></div>
            <dl><div><dt>行</dt><dd>{numberFormatter.format(detail.table.rowCount)}</dd></div><div><dt>字段</dt><dd>{detail.table.columnCount}</dd></div></dl>
          </header>
          <nav className="table-view-tabs" aria-label="数据表视图">
            <button type="button" className={view === "schema" ? "active" : ""} onClick={() => setView("schema")}><Columns3 size={15} />字段结构</button>
            <button type="button" className={view === "rows" ? "active" : ""} onClick={() => setView("rows")}><Braces size={15} />数据预览</button>
          </nav>
          <div className={loading ? "table-content loading" : "table-content"}>
            {view === "schema" ? <SchemaView detail={detail} onSelectTable={selectTable} /> : <RowsView detail={detail} onPage={setPage} />}
          </div>
        </> : <div className="table-loading"><Database size={28} /><span>{error ?? "正在读取数据表…"}</span></div>}
        {error && detail ? <div className="table-error">{error}</div> : null}
      </section>
    </div></> : <GovernanceReview />}
  </main>;
}
