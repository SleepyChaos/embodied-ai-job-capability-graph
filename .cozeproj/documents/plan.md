# 数据库 v5 三库分离重构计划

## 概述

将现有 SQLite v4 单体数据库重构为 PostgreSQL（Supabase）三库分离架构：**职业数据库**（6 方向 → 子方向 → 职业组 → 职业单元/JD 条目）、**能力数据库**（6 方向 → 能力分类 → 能力节点 + 别名）、**企业数据库**（轻量企业信息）。每条 JD 条目（职业单元）存储 xlsx 全字段、语义向量、企业外键和多对多能力别名关联。导入 xlsx 时通过 LLM 自动提取能力要求并匹配/新建能力节点。前端 DataOverview 模块适配新表结构，图谱可视化重新设计。

## 技术方案

| 维度 | 选择 | 理由 |
|------|------|------|
| 数据库引擎 | Supabase (PostgreSQL) | 用户要求 PostgreSQL；pgvector 原生支持语义向量检索；Supabase 提供托管实例 |
| Schema 版本管理 | SQL 迁移文件 + Git | 所有 DDL/DML 脚本存储在 `database/migrations/` 目录，通过 GitHub 追踪变更 |
| 后端框架 | FastAPI (Python) | 沿用现有技术栈，改为 psycopg2/asyncpg 连接 PostgreSQL |
| 能力提取 | LLM 自动提取 + 向量匹配 | 导入 xlsx 时调用 LLM 从 JD 描述中抽取能力，embedding 匹配已有能力或自动新建 |
| 语义向量 | pgvector 扩展 | 利用 PostgreSQL 原生向量类型和余弦相似度索引，替代 SQLite BLOB 方案 |
| 前端框架 | Vite + React + TypeScript | 沿用现有技术栈 |
| 图谱可视化 | AntV G6 | 沿用现有组件，适配新数据结构 |

## 功能模块

### 1. 职业数据库 (Career Database)

按 6 大方向组织，3 层分类 + 叶节点（职业单元 = JD 条目）。

```
6 大方向（与图片一致）
├─ 1. 战略与经营管理
├─ 2. 研究、设计与算法
├─ 3. 工程开发与实现
├─ 4. 测试、生产与供应链
├─ 5. 商业化、服务与支持
└─ 6. 职能支撑平台
```

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| `career_directions` | 6 大方向 | `id`, `code`, `name`, `sort_order` |
| `career_sub_directions` | 二级方向 (如 4.1, 4.2) | `id`, `direction_id` FK, `code`, `name`, `sort_order` |
| `career_groups` | 三级职业组 (可选层) | `id`, `sub_direction_id` FK, `name`, `sort_order` |
| `career_units` | 叶节点 = JD 条目 | 见下方字段详表 |

**career_units 字段详表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PK | 主键 |
| `group_id` | FK → career_groups | 所属职业组（可空，直接挂子方向时为空） |
| `sub_direction_id` | FK → career_sub_directions | 所属子方向（冗余，便于查询） |
| `enterprise_id` | FK → enterprises | 所属企业 |
| `job_title` | TEXT NOT NULL | 岗位名称 |
| `city` | TEXT | 城市 |
| `salary` | TEXT | 薪资 |
| `experience` | TEXT | 经验要求 |
| `education` | TEXT | 学历要求 |
| `jd_url` | TEXT | 岗位链接 |
| `company_career_url` | TEXT | 公司招聘页 |
| `collected_at` | DATE | 收录时间 |
| `jd_description` | TEXT | JD 完整描述 |
| `data_source` | TEXT | 数据来源标识 |
| `other_info` | TEXT | 其他信息 |
| `detail_status` | TEXT | 详情页采集状态 |
| `detail_title` | TEXT | 详情页标题 |
| `recruitment_count` | INTEGER | 招聘人数 |
| `keywords` | TEXT | 关键词 |
| `region` | TEXT | 地区 |
| `source_platform` | TEXT | 来源平台 |
| `capability_requirements_text` | TEXT | LLM 提取的能力要求原文 |
| `semantic_vector` | vector(1536) | JD 综合语义向量 (pgvector) |
| `created_at` / `updated_at` | TIMESTAMPTZ | 时间戳 |

### 2. 能力数据库 (Ability Database)

同样按 6 大方向组织，2 层分类 + 叶节点（能力节点 + 别名）。

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| `ability_directions` | 6 大能力方向 | `id`, `code`, `name`, `sort_order` |
| `ability_categories` | 二级能力分类 | `id`, `direction_id` FK, `code`, `name`, `parent_id` (自引用支持多层), `sort_order` |
| `ability_nodes` | 底层能力节点 | `id`, `category_id` FK, `name`, `name_en`, `description`, `source_type`, `confidence`, `review_status`, `status` |
| `ability_aliases` | 能力别名 | `id`, `ability_node_id` FK, `alias_name`, `normalized_alias`, `alias_type` |
| `ability_relations` | 能力间关系 | `id`, `source_id` FK, `target_id` FK, `relation_type`, `weight` |

