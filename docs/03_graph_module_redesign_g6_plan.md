# 图谱模块重构方案：能力图谱与职业图谱

版本：v1.0

日期：2026-07-19

目标：保留原始岗位与 JD 数据，将当前“岗位—技能星状图”升级为能力本体图谱和职业关联图谱，并将前端渲染器从 Cytoscape.js 迁移到 AntV G6 5.1。

## 1. 需求理解

### 1.1 能力图谱

能力图谱回答“具身智能行业需要哪些能力，这些能力如何从宏观方向逐级细化”。

~~~text
具身智能（L0 根）
└── 一级能力 L1（6个能力方向）
    └── 二级能力 L2（如软件开发）
        └── 三级能力 L3（如 C++ 开发）
            ├── 同义/缩写/拼写别名
            └── 技术版本或变体（C++17、C++20、C++21）
~~~

六个一级能力方向建议与人才图谱保持可解释映射，但使用“能力”命名：

1. 战略与经营管理能力
2. 研究、设计与算法能力
3. 工程开发与实现能力
4. 测试、生产与供应链能力
5. 商业化、服务与支持能力
6. 职能支撑能力

第六项不建议只命名为“人员管理能力”，因为参考人才图谱还包含财务、法务、合规、知识产权、IT 支持和数据安全等能力。

别名需要区分语义：C++ Programming 可以是 C++ 开发的同义别名；C++17、C++21 并非完全等价的别名，而是版本变体，应使用 VARIANT_OF 关系，否则后续无法分析技术版本需求变化。

### 1.2 职业图谱

职业图谱回答“一个职业需要哪些能力、哪些职业相似、职业群如何形成”。

- 标准职业是核心节点。
- 三级能力是职业的子核心节点。
- 职业之间用可解释的 SIMILAR_TO 关系连接。
- 6个一级职业方向和18个二级职业分类用于组合分区。
- 相似岗位名称归并为职业别名，不与标准职业并列计算。
- 点击职业后只展开该职业的核心能力、相似职业和证据，避免全量岗位—能力二部图形成“毛线团”。

职业领域应提供两种模式：

1. **标准分类模式**：严格按人才图谱既有6个一级、18个二级分类展示，适合解释和汇报。
2. **数据发现模式**：根据能力相似网络运行 Louvain/Leiden 等社区发现，观察数据是否形成不同职业群；结果只作为分析建议，不自动覆盖标准分类。

“固定六大方向”和“根据密度自动分群”不能混为一个结论。系统应将标准分类与数据聚类并列比较，并突出跨分类高相似职业。

## 2. 当前数据库适配性

### 2.1 可复用部分

| 当前结构 | 数据量 | 结论 | 用途 |
|---|---:|---|---|
| job_positions | 106 | 基本适配 | 标准职业节点 |
| job_categories | 130 | 高度适配 | 6个 L1、18个 L2、106个 L3 职业分类 |
| job_category_memberships | 106 | 适配 | 职业归属关系 |
| job_aliases | 66 | 部分适配 | 职业别名，需要增加别名类型和审核状态 |
| raw_jd_documents | 3,322 | 适配 | 关系证据与能力抽取来源 |
| job_skill_evidence | 1,594 | 适配 | 岗位—能力关系证据基础 |
| graph_snapshots 及版本表 | 1个基线 | 适配 | 图谱版本与动态演化 |

现有职业分类已经具备参考图片中的6×3结构，因此职业侧不需要推倒重建。

### 2.2 不适配或不足

| 问题 | 当前实际情况 | 影响 |
|---|---|---|
| 能力本体缺失 | skill_categories 只有1个根节点和5个技能类型节点 | 无法展示 L0→L1→L2→L3 能力树 |
| 原始技能与规范能力混用 | skills 同时承担抽取词和规范节点 | 同义词、版本、噪声无法正确归并 |
| 能力别名缺失 | 没有能力 alias 表 | C++、CPP、C++ Programming 无法统一 |
| 技术变体关系缺失 | 没有 VARIANT_OF 等关系 | C++17/C++21 会被错误当同义词或无关技能 |
| 能力类型失真 | 136个技能全部为 hard_skill | 通用能力、工具、领域知识无法区分 |
| 关系权重无区分 | 1,594条关系全部 required，weight=0.8，confidence=0.8 | 无法支持可靠排名和相似度 |
| 岗位画像覆盖不足 | 106个岗位中仅27个有技能关系，79个为空 | 全职业网络存在大量孤点 |
| 职业相似度缺失 | 没有相似度表、算法版本和解释字段 | 前端无法稳定呈现职业关联 |
| 别名覆盖不足 | 66条别名仅覆盖22个岗位 | 原始 JD 标题仍可能形成错误映射 |

