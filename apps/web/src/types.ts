// === App Types ===

export type AppSection = "overview" | "import" | "capability-graph";

// === Data Overview Types ===

export type OverviewStats = {
  totalTables: number;
  totalRows: number;
};

export type TableSummary = {
  name: string;
  description: string;
  rowCount: number;
};

export type TableGroup = {
  key: string;
  name: string;
  tables: TableSummary[];
};

export type ColumnInfo = {
  name: string;
  type: string;
  nullable: boolean;
  primaryKey: boolean;
};

export type TableDetail = {
  name: string;
  description: string;
  columns: ColumnInfo[];
  data: Record<string, unknown>[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
};

// === Import Types ===

export type ImportResult = {
  batchId: number;
  batchCode: string;
  status: "completed" | "completed_with_errors" | "failed";
  statistics: {
    total: number;
    success: number;
    skipped: number;
    failed: number;
    capabilitiesCreated: number;
    aliasesCreated: number;
  };
  errors: string[];
};

export type ImportBatch = {
  id: number;
  batchCode: string;
  sourceFilename: string;
  status: string;
  totalCount: number;
  successCount: number;
  skipCount: number;
  failCount: number;
  capabilitiesCreated: number;
  aliasesCreated: number;
  createdAt: string;
};

// === Career Types ===

export type CareerDirection = {
  id: number;
  code: string;
  name: string;
  sortOrder: number;
  subDirections: CareerSubDirection[];
};

export type CareerSubDirection = {
  id: number;
  directionId: number;
  code: string;
  name: string;
  sortOrder: number;
};

export type CareerUnit = {
  id: number;
  subDirectionId: number;
  companyId: number | null;
  jobTitle: string;
  city: string | null;
  salary: string | null;
  experience: string | null;
  education: string | null;
  url: string | null;
  jdDescription: string | null;
  dataSource: string | null;
  sourcePlatform: string | null;
  otherInfo: string | null;
  semanticVector: unknown | null;
  createdAt: string;
  updatedAt: string;
  // Joined fields
  subDirectionName?: string;
  companyName?: string;
};

export type JobCapabilityLink = {
  id: number;
  careerUnitId: number;
  capabilityAliasId: number;
  extractionMethod: string;
  confidence: number;
  evidenceText: string | null;
  createdAt: string;
  // Joined fields
  capabilityName?: string;
  aliasName?: string;
};

// === Capability Types ===

export type CapabilityDirection = {
  id: number;
  code: string;
  name: string;
  sortOrder: number;
  categories: CapabilityCategory[];
};

export type CapabilityCategory = {
  id: number;
  directionId: number;
  code: string;
  name: string;
  sortOrder: number;
};

export type Capability = {
  id: number;
  categoryId: number;
  code: string;
  name: string;
  description: string | null;
  sortOrder: number;
  // Joined fields
  categoryName?: string;
  directionName?: string;
};

export type CapabilityAlias = {
  id: number;
  capabilityId: number;
  aliasName: string;
  normalizedAlias: string;
  aliasType: string;
  confidence: number;
};

export type CapabilityDetail = {
  id: number;
  name: string;
  code: string;
  description: string | null;
  categoryId: number;
  categoryName: string;
  directionId: number;
  directionName: string;
  aliases: CapabilityAlias[];
  jobCount: number;
};

export type CapabilityTreeNode = {
  id: string;
  name: string;
  code: string;
  level: "root" | "direction" | "category" | "capability";
  capabilityId?: number;
  children?: CapabilityTreeNode[];
};

// === Enterprise Types ===

export type Company = {
  id: number;
  name: string;
  normalizedName: string;
  displayName: string | null;
  liepinUrl: string | null;
  createdAt: string;
  updatedAt: string;
  // Computed field
  jobCount?: number;
};

// === Pagination ===

export type Pagination = {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};

export type PaginatedResponse<T> = {
  items: T[];
  pagination: Pagination;
};
