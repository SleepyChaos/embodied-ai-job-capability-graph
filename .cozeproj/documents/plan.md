# 数据库三库重构计划

## 概述

将现有 SQLite v4 单体数据库完全重建为三库分离架构：**职业数据库**（6 方向 → 子方向 → 职业单元/JD 条目）、**能力数据库**（6 方向 → 能力分类 → 能力项 + 别名）、**企业数据库**（轻量企业信息）。每条职业单元对应 XLSX 一行 JD 数据，存储企业外键、多对多能力别名关联和综合语义向量。XLSX 导入时自动从 JD 描述中抽取能力要求并匹配/新建能力节点。前端数据总览模块适配新表结构，图谱可视化后续重构。

## 技术方案

| 维度 | 选择 | 理由 |
|------|------|------|
| 数据库引擎 | SQLite (WAL) | 沿用现有方案，轻量无外部依赖；向量用 BLOB 存储 + Python 计算余弦 |
| 后端框架 | FastAPI (Python) | 沿用现有技术栈 |
| XLSX 解析 | openpyxl | Python 生态成熟的 xlsx 解析库 |
| 能力抽取 | 词典匹配 + 向量相似度 | 复用现有 CapabilityLexicon 模式，扩展自动新建能力 |
| 语义向量 | float32 BLOB | 沿用现有 pack/unpack 方案，后续可迁移至 pgvector |
| 前端框架 | Vite + React + TypeScript | 沿用现有技术栈 |

## 功能模块

### 1. 职业数据库

6 大方向 → 二级子方向 → 职业单元（叶节点 = JD 条目），3 层分类。

```
6 大方向
├─ 1. 战略与管理
├─ 2. 研究、设计与算法
├─ 3. 工程开发与实现
├─ 4. 测试、生产与供应链
├─ 5. 商业化、服务与支持
└─ 6. 职能支撑平台
```

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| `career_directions` | 6 大方向 | `id`, `code`, `name`, `sort_order` |
| `career_sub_directions` | 二级方向 (如 4.1) | `id`, `direction_id` FK, `code`, `name`, `sort_order` |
| `career_units` | 职业单元 = JD 条目 | 见下方字段详表 |

**career_units 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `sub_direction_id` | FK → career_sub_directions | 所属子方向 |
| `company_id` | FK → companies | 所属企业 |
| `job_title` | TEXT NOT NULL | 岗位名称 |
| `city` | TEXT | 城市 |
| `salary` | TEXT | 薪资 |
| `experience` | TEXT | 经验要求 |
| `education` | TEXT | 学历要求 |
| `url` | TEXT | 岗位链接 |
| `jd_description` | TEXT | JD 描述 |
| `other_info` | TEXT | 其他信息 |
| `data_source` | TEXT | 数据来源 |
| `source_platform` | TEXT | 来源平台 |
| `collected_at` | TEXT | 收录时间 |
| `semantic_vector` | BLOB | 综合语义向量 (float32) |
| `capability_requirements` | TEXT | 提取的能力要求 JSON |
| `created_at` / `updated_at` | TEXT | 时间戳 |

**关联表**：

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| `job_capability_links` | JD ↔ 能力别名多对多 | `career_unit_id` FK, `capability_alias_id` FK, `extraction_method`, `confidence`, `evidence_text` |

### 2. 能力数据库

6 大方向 → 能力分类 → 能力项（有别称），3 层分类。

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| `capability_directions` | 6 大方向 | `id`, `code`, `name`, `sort_order` |
| `capability_categories` | 二级分类 | `id`, `direction_id` FK, `code`, `name`, `sort_order` |
| `capabilities` | 底层能力项 | `id`, `category_id` FK, `name`, `code`, `description` |
| `capability_aliases` | 能力别称 | `id`, `capability_id` FK, `alias_name`, `normalized_alias`, `alias_type` |

### 3. 企业数据库

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| `companies` | 企业信息 | `id`, `name`, `normalized_name`, `display_name`, `website`, `liepin_url`, `description`, `industry`, `scale` |

企业表保持轻量，核心作用是作为职业单元的外键引用。不确定的字段留空（nullable）。

### 4. XLSX 导入管道

**上传接口**：`POST /api/v1/import/xlsx`（multipart/form-data）

**导入流程**：
1. 解析 XLSX 文件（openpyxl）
2. 逐行处理：
   - 按公司名查找或创建 `companies` 记录
   - 创建 `career_units` 记录（含全部 JD 字段）
   - 从 JD 描述中自动抽取能力要求
   - 为每个抽取的能力：匹配已有别名 → 创建 `job_capability_links`；无匹配 → 新建 `capabilities` + `capability_aliases`
3. 生成并存储语义向量
4. 返回导入统计（成功/跳过/失败数）

**能力抽取策略**：
- 基于词典匹配（复用 CapabilityLexicon 模式）
- 向量相似度匹配（余弦 > 阈值时归入已有能力）
- 无匹配时自动新建能力项并创建别名

### 5. Repository 与 API 层重写

**新增 Repository**：
- `CareerRepository`：替代 `repository.py` + `v4_repository.py` 中的职业/图谱部分
- `CapabilityRepository`：替代能力相关查询
- `CompanyRepository`：企业 CRUD
- `ImportService`：XLSX 导入 + 能力抽取

