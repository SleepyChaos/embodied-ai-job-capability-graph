import { AlertTriangle, BriefcaseBusiness, GitBranch, LoaderCircle, Minus, Plus, RefreshCw, RotateCcw, Search, Tags } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import type { CapabilityGraphDetail, GraphPayloadV2 } from "../types";
import type { GraphCanvasHandle } from "./GraphCanvas";

const GraphCanvas = lazy(() => import("./GraphCanvas").then((module) => ({ default: module.GraphCanvas })));

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

export function CapabilityGraphExplorer({ onSwitch, onSpectrum }: { onSwitch: () => void; onSpectrum: () => void }) {
  const initial = new URLSearchParams(location.search);
  const [payload, setPayload] = useState<GraphPayloadV2 | null>(null);
  const [selectedId, setSelectedId] = useState<string | undefined>(initial.get("node") ?? undefined);
  const [query, setQuery] = useState(initial.get("q") ?? "");
  const [detail, setDetail] = useState<CapabilityGraphDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const graphRef = useRef<GraphCanvasHandle>(null);

  const load = useCallback(async (initialLoad = false) => {
    const controller = new AbortController();
    if (initialLoad) setLoading(true);
    else setRefreshing(true);
    try {
      const value = await api.getCapabilityGraph(controller.signal);
      setPayload(value);
      setSelectedId((current) => current && value.nodes.some((node) => node.id === current)
        ? current
        : "capability-root");
      setError(null);
    } catch (cause) {
      if ((cause as Error).name !== "AbortError") setError((cause as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
    return () => controller.abort();
  }, []);

  useEffect(() => {
    void load(true);
    const timer = window.setInterval(() => void load(false), 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    params.set("section", "graph");
    params.set("graph", "capability");
    if (selectedId) params.set("node", selectedId); else params.delete("node");
    if (query.trim()) params.set("q", query.trim()); else params.delete("q");
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [query, selectedId]);

  const selected = payload?.nodes.find((node) => node.id === selectedId);
  const selectedCapabilityId = selected?.data.kind === "canonical"
    ? Number(selected.data.databaseId)
    : null;

  useEffect(() => {
    if (!selectedCapabilityId) {
      setDetail(null);
      setDetailLoading(false);
      return;
    }
    const controller = new AbortController();
    setDetail(null);
    setDetailLoading(true);
    api.getCapabilityGraphDetail(selectedCapabilityId, controller.signal)
      .then(setDetail)
      .catch((cause) => {
        if (cause.name !== "AbortError") setError(cause.message);
      })
      .finally(() => setDetailLoading(false));
    return () => controller.abort();
  }, [selectedCapabilityId]);

  const filtered = useMemo(() => {
    if (!payload) return [];
    const normalized = query.trim().toLocaleLowerCase("zh-CN");
    return payload.nodes.filter((node) => {
      if (!normalized) return true;
      const haystack = `${node.data.label} ${String(node.data.searchText ?? "")}`.toLocaleLowerCase("zh-CN");
      return haystack.includes(normalized);
    });
  }, [payload, query]);

  const selectNode = (id: string) => {
    setSelectedId(id);
    window.requestAnimationFrame(() => graphRef.current?.focus(id));
  };

  const metrics = payload?.snapshot.metrics;

  return (
    <div className="v4-graph-page capability-graph-page">
      <aside className="graph-index-panel">
        <div className="panel-kicker"><GitBranch size={14} />能力本体工作台</div>
        <h1>能力图谱</h1>
        <p>完整陈列方向、分类与能力总称。搜索也会匹配未展开到画布中的能力别称。</p>
        <div className="graph-kind-switch">
          <button className="active">能力图谱</button>
          <button onClick={onSwitch}>职业属性图谱</button>
          <button onClick={onSpectrum}>职业色系谱</button>
        </div>
        <div className="graph-level-summary" aria-label="图谱层级">
          <span><strong>{metrics?.directionCount ?? 0}</strong>方向</span>
          <span><strong>{metrics?.categoryCount ?? 0}</strong>分类</span>
          <span><strong>{metrics?.capabilityCount ?? 0}</strong>总称</span>
        </div>
        <label className="graph-search">
          <Search size={15} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索方向、分类、总称或别称" />
        </label>
        <div className="directory-result-count">{query ? `找到 ${filtered.length} 个节点` : `全部 ${filtered.length} 个节点`}</div>
        <div className="graph-directory" role="list">
          {filtered.map((node) => {
            const level = Number(node.data.level ?? 0);
            return (
              <button
                role="listitem"
                className={selectedId === node.id ? "selected" : ""}
                key={node.id}
                onClick={() => selectNode(node.id)}
                style={{ paddingLeft: 8 + Math.min(level, 3) * 10 }}
              >
                <span className="directory-dot" style={{ background: String(node.data.color ?? "#26364d") }} />
                <span>
                  <strong>{node.data.label}</strong>
                  <small>{level === 0 ? "图谱中心" : level === 1 ? `${node.data.capabilityCount ?? 0} 个能力总称` : level === 2 ? `${node.data.capabilityCount ?? 0} 个总称` : `${node.data.aliasCount ?? 0} 个别称 · ${node.data.jobCount ?? 0} 个岗位`}</small>
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      <main className="graph-main-panel">
        <header className="graph-page-header">
          <div>
            <span>径向层级树 · 数据库实时视图</span>
            <h2>{payload?.snapshot.name ?? "读取能力本体"}</h2>
            <small>更新于 {formatUpdatedAt(payload?.snapshot.at)} · 每 30 秒自动同步</small>
          </div>
          <div className="coverage-chip"><strong>{Math.round((payload?.meta.coverage ?? 0) * 100)}%</strong><span>已关联岗位</span></div>
        </header>
        {payload?.meta.warnings.map((warning) => <div className="data-warning" key={warning}><AlertTriangle size={15} />{warning}</div>)}
        {error && payload ? <div className="data-warning error"><AlertTriangle size={15} />刷新失败，继续显示上一次有效数据：{error}</div> : null}
        <section className="v4-graph-stage">
          {loading ? (
            <div className="graph-state"><LoaderCircle className="spin" />正在从数据库生成能力图谱</div>
          ) : error && !payload ? (
            <div className="graph-state error"><AlertTriangle />{error}</div>
          ) : payload ? (
            <Suspense fallback={<div className="graph-state">加载图谱渲染器</div>}>
              <GraphCanvas
                ref={graphRef}
                payload={payload}
                graphKind="capability"
                mode="taxonomy"
                selectedId={selectedId}
                onNodeSelect={selectNode}
                onEdgeSelect={() => undefined}
              />
            </Suspense>
          ) : null}
          <div className="canvas-tools">
            <button onClick={() => void load(false)} aria-label="刷新数据库图谱" title="刷新数据库图谱"><RefreshCw className={refreshing ? "spin" : ""} size={16} /></button>
            <button onClick={() => graphRef.current?.zoomIn()} aria-label="放大"><Plus size={16} /></button>
            <button onClick={() => graphRef.current?.zoomOut()} aria-label="缩小"><Minus size={16} /></button>
            <button onClick={() => graphRef.current?.fit()} aria-label="适配画布"><RotateCcw size={16} /></button>
          </div>
          <div className="graph-legend"><span>中心</span><span>6 大方向</span><span>18 个分类</span><span>能力总称</span></div>
        </section>
      </main>

      <aside className="graph-detail-panel">
        <span className="detail-eyebrow">{selected?.data.kind === "canonical" ? "能力总称详情" : "节点概览"}</span>
        {selected ? (
          <>
            <h2>{selected.data.label}</h2>
            <span className="taxonomy-badge">
              {selected.data.kind === "root" ? "图谱中心" : selected.data.kind === "direction" ? "能力方向" : selected.data.kind === "category" ? "能力分类" : "正式能力总称"}
            </span>
            {selected.data.description ? <p className="graph-detail-description">{String(selected.data.description)}</p> : null}
            <dl className="detail-metrics">
              <div><dt>能力总称</dt><dd>{selected.data.capabilityCount ?? "—"}</dd></div>
              <div><dt>能力别称</dt><dd>{selected.data.aliasCount ?? "—"}</dd></div>
              <div><dt>关联岗位</dt><dd>{selected.data.jobCount ?? "—"}</dd></div>
            </dl>
            {detailLoading ? <div className="detail-loading"><LoaderCircle className="spin" />正在读取关联数据</div> : null}
            {detail ? (
              <>
                <div className="graph-detail-path">{detail.path.map((item) => <span key={item.code}>{item.name}</span>)}</div>
                <section className="graph-detail-section">
                  <h3><Tags size={14} />包含的能力别称 <b>{detail.aliases.length}</b></h3>
                  {detail.aliases.length ? <div className="graph-alias-list">{detail.aliases.map((alias) => <span key={alias.id}>{alias.name}<small>{Math.round(alias.confidence * 100)}%</small></span>)}</div> : <p>尚无别称。</p>}
                </section>
                <section className="graph-detail-section">
                  <h3><BriefcaseBusiness size={14} />关联的单条 JD <b>{detail.jobs.length}</b></h3>
                  {detail.jobs.length ? (
                    <div className="graph-job-list">
                      {detail.jobs.map((job) => (
                        <article key={job.id}>
                          <strong>{job.title}</strong>
                          <small>{job.company ?? "企业信息待补充"} · 匹配 {Math.round(job.confidence * 100)}%</small>
                          {job.evidence ? <p>{job.evidence}</p> : null}
                        </article>
                      ))}
                    </div>
                  ) : <p>尚未关联到已审批 JD。</p>}
                </section>
              </>
            ) : null}
          </>
        ) : (
          <>
            <h2>选择一个节点</h2>
            <p className="detail-copy">点击画布或左侧目录。选择能力总称后，这里会显示它包含的别称及关联的单条企业 JD。</p>
          </>
        )}
        <div className="fallback-note"><strong>为什么不画出别称？</strong><p>别称保留在右侧详情与搜索索引中，避免数据增长后上万个叶节点压垮图谱可读性。</p></div>
      </aside>
    </div>
  );
}
