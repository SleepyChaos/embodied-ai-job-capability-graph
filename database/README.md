# 数据库目录

## 版本迁移

- `001_additive_v2_schema.sql`：岗位事实库和图谱 MVP 的增量结构。
- `002_capability_career_graph_v3.sql`：能力本体、职业分类、画像、相似边与快照。
- `003_vector_matching_pipeline.sql`：招聘版本、向量模型、向量任务、候选匹配和人工审核。

迁移和校验脚本位于 `scripts/`。迁移始终从源数据库复制生成新版本，不覆盖旧数据库。

## 演示数据库

`demo_v4.db` 由 `scripts/create_demo_database.py` 从本地 v4 数据库生成。它删除以下内容：

- 原始 JD、JD 能力证据和 JD 语义向量；
- 招聘身份与历史版本；
- 向量计算任务、匹配候选和人工审核记录；
- 采集批次及逐条数据关联；
- 旧版证据原文。

它保留能力本体、标准职业、聚合职业能力画像、相似关系和图谱快照，用于不接触原始采集数据的界面演示。

重新生成：

```powershell
.\apps\api\.venv\Scripts\python.exe .\scripts\create_demo_database.py `
  --source .\embodied_ai_jobs_v4.db `
  --target .\database\demo_v4.db
```

完整数据库、迁移报告中的本机路径以及原始数据文件均由 `.gitignore` 排除。
