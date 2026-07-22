import { useEffect, useState } from "react";

import { api } from "./api";
import { AppHeader } from "./components/AppHeader";
import { EvidenceCatalog, JobCatalog } from "./components/CatalogPages";
import { GraphExplorer } from "./components/GraphExplorer";
import { MatcherLab } from "./components/MatcherLab";
import type { AppSection, Evidence, JobDetail, JobSummary } from "./types";

function initialSection(): AppSection {
  const value = new URLSearchParams(location.search).get("section");
  return value === "matcher" || value === "jobs" || value === "evidence" ? value : "graph";
}

export default function App() {
  const [section, setSection] = useState<AppSection>(initialSection);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    api.listJobs("", 100, controller.signal).then((result) => setJobs(result.items)).catch(() => setJobs([]));
    return () => controller.abort();
  }, []);

  const selectJob = (item: JobSummary) => {
    const controller = new AbortController();
    api.getJob(item.id, controller.signal).then(setJob).catch(() => setJob(null));
    api.listEvidence({ jobId: item.id }, controller.signal).then((result) => setEvidence(result.items)).catch(() => setEvidence([]));
  };

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    params.set("section", section);
    params.delete("view");
    if (section !== "graph") for (const key of ["graph", "node", "job", "mode", "topK", "threshold"]) params.delete(key);
    if (section !== "matcher") params.delete("run");
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [section]);

  return <div className="app-shell">
    <AppHeader activeSection={section} onNavigate={setSection} onOpenFilters={() => undefined} />
    {section === "graph" ? <GraphExplorer /> : null}
    {section === "matcher" ? <MatcherLab /> : null}
    {section === "jobs" ? <JobCatalog jobs={jobs} onOpenJob={(item) => { selectJob(item); history.replaceState(null, "", `?section=graph&graph=career&job=${item.id}`); setSection("graph"); }} /> : null}
    {section === "evidence" ? <EvidenceCatalog jobs={jobs} selectedJobId={job?.id} evidence={evidence} onSelectJob={selectJob} /> : null}
  </div>;
}