### 3. 企业数据库 (Enterprise Database)

轻量设计，保证职业条目可正确索引。

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| `enterprises` | 企业基本信息 | `id`, `name`, `normalized_name` UNIQUE, `display_name`, `industry`, `website`, `city`, `description`, `created_at` |

### 4. 关联表

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| `career_unit_abilities` | 职业单元 ↔ 能力别名 多对多 | `career_unit_id` FK, `ability_alias_id` FK, `evidence_text`, `importance`, `extraction_method` |

### 5. 辅助表

| 表名 | 职责 |
|------|------|
| `schema_migrations` | 迁移版本追踪 |
| `data_import_batches` | xlsx 导入批次记录 |
| `embedding_models` | 向量模型版本与状态 |

## 是否有原型设计

是（设计引导工具已开启，需先完成 DataOverview 适配原型）

## 实施步骤

### 阶段一：原型设计

加载 `design-canvas` 技能，为 DataOverview 数据展示模块设计原型 HTML。重点展示三库分离后的表结构浏览、数据预览和分类导航。原型完成后提示用户确认，确认后进入开发阶段。

涉及文件：原型 HTML 输出到 `.cozeproj/prototype/web/` 目录。

### 阶段二：代码开发

**步骤 1：Supabase 集成与数据库 Schema 创建**

加载 Supabase 技能，创建 PostgreSQL 连接。编写 v5 迁移脚本（`database/migrations/004_v5_three_db_schema.sql`），包含三库全部表定义、pgvector 扩展、索引和触发器。编写种子数据脚本（`database/seeds/v5_seed_directions.sql`）预填 6 大方向和子方向。

涉及文件：`database/migrations/004_v5_three_db_schema.sql`、`database/seeds/v5_seed_directions.sql`、`apps/api/app/database.py`（改为 PostgreSQL 连接）

**步骤 2：后端 API 层重构**

重写 FastAPI 路由和数据访问层，适配新 Schema。新增三组 RESTful 端点：职业（方向/子方向/职业组/职业单元 CRUD + 分页 + 搜索）、能力（方向/分类/节点/别名 CRUD）、企业（CRUD）。保留现有 health 和 data-overview 端点结构，改为查询新表。

涉及文件：`apps/api/app/main.py`、`apps/api/app/v5_repository.py`（新建）、`apps/api/app/data_overview.py`

**步骤 3：xlsx 数据导入管道与 LLM 能力提取**

实现 xlsx 解析 → 企业创建/匹配 → 职业单元创建 → LLM 能力提取 → 能力匹配/新建 → 向量生成的完整管道。导入时自动：(1) 解析 xlsx 每行为一条 career_unit；(2) 按公司名匹配或新建 enterprise；(3) 调用 LLM 从 JD 描述提取能力要求列表；(4) 对每个提取的能力，通过向量相似度匹配已有能力节点（阈值可配），匹配成功则关联别名，否则新建能力节点+别名；(5) 生成 JD 综合语义向量存入 pgvector 字段。

> **注意**：此步骤需等待用户提供 xlsx 数据文件（文件名可能为"具身智能岗位_合并去重.xlsx"），或使用工作区中已有的 xlsx 文件。在数据文件就绪前，先完成管道代码框架和 API 端点，数据导入操作延后执行。

涉及文件：`apps/api/app/import_pipeline.py`（新建）、`scripts/import_xlsx_v5.py`（新建）

**步骤 4：前端 DataOverview 模块适配**

根据原型重构 DataOverview 组件，适配新的三库表结构。表目录按"职业数据库""能力数据库""企业数据库""关联与辅助"四组展示。Schema 视图展示 PostgreSQL 字段类型、约束和外键。数据预览视图支持分页浏览新表数据。

涉及文件：`apps/web/src/components/DataOverview.tsx`、`apps/web/src/api.ts`、`apps/web/src/types.ts`

**步骤 5：前端图谱可视化适配**

重构 GraphExplorer 和 GraphCanvas 组件，适配新的三库数据结构。能力图谱展示 ability_directions → ability_categories → ability_nodes 三层树形结构。职业图谱展示 career_directions → career_sub_directions → career_groups → career_units 层级结构，节点间通过 career_unit_abilities 关联边连接。

涉及文件：`apps/web/src/components/GraphExplorer.tsx`、`apps/web/src/components/GraphCanvas.tsx`

**步骤 6：集成测试与验证**

执行后端 API 冒烟测试（全部端点），验证 xlsx 导入管道端到端流程，检查前端数据展示和图谱渲染。

涉及文件：测试命令通过 `test_run` 执行
