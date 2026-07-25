import {
  AlertCircle,
  ArrowRightLeft,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  CircleDot,
  Layers3,
  LoaderCircle,
  Play,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import type {
  CareerCluster,
  CareerClusterCandidate,
  CareerClusteringStatus,
} from "../types";

const relationLabels: Record<string, string> = {
  same: "语义等价",
  broader: "候选范围更宽",
  narrower: "候选范围更窄",
  related: "相关但不等价",
  different: "语义不同",
};

function percent(value: number | null | undefined) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

export function CareerClusterReview() {
  const [status, setStatus] = useState<CareerClusteringStatus | null>(null);
  const [candidates, setCandidates] = useState<CareerClusterCandidate[]>([]);
  const [clusters, setClusters] = useState<CareerCluster[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [approvedName, setApprovedName] = useState("");
  const [targetId, setTargetId] = useState("");
  const [targetSearch, setTargetSearch] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [statusResult, candidateResult, clusterResult] = await Promise.all([
        api.getCareerClusteringStatus(signal),
        api.getCareerClusterCandidates(signal),
        api.getCareerClusters(signal),
      ]);
      setStatus(statusResult);
      setCandidates(candidateResult.items);
      setClusters(clusterResult.items);
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
  }, []);

  const selected = candidates.find((candidate) => candidate.id === selectedId)
    ?? candidates[0]
    ?? null;

  useEffect(() => {
    if (!selected) {
      setSelectedId(null);
      setApprovedName("");
      setTargetId("");
      return;
    }
    setSelectedId(selected.id);
    setApprovedName(selected.proposed_name);
    if (selected.suggested_cluster_id && selected.suggested_relation === "same") {
      setTargetId(String(selected.suggested_cluster_id));
      setTargetSearch(selected.suggested_cluster_name ?? "");
    } else {
      setTargetId("");
      setTargetSearch("");
    }
    setReviewNote("");
  }, [selected?.id]);

  const filteredClusters = useMemo(() => {
    const query = targetSearch.trim().toLocaleLowerCase();
    const sameCategory = clusters.filter(
      (cluster) => !selected || cluster.sub_direction_code === selected.sub_direction_code,
    );
    if (!query) return sameCategory.slice(0, 80);
    return sameCategory.filter((cluster) => [
      cluster.name,
      cluster.description,
      cluster.direction_name,
      cluster.sub_direction_name,
    ].some((value) => value.toLocaleLowerCase().includes(query))).slice(0, 80);
  }, [clusters, selected, targetSearch]);

  const selectedTarget = clusters.find((cluster) => cluster.id === Number(targetId)) ?? null;

  const runReview = async (decision: "approve" | "merge" | "reject") => {
    if (!selected) return;
    if (decision === "merge" && !Number(targetId)) {
      setError("请选择要归并到的正式职业簇");
      return;
    }
    setBusyAction(decision);
    setError(null);
    setNotice(null);
    try {
      await api.reviewCareerClusterCandidate(selected.id, {
        decision,
        approvedName: approvedName.trim(),
        targetClusterId: decision === "merge" ? Number(targetId) : undefined,
        reviewNote,
      });
      setNotice(decision === "approve" ? "已创建职业簇并关联该JD" : decision === "merge" ? "该JD已归入已有职业簇" : "已拒绝该职业簇候选");
      await load();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusyAction(null);
    }
  };

  const runBatch = async () => {
    setBusyAction("batch");
    setError(null);
    setNotice(null);
    try {
      const result = await api.runCareerClusteringBatch(5);
      const failed = result.items.filter((item) => item.status === "failed").length;
      setNotice(`已处理 ${result.count} 条JD${failed ? `，其中 ${failed} 条需要检查` : ""}`);
      await load();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusyAction(null);
    }
  };

  return <section className="governance-dashboard career-cluster-dashboard" aria-label="职业聚类看板">
    <header className="governance-summary">
      <div className="governance-summary-copy">
        <h2>职业聚类工作台</h2>
        <p>按已审批能力画像组织单条企业JD；职业簇是上层分组，不会合并或改写JD。</p>
      </div>
      <div className="governance-stats">
        <div><BriefcaseBusiness size={17} /><span><strong>{status?.eligible_job_count ?? "—"}</strong><small>可聚类JD</small></span></div>
        <div><CheckCircle2 size={17} /><span><strong>{status?.clustered_job_count ?? "—"}</strong><small>已聚类JD</small></span></div>
        <div><Layers3 size={17} /><span><strong>{status?.active_cluster_count ?? "—"}</strong><small>正式职业簇</small></span></div>
        <div><CircleDot size={17} /><span><strong>{status?.pending_count ?? "—"}</strong><small>待人工审核</small></span></div>
      </div>
    </header>

    <div className="career-cluster-toolbar">
      <div><Sparkles size={15} /><span>模型 {status?.model ?? "未配置"}</span><small>低于80%重做，80%～89.99%人工审核，达到90%自动处理</small></div>
      <button type="button" onClick={() => void runBatch()} disabled={Boolean(busyAction) || !status?.configured}>
        {busyAction === "batch" ? <LoaderCircle className="spinning" size={15} /> : <Play size={15} />}
        {busyAction === "batch" ? "正在聚类…" : "处理下一批5条"}
      </button>
      <button type="button" className="icon-button" onClick={() => void load()} disabled={loading} aria-label="刷新职业聚类"><RefreshCw className={loading ? "spinning" : ""} size={15} /></button>
    </div>

    {error ? <div className="governance-message error"><AlertCircle size={16} />{error}</div> : null}
    {notice ? <div className="governance-message success"><CheckCircle2 size={16} />{notice}</div> : null}

    <div className="governance-workspace">
      <div className="governance-list">
        <div className="governance-list-heading"><span>职业簇候选</span><small>{candidates.length} 条待处理</small></div>
        <div className="governance-list-scroll">
          {loading && candidates.length === 0 ? <div className="governance-empty"><LoaderCircle className="spinning" size={24} /><span>正在读取职业聚类队列…</span></div> : null}
          {!loading && candidates.length === 0 ? <div className="governance-empty"><CheckCircle2 size={26} /><strong>当前队列已清空</strong><span>可点击上方按钮处理新的JD</span></div> : null}
          {candidates.map((candidate) => <button
            type="button"
            key={candidate.id}
            className={selected?.id === candidate.id ? "governance-row active" : "governance-row"}
            onClick={() => setSelectedId(candidate.id)}
          >
            <span className="governance-row-id">#{candidate.id}</span>
            <span className="governance-row-main"><strong>{candidate.proposed_name}</strong><small>{candidate.job_title} · {candidate.company_name || "未知企业"}</small></span>
            <span className="governance-row-meta">{percent(Math.min(candidate.profile_confidence, candidate.classification_confidence))}</span>
          </button>)}
        </div>
      </div>

      <div className="governance-detail">
        {!selected ? <div className="governance-empty detail"><BriefcaseBusiness size={30} /><strong>暂无待审核职业簇</strong><span>各项判断达到90%的结果会直接进入正式职业簇库</span></div> : <>
          <header className="governance-detail-header">
            <div><span>职业簇候选 #{selected.id}</span><h3>{selected.proposed_name}</h3><p>JD #{selected.career_unit_id} · {selected.job_title} · {selected.company_name || "未知企业"}</p></div>
            <span className="governance-status">待审核</span>
          </header>

          <section className="governance-definition"><h4>职业簇定义</h4><p>{selected.description}</p></section>
          <section className="career-cluster-taxonomy">
            <div><small>一级方向</small><strong>{selected.direction_code} · {selected.direction_name}</strong></div>
            <div><small>二级方向</small><strong>{selected.sub_direction_code} · {selected.sub_direction_name}</strong></div>
          </section>
          <section className="governance-evidence">
            <div><h4>已审批能力证据 · {selected.capability_evidence.length} 项</h4><span>职业画像依据</span></div>
            <div className="career-cluster-capabilities">
              {selected.capability_evidence.map((capability) => <article key={capability.id}>
                <strong>{capability.name}</strong><span>{percent(capability.confidence)}</span>
                <small>{capability.direction_name} / {capability.category_name}</small>
              </article>)}
            </div>
          </section>
          <dl className="governance-confidence">
            <div><dt>职业画像可信度</dt><dd>{percent(selected.profile_confidence)}</dd><small>低于80%重做；80%～89.99%转人工审核；达到90%可自动处理。</small></div>
            <div><dt>分类可信度</dt><dd>{percent(selected.classification_confidence)}</dd><small>低于80%重做；80%～89.99%转人工审核；达到90%可自动处理。</small></div>
          </dl>

          {selected.suggested_cluster_id ? <section className="governance-suggestion">
            <header><div><ArrowRightLeft size={14} /><span>已有职业簇比较</span></div><b>{percent(selected.suggested_confidence)}</b></header>
            <div className="governance-suggestion-main">
              <div><strong>#{selected.suggested_cluster_id} · {selected.suggested_cluster_name}</strong><small>{relationLabels[selected.suggested_relation] ?? selected.suggested_relation}</small></div>
              <p>{selected.suggested_cluster_description}</p><blockquote>{selected.reasoning}</blockquote>
            </div>
          </section> : null}

          <section className="governance-form">
            <label><span>审核后的中文职业簇名称</span><input value={approvedName} onChange={(event) => setApprovedName(event.target.value)} /></label>
            <label className="governance-target-field">
              <span>归并到同一子方向的已有职业簇</span>
              <div className="governance-target-search"><Search size={14} /><input value={targetSearch} onChange={(event) => setTargetSearch(event.target.value)} placeholder="搜索职业簇名称或定义" /></div>
              <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
                <option value="">选择已有职业簇</option>
                {filteredClusters.map((cluster) => <option key={cluster.id} value={cluster.id}>#{cluster.id} · {cluster.name}｜{cluster.member_count}条JD</option>)}
              </select>
              {selectedTarget ? <small className="governance-target-preview">{selectedTarget.direction_name} / {selectedTarget.sub_direction_name} · {selectedTarget.description}</small> : null}
            </label>
            <label><span>审核备注</span><textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="记录职业边界、归并依据或拒绝原因" /></label>
          </section>

          <footer className="governance-actions">
            <button type="button" className="reject" disabled={Boolean(busyAction)} onClick={() => void runReview("reject")}><X size={15} />拒绝</button>
            <button type="button" className="merge" disabled={Boolean(busyAction)} onClick={() => void runReview("merge")}><ArrowRightLeft size={15} />归并到已有</button>
            <button type="button" className="approve" disabled={Boolean(busyAction)} onClick={() => void runReview("approve")}><Check size={15} />批准新职业簇</button>
          </footer>
        </>}
      </div>
    </div>
  </section>;
}
