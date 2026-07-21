import { useEffect, useState } from "react";

import { api } from "./api";
import { AppHeader } from "./components/AppHeader";
import { EvidenceCatalog } from "./components/CatalogPages";
import { DataOverview } from "./components/DataOverview";
import { GraphExplorer } from "./components/GraphExplorer";
import { MatcherLab } from "./components/MatcherLab";
import type { AppSection, Evidence, JobDetail, JobSummary } from "./types";

function initialSection(): AppSection {
  const value = new URLSearchParams(location.search).get("section");
  if (value === "jobs" || value === "data") return "data";
  return value === "matcher" || value === "evidence" ? value : "graph";
}

export default function App() {
  const [section, setSection] = useState<AppSection>(initialSection);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);

  useEffect(() => {
    if (section !== "evidence") return undefined;
    const controller = new AbortController();
    api.listJobs("", 100, controller.signal).then((result) => setJobs(result.items)).catch(() => setJobs([]));
    return () => controller.abort();
  }, [section]);

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
    if (section !== "data") for (const key of ["table", "tab", "page"]) params.delete(key);
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [section]);

  return <div className="app-shell">
    <AppHeader activeSection={section} onNavigate={setSection} onOpenFilters={() => undefined} />
    {section === "graph" ? <GraphExplorer /> : null}
    {section === "matcher" ? <MatcherLab /> : null}
    {section === "data" ? <DataOverview /> : null}
    {section === "evidence" ? <EvidenceCatalog jobs={jobs} selectedJobId={job?.id} evidence={evidence} onSelectJob={selectJob} /> : null}
  </div>;
}
