# LLM 职业聚类流程

## 1. 数据边界

单条企业 JD 始终是职业数据库的最小单元。职业聚类只增加上层分组：

`单条JD → 职业簇成员关系 → 中文职业簇 → 职业子方向 → 职业方向`

聚类不会合并、删除或改写 JD，也不会把职位名称当作职业别称。

## 2. 聚类依据

只有具备已审批正式能力的 JD 才能进入职业聚类。模型按以下顺序判断：

1. 已审批能力总称、方向、分类、可信度及 JD 原文证据；
2. 岗位标题；
3. JD 职责和任职要求；
4. 现有正式职业簇及其边界描述；
5. 固定的六大职业方向和 18 个职业子方向。

## 3. 自动化规则

- 任一关键可信度低于 80%：整次重做，最多三次；
- 所有关键可信度均达到 90%：自动归入已有职业簇或创建中文职业簇；
- 没有低于 80%，但至少一项处于 80%～89.99%：进入人工审核；
- 连续三次仍低于 80%：在 `career_units` 标记职业聚类失败并保存原因；
- 正式职业簇名称必须包含中文；
- 职业簇不能跨职业子方向归并。

## 4. 数据表

- `career_clustering_runs`：模型运行、重试和原始输出审计；
- `career_cluster_candidates`：人工审核候选；
- `career_clusters`：正式职业簇；
- `career_cluster_memberships`：单条 JD 到正式职业簇的一对一主归属。

`career_units.career_clustering_status` 保存
`not_started / processing / review / succeeded / failed`，并通过
`career_clustering_failure_reason` 保存最终失败原因。

职业簇完成自动或人工批准后，系统同步将分类结果写入
`career_units.sub_direction_id`，供职业色系谱与后续图谱使用。

## 5. 接口

- `GET /api/v1/career-clustering/status`
- `POST /api/v1/career-clustering/career-units/{career_unit_id}`
- `POST /api/v1/career-clustering/batch?limit=5`
- `GET /api/v1/career-clustering/candidates`
- `GET /api/v1/career-clustering/clusters`
- `POST /api/v1/career-clustering/candidates/{candidate_id}/review`

## 6. 外部模型数据说明

运行职业聚类时会将岗位标题、JD 描述片段和已审批能力证据发送到配置的
DeepSeek API。批量实跑前应确认数据使用和外发授权；未授权时可完成迁移、
编译和本地规则测试，但不应调用外部模型。
