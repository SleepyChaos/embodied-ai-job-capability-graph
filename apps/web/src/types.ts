// === Data Overview Types ===

export type TableSummary = {
  name: string;
  display_name: string;
  description: string;
  row_count: number;
  group: string;
  group_label: string;
};

export type ColumnInfo = {
  name: string;
  type: string;
  notnull: boolean;
  pk: boolean;
  description: string;
};

export type TableDetail = {
  name: string;
  display_name: string;
  description: string;
  row_count: number;
  group: string;
  group_label: string;
  columns: ColumnInfo[];
  data: Record<string, unknown>[];
  page: { page: number; pageSize: number; total: number };
};

export type DatabaseStats = {
  total_tables: number;
  total_records: number;
  groups: { group: string; label: string; table_count: number; record_count: number }[];
};

// === Import Types ===

export type ImportResult = {
  total_rows: number;
  imported: number;
  skipped: number;
  failed: number;
  new_capabilities_created: number;
  new_aliases_created: number;
  details: ImportDetail[];
};

export type ImportDetail = {
  row: number;
  company: string;
  position: string;
  status: "imported" | "skipped" | "failed";
  capabilities_extracted: number;
  message: string;
};

export type ImportHistoryItem = {
  id: number;
  filename: string;
  imported_at: string;
  total_rows: number;
  imported: number;
  skipped: number;
  failed: number;
  status: "completed" | "partial" | "failed";
};

// === Career Types ===

export type CareerDirection = {
  id: number;
  code: string;
  name: string;
  sort_order: number;
};

export type CareerSubDirection = {
  id: number;
  direction_id: number;
  code: string;
  name: string;
  sort_order: number;
  direction?: CareerDirection;
};

export type CareerUnit = {
  id: number;
  sub_direction_id: number;
  company_id: number | null;
  position_name: string;
  city: string | null;
  salary: string | null;
  experience: string | null;
  education: string | null;
  url: string | null;
  jd_description: string | null;
  data_source: string | null;
  source_platform: string | null;
  collected_at: string | null;
  sub_direction?: CareerSubDirection;
  company?: { id: number; name: string } | null;
  capability_count: number;
};

// === Capability Types ===

export type CapabilityDirection = {
  id: number;
  code: string;
  name: string;
  sort_order: number;
};

export type CapabilityCategory = {
  id: number;
  direction_id: number;
  code: string;
  name: string;
  sort_order: number;
};

export type Capability = {
  id: number;
  category_id: number;
  name: string;
  description: string | null;
  aliases: CapabilityAlias[];
};

export type CapabilityAlias = {
  id: number;
  capability_id: number;
  alias: string;
  alias_type: string;
};

// === Company Types ===

export type Company = {
  id: number;
  name: string;
  website: string | null;
  industry: string | null;
  description: string | null;
  liepin_url: string | null;
};

// === Common Types ===

export type Page<T> = {
  items: T[];
  page: { page: number; pageSize: number; total: number };
};

export type AppSection = "overview" | "import";