当前27个有画像的岗位平均关联59项技能，多个通用词几乎关联全部岗位。使用当前等权数据计算时，351对岗位组合全部达到0.3以上相似度，因此现数据不适合直接生成职业相似网络。

### 2.3 重构结论

数据库“部分适配，能力侧需要增量重构”。继续采用 SQLite 作为事实库与 MVP 图数据源，执行 v3 加法迁移；保留 skills 作为“原始技能提及/旧技能实体”，通过映射表接入新的规范能力本体，不修改或删除原数据。

## 3. v3 目标数据模型

~~~mermaid
erDiagram
    CAPABILITY_NODES ||--o{ CAPABILITY_NODES : parent
    CAPABILITY_NODES ||--o{ CAPABILITY_ALIASES : has
    CAPABILITY_NODES ||--o{ CAPABILITY_RELATIONS : source
    CAPABILITY_NODES ||--o{ CAPABILITY_RELATIONS : target
    SKILLS ||--o{ SKILL_CAPABILITY_MAPPINGS : normalized_to
    CAPABILITY_NODES ||--o{ SKILL_CAPABILITY_MAPPINGS : canonical
    JOB_POSITIONS ||--o{ JOB_CAPABILITY_PROFILES : requires
    CAPABILITY_NODES ||--o{ JOB_CAPABILITY_PROFILES : capability
    JOB_POSITIONS ||--o{ JOB_SIMILARITIES : job_a
    JOB_POSITIONS ||--o{ JOB_SIMILARITIES : job_b
    GRAPH_SNAPSHOTS ||--o{ JOB_CAPABILITY_PROFILES : versions
    GRAPH_SNAPSHOTS ||--o{ JOB_SIMILARITIES : versions
~~~

### 3.1 capability_nodes

规范能力本体节点。

- id、capability_code、capability_name、capability_name_en
- parent_id
- level：0/1/2/3
- node_kind：root/domain/category/capability/variant
- description、sort_order、status
- source_type、confidence、review_status
- valid_from、valid_to、version

普通能力节点只允许一个主父节点，保证主图是一棵稳定树；跨域关系放入 capability_relations。

### 3.2 capability_aliases

能力规范化词典。

- capability_id、alias_name、normalized_alias
- alias_type：synonym/abbreviation/spelling/translation/legacy_label
- source、usage_frequency、confidence、review_status

### 3.3 capability_relations

承载非树状语义关系。

- source_capability_id、target_capability_id
- relation_type：VARIANT_OF/PREREQUISITE_OF/RELATED_TO/BROADER_THAN
- weight、confidence、evidence_count、review_status

例如 C++17 VARIANT_OF C++开发。

### 3.4 skill_capability_mappings

连接旧 skills 与新规范能力节点，使迁移可追溯。

- skill_id、capability_id
- mapping_type：exact/broader/narrower/related/variant
- method：rule/dictionary/embedding/llm/manual
- confidence、review_status、reviewed_by

### 3.5 job_capability_profiles

替代前端直接使用旧 job_skill_mapping，成为职业图谱的规范关系。

- snapshot_id、job_id、capability_id
- importance、proficiency_required
- frequency、jd_count、source_count
- weight、confidence、evidence_count
- calculation_version、review_status

### 3.6 job_similarities

保存可解释、可版本化的职业相似关系。

- snapshot_id、job_a_id、job_b_id
- score_total
- capability_cosine、core_jaccard、hierarchy_score
- shared_capability_count、coverage_a、coverage_b
- algorithm_version、threshold_version
- review_status、computed_at

另建 job_similarity_explanations 保存每条相似边贡献最大的共享能力及贡献值，前端点击边时可解释“为什么相似”。

### 3.7 可选结构

- career_aliases_v3：增强旧岗位别名，增加 alias_type、normalized_alias、confidence、review_status。
- graph_layout_cache：按 snapshot、graph_type、filter_hash 保存稳定坐标，避免力导向图每次打开都重新洗牌。
- career_communities：保存数据发现模式的社区结果，不覆盖标准职业分类。

## 4. 数据加工与相似度

### 4.1 能力本体构建

1. 人工建立 L0、6个 L1 和候选 L2 骨架。
2. 将136个旧技能作为原始词项执行清洗、合并和层级归属。
3. 用词典规则处理缩写、语言和拼写变体。
4. 用向量/LLM生成候选映射，但只写入 pending，不直接成为已审核事实。
5. 对 C++17/C++21 等版本使用 VARIANT_OF，不写为同义别名。
6. 依据 JD 证据重新计算岗位—能力频率、重要性、权重和置信度。
7. 对79个无画像岗位标记 insufficient_evidence；没有证据时不通过分类模板凭空补齐能力。

### 4.2 职业相似度

每个岗位形成以 L3 规范能力为维度的向量。

~~~text
ability_weight =
  importance_multiplier
  × log(1 + supporting_jd_count)
  × IDF(capability)
  × evidence_confidence
~~~

- required/preferred/optional 初始乘数可取 1.0/0.65/0.35。
- IDF 下调“沟通能力、团队协作”等全行业通用能力的影响。
- 能力画像覆盖不足的岗位不生成高置信相似边。

总相似度初始公式：

~~~text
score = 0.70 × weighted_cosine(L3能力)
      + 0.20 × weighted_jaccard(核心能力)
      + 0.10 × hierarchy_proximity(L2能力方向)
~~~

公式必须带 algorithm_version，后续在评估集上调权。前端默认每个职业只保留 Top-K（建议3～5）且超过阈值的边，不能呈现全连接图。

## 5. G6 技术路线

官方文档当前为 G6 5.1.1。G6 提供节点、边、Combo、树布局、力导向布局、展开收起、选择/聚焦、图例、缩略图和大图视口优化，适合本次重构。

### 5.1 能力图谱

图类型：根节点明确的有序树。

- 主布局：mindmap 或 compact-box，从左到右展示 L0→L3，中文长标签保持水平。
- 备选布局：radial，只用于宏观展示各层与根节点距离。
- 边：树边使用直线或平滑折线；VARIANT_OF/RELATED_TO 在选择节点后按需显示。
- 交互：collapse-expand、click-select、focus-element、zoom-canvas、drag-canvas。
- 稳定性：固定 L1/L2 排序，展开分支时保持其他分支位置。

G6 官方不推荐树图与 Combo 混用，因此能力树不使用 Combo；能力方向通过节点颜色、分支底色和面包屑表达。

### 5.2 职业图谱

图类型：带标准分组的无向相似网络，并在选择职业时展开职业—能力邻域。

主布局：combo-combined。

- 外层：6个 L1 职业方向作为外层 Combo。
- 内层：18个 L2 职业分类作为嵌套 Combo。
- Combo 内：职业节点使用 grid/concentric。
- Combo 间：使用 force 布局，由 Top-K 相似边产生拉力。

备选布局：force-atlas2 + Hull/BubbleSets，用于数据发现模式，让社区形态由数据产生。

- 相似度映射线宽与透明度，不只使用颜色。
- 点击相似边显示共享能力与分数组成。
- 默认只显示职业—职业 Top-K 边；职业—能力边仅在选中职业后展开。
- 布局结束后缓存坐标；筛选只做局部更新。

### 5.3 React 集成

- 锁定 @antv/g6 5.1.x，不使用 G6 4.x 的 changeData 等旧 API。
- React 负责页面、筛选器、URL 状态和详情面板；G6 实例独占 Canvas 生命周期。
- 在 useEffect 中创建 Graph，通过 ref 保存，清理函数必须 graph.destroy()，适配 React StrictMode。
- 数据更新使用 G6 5.x 的 setData/updateData 后 render/draw，不销毁并重建整个图。
- 建立 GraphAdapter，将后端领域 DTO 转为 G6 的 nodes/edges/combos，避免 G6 字段渗透进数据库模型。

### 5.4 三个学习性 Spike

1. **能力树 Spike**：30～50节点，验证4层树、展开收起、面包屑、搜索定位和中文长标签。
2. **职业网络 Spike**：106职业、6/18嵌套 Combo、Top-K 相似边、职业点击展开能力。
3. **性能 Spike**：500节点/2,000边压力数据，测试 Web Worker、optimize-viewport-transform、标签分级和移动端操作。

官方资料：

- [G6 介绍](https://g6.antv.antgroup.com/en/manual/introduction/)
- [布局总览](https://g6.antv.antgroup.com/en/manual/layout/overview)
- [ComboCombined](https://g6.antv.antgroup.com/manual/layout/combo-combined-layout)
- [展开/收起](https://g6.antv.antgroup.com/manual/behavior/collapse-expand)
- [React 集成](https://g6.antv.antgroup.com/manual/getting-started/integration/react)
- [数据 API](https://g6.antv.antgroup.com/en/manual/data)
- [交互总览](https://g6.antv.antgroup.com/en/manual/behavior/overview)
- [插件总览](https://g6.antv.antgroup.com/en/manual/plugin/overview)
- [G6 GitHub](https://github.com/antvis/G6)

## 6. 后端接口修改

不再让一个通用 neighborhood 接口承担两种图谱语义。

### 6.1 能力图谱

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /api/v1/capability-graph/tree | 获取指定根、深度和分支的能力树 |
| GET | /api/v1/capabilities/{id} | 能力详情、父路径、统计与审核状态 |
| GET | /api/v1/capabilities/{id}/aliases | 同义词、缩写、翻译别名 |
| GET | /api/v1/capabilities/{id}/relations | 变体、前置和相关能力 |
| GET | /api/v1/capabilities/{id}/jobs | 要求该能力的职业列表 |
| GET | /api/v1/capabilities/search | 按标准名称和别名搜索定位 |

### 6.2 职业图谱

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /api/v1/career-graph/overview | 返回职业节点、标准分类 Combo 和 Top-K 相似边 |
| GET | /api/v1/career-graph/jobs/{id} | 返回职业中心、核心能力和相似职业 |
| GET | /api/v1/jobs/{id}/similarities | 相似职业排名与分数分解 |
| GET | /api/v1/job-similarities/{a}/{b} | 两职业共享能力和证据解释 |
| GET | /api/v1/career-communities | 数据发现模式的社区结果 |

### 6.3 前端 DTO

~~~json
{
  "graphType": "career",
  "snapshot": { "code": "...", "algorithmVersion": "career-sim-v1" },
  "nodes": [
    { "id": "job:39", "type": "career", "data": { "label": "...", "categoryL1": "...", "coverage": 0.82 }, "combo": "career-l2:48" }
  ],
  "edges": [
    { "id": "similar:39:41", "source": "job:39", "target": "job:41", "type": "SIMILAR_TO", "data": { "score": 0.73, "sharedCount": 12 } }
  ],
  "combos": [
    { "id": "career-l1:47", "type": "career-domain", "data": { "label": "工程开发与实现" } },
    { "id": "career-l2:48", "combo": "career-l1:47", "type": "career-category", "data": { "label": "软件与仿真开发" } }
  ],
  "meta": { "partial": false, "coverage": 0.74, "warnings": [] }
}
~~~

## 7. 前端功能

### 7.1 图谱探索页

顶部增加：能力图谱 | 职业图谱。

能力图谱阅读路径：

1. 首屏只展开 L0、6个 L1 和选中的一个 L2 分支。
2. 点击节点展开下一层，右侧显示定义、父路径、别名、相关岗位和证据。
3. 搜索别名时定位到标准能力并展开完整父路径。
4. 别名默认作为详情标签；切换“显示语义关系”后再显示别名/变体节点。

职业图谱阅读路径：

1. 首屏显示6个领域和职业分布，二级分类可折叠。
2. 点击职业进入焦点模式，只保留该职业、核心能力和 Top-K 相似职业。
3. 点击相似边显示共享能力、相似度分解和证据覆盖。
4. 支持“标准分类/数据聚类”切换。

### 7.2 URL 状态

~~~text
?graph=capability&node=capability:CPP&depth=3&relations=variant
?graph=career&job=39&mode=taxonomy&threshold=0.55&topK=4
~~~

需要保存图谱类型、选中节点、展开路径、分类/聚类模式、阈值、Top-K、筛选项和快照版本。返回键应恢复上一图状态。

### 7.3 移动端

- 能力图谱默认单分支逐级阅读，不把整棵树缩小塞入屏幕。
- 职业图谱默认职业焦点邻域，不显示完整106职业网络。
- 点击区域至少44px，重要信息不依赖 hover。
- 底部抽屉显示详情和证据；双指缩放归 G6，页面滚动与画布手势明确分工。

## 8. 最终实施计划

### 阶段0：规则冻结与样例集（1～2天）

- 确认6个一级能力方向及 L2/L3 命名规则。
- 选取10个代表岗位和30～50个能力作为金标样例。
- 明确别名与技术变体判定规则。

验收：输出能力本体样例、职业分类样例和人工认可的相似职业对。

### 阶段1：数据库 v3 与能力本体（3～5天）

- 新增 v3 表、约束、索引和只读视图。
- 建立 L0/L1/L2 能力骨架。
- 将136个旧技能映射到规范能力或待审核队列。
- 扩展职业别名覆盖与类型。

验收：原始表哈希不变；能力树无环、层级合法；每个映射可追溯。

### 阶段2：画像重算与职业相似度（3～5天）

- 从 JD 证据重新计算岗位能力频率、importance、weight、confidence。
- 实现 IDF 降权和相似度分解。
- 生成 Top-K 相似边、解释贡献和覆盖度。
- 实现标准分类与社区发现对照。

验收：金标相似岗位 Top-K 命中率达到约定指标；低覆盖岗位明确提示。

### 阶段3：后端 API（2～3天）

- 实现能力树、能力详情、职业总览、职业焦点、相似度解释接口。
- 更新 OpenAPI、缓存策略、参数上限和错误码。
- 增加树无环、DTO、相似度对称性、Top-K 和证据回溯测试。

验收：接口测试通过；所有边都有算法版本或事实证据。

### 阶段4：G6 前端替换（4～6天）

- 建立 G6 renderer/adapter，移除 Cytoscape 运行依赖。
- 完成能力图谱树布局、展开收起和搜索定位。
- 完成职业图谱 ComboCombined、焦点邻域和相似边解释。
- 接入 URL 状态、详情面板、加载/部分数据/空状态。

验收：两类图谱核心流程完成；布局稳定；控制台无错；桌面与移动可用。

### 阶段5：性能、可用性与竞赛展示（2～3天）

- 500节点/2,000边压力测试和 Worker 验证。
- 键盘操作、色弱冗余编码、触控命中和 reduced-motion 检查。
- 制作“标准分类 vs 数据聚类”“两个职业为何相似”的比赛讲解场景。
- 输出桌面/移动验收截图和演示脚本。

## 9. 风险控制

| 风险 | 控制措施 |
|---|---|
| 能力分类靠模型自动生成而不稳定 | 本体骨架人工冻结，自动映射进入审核队列 |
| 高通用技能导致所有职业相似 | IDF 降权、核心能力 Jaccard、Top-K 和覆盖阈值 |
| 79个岗位无能力画像 | 明确低覆盖状态，优先补证据，不用模板伪造 |
| 全量图过密 | 总览聚合、点击展开、边阈值、Top-K、移动端焦点邻域 |
| 力导向每次位置变化 | 固定分类约束、稳定排序、坐标缓存、局部更新 |
| G6 版本 API 混用 | 锁定5.1.x并按5.x数据 API 开发 |
| Combo 与树布局冲突 | 能力树不用 Combo；Combo 仅用于职业网络 |

## 10. 推荐开发顺序

~~~text
能力本体和别名规则
→ v3 数据库
→ 岗位能力画像重算
→ 职业相似度验证
→ 新后端 DTO/API
→ G6 两个 Spike
→ 正式替换前端渲染器
~~~

第一个开发里程碑应是“数据库 v3 + 能力树 API + G6 能力树 Spike”。它能最早验证本体结构、数据契约和 G6 交互，同时不会被尚未成熟的职业相似度算法阻塞。
