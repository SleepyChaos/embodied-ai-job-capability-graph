import { Database, ExternalLink, ShieldAlert } from "lucide-react";

import type { Evidence, JobSummary } from "../types";

type EvidenceCatalogProps = {
  jobs: JobSummary[];
  selectedJobId?: number;
  evidence: Evidence[];
  onSelectJob: (job: JobSummary) => void;
};

export function EvidenceCatalog({ jobs, selectedJobId, evidence, onSelectJob }: EvidenceCatalogProps) {
  return (
    <main className="content-page">
      <div className="page-hero">
        <div><span className="page-kicker"><Database size={14} />可追溯数据</span><h1>数据证据</h1><p>按岗位核查技能映射的原始招聘 JD；迁移证据在人工复核前统一标记为待审核。</p></div>
        <div className="hero-stat amber"><strong>{evidence.length}</strong><span>当前结果</span></div>
      </div>
      <div className="evidence-controls">
        <label>选择岗位<select value={selectedJobId ?? ""} onChange={(event) => { const job = jobs.find((item) => item.id === Number(event.target.value)); if (job) onSelectJob(job); }}>
          {jobs.map((job) => <option value={job.id} key={job.id}>{job.name}</option>)}
        </select></label>
        <span><ShieldAlert size={16} />当前证据尚未完成人工审核</span>
      </div>
      <div className="evidence-table" role="table" aria-label="岗位关系证据">
        <div className="evidence-table-head" role="row"><span>企业 / 原始岗位</span><span>映射技能</span><span>来源</span><span>状态</span><span>原文</span></div>
        {evidence.map((item) => (
          <article className="evidence-table-row" role="row" key={item.id}>
            <div><strong>{item.company ?? "未知企业"}</strong><small>{item.rawTitle ?? item.jobName}</small></div>
            <span>{item.skillName}</span><span>{item.source}</span>
            <span className={item.verified ? "verified-badge" : "pending-badge"}>{item.verified ? "已审核" : "待审核"}</span>
            <span>{item.url ? <a href={item.url} target="_blank" rel="noreferrer" aria-label={`查看 ${item.rawTitle ?? item.jobName} 原始 JD`}><ExternalLink size={17} /></a> : "—"}</span>
          </article>
        ))}
      </div>
      {evidence.length === 0 ? <div className="catalog-empty">当前岗位暂无证据</div> : null}
    </main>
  );
}
