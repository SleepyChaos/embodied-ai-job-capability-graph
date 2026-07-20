import { Database, ExternalLink, Search, ShieldAlert, Sparkles } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import type { Evidence, JobSummary } from "../types";

type JobCatalogProps = {
  jobs: JobSummary[];
  onOpenJob: (job: JobSummary) => void;
};

export function JobCatalog({ jobs, onOpenJob }: JobCatalogProps) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
  const filteredJobs = useMemo(() => jobs.filter((job) => (
    !deferredQuery || `${job.name} ${job.categoryL1} ${job.categoryL2 ?? ""}`.toLowerCase().includes(deferredQuery)
  )), [deferredQuery, jobs]);

  return (
    <main className="content-page">
      <div className="page-hero">
        <div><span className="page-kicker"><Sparkles size={14} />岗位资产</span><h1>岗位目录</h1><p>浏览已规范化的具身智能岗位，进入岗位中心查看能力结构和证据。</p></div>
        <div className="hero-stat"><strong>{jobs.length}</strong><span>规范岗位</span></div>
      </div>
      <label className="catalog-search"><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索岗位名称或分类" /></label>
      <div className="job-card-grid">
        {filteredJobs.map((job) => (
          <article className="job-card" key={job.id}>
            <div className="job-card-top"><span>{job.categoryL2 ?? job.categoryL1}</span>{job.emerging ? <em>新兴岗位</em> : null}</div>
            <h2>{job.name}</h2>
            <p>{job.categoryL1}</p>
            <dl><div><dt>技能</dt><dd>{job.skillCount}</dd></div><div><dt>证据</dt><dd>{job.evidenceCount}</dd></div></dl>
            <button type="button" onClick={() => onOpenJob(job)}>进入岗位图谱</button>
          </article>
        ))}
      </div>
      {filteredJobs.length === 0 ? <div className="catalog-empty">没有匹配的岗位</div> : null}
    </main>
  );
}

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
