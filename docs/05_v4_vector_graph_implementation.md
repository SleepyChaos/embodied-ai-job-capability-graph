# v4 岗位向量与双图谱实现说明

## 已实现闭环

`embodied_ai_jobs_v4.db` 由 v3 非破坏迁移生成。招聘身份、JD 版本、能力提及、模型注册、向量任务、匹配候选、人工决定、候选能力与相似度分项均有独立表。v3 的源记录逐行保留；后续回算只在允许追加的快照、画像和相似度表中新增版本化结果。

单条或批量任务通过 `vectorization_runs` 入队。开发环境可由 FastAPI 的后台任务即时执行，部署时可关闭内联处理并运行单进程 `app.worker`。任务使用幂等键、租约、短事务与 WAL，不依赖 Redis/Celery。

能力抽取首版采用“标准三级能力 + 已审核别名”的确定性词典匹配。证据权重按角色、抽取置信度与映射置信度相乘，同一能力多次出现用概率饱和公式聚合；L3 归一化后沿能力树生成 L2/L1 向量。六大方向只用于解释，候选排序仍以 L3 为主体。

语义适配器实现了 `BAAI/bge-small-zh-v1.5` 的 512 维归一化输出和 float32 BLOB 存储。模型缺失或下载失败时，任务标记为 `partial` 并明确返回警告，能力向量、标题、核心能力 Jaccard 与属性兼容度仍可工作。

## 图谱接口

- `GET /api/v1/capability-graph/tree`
- `GET /api/v1/capabilities/{id}`
- `GET /api/v1/capabilities/{id}/relations`
- `GET /api/v1/capabilities/{id}/jobs`
- `GET /api/v1/capabilities/search`
- `GET /api/v1/career-graph/overview`
- `GET /api/v1/career-graph/jobs/{id}`
- `GET /api/v1/jobs/{id}/similarities`
- `GET /api/v1/job-similarities/{a}/{b}`
- `GET /api/v1/career-communities`

统一响应使用 `GraphPayloadV2`。React 负责 URL、筛选、选择与详情，G6 只负责布局、Canvas 和图元素交互。能力图为 LR 层级树；职业图支持标准 Combo 分类与相似社区两种布局。左侧目录是画布不可用时的等价备用入口。

## 当前数据覆盖与边界

3,322 条 JD 中有 3,296 条映射记录，但只落在 30 个不同标准职业上，因此能力回算得到 30/106 个职业画像。系统在 API 与界面中显示 28.3% 覆盖率及告警；未覆盖的 76 个职业保留分类节点，不生成虚假的能力或相似边。

本次 BGE 匿名下载在 Hugging Face 权重传输前停滞，已安全终止。数据库保留模型配置和可重试脚本 `scripts/backfill_embeddings_v4.py`；当前运行采用能力向量降级路径，匹配结果明确标为 `partial`。

## 验证结果

- v4 SQLite `integrity_check=ok`，无外键错误。
- 3,322 个招聘身份和 3,322 个当前版本，2 个重复候选。
- 21,123 条能力证据，1,386 条职业能力画像行，81 条保留相似边。
- FastAPI pytest 9 项通过。
- TypeScript 与 Vite 生产构建通过。
- v4 校验报告：`database/v4_verification_report.json`。
