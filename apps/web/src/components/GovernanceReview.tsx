import {
  AlertCircle,
  ArrowRightLeft,
  Check,
  CheckCircle2,
  CircleDot,
  FileSearch,
  Layers3,
  LoaderCircle,
  RefreshCw,
  Search,
  Sparkles,
  Tags,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import type {
  ActiveCapability,
  CapabilityCandidate,
  CategoryCandidate,
  GovernanceQueueKind,
  GovernanceSummary,
  NormalizationCandidate,
} from "../types";

type ReviewItem = CapabilityCandidate | CategoryCandidate | NormalizationCandidate;

const queueLabels: Record<GovernanceQueueKind, { title: string; description: string }> = {
  capabilities: { title: "能力总称候选", description: "审核名称、描述和分类后进入正式能力库" },
  categories: { title: "二级分类候选", description: "仅在现有18个分类确实无法容纳时新增" },
  normalizations: { title: "语义归并复核", description: "确认两个能力是否真正等价，而不只是相关" },
};

const requirementLabels: Record<string, string> = {
  required: "任职必备",
  preferred: "优先条件",
  responsibility: "岗位职责",
  mentioned: "一般提及",
};

const relationLabels: Record<string, string> = {
  same: "语义等价",
  broader: "新能力范围更宽",
  narrower: "新能力范围更窄",
  related: "仅相关，不等价",
  different: "语义不同",
};

const sourceFieldLabels: Record<string, string> = {
  job_title: "岗位名称",
  jd_description: "JD 描述",
  other_info: "其他信息",
  combined_text: "合并原文",
};

function confidenceLabel(value: number | null | undefined) {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function itemTitle(item: ReviewItem) {
  if ("proposed_name" in item) return item.proposed_name;
  return item.proposed_canonical_name;
}

function itemSubtitle(item: ReviewItem) {
  if ("category_name" in item) return [item.direction_name, item.category_name].filter(Boolean).join(" / ");
  if ("direction_name" in item) return item.direction_name;
  return `建议归并至：${item.candidate_capability_name}`;
}

export function GovernanceReview() {
  const [summary, setSummary] = useState<GovernanceSummary | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityCandidate[]>([]);
  const [categories, setCategories] = useState<CategoryCandidate[]>([]);
  const [normalizations, setNormalizations] = useState<NormalizationCandidate[]>([]);
  const [activeCapabilities, setActiveCapabilities] = useState<ActiveCapability[]>([]);
  const [queue, setQueue] = useState<GovernanceQueueKind>("capabilities");
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
      const [summaryResult, capabilityResult, categoryResult, normalizationResult, activeResult] = await Promise.all([
        api.getGovernanceSummary(signal),
        api.getCapabilityCandidates(signal),
        api.getCategoryCandidates(signal),
        api.getNormalizationCandidates(signal),
        api.getActiveCapabilities(signal),
      ]);
      setSummary(summaryResult);
      setCapabilities(capabilityResult.items);
      setCategories(categoryResult.items);
      setNormalizations(normalizationResult.items);
      setActiveCapabilities(activeResult.items);
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

  const items = useMemo<ReviewItem[]>(() => {
    if (queue === "capabilities") return capabilities;
    if (queue === "categories") return categories;
    return normalizations;
  }, [capabilities, categories, normalizations, queue]);

  const selected = items.find((item) => item.id === selectedId) ?? items[0] ?? null;

  useEffect(() => {
    if (!selected) {
      setSelectedId(null);
      setApprovedName("");
      return;
    }
    setSelectedId(selected.id);
    setApprovedName(itemTitle(selected));
    if (
      "suggested_capability_id" in selected
      && selected.suggested_capability_id
      && selected.suggested_relation === "same"
    ) {
      setTargetId(String(selected.suggested_capability_id));
      setTargetSearch(selected.suggested_capability_name ?? "");
    } else {
      setTargetId("");
      setTargetSearch("");
    }
    setReviewNote("");
  }, [queue, selected?.id]);

  const filteredCapabilities = useMemo(() => {
    const query = targetSearch.trim().toLocaleLowerCase();
    if (!query) return activeCapabilities.slice(0, 80);
    return activeCapabilities.filter((capability) => [
      capability.name,
      capability.aliases,
      capability.category_name,
      capability.direction_name,
    ].some((value) => value?.toLocaleLowerCase().includes(query))).slice(0, 80);
  }, [activeCapabilities, targetSearch]);

  const selectedCapabilityTarget = activeCapabilities.find(
    (capability) => capability.id === Number(targetId),
  ) ?? null;

  const counts = {
    capabilities: summary?.capability_count ?? capabilities.length,
    categories: summary?.category_count ?? categories.length,
    normalizations: summary?.normalization_count ?? normalizations.length,
  };

  const runReview = async (decision: "approve" | "merge" | "reject") => {
    if (!selected) return;
    if (decision === "merge" && !Number(targetId)) {
      setError("请输入要归并到的正式记录 ID");
      return;
    }
    setBusyAction(decision);
    setError(null);
    setNotice(null);
    try {
      if (queue === "capabilities") {
        await api.reviewCapabilityCandidate(selected.id, {
          decision,
          approvedName: approvedName.trim(),
          targetCapabilityId: decision === "merge" ? Number(targetId) : undefined,
          reviewNote,
        });
      } else if (queue === "categories") {
        await api.reviewCategoryCandidate(selected.id, {
          decision,
          approvedName: approvedName.trim(),
          targetCategoryId: decision === "merge" ? Number(targetId) : undefined,
          reviewNote,
        });
      } else {
        await api.reviewNormalizationCandidate(selected.id, { decision, reviewNote });
      }
      setNotice(decision === "approve" ? "已批准并写入正式库" : decision === "merge" ? "已完成归并" : "已拒绝该候选");
      await load();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusyAction(null);
    }
  };

  return <section className="governance-dashboard" aria-label="能力审核看板">
    <header className="governance-summary">
      <div className="governance-summary-copy">
        <h2>能力治理工作台</h2>
        <p>把 AI 抽取结果整理为稳定、可复用、可追溯的正式能力本体。</p>
      </div>
      <div className="governance-stats">
        <div><Sparkles size={17} /><span><strong>{summary?.completed_run_count ?? "—"}</strong><small>已处理JD</small></span></div>
        <div><CircleDot size={17} /><span><strong>{counts.capabilities + counts.categories + counts.normalizations}</strong><small>审核任务</small></span></div>
        <div><CheckCircle2 size={17} /><span><strong>{summary?.active_capability_count ?? "—"}</strong><small>正式能力</small></span></div>
        <div><Tags size={17} /><span><strong>{summary?.active_alias_count ?? "—"}</strong><small>正式别称</small></span></div>
      </div>
    </header>

    <div className="governance-queue-tabs" role="tablist" aria-label="审核队列">
      {(Object.keys(queueLabels) as GovernanceQueueKind[]).map((kind) => <button
        key={kind}
        type="button"
        role="tab"
        aria-selected={queue === kind}
        className={queue === kind ? "active" : ""}
        onClick={() => setQueue(kind)}
      >
        {kind === "capabilities" ? <Sparkles size={15} /> : kind === "categories" ? <Layers3 size={15} /> : <ArrowRightLeft size={15} />}
        <span><strong>{queueLabels[kind].title}</strong><small>{queueLabels[kind].description}</small></span>
        <b>{counts[kind]}</b>
      </button>)}
      <button className="governance-refresh" type="button" onClick={() => void load()} disabled={loading} aria-label="刷新审核队列">
        <RefreshCw size={15} className={loading ? "spinning" : ""} />
      </button>
    </div>

    {error ? <div className="governance-message error"><AlertCircle size={16} />{error}</div> : null}
    {notice ? <div className="governance-message success"><CheckCircle2 size={16} />{notice}</div> : null}

    <div className="governance-workspace">
      <div className="governance-list">
        <div className="governance-list-heading"><span>{queueLabels[queue].title}</span><small>{items.length} 条待处理</small></div>
        <div className="governance-list-scroll">
          {loading && items.length === 0 ? <div className="governance-empty"><LoaderCircle className="spinning" size={24} /><span>正在读取审核队列…</span></div> : null}
          {!loading && items.length === 0 ? <div className="governance-empty"><CheckCircle2 size={26} /><strong>当前队列已清空</strong><span>没有需要处理的候选记录</span></div> : null}
          {items.map((item) => <button
            type="button"
            className={selected?.id === item.id ? "governance-row active" : "governance-row"}
            key={item.id}
            onClick={() => setSelectedId(item.id)}
          >
            <span className="governance-row-id">#{item.id}</span>
            <span className="governance-row-main"><strong>{itemTitle(item)}</strong><small>{itemSubtitle(item)}</small></span>
            <span className="governance-row-meta">
              {"extraction_confidence" in item ? confidenceLabel(item.extraction_confidence) : confidenceLabel(item.confidence)}
            </span>
          </button>)}
        </div>
      </div>

      <div className="governance-detail">
        {!selected ? <div className="governance-empty detail"><FileSearch size={30} /><strong>选择一条候选开始审核</strong><span>左侧队列会展示 AI 抽取和归并建议</span></div> : <>
          <header className="governance-detail-header">
            <div><span>审核编号 #{selected.id}</span><h3>{itemTitle(selected)}</h3><p>{itemSubtitle(selected)}</p></div>
            <span className="governance-status">待审核</span>
          </header>

          {"surface_name" in selected ? <section className="governance-naming">
            <div><small>JD原始称呼</small><strong>{selected.surface_name}</strong><p>来自原始岗位文本，批准归并后保存为别称。</p></div>
            <ArrowRightLeft size={17} />
            <div><small>LLM建议总称</small><strong>{"proposed_name" in selected ? selected.proposed_name : selected.proposed_canonical_name}</strong><p>模型根据能力边界整理后的规范化称呼。</p></div>
          </section> : null}

          {"description" in selected ? <section className="governance-definition"><h4>能力定义</h4><p>{selected.description}</p></section> : null}
          {"proposed_description" in selected ? <section className="governance-definition"><h4>分类定义</h4><p>{selected.proposed_description || "AI 未提供分类定义"}</p></section> : null}
          {"candidate_capability_description" in selected ? <section className="normalization-compare">
            <div><small>新提及</small><strong>{selected.proposed_canonical_name}</strong><p>{selected.description}</p></div>
            <ArrowRightLeft size={18} />
            <div><small>已有总称</small><strong>{selected.candidate_capability_name}</strong><p>{selected.candidate_capability_description}</p></div>
          </section> : null}

          {"evidence_text" in selected ? <section className="governance-evidence">
            <div><h4>JD 原文证据 · {selected.evidence_details?.length || 1} 条</h4><span>{requirementLabels[selected.requirement_level] ?? selected.requirement_level}</span></div>
            <div className="governance-evidence-list">
              {(selected.evidence_details?.length ? selected.evidence_details : [{
                id: 0,
                mention_id: 0,
                evidence_text: selected.evidence_text,
                evidence_section: selected.evidence_section,
                source_field: "combined_text" as const,
                start_offset: 0,
                end_offset: selected.evidence_text.length,
                ordinal: 0,
                is_primary: 1 as const,
                source_hash: "",
              }]).map((evidence) => <article key={`${evidence.id}-${evidence.ordinal}`}>
                <blockquote>{evidence.evidence_text}</blockquote>
                <small>
                  {evidence.is_primary ? "主证据 · " : ""}
                  {sourceFieldLabels[evidence.source_field] ?? evidence.source_field}
                  {" · "}字符 {evidence.start_offset}–{evidence.end_offset}
                </small>
              </article>)}
            </div>
            <small>来源岗位：{selected.job_title} · 职业单元 #{selected.career_unit_id}</small>
          </section> : null}

          {"extraction_confidence" in selected ? <dl className="governance-confidence">
            <div>
              <dt>抽取可信度</dt>
              <dd>{confidenceLabel(selected.extraction_confidence)}</dd>
              <small>判断能力是否确实由 JD 原文支持，以及建议称呼是否准确。低于 90% 整批重做；新总称超过 95% 可自动创建。</small>
            </div>
            <div>
              <dt>分类可信度</dt>
              <dd>{confidenceLabel(selected.classification_confidence)}</dd>
              <small>判断该能力归入一级方向和二级分类是否准确。低于 90% 时整批退回重做。</small>
            </div>
          </dl> : null}

          {"suggested_capability_id" in selected && selected.suggested_capability_id ? <section className="governance-suggestion">
            <header><div><Sparkles size={14} /><span>LLM相似总称比较</span></div><b>{confidenceLabel(selected.suggested_confidence)}</b></header>
            <div className="governance-suggestion-main">
              <div><strong>#{selected.suggested_capability_id} · {selected.suggested_capability_name}</strong><small>{relationLabels[selected.suggested_relation ?? ""] ?? selected.suggested_relation}</small></div>
              <p>{selected.suggested_capability_description}</p>
              <blockquote>{selected.suggested_reasoning}</blockquote>
            </div>
          </section> : null}
          {"relation" in selected ? <dl className="governance-confidence">
            <div><dt>AI关系判断</dt><dd>{selected.relation}</dd></div>
            <div><dt>等价可信度</dt><dd>{confidenceLabel(selected.confidence)}</dd></div>
          </dl> : null}

          <section className="governance-form">
            {queue !== "normalizations" ? <label><span>审核后的规范名称</span><input value={approvedName} onChange={(event) => setApprovedName(event.target.value)} /></label> : null}
            {queue === "capabilities" ? <label className="governance-target-field">
              <span>归并到已有总称</span>
              <div className="governance-target-search"><Search size={14} /><input value={targetSearch} onChange={(event) => setTargetSearch(event.target.value)} placeholder="搜索总称、别称或分类" /></div>
              <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
                <option value="">选择已有总称（共 {activeCapabilities.length} 条）</option>
                {filteredCapabilities.map((capability) => <option key={capability.id} value={capability.id}>
                  #{capability.id} · {capability.name}｜{capability.category_name}
                </option>)}
              </select>
              {selectedCapabilityTarget ? <small className="governance-target-preview">
                {selectedCapabilityTarget.direction_name} / {selectedCapabilityTarget.category_name}
                {selectedCapabilityTarget.aliases ? ` · 别称：${selectedCapabilityTarget.aliases}` : ""}
              </small> : null}
            </label> : null}
            {queue === "categories" ? <label><span>归并目标二级分类 ID</span><input inputMode="numeric" value={targetId} onChange={(event) => setTargetId(event.target.value.replace(/\D/g, ""))} placeholder="现有二级分类 ID" /></label> : null}
            <label><span>审核备注</span><textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="记录命名调整、归并依据或拒绝原因" /></label>
          </section>

          <footer className="governance-actions">
            <button type="button" className="reject" disabled={Boolean(busyAction)} onClick={() => void runReview("reject")}><X size={15} />{busyAction === "reject" ? "处理中…" : "拒绝"}</button>
            {queue !== "normalizations" ? <button type="button" className="merge" disabled={Boolean(busyAction)} onClick={() => void runReview("merge")}><ArrowRightLeft size={15} />{busyAction === "merge" ? "处理中…" : "归并到已有"}</button> : null}
            <button type="button" className="approve" disabled={Boolean(busyAction)} onClick={() => void runReview("approve")}><Check size={15} />{busyAction === "approve" ? "处理中…" : queue === "normalizations" ? "确认等价" : "批准进入正式库"}</button>
          </footer>
        </>}
      </div>
    </div>
  </section>;
}