**API 端点**：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/import/xlsx` | POST | 上传并导入 XLSX |
| `/api/v1/import/status/{batch_id}` | GET | 查询导入状态 |
| `/api/v1/career-directions` | GET | 职业方向树 |
| `/api/v1/career-units` | GET | 职业单元列表（分页/筛选） |
| `/api/v1/career-units/{id}` | GET | 职业单元详情 |
| `/api/v1/capability-directions` | GET | 能力方向树 |
| `/api/v1/capabilities` | GET | 能力列表 |
| `/api/v1/capabilities/{id}` | GET | 能力详情（含别名） |
| `/api/v1/companies` | GET | 企业列表 |
| `/api/v1/companies/{id}` | GET | 企业详情（含关联 JD） |
| `/api/v1/data-overview/tables` | GET | 数据总览（保留） |
| `/api/v1/data-overview/tables/{name}` | GET | 表详情（保留） |

旧端点（`/graph/*`, `/skills`, `/vectorization/*`, `/career-graph/*` 等）全部移除，待后续图谱重构时重新设计。

### 6. 前端适配

- `api.ts`：更新 API 调用，移除旧端点，新增导入/职业/能力/企业端点
- `types.ts`：更新类型定义，匹配新 Schema
- `DataOverview.tsx`：适配新的表分组（职业/能力/企业三部分）
- `App.tsx`：暂时移除图谱相关 Tab（GraphExplorer、MatcherLab），保留数据总览和目录
- 新增：XLSX 上传导入页面

## 是否有原型设计

是

## 实施步骤

### 阶段一：原型设计

加载 design-canvas 技能，设计数据总览页面和导入页面原型。重点展示三库分组结构、表列表、数据预览和 XLSX 上传交互。

### 阶段二：代码开发

1. **数据库 Schema 重建** — 创建全新迁移脚本 `database/migrations/004_three_db_rebuild.sql`（DROP 旧表 + CREATE 新表），编写种子数据脚本填充职业/能力分类层级（6 方向 + ~18 子方向），更新 `database.py` 配置。涉及文件：`database/migrations/004_three_db_rebuild.sql`, `scripts/seed_taxonomy.py`

2. **XLSX 导入管道** — 新增 `apps/api/app/import_service.py`（XLSX 解析 + 导入管道 + 能力抽取逻辑），新增上传 API 路由，集成 openpyxl 依赖。涉及文件：`apps/api/app/import_service.py`, `apps/api/app/main.py`

3. **Repository 与 API 层重写** — 新增 `apps/api/app/career_repository.py`、`apps/api/app/capability_repository.py`、`apps/api/app/company_repository.py`，重写 `main.py` 路由，移除旧端点，保留并适配 DataOverview。涉及文件：`apps/api/app/main.py`, `apps/api/app/career_repository.py`, `apps/api/app/data_overview.py`

4. **前端适配** — 更新 `api.ts` 和 `types.ts`，适配 `DataOverview.tsx` 的新表分组，更新 `App.tsx` 导航（暂时隐藏图谱 Tab），新增导入页面。涉及文件：`apps/web/src/api.ts`, `apps/web/src/App.tsx`, `apps/web/src/components/DataOverview.tsx`

5. **集成测试与验证** — 验证数据库初始化、种子数据正确性、XLSX 导入管道（含能力抽取）、API 端点响应、前端数据总览展示。

## 页面规格

### 全局导航

##### @nav(web-topbar)
> type: topbar
> platform: web

- @page(/) 数据总览
- @page(/import) 数据导入

### 页面详情

##### @page(/) 数据总览

**核心职责**：浏览三库（职业/能力/企业）的所有数据表，查看表结构和数据预览。
**访问路径**：导航直达。
**布局**：顶部标题栏 + 主内容区按三库分组展示表卡片列表，点击表卡片展开表详情（列信息 + 分页数据预览）。

**列表项字段**：表中文名 / 表英文名 / 记录数 / 所属分组

**交互说明**

| 元素 | 动作 | 响应 | 传参 | 备注 |
|------|------|------|------|------|
| Logo | 点击 | 刷新当前页 | — | — |
| 表卡片 | 点击 | 展开/折叠表详情面板 | table_name | 展示列定义和前 25 行数据 |
| 分组标题 | 点击 | 折叠/展开该分组下所有表卡片 | — | — |
| 数据导入 | 点击 | 跳转 @page(/import) | — | 顶部导航 |

##### @page(/import) 数据导入

**核心职责**：上传 XLSX 文件并触发数据导入，展示导入进度和结果。
**访问路径**：导航直达。
**布局**：顶部标题栏 + 文件上传区域 + 导入结果面板（统计摘要 + 错误详情）。

**交互说明**

| 元素 | 动作 | 响应 | 传参 | 备注 |
|------|------|------|------|------|
| Logo | 点击 | 跳转 @page(/) | — | — |
| 上传区域 | 拖拽/点击选择文件 | 选择 XLSX 文件后显示文件信息 | — | 仅接受 .xlsx |
| 开始导入 | 点击 | 调用导入 API，显示进度 | file | 按钮在文件选择后可用 |
| 数据总览 | 点击 | 跳转 @page(/) | — | 导入完成后显示 |
