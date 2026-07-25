import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  CircleDot,
  Filter,
  LoaderCircle,
  Play,
  RefreshCw,
  Search,
  Sheet,
  Sparkles,
  Waypoints,
} from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import type {
  JDPipelineJob,
  JDPipelineStatus,
  JDPipelineSummary,
} from "../types";

const statusLabels: Record<JDPipelineStatus, string> = {
  not_started: "未开始",
  processing: "处理中",
  review: "待审核",
  succeeded: "成功",
  failed: "失败",
};

const statusOptions = Object.entries(statusLabels) as [JDPipelineStatus, string][];

function StatusBadge({ status }: { status: JDPipelineStatus }) {
  return <span className={`pipeline-status ${status}`}>{statusLabels[status]}</span>;
}

export function JDPipelineMonitor() {
  const [summary, setSummary] = useState<JDPipelineSummary | null>(null);
  const [jobs, setJobs] = useState<JDPipelineJob[]>([]);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim());
  const [source, setSource] = useState("");
  const [capabilityStatus, setCapabilityStatus] = useState<JDPipelineStatus | "">("");
  const [careerStatus, setCareerStatus] = useState<JDPipelineStatus | "">("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(() => new Set());
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<"capability" | "career" | "both" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const pageSize = 30;

  const load = async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [summaryResult, jobResult] = await Promise.all([
        api.getJDPipelineSummary(signal),
        api.getJDPipelineJobs({
          query: deferredQuery,
          source,
          capabilityStatus,
          careerStatus,
          page,
          pageSize,
        }, signal),
      ]);
      setSummary(summaryResult);
      setJobs(jobResult.items);
      setTotal(jobResult.page.total);
      setSelected((current) => {
        const visible = new Set(jobResult.items.map((job) => job.id));
        return new Set([...current].filter((id) => visible.has(id)));
      });
    } catch (reason) {
      if ((reason as Error).name !== "AbortError") setError((reason as Error).message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [deferredQuery, source, capabilityStatus, careerStatus, page]);

  useEffect(() => {
    setPage(1);
  }, [deferredQuery, source, capabilityStatus, careerStatus]);

  const selectedIds = useMemo(() => [...selected].slice(0, 10), [selected]);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pageSelected = jobs.length > 0 && jobs.every((job) => selected.has(job.id));

  const toggleJob = (jobId: number) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(jobId)) next.delete(jobId);
      else if (next.size < 10) next.add(jobId);
      return next;
    });
  };

  const selectPage = () => {
    setSelected(pageSelected ? new Set() : new Set(jobs.slice(0, 10).map((job) => job.id)));
  };

  const selectActionable = (kind: "capability" | "career") => {
    const actionable = jobs.filter((job) => (
      kind === "capability"
        ? ["not_started", "failed"].includes(job.capability_extraction_status)
        : job.capability_extraction_status === "succeeded"
          && ["not_started", "failed"].includes(job.career_clustering_status)
    )).slice(0, 10);
    setSelected(new Set(actionable.map((job) => job.id)));
  };

  const run = async (action: "capability" | "career" | "both") => {
    if (!selectedIds.length) {
      setError("请先勾选要处理的JD，单次最多10条");
      return;
    }
    setBusyAction(action);
    setError(null);
    setNotice(null);
    try {
      const result = await api.processJDPipeline(selectedIds, action);
      const failed = result.items.filter((item) => item.status === "failed").length;
      setNotice(`已处理 ${result.count} 条JD${failed ? `，${failed} 条执行失败，原因已写入JD记录` : ""}`);
      setSelected(new Set());
      await load();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusyAction(null);
    }
  };

  return <section className="pipeline-monitor" aria-label="JD处理流程监控">
    <header className="pipeline-monitor-header">
      <div><span><Sheet size={15} />XLSX JD治理</span><h2>JD流程监控</h2><p>监控能力提取和职业聚类，筛选失败或未处理记录并执行补处理。</p></div>
      <div className="pipeline-import-card">
        <small>最近导入批次</small>
        <strong>{summary?.latestImport?.source_file ?? "暂无导入记录"}</strong>
        <span>{summary?.latestImport ? `${summary.latestImport.success_count}/${summary.latestImport.total_count} 条成功 · ${summary.latestImport.status}` : "—"}</span>
      </div>
    </header>

    <div className="pipeline-metrics">
      <div><Sheet size={18} /><span><strong>{summary?.total ?? "—"}</strong><small>全部JD</small></span></div>
      <div><Sparkles size={18} /><span><strong>{summary?.capability_succeeded ?? "—"}</strong><small>能力提取成功</small></span><b>{summary?.capability_failed ?? 0} 失败</b></div>
      <div><Waypoints size={18} /><span><strong>{summary?.career_succeeded ?? "—"}</strong><small>职业聚类成功</small></span><b>{summary?.career_ready ?? 0} 待聚类</b></div>
      <div><CircleDot size={18} /><span><strong>{(summary?.capability_review ?? 0) + (summary?.career_review ?? 0)}</strong><small>人工审核任务</small></span></div>
    </div>

    <section className="pipeline-filters">
      <label className="pipeline-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索JD、企业或ID" /></label>
      <label><Filter size={14} /><select value={source} onChange={(event) => setSource(event.target.value)}><option value="">全部数据来源</option>{summary?.sources.map((item) => <option value={item.name} key={item.name}>{item.name}（{item.count}）</option>)}</select></label>
      <label><select value={capabilityStatus} onChange={(event) => setCapabilityStatus(event.target.value as JDPipelineStatus | "")}><option value="">全部能力状态</option>{statusOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      <label><select value={careerStatus} onChange={(event) => setCareerStatus(event.target.value as JDPipelineStatus | "")}><option value="">全部职业状态</option>{statusOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      <button type="button" className="pipeline-refresh" onClick={() => void load()} disabled={loading} aria-label="刷新JD状态"><RefreshCw className={loading ? "spinning" : ""} size={15} /></button>
    </section>

    <section className="pipeline-actions">
      <div><strong>已选择 {selectedIds.length}/10 条</strong><button type="button" onClick={() => selectActionable("capability")}>选择本页未提取/失败</button><button type="button" onClick={() => selectActionable("career")}>选择本页待聚类/失败</button></div>
      <div>
        <button type="button" disabled={Boolean(busyAction)} onClick={() => void run("capability")}>{busyAction === "capability" ? <LoaderCircle className="spinning" size={14} /> : <Sparkles size={14} />}能力补处理</button>
        <button type="button" disabled={Boolean(busyAction)} onClick={() => void run("career")}>{busyAction === "career" ? <LoaderCircle className="spinning" size={14} /> : <Waypoints size={14} />}职业聚类</button>
        <button type="button" className="primary" disabled={Boolean(busyAction)} onClick={() => void run("both")}>{busyAction === "both" ? <LoaderCircle className="spinning" size={14} /> : <Play size={14} />}串联处理</button>
      </div>
    </section>

    {error ? <div className="governance-message error"><AlertCircle size={16} />{error}</div> : null}
    {notice ? <div className="governance-message success"><CheckCircle2 size={16} />{notice}</div> : null}

    <div className="pipeline-table-wrap">
      <table className="pipeline-table">
        <thead><tr><th><button type="button" className={pageSelected ? "checked" : ""} onClick={selectPage} aria-label="选择本页"><Check size={12} /></button></th><th>JD与来源</th><th>能力提取</th><th>职业聚类</th><th>结果与失败原因</th></tr></thead>
        <tbody>{jobs.map((job) => <tr key={job.id} className={selected.has(job.id) ? "selected" : ""}>
          <td><button type="button" className={selected.has(job.id) ? "checked" : ""} onClick={() => toggleJob(job.id)} aria-label={`选择JD ${job.id}`}><Check size={12} /></button></td>
          <td><strong>{job.job_title}</strong><small>#{job.id} · {job.company_name || "未知企业"}</small><em>{job.data_source || "未标记来源"}</em></td>
          <td><StatusBadge status={job.capability_extraction_status} /><small>{job.capability_count} 项正式能力{job.capability_attempt_count ? ` · ${job.capability_attempt_count}次` : ""}</small></td>
          <td><StatusBadge status={job.career_clustering_status} /><small>{job.cluster_name ? `${job.cluster_name} · ${job.sub_direction_code}` : job.capability_extraction_status !== "succeeded" ? "等待能力提取成功" : "可以开始聚类"}</small></td>
          <td>{job.capability_extraction_failure_reason || job.career_clustering_failure_reason
            ? <span className="pipeline-failure" title={job.capability_extraction_failure_reason || job.career_clustering_failure_reason || ""}>{job.capability_extraction_failure_reason || job.career_clustering_failure_reason}</span>
            : <span className="pipeline-ok">{job.capability_extraction_status === "succeeded" && job.career_clustering_status === "succeeded" ? "两项流程已完成" : "—"}</span>}</td>
        </tr>)}</tbody>
      </table>
      {loading ? <div className="pipeline-loading"><LoaderCircle className="spinning" size={22} />正在读取JD流程状态…</div> : null}
      {!loading && jobs.length === 0 ? <div className="pipeline-loading"><AlertCircle size={22} />没有符合筛选条件的JD</div> : null}
    </div>

    <footer className="pipeline-pagination">
      <span>第 {page}/{totalPages} 页 · 共 {total} 条</span>
      <div><button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ArrowLeft size={14} /></button><button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}><ArrowRight size={14} /></button></div>
    </footer>
  </section>;
}
