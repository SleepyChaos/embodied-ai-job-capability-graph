import { AlertTriangle, BriefcaseBusiness, Building2, Hexagon, LoaderCircle, RefreshCw, Search, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import type { CareerGraphJobDetail, CareerSpectrumPayload } from "../types";
import { CareerSpectrumCanvas } from "./CareerSpectrumCanvas";

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

type Props = {
  onCapability: () => void;
  onCareer: () => void;
  onOpenCareer: (jobId: number) => void;
};

export function CareerSpectrumExplorer(props: Props) {
  const initial = new URLSearchParams(location.search);
  const [payload, setPayload] = useState<CareerSpectrumPayload | null>(null);
  const [selectedId, setSelectedId] = useState<number | undefined>(
    Number(initial.get("job")) || undefined,
  );
  const [detail, setDetail] = useState<CareerGraphJobDetail | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (initialLoad = false) => {
    if (initialLoad) setLoading(true); else setRefreshing(true);
    try {
      const value = await api.getCareerSpectrum();
      setPayload(value);
      setSelectedId((current) => current && value.jobs.some((job) => job.id === current)
        ? current
        : value.jobs[0]?.id);
      setError(null);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load(true);
    const timer = window.setInterval(() => void load(false), 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    params.set("section", "graph");
    params.set("graph", "spectrum");
    params.delete("node");
    if (selectedId) params.set("job", String(selectedId)); else params.delete("job");
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    api.getCareerGraphJobDetail(selectedId, controller.signal)
      .then(setDetail)
      .catch((cause) => {
        if (cause.name !== "AbortError") setError(cause.message);
      })
      .finally(() => setDetailLoading(false));
    return () => controller.abort();
  }, [selectedId]);

  const filteredJobs = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("zh-CN");
    return (payload?.jobs ?? []).filter((job) => {
      const value = `${job.title} ${job.company ?? ""} ${job.directionName} ${job.subDirectionName}`
        .toLocaleLowerCase("zh-CN");
      return !normalized || value.includes(normalized);
    });
  }, [payload, query]);
  const selectedJob = payload?.jobs.find((job) => job.id === selectedId);

  return (
    <div className="v4-graph-page spectrum-page">
      <aside className="graph-index-panel">
        <div className="panel-kicker"><Hexagon size={14} />职业色系工作台</div>
        <h1>职业色系谱</h1>
        <p>只展示已审批JD；六个蜂窝扇区分别对应六大职业方向。</p>
        <div className="graph-kind-switch">
          <button onClick={props.onCapability}>能力图谱</button>
          <button onClick={props.onCareer}>职业属性图谱</button>
          <button className="active">职业色系谱</button>
        </div>
        <div className="spectrum-direction-summary">
          {payload?.directions.map((direction) => (
            <div key={direction.id}>
              <i style={{ background: direction.color }} />
              <span>{direction.name}</span>
              <strong>{direction.count}</strong>
            </div>
          ))}
        </div>
        <label className="graph-search">
          <Search size={15} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索JD、企业或分类" />
        </label>
        <div className="directory-result-count">{query ? `找到 ${filteredJobs.length} 条正式JD` : `全部 ${filteredJobs.length} 条正式JD`}</div>
        <div className="graph-directory spectrum-directory" role="list">
          {filteredJobs.map((job) => (
            <button
              role="listitem"
              className={selectedId === job.id ? "selected" : ""}
              key={job.id}
              onClick={() => setSelectedId(job.id)}
              onDoubleClick={() => props.onOpenCareer(job.id)}
            >
              <span className="spectrum-directory-dot" style={{ background: job.color }} />
              <span>
                <strong>{job.title}</strong>
                <small>{job.company ?? "企业待补充"} · {job.subDirectionName}</small>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <main className="graph-main-panel">
        <header className="graph-page-header">
          <div>
            <span>六方向 · 实心六边形蜂窝</span>
            <h2>{payload?.snapshot.name ?? "读取职业色系"}</h2>
            <small>更新于 {formatUpdatedAt(payload?.snapshot.at)} · 双击JD进入职业属性图谱</small>
          </div>
          <div className="coverage-chip"><strong>{payload?.snapshot.metrics.jobCount ?? 0}</strong><span>正式 JD</span></div>
        </header>
        {payload?.meta.warnings.map((warning) => <div className="data-warning" key={warning}><AlertTriangle size={15} />{warning}</div>)}
        <section className="v4-graph-stage spectrum-stage">
          {loading ? (
            <div className="graph-state"><LoaderCircle className="spin" />正在生成职业蜂窝</div>
          ) : error && !payload ? (
            <div className="graph-state error"><AlertTriangle />{error}</div>
          ) : payload ? (
            <CareerSpectrumCanvas
              directions={payload.directions}
              jobs={payload.jobs}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onOpenCareer={props.onOpenCareer}
            />
          ) : null}
          <button className="spectrum-refresh" onClick={() => void load(false)}>
            <RefreshCw className={refreshing ? "spin" : ""} size={14} />同步数据库
          </button>
          <div className="spectrum-instruction">悬停查看企业与二级分类 · 单击查看详情 · 双击进入关系邻域</div>
        </section>
      </main>

      <aside className="graph-detail-panel spectrum-detail-panel">
        <span className="detail-eyebrow">正式JD详情</span>
        {selectedJob ? (
          <>
            <h2>{selectedJob.title}</h2>
            <span className="taxonomy-badge">{selectedJob.directionName} / {selectedJob.subDirectionName}</span>
            <p className="graph-detail-description">{selectedJob.company ?? "企业信息待补充"}{selectedJob.city ? ` · ${selectedJob.city}` : ""}</p>
            {detailLoading ? <div className="detail-loading"><LoaderCircle className="spin" />正在读取完整岗位信息</div> : null}
            {detail ? (
              <>
                <dl className="detail-metrics">
                  <div><dt>企业归属</dt><dd>{detail.company.name ?? "—"}</dd></div>
                  <div><dt>城市</dt><dd>{detail.city || "—"}</dd></div>
                  <div><dt>薪资</dt><dd>{detail.salary || "—"}</dd></div>
                  <div><dt>经验</dt><dd>{detail.experience || "—"}</dd></div>
                  <div><dt>学历</dt><dd>{detail.education || "—"}</dd></div>
                  <div><dt>正式能力</dt><dd>{detail.capabilities.length}</dd></div>
                </dl>
                <section className="graph-detail-section">
                  <h3><BriefcaseBusiness size={14} />岗位描述</h3>
                  <p className="spectrum-jd-description">{detail.description || "暂无岗位描述"}</p>
                </section>
                <section className="graph-detail-section">
                  <h3><Sparkles size={14} />关联能力 <b>{detail.capabilities.length}</b></h3>
                  <div className="spectrum-capability-tags">{detail.capabilities.map((capability) => <span key={capability.id}>{capability.name}</span>)}</div>
                </section>
                <button className="spectrum-open-relation" onClick={() => props.onOpenCareer(detail.id)}>
                  <Building2 size={14} />进入该JD的职业属性图谱
                </button>
              </>
            ) : null}
          </>
        ) : <><h2>选择一个JD节点</h2><p className="detail-copy">悬停观察局部避让效果，单击读取完整岗位信息，双击进入它的职业属性关系邻域。</p></>}
      </aside>
    </div>
  );
}
