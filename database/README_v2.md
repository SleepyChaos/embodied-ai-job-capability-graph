# 岗位能力图谱数据库 v2

## 改造原则

`embodied_ai_jobs.db` 是只读基线，未被修改。`embodied_ai_jobs_v2.db` 由 SQLite 备份 API 复制后执行增量迁移得到。

v2 保留以下旧表的全部字段与数据：

- `data_sources`
- `raw_jd_documents`
- `job_positions`
- `job_aliases`
- `skill_taxonomy`
- `skills`
- `job_skill_mapping`

迁移验证对以上表按 `rowid` 顺序逐值计算 SHA-256 摘要，而不只比较行数。

## v2 新增能力

| 能力 | 主要表 |
|---|---|
| 采集批次与导入审计 | `ingestion_batches`, `jd_batch_memberships` |
| 企业规范化 | `companies`, `jd_company_links` |
| 正确命名的岗位分类 | `job_categories`, `job_category_memberships` |
| 独立技能分类 | `skill_categories`, `skill_category_memberships` |
| 不可变图谱快照 | `graph_snapshots`, `job_definition_versions`, `skill_definition_versions` |
| 关系证据溯源 | `job_skill_evidence` |
| 快照关系 | `graph_snapshot_job_skills` |
| 演化事件 | `change_events` |
| 人工审核 | `manual_review_tasks` |
| 图数据库同步 | `graph_sync_runs` |

兼容视图：

- `v_job_skill_current`：每个岗位—技能对的当前有效版本。
- `v_job_skill_evidence_detail`：关系、JD、企业、来源和证据的联查视图。
- `v_graph_nodes`、`v_graph_edges`：图谱导出和 API 的数据库无关读模型。

## 当前基线快照

迁移建立 `baseline-v1`，只表达旧数据库当时的状态，不声称数据已经经过多源或人工验证。

当前派生结果：

- 130 个岗位分类节点，106 个岗位分类归属。
- 6 个技能分类节点，136 个技能分类归属。
- 1,594 条规范化关系证据。
- 1,594 条基线快照岗位—技能边。
- 图谱兼容视图共 421 个节点、2,475 条边。

## 运行

首次迁移：

```powershell
python scripts/migrate_database_v2.py `
  --source embodied_ai_jobs.db `
  --target embodied_ai_jobs_v2.db `
  --migration database/migrations/001_additive_v2_schema.sql `
  --report database/v2_migration_report.json
```

迁移脚本拒绝覆盖已经存在的目标数据库。

独立验证：

```powershell
python scripts/verify_database_v2.py `
  --source embodied_ai_jobs.db `
  --target embodied_ai_jobs_v2.db `
  --report database/v2_verification_report.json
```

## 连接约定

SQLite 的外键启用状态属于连接级配置。所有应用连接必须首先执行：

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

写事务推荐使用 WAL 模式；离线评审或只读演示不强制修改数据库日志模式。

旧表 `skill_taxonomy` 实际保存岗位层级，v2 不删除或重命名它，以免破坏兼容性；新代码应读取 `job_categories` 和 `skill_categories`。
