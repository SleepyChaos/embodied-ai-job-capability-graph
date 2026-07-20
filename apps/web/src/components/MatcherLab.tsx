import { AlertTriangle, ArrowRight, Check, LoaderCircle, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api";
import type { MatchCandidate, VectorizationRun } from "../types";

const EMPTY_JOB = { company: "宇树科技", title: "运动控制算法工程师", responsibilities: "负责四足机器人运动控制算法、轨迹规划与仿真验证。", requirements: "熟悉 C++、Python、ROS2，掌握控制理论或强化学习。", niceToHave: "具备机器人动力学、Mujoco 仿真或实机调试经验。", location: "杭州", seniority: "高级" };

const SUGGESTION_LABEL: Record<string, string> = { SAME_CAREER: "建议归入已有职业", RELATED_CAREER: "相关但不同职业", NEW_CAREER_CANDIDATE: "候选新职业", INSUFFICIENT_EVIDENCE: "信息不足", EXACT_DUPLICATE: "重复记录", POSTING_VERSION: "岗位版本更新" };

export function MatcherLab() {
  const initialRun = Number(new URLSearchParams(location.search).get("run")) || null;
  const [job, setJob] = useState(EMPTY_JOB);
  const [runId, setRunId] = useState<number | null>(initialRun);
  const [run, setRun] = useState<VectorizationRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selected, setSelected] = useState<MatchCandidate | null>(null);

  useEffect(() => {
    if (!runId) return;
    const params = new URLSearchParams(location.search); params.set("section", "matcher"); params.set("run", String(runId)); history.replaceState(null, "", `${location.pathname}?${params}`);
    let timer = 0;
    const poll = () => api.getVectorizationRun(runId).then((value) => {
      setRun(value); setSelected((current) => current ?? value.candidates[0] ?? null);
      if (["queued", "running"].includes(value.status)) timer = window.setTimeout(poll, 900);
    }).catch((cause) => setError(cause.message));
    void poll();
    return () => window.clearTimeout(timer);
  }, [runId]);

  const submit = async () => {
    setSubmitting(true); setError(null); setRun(null); setSelected(null);
    try { const result = await api.createVectorizationRun(job); setRunId(result.runId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "任务提交失败"); }
    finally { setSubmitting(false); }
  };

  const decide = async (decision: string) => {
    if (!runId) return;
    try {
      await api.decideMatch({ runId, candidateId: selected?.id, targetJobId: selected?.jobId, decision, reviewer: "local-admin" });
      setRun(await api.getVectorizationRun(runId));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "审核提交失败"); }
  };

  return <main className="matcher-page">
    <header className="matcher-hero"><div><span className="page-kicker"><Sparkles size={15} />岗位匹配实验室</span><h1>从一条新 JD 到可解释的职业建议</h1><p>三级能力稀疏向量负责结构匹配；BGE 512 维向量补充语义判断。任何正式归并仍需人工审核。</p></div><div className="pipeline-mini"><span>能力抽取</span><ArrowRight /><span>混合评分</span><ArrowRight /><span>人工审核</span></div></header>
    <div className="matcher-grid">
      <section className="jd-editor card"><div className="card-heading"><div><span>01</span><h2>输入岗位</h2></div><small>支持网页粘贴与结构化字段</small></div>
        <div className="form-grid"><label>公司<input value={job.company} onChange={(e) => setJob({ ...job, company: e.target.value })} /></label><label>岗位名称<input value={job.title} onChange={(e) => setJob({ ...job, title: e.target.value })} /></label><label>地点<input value={job.location} onChange={(e) => setJob({ ...job, location: e.target.value })} /></label><label>职级<input value={job.seniority} onChange={(e) => setJob({ ...job, seniority: e.target.value })} /></label></div>
        <label>岗位职责<textarea rows={4} value={job.responsibilities} onChange={(e) => setJob({ ...job, responsibilities: e.target.value })} /></label><label>任职要求<textarea rows={4} value={job.requirements} onChange={(e) => setJob({ ...job, requirements: e.target.value })} /></label><label>优先条件<textarea rows={3} value={job.niceToHave} onChange={(e) => setJob({ ...job, niceToHave: e.target.value })} /></label>
        <button className="primary-action" onClick={submit} disabled={submitting || !job.title.trim()}>{submitting ? <LoaderCircle className="spin" /> : <Sparkles />}开始计算岗位向量</button>
      </section>
      <section className="vector-result card"><div className="card-heading"><div><span>02</span><h2>向量画像</h2></div><small>{run ? `${run.model.code} · ${run.model.dimensions}D` : "等待计算"}</small></div>
        {!run ? <div className="empty-result"><Sparkles /><strong>尚未生成岗位画像</strong><span>提交后将显示六大方向分布与三级能力贡献。</span></div> : ["queued", "running"].includes(run.status) ? <div className="empty-result"><LoaderCircle className="spin" /><strong>正在计算 {Math.round(run.progress * 100)}%</strong><span>能力抽取与职业候选召回在后台执行。</span></div> : <><div className="run-status"><span className={run.status}>{run.status === "succeeded" ? "完整计算" : "能力向量已完成"}</span><small>{run.semanticAvailable ? "语义向量已启用" : "语义模型未就绪，已透明降级"}</small></div>{run.warnings.map((item) => <div className="inline-warning" key={item}><AlertTriangle />{item}</div>)}<div className="domain-bars">{run.resultSummary?.domainVector.map((item) => <div key={item.id}><span>{item.name}</span><i><b style={{ width: `${Math.round(item.weight * 100)}%` }} /></i><strong>{Math.round(item.weight * 100)}</strong></div>)}</div><h3>三级能力 Top 贡献</h3><div className="capability-chips">{run.resultSummary?.topCapabilities.map((item) => <span key={item.id}>{item.name}<b>{Math.round(item.weight * 100)}</b></span>)}</div></>}
      </section>
      <section className="candidate-panel card"><div className="card-heading"><div><span>03</span><h2>候选职业</h2></div><small>{run?.candidateCount ?? 0} 个候选</small></div>
        <div className="candidate-list">{run?.candidates.map((item) => <button className={selected?.id === item.id ? "selected" : ""} onClick={() => setSelected(item)} key={item.id}><em>{item.rank}</em><span><strong>{item.jobName}</strong><small>{item.categoryL2} · {SUGGESTION_LABEL[item.suggestion] ?? item.suggestion}</small></span><b>{Math.round(item.score * 100)}</b></button>)}</div>
      </section>
      <section className="decision-panel card"><div className="card-heading"><div><span>04</span><h2>解释与审核</h2></div><small>match-threshold-v1</small></div>
        {selected ? <><div className="candidate-title"><div><span>#{selected.rank} 候选</span><h3>{selected.jobName}</h3></div><div className="score-orb">{Math.round(selected.score * 100)}</div></div><div className="score-breakdown">{Object.entries(selected.components).filter(([,value]) => value !== null).map(([key,value]) => <div key={key}><span>{key}</span><i><b style={{ width: `${Number(value) * 100}%` }} /></i><strong>{Math.round(Number(value) * 100)}</strong></div>)}</div><div className="evidence-tags"><strong>共享能力</strong>{selected.explanation.sharedCapabilities?.length ? selected.explanation.sharedCapabilities.map((name) => <span key={name}>{name}</span>) : <small>暂无共享能力证据</small>}</div><div className="decision-actions"><button onClick={() => decide("SAME_CAREER")}><Check />归入该职业</button><button onClick={() => decide("RELATED_CAREER")}>建立相关关系</button><button onClick={() => decide("NEW_CAREER_CANDIDATE")}>创建新职业</button><button onClick={() => decide("INSUFFICIENT_EVIDENCE")}>标记信息不足</button></div>{run?.decision ? <div className="decision-recorded"><Check />本任务已记录人工审核决定</div> : null}</> : <div className="empty-result"><ArrowRight /><strong>选择候选职业</strong><span>这里将展示总分、五项分解、共享与缺失能力。</span></div>}
      </section>
    </div>{error ? <div className="toast-error"><AlertTriangle />{error}</div> : null}
  </main>;
}
