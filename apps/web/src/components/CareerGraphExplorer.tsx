import { AlertTriangle, BriefcaseBusiness, Building2, GitBranch, LoaderCircle, Minus, Plus, RefreshCw, RotateCcw, Search, Sparkles } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import type { CareerGraphJobDetail, GraphNodeV2, GraphPayloadV2 } from "../types";
import type { CareerGraphCanvasHandle } from "./CareerGraphCanvas";

const CareerGraphCanvas = lazy(() => import("./CareerGraphCanvas").then((module) => ({ default: module.CareerGraphCanvas })));

function formatUpdatedAt(value?: string) {
  if (!value) return "等待数据库时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function CareerGraphExplorer({ onSwitch, onSpectrum }: { onSwitch: () => void; onSpectrum: () => void }) {
  const initial = new URLSearchParams(location.search);
  const initialJobId = Number(initial.get("job")) || undefined;
  const initialNodeId = initial.get("node") ?? (initialJobId ? `job:${initialJobId}` : undefined);
  const [payload, setPayload] = useState<GraphPayloadV2 | null>(null);
  const [directoryNodes, setDirectoryNodes] = useState<GraphNodeV2[]>([]);
  const [directoryMetrics, setDirectoryMetrics] = useState<Record<string, number>>({});
  const [selectedId, setSelectedId] = useState<string | undefined>(initialNodeId);
  const [detail, setDetail] = useState<CareerGraphJobDetail | null>(null);
  const [query, setQuery] = useState(initial.get("q") ?? "");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const graphRef = useRef<CareerGraphCanvasHandle>(null);
  const centerNodeRef = useRef<string | undefined>(initialNodeId);

  const loadDirectory = useCallback(async () => {
    try {
      const value = await api.getCareerGraphDirectory();
      setDirectoryNodes(value.items);
      setDirectoryMetrics(value.metrics);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }, []);

  const load = useCallback(async (nodeId?: string, initialLoad = false, navigation = false) => {
    if (initialLoad) setLoading(true);
    else if (navigation) setNavigating(true);
    else setRefreshing(true);
    try {
      const value = await api.getCareerGraph(nodeId, 14);
      const resolvedCenter = value.meta.focusNodeId
        ?? nodeId
        ?? value.nodes.find((node) => node.data.focused)?.id
        ?? value.nodes[0]?.id;
      setPayload(value);
      setSelectedId(resolvedCenter);
      centerNodeRef.current = resolvedCenter;
      setError(null);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
      if (navigation) window.setTimeout(() => setNavigating(false), 420);
    }
  }, []);

  useEffect(() => {
    void load(centerNodeRef.current, true);
    void loadDirectory();
    const timer = window.setInterval(() => {
      void load(centerNodeRef.current, false);
      void loadDirectory();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [load, loadDirectory]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    params.set("section", "graph");
    params.set("graph", "career");
    if (selectedId) params.set("node", selectedId); else params.delete("node");
    params.delete("job");
    if (query.trim()) params.set("q", query.trim()); else params.delete("q");
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [query, selectedId]);

  const selected = payload?.nodes.find((node) => node.id === selectedId);
  const selectedJobId = selected?.data.kind === "job" ? Number(selected.data.databaseId) : null;

  useEffect(() => {
    if (!selectedJobId) {
      setDetail(null);
      setDetailLoading(false);
      return;
    }
    const controller = new AbortController();
    setDetail(null);
    setDetailLoading(true);
    api.getCareerGraphJobDetail(selectedJobId, controller.signal)
      .then(setDetail)
      .catch((cause) => {
        if (cause.name !== "AbortError") setError(cause.message);
      })
      .finally(() => setDetailLoading(false));
    return () => controller.abort();
  }, [selectedJobId]);

  const filtered = useMemo(() => {
    if (!directoryNodes.length) return [];
    const normalized = query.trim().toLocaleLowerCase("zh-CN");
    return directoryNodes.filter((node) => {
      const haystack = [
        node.data.label,
        node.data.companyName,
        node.data.directionName,
        node.data.categoryName,
      ].filter(Boolean).join(" ").toLocaleLowerCase("zh-CN");
      return !normalized || haystack.includes(normalized);
    }).sort((left, right) => {
      const order = { job: 0, company: 1, canonical: 2 } as Record<string, number>;
      return (order[String(left.data.kind)] ?? 3) - (order[String(right.data.kind)] ?? 3)
        || left.data.label.localeCompare(right.data.label, "zh-CN");
    });
  }, [directoryNodes, query]);

  const connected = useMemo(() => {
    if (!payload || !selectedId) return [];
    const ids = payload.edges.flatMap((edge) => {
      if (edge.source === selectedId) return [edge.target];
      if (edge.target === selectedId) return [edge.source];
      return [];
    });
    return ids.map((id) => payload.nodes.find((node) => node.id === id)).filter(Boolean);
  }, [payload, selectedId]);

  const selectNode = (id: string) => {
    setSelectedId(id);
    centerNodeRef.current = id;
    void load(id, false, true);
  };

  const metrics = payload?.snapshot.metrics;

  return (
    <div className="v4-graph-page career-graph-page">
      <aside className="graph-index-panel">
        <div className="panel-kicker"><GitBranch size={14} />职业关系工作台</div>
        <h1>职业属性图谱</h1>
        <p>以单条企业 JD 为最小职业单元，通过正式能力总称和企业两个桥梁观察职业关联。</p>
        <div className="graph-kind-switch">
          <button onClick={onSwitch}>能力图谱</button>
          <button className="active">职业属性图谱</button>
          <button onClick={onSpectrum}>职业色系谱</button>
        </div>
        <div className="graph-level-summary">
          <span><strong>{directoryMetrics.jobCount ?? 0}</strong>JD</span>
          <span><strong>{directoryMetrics.companyCount ?? 0}</strong>企业</span>
          <span><strong>{directoryMetrics.capabilityCount ?? 0}</strong>能力</span>
        </div>
        <label className="graph-search">
          <Search size={15} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 JD、企业或能力总称" />
        </label>
        <div className="directory-result-count">{query ? `全局找到 ${filtered.length} 个节点` : `全部可选 ${directoryNodes.length} 个节点`}</div>
        <div className="graph-directory career-directory" role="list">
          {filtered.map((node) => (
            <button
              role="listitem"
              className={selectedId === node.id ? "selected" : ""}
              key={node.id}
              onClick={() => selectNode(node.id)}
            >
              <span className="directory-node-icon" data-kind={String(node.data.kind)}>
                {node.data.kind === "job" ? <BriefcaseBusiness size={12} /> : node.data.kind === "company" ? <Building2 size={12} /> : <Sparkles size={12} />}
              </span>
              <span>
                <strong>{node.data.label}</strong>
                <small>{node.data.kind === "job" ? `${node.data.companyName ?? "企业待补充"} · ${node.data.capabilityCount ?? 0} 项能力` : node.data.kind === "company" ? `${node.data.jobCount ?? 0} 条企业 JD` : `${node.data.directionName} · ${node.data.jobCount ?? 0} 条关联 JD`}</small>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <main className="graph-main-panel">
        <header className="graph-page-header">
          <div>
            <span>JD — 能力总称 / JD — 企业</span>
            <h2>{payload?.snapshot.name ?? "读取职业关系"}</h2>
            <small>更新于 {formatUpdatedAt(payload?.snapshot.at)} · 点击任意节点切换关联邻域</small>
          </div>
          <div className="coverage-chip"><strong>{metrics?.processedJobCount ?? 0}</strong><span>已关联 JD</span></div>
        </header>
        {payload?.meta.warnings.map((warning) => <div className="data-warning" key={warning}><AlertTriangle size={15} />{warning}</div>)}
        {error && payload ? <div className="data-warning error"><AlertTriangle size={15} />刷新失败，继续显示上一次有效数据：{error}</div> : null}
        <section className={`v4-graph-stage career-graph-stage${navigating ? " is-transitioning" : ""}`}>
          {loading ? (
            <div className="graph-state"><LoaderCircle className="spin" />正在构建职业属性邻域</div>
          ) : error && !payload ? (
            <div className="graph-state error"><AlertTriangle />{error}</div>
          ) : payload ? (
            <Suspense fallback={<div className="graph-state">加载关系图谱渲染器</div>}>
              <CareerGraphCanvas ref={graphRef} payload={payload} selectedId={selectedId} onNodeSelect={selectNode} />
            </Suspense>
          ) : null}
          {navigating ? <div className="graph-transition-indicator"><LoaderCircle className="spin" />正在展开关联节点</div> : null}
          <div className="canvas-tools">
            <button onClick={() => void load(centerNodeRef.current, false)} aria-label="刷新数据库图谱"><RefreshCw className={refreshing ? "spin" : ""} size={16} /></button>
            <button onClick={() => graphRef.current?.zoomIn()} aria-label="放大"><Plus size={16} /></button>
            <button onClick={() => graphRef.current?.zoomOut()} aria-label="缩小"><Minus size={16} /></button>
            <button onClick={() => graphRef.current?.fit()} aria-label="适配画布"><RotateCcw size={16} /></button>
          </div>
          <div className="graph-legend career-legend">
            <span>单条 JD</span><span>企业</span><span>能力总称</span><span>虚线：企业归属</span>
          </div>
        </section>
      </main>

      <aside className="graph-detail-panel">
        <span className="detail-eyebrow">{selected?.data.kind === "job" ? "单条 JD 详情" : selected?.data.kind === "company" ? "企业节点" : selected ? "能力总称" : "阅读提示"}</span>
        {selected ? (
          <>
            <h2>{selected.data.label}</h2>
            <span className="taxonomy-badge">{selected.data.kind === "job" ? "职业 JD" : selected.data.kind === "company" ? "企业" : "正式能力总称"}</span>
            {selected.data.kind === "job" ? (
              <>
                <p className="graph-detail-description">{String(selected.data.companyName ?? "企业信息待补充")}{selected.data.city ? ` · ${selected.data.city}` : ""}</p>
                {detailLoading ? <div className="detail-loading"><LoaderCircle className="spin" />正在读取 JD 证据</div> : null}
                {detail ? (
                  <>
                    <dl className="detail-metrics">
                      <div><dt>正式能力</dt><dd>{detail.capabilities.length}</dd></div>
                      <div><dt>企业全部 JD</dt><dd>{detail.company.jobCount}</dd></div>
                      <div><dt>能力处理</dt><dd>{detail.processed ? "已完成" : "待处理"}</dd></div>
                    </dl>
                    <section className="graph-detail-section">
                      <h3><Sparkles size={14} />关联能力总称 <b>{detail.capabilities.length}</b></h3>
                      {detail.capabilities.length ? <div className="career-capability-list">{detail.capabilities.map((capability) => <article key={capability.id}><strong>{capability.name}</strong><small>{capability.direction} / {capability.category} · {Math.round(capability.confidence * 100)}%</small>{capability.evidence[0] ? <p>{capability.evidence[0]}</p> : null}</article>)}</div> : <p>该 JD 尚未完成能力提取与审批。</p>}
                    </section>
                  </>
                ) : null}
              </>
            ) : (
              <>
                {selected.data.description ? <p className="graph-detail-description">{String(selected.data.description)}</p> : null}
                <dl className="detail-metrics">
                  <div><dt>{selected.data.kind === "company" ? "企业全部 JD" : "关联 JD"}</dt><dd>{selected.data.jobCount ?? 0}</dd></div>
                  <div><dt>{selected.data.kind === "company" ? "已审批关联 JD" : "当前可见邻居"}</dt><dd>{connected.length}</dd></div>
                </dl>
                <section className="graph-detail-section">
                  <h3><BriefcaseBusiness size={14} />当前画布中的关联 JD <b>{connected.length}</b></h3>
                  <div className="connected-node-list">{connected.filter((node) => node?.data.kind === "job").map((node) => <button key={node!.id} onClick={() => selectNode(node!.id)}>{node!.data.label}</button>)}</div>
                </section>
              </>
            )}
          </>
        ) : <><h2>选择一个节点</h2><p className="detail-copy">蓝色是单条 JD，橙色是企业，其他颜色是能力总称。点击 JD 会加载它的能力证据与同企业岗位邻域。</p></>}
        <div className="fallback-note"><strong>别称如何参与？</strong><p>JD 与能力总称的连线由底层“提取别称 → 正式总称”关系生成；别称保留为证据，不单独占用画布节点。</p></div>
      </aside>
    </div>
  );
}
