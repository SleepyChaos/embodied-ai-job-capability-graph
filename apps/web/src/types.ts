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

export type AppSection = "graph" | "matcher" | "data" | "evidence";
export type GraphKind = "capability" | "career";

export type DataTableSummary = {
  name: string;
  displayName: string;
  description: string;
  group: string;
  rowCount: number;
  columnCount: number;
  foreignKeyCount: number;
};

export type DataOverviewPayload = {
  database: { fileName: string; schemaVersion: string | null; fileSizeBytes: number };
  summary: { tableCount: number; nonEmptyTableCount: number; totalRows: number; relationshipCount: number };
  groups: { name: string; tables: string[] }[];
  tables: DataTableSummary[];
};

export type DataForeignKey = {
  id: number;
  sequence: number;
  table: string;
  column: string | null;
  from: string;
  onUpdate: string;
  onDelete: string;
};

export type DataColumn = {
  position: number;
  name: string;
  description: string;
  declaredType: string;
  typeCategory: "integer" | "text" | "blob" | "real" | "numeric";
  nullable: boolean;
  defaultValue: string | null;
  primaryKeyPosition: number | null;
  unique: boolean;
  foreignKeys: DataForeignKey[];
};

export type DatabaseValue = string | number | boolean | null | { kind: "blob"; bytes: number };

export type DataTableDetail = {
  table: DataTableSummary;
  columns: DataColumn[];
  foreignKeys: DataForeignKey[];
  incomingReferences: { table: string; column: string; targetColumn: string | null }[];
  indexes: { name: string; unique: boolean; origin: string; partial: boolean; columns: string[] }[];
  rows: Record<string, DatabaseValue>[];
  page: { page: number; pageSize: number; total: number };
};

export type GovernanceQueueKind = "capabilities" | "categories" | "normalizations";

export type GovernanceSummary = {
  capability_count: number;
  category_count: number;
  normalization_count: number;
  active_capability_count: number;
  active_alias_count: number;
  completed_run_count: number;
};

export type CapabilityEvidenceDetail = {
  id: number;
  mention_id: number;
  evidence_text: string;
  evidence_section: string;
  source_field: "job_title" | "jd_description" | "other_info" | "combined_text";
  start_offset: number;
  end_offset: number;
  ordinal: number;
  is_primary: 0 | 1;
  source_hash: string;
};

export type CapabilityCandidate = {
  id: number;
  proposed_name: string;
  normalized_name: string;
  description: string;
  category_code: string | null;
  category_name: string | null;
  direction_code: string | null;
  direction_name: string | null;
  career_unit_id: number;
  job_title: string;
  surface_name: string;
  evidence_text: string;
  evidence_section: string;
  evidence_details: CapabilityEvidenceDetail[];
  requirement_level: string;
  extraction_confidence: number;
  classification_confidence: number;
  suggested_capability_id: number | null;
  suggested_capability_name: string | null;
  suggested_capability_description: string | null;
  suggested_relation: "same" | "broader" | "narrower" | "related" | "different" | null;
  suggested_confidence: number | null;
  suggested_reasoning: string | null;
};

export type ActiveCapability = {
  id: number;
  name: string;
  description: string | null;
  category_id: number;
  category_code: string;
  category_name: string;
  direction_code: string;
  direction_name: string;
  aliases: string | null;
};

export type CategoryCandidate = {
  id: number;
  proposed_name: string;
  proposed_description: string;
  direction_code: string;
  direction_name: string;
  confidence: number;
  career_unit_id: number;
  job_title: string;
};

export type NormalizationCandidate = {
  id: number;
  surface_name: string;
  proposed_canonical_name: string;
  description: string;
  evidence_text: string;
  evidence_section: string;
  evidence_details: CapabilityEvidenceDetail[];
  requirement_level: string;
  career_unit_id: number;
  job_title: string;
  candidate_capability_id: number;
  candidate_capability_name: string;
  candidate_capability_description: string;
  relation: "same" | "broader" | "narrower" | "related" | "different" | "uncertain";
  confidence: number;
  reasoning: string;
};

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
  meta: {
    partial: boolean;
    stale: boolean;
    coverage: number;
    warnings: string[];
    live?: boolean;
    focusNodeId?: string;
  };
};

export type CapabilityGraphDetail = {
  id: number;
  name: string;
  description: string;
  path: { code: string; name: string }[];
  aliases: { id: number; name: string; type: string; confidence: number }[];
  jobs: {
    id: number;
    title: string;
    company: string | null;
    confidence: number;
    evidence: string | null;
    matchedAliases: string[];
    extractionMethods: string[];
  }[];
};

export type CareerGraphJobDetail = {
  id: number;
  title: string;
  city: string;
  salary: string;
  experience: string;
  education: string;
  description: string;
  url: string;
  processed: boolean;
  company: { id: number | null; name: string | null; jobCount: number };
  capabilities: {
    id: number;
    name: string;
    description: string;
    category: string;
    direction: string;
    confidence: number;
    aliases: string[];
    evidence: string[];
  }[];
};

export type CareerGraphDirectory = {
  at: string;
  items: GraphNodeV2[];
  metrics: Record<string, number>;
};

export type CareerSpectrumDirection = {
  id: number;
  code: string;
  name: string;
  sortOrder: number;
  count: number;
  color: string;
};

export type CareerSpectrumJob = {
  id: number;
  title: string;
  companyId: number | null;
  company: string | null;
  city: string;
  salary: string;
  experience: string;
  education: string;
  capabilityCount: number;
  averageConfidence: number;
  directionId: number;
  directionCode: string;
  directionName: string;
  directionOrder: number;
  subDirectionId: number;
  subDirectionCode: string;
  subDirectionName: string;
  color: string;
  classificationSource: string;
};

export type CareerSpectrumPayload = {
  snapshot: {
    name: string;
    at: string;
    metrics: Record<string, number>;
  };
  directions: CareerSpectrumDirection[];
  jobs: CareerSpectrumJob[];
  meta: {
    live: boolean;
    classificationSource: string;
    warnings: string[];
  };
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
