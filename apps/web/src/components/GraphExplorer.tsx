import { AlertTriangle, GitBranch, LoaderCircle, Minus, Plus, RotateCcw, Search } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import type { GraphCanvasHandle } from "./GraphCanvas";
import type { GraphEdgeV2, GraphKind, GraphPayloadV2 } from "../types";

const GraphCanvas = lazy(() => import("./GraphCanvas").then((module) => ({ default: module.GraphCanvas })));

export function GraphExplorer() {
  const initial = new URLSearchParams(location.search);
  const [kind, setKind] = useState<GraphKind>(initial.get("graph") === "career" ? "career" : "capability");
  const [mode, setMode] = useState<"taxonomy" | "community">(initial.get("mode") === "community" ? "community" : "taxonomy");
  const [payload, setPayload] = useState<GraphPayloadV2 | null>(null);
  const [selectedId, setSelectedId] = useState<string | undefined>(() => {
    if (initial.get("graph") === "career") return initial.get("job") ? `job:${initial.get("job")}` : undefined;
    const node = initial.get("node");
    return node?.startsWith("capability:") ? node : undefined;
  });
  const [selectedEdge, setSelectedEdge] = useState<GraphEdgeV2 | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const graphRef = useRef<GraphCanvasHandle>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const task = kind === "capability" ? api.getCapabilityGraph(controller.signal) : api.getCareerGraph(4, 0.25, controller.signal);
    task.then((value) => {
      setPayload(value);
      if (kind === "capability") setSelectedId((current) => current ?? value.nodes.find((node) => node.data.level === 1)?.id);
    }).catch((cause) => { if (cause.name !== "AbortError") setError(cause.message); }).finally(() => setLoading(false));
    return () => controller.abort();
  }, [kind]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    params.set("section", "graph");
    params.set("graph", kind);
    if (kind === "career") params.set("mode", mode); else params.delete("mode");
    if (selectedId?.startsWith("capability:")) params.set("node", selectedId); else params.delete("node");
    if (kind === "career" && selectedId?.startsWith("job:")) params.set("job", selectedId.slice(4)); else params.delete("job");
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [kind, mode, selectedId]);

  const selected = payload?.nodes.find((node) => node.id === selectedId);
  const selectedCapabilityId = kind === "capability" ? selectedId : undefined;
  const displayPayload = useMemo(() => {
    if (!payload) return payload;
    if (kind === "capability") {
      const parentByChild = new Map(payload.edges.filter((edge) => edge.type === "PARENT_OF").map((edge) => [edge.target, edge.source]));
      let branch = selectedCapabilityId;
      while (branch && payload.nodes.find((node) => node.id === branch)?.data.level !== 1) branch = parentByChild.get(branch);
      const visible = new Set(payload.nodes.filter((node) => Number(node.data.level) <= 2).map((node) => node.id));
      if (branch) {
        visible.add(branch);
        let frontier = new Set([branch]);
        for (let level = 0; level < 3; level += 1) {
          const next = new Set(payload.edges.filter((edge) => edge.type === "PARENT_OF" && frontier.has(edge.source)).map((edge) => edge.target));
          next.forEach((id) => visible.add(id));
          frontier = next;
        }
      }
      return { ...payload, nodes: payload.nodes.filter((node) => visible.has(node.id)), edges: payload.edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)), meta: { ...payload.meta, partial: true } };
    }
    if (mode !== "community") return payload;
    const connected = new Set(payload.edges.flatMap((edge) => [edge.source, edge.target]));
    const hiddenCount = payload.nodes.length - connected.size;
    return {
      ...payload,
      nodes: payload.nodes.filter((node) => connected.has(node.id)),
      combos: [],
      meta: {
        ...payload.meta,
        partial: hiddenCount > 0,
        warnings: hiddenCount > 0
          ? [...payload.meta.warnings, `数据聚类模式隐藏了 ${hiddenCount} 个暂无相似边的职业，可在标准分类或左侧目录中查看。`]
          : payload.meta.warnings,
      },
    };
  }, [kind, mode, payload, selectedCapabilityId]);
  const filtered = useMemo(() => {
    if (!payload) return [];
    const normalized = query.trim().toLowerCase();
    return payload.nodes.filter((node) => !normalized || node.data.label.toLowerCase().includes(normalized)).slice(0, 80);
  }, [payload, query]);

  return (
    <div className="v4-graph-page">
      <aside className="graph-index-panel">
        <div className="panel-kicker"><GitBranch size={14} />双图谱工作台</div>
        <h1>{kind === "capability" ? "能力图谱" : "职业图谱"}</h1>
        <p>{kind === "capability" ? "从具身智能根节点逐级查看能力方向、能力簇与三级技术能力。" : "在六大职业方向中观察标准职业及经审核的相似关系。"}</p>
        <div className="graph-kind-switch">
          <button className={kind === "capability" ? "active" : ""} onClick={() => { setKind("capability"); setSelectedId(undefined); }}>能力图谱</button>
          <button className={kind === "career" ? "active" : ""} onClick={() => { setKind("career"); setSelectedId(undefined); }}>职业图谱</button>
        </div>
        {kind === "career" ? <div className="mode-switch"><button className={mode === "taxonomy" ? "active" : ""} onClick={() => setMode("taxonomy")}>标准分类</button><button className={mode === "community" ? "active" : ""} onClick={() => setMode("community")}>数据聚类</button></div> : null}
        <label className="graph-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={kind === "capability" ? "搜索能力或别名" : "搜索标准职业"} /></label>
        <div className="graph-directory" role="list">
          {filtered.map((node) => <button role="listitem" className={selectedId === node.id ? "selected" : ""} key={node.id} onClick={() => setSelectedId(node.id)}><span className="directory-dot" style={{ background: String(node.data.color ?? "#155eef") }} /><span><strong>{node.data.label}</strong><small>{kind === "capability" ? `L${node.data.level} · ${node.data.jobCount ?? 0} 个职业` : `${node.data.categoryL2} · ${node.data.capabilityCount ?? 0} 项能力`}</small></span></button>)}
        </div>
      </aside>

      <main className="graph-main-panel">
        <header className="graph-page-header">
          <div><span>{kind === "capability" ? "有序根树" : mode === "taxonomy" ? "标准分类网络" : "相似社区网络"}</span><h2>{payload?.snapshot.name ?? "读取最新快照"}</h2></div>
          <div className="coverage-chip"><strong>{Math.round((payload?.meta.coverage ?? 0) * 100)}%</strong><span>画像覆盖率</span></div>
        </header>
        {displayPayload?.meta.warnings.map((warning) => <div className="data-warning" key={warning}><AlertTriangle size={15} />{warning}</div>)}
        <section className="v4-graph-stage">
          {loading ? <div className="graph-state"><LoaderCircle className="spin" />正在加载 v4 图谱</div> : error ? <div className="graph-state error"><AlertTriangle />{error}</div> : displayPayload ? <Suspense fallback={<div className="graph-state">加载 G6 渲染器</div>}><GraphCanvas ref={graphRef} payload={displayPayload} graphKind={kind} mode={mode} selectedId={selectedId} onNodeSelect={setSelectedId} onEdgeSelect={setSelectedEdge} /></Suspense> : null}
          <div className="canvas-tools"><button onClick={() => graphRef.current?.zoomIn()} aria-label="放大"><Plus size={16} /></button><button onClick={() => graphRef.current?.zoomOut()} aria-label="缩小"><Minus size={16} /></button><button onClick={() => graphRef.current?.fit()} aria-label="适配画布"><RotateCcw size={16} /></button></div>
        </section>
      </main>

      <aside className="graph-detail-panel">
        <span className="detail-eyebrow">{selectedEdge ? "关系解释" : selected ? "节点详情" : "阅读提示"}</span>
        {selectedEdge ? <><h2>相似关系</h2><div className="score-orb">{Math.round(Number(selectedEdge.data.score ?? selectedEdge.data.weight ?? 0) * 100)}</div><dl className="detail-metrics"><div><dt>关系类型</dt><dd>{selectedEdge.type}</dd></div><div><dt>源节点</dt><dd>{payload?.nodes.find((n) => n.id === selectedEdge.source)?.data.label}</dd></div><div><dt>目标节点</dt><dd>{payload?.nodes.find((n) => n.id === selectedEdge.target)?.data.label}</dd></div></dl></> : selected ? <><h2>{selected.data.label}</h2><span className="taxonomy-badge">{kind === "capability" ? `L${selected.data.level} ${selected.data.kind ?? "能力"}` : selected.data.categoryL1}</span><dl className="detail-metrics"><div><dt>数据库 ID</dt><dd>{selected.data.databaseId}</dd></div><div><dt>关联能力</dt><dd>{selected.data.capabilityCount ?? "—"}</dd></div><div><dt>岗位证据</dt><dd>{selected.data.jdCount ?? selected.data.jobCount ?? "—"}</dd></div><div><dt>别名数量</dt><dd>{selected.data.aliasCount ?? "—"}</dd></div></dl></> : <><h2>选择一个节点</h2><p className="detail-copy">图谱画布与左侧目录使用同一份数据。点击任一节点可查看分类、覆盖度和证据规模；点击职业相似边可查看分数组成。</p></>}
        <div className="fallback-note"><strong>可访问备用呈现</strong><p>画布无法操作时，可使用左侧树形目录完成搜索和定位，核心信息不依赖悬停。</p></div>
      </aside>
    </div>
  );
}
