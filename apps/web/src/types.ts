export type ViewMode = "job" | "overview";

export type GraphNode = {
  key: string;
  type: "JobCategory" | "Job" | "SkillCategory" | "Skill" | "Company" | "DataSource";
  label: string;
  properties: Record<string, unknown>;
};

export type GraphEdge = {
  key: string;
  type: string;
  source: string;
  target: string;
  properties: Record<string, unknown>;
};

export type Snapshot = {
  code: string;
  name: string;
  at: string;
  status: string;
  baseline: boolean;
  metrics: Record<string, number>;
};

export type GraphPayload = {
  snapshot: Snapshot;
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: {
    partial: boolean;
    stale: boolean;
    nodeCount: number;
    edgeCount: number;
    totalNodeCount?: number;
    totalEdgeCount?: number;
    root?: string;
    aggregation: string;
    warnings: string[];
  };
};

export type JobSummary = {
  id: number;
  key: string;
  name: string;
  code: string | null;
  categoryL1: string;
  categoryL2: string | null;
  emerging: boolean;
  skillCount: number;
  evidenceCount: number;
};

export type JobSkillRelation = {
  mappingId: number;
  jobId: number;
  skillId: number;
  skillKey: string;
  skillName: string;
  skillType: string;
  importance: "required" | "preferred" | "optional";
  proficiency: string | null;
  weight: number | null;
  confidence: number | null;
  version: number;
  evidenceCount: number;
  evidenceStatus: "verified" | "unverified" | "missing";
};

export type JobDetail = JobSummary & {
  nameEn: string | null;
  responsibilities: string | null;
  scenarios: string | null;
  jdCount: number;
  snapshot: Snapshot;
  skillGroups: Record<string, JobSkillRelation[]>;
};

export type Evidence = {
  id: number;
  mappingId: number;
  jobId: number;
  jobName: string;
  skillId: number;
  skillName: string;
  jdId: number;
  role: string;
  excerpt: string | null;
  source: string;
  company: string | null;
  rawTitle: string | null;
  url: string | null;
  fetchedAt: string | null;
  publishedAt: string | null;
  confidence: number | null;
  verified: boolean;
  extractionMethod: string;
};

export type Page<T> = {
  items: T[];
  page: { page: number; pageSize: number; total: number };
};

export type ImportanceFilter = "all" | "required" | "preferred" | "optional";

export type AppSection = "graph" | "matcher" | "jobs" | "evidence";
export type GraphKind = "capability" | "career";

export type GraphNodeV2 = {
  id: string;
  type: "capability" | "career";
  comboId?: string;
  data: {
    databaseId: number;
    label: string;
    level?: number;
    kind?: string;
    categoryL1?: string;
    categoryL2?: string;
    capabilityCount?: number;
    jdCount?: number;
    jobCount?: number;
    aliasCount?: number;
    color?: string;
    [key: string]: unknown;
  };
};

export type GraphEdgeV2 = {
  id: string;
  source: string;
  target: string;
  type: string;
  data: { score?: number; weight?: number; [key: string]: unknown };
};

export type GraphComboV2 = {
  id: string;
  type: "domain" | "category";
  parentId?: string;
  data: { label: string; color?: string };
};

export type GraphPayloadV2 = {
  schemaVersion: "2";
  graphType: GraphKind;
  snapshot: Snapshot & { id: number };
  nodes: GraphNodeV2[];
  edges: GraphEdgeV2[];
  combos: GraphComboV2[];
  meta: { partial: boolean; stale: boolean; coverage: number; warnings: string[] };
};

export type MatchCandidate = {
  id: number;
  rank: number;
  jobId: number;
  jobName: string;
  categoryL1: string;
  categoryL2: string;
  suggestion: string;
  score: number;
  coverage: number;
  components: Record<string, number | null>;
  explanation: {
    sharedCapabilities?: string[];
    missingCapabilities?: string[];
    newCapabilities?: string[];
  };
};

export type VectorizationRun = {
  id: number;
  source: string;
  status: "queued" | "running" | "succeeded" | "partial" | "failed" | "cancelled";
  progress: number;
  semanticAvailable: boolean;
  capabilityCount: number;
  candidateCount: number;
  model: { code: string; name: string; revision: string; dimensions: number };
  warnings: string[];
  error: string | null;
  resultSummary: {
    domainVector: { id: number; name: string; weight: number }[];
    topCapabilities: { id: number; name: string; weight: number }[];
    evidenceCount: number;
  } | null;
  candidates: MatchCandidate[];
  decision: Record<string, unknown> | null;
};
