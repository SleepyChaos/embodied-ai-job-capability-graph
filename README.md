# 具身智能岗位能力图谱

面向挑战杯项目的多源异构岗位数据系统。当前版本实现了岗位事实库、能力本体、职业相似网络、岗位向量计算、人工审核和 AntV G6 双图谱呈现。

## 已实现能力

- 201 个能力节点：具身智能 → 六大一级能力 → 二级能力 → 三级能力与技术变体。
- 106 个标准职业及六大方向、二级职业分类。
- JD 能力证据抽取和 L3/L2/L1 稀疏能力向量。
- `BAAI/bge-small-zh-v1.5` 512 维语义向量适配器。
- 能力、语义、核心能力 Jaccard、标题和属性兼容度混合匹配。
- 人工确认“归并、相关、新职业或信息不足”，未经审核不修改正式映射。
- AntV G6 能力层级图和职业相似网络。
- 岗位目录、数据证据与岗位匹配实验室。

## 项目结构

```text
apps/api/       FastAPI API、向量任务和单进程工作进程
apps/web/       React、TypeScript、AntV G6 前端
database/       v2-v4 增量迁移、脱敏演示库和数据说明
scripts/        迁移、回算、验证与演示库生成脚本
docs/           架构、模块设计、接口与视觉验收材料
```

## 数据入口与演示范围

推荐使用 [`database/demo_v4.db`](database/demo_v4.db) 演示。它由 [演示库生成脚本](scripts/create_demo_database.py) 清理逐条 JD、证据原文、招聘版本、向量任务和人工操作记录，保留能力本体、标准职业、聚合画像和相似关系；清理范围见 [数据库说明](database/README.md)。

当前版本还跟踪着 `data/embodied_ai_jobs_v4.db` 运行数据库和 `assets/具身智能岗位_合并去重.xlsx`。它们与演示库不是同一份数据，不能声称本仓库只含脱敏演示数据。需要自行核对其内容、来源和适用范围；下方启动方式会新建单独的演示运行副本，不覆盖已有运行库。

此项目提供双图谱与匹配 MVP；同账号的 [岗位能力图谱主项目](https://github.com/SleepyChaos/job-capability-graph) 承载另一套后续研究与开发。两仓的数据库和脚本入口不同，不能直接互换。

## 本地启动

需要 Python 3.10+、Node.js 与 pnpm。以下命令在仓库根目录使用 PowerShell；后端与前端分别使用终端，并在启动后端的同一终端设置数据库路径。复制演示库得到运行副本：

```powershell
New-Item -ItemType Directory -Force data | Out-Null
# demo-local.db 只用于本地演示；重复执行会重置这份副本。
Copy-Item database\demo_v4.db data\demo-local.db
$env:EMBODIED_DB_PATH = (Resolve-Path data\demo-local.db)
```

启动后端：

```powershell
cd apps\api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动前端：

```powershell
cd apps\web
pnpm install
pnpm dev
```

访问 [http://127.0.0.1:5173](http://127.0.0.1:5173)。API 文档位于 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

演示库不含原始 JD，因此可浏览双图谱和聚合画像；岗位匹配实验室可计算能力向量，但语义向量需要另外下载模型。

### LLM 能力抽取

当前三库架构支持使用 DeepSeek 对 JD 进行能力抽取、六大方向分类和语义等价判断。密钥只通过环境变量提供：

```powershell
$env:DEEPSEEK_API_KEY = "在本机设置的密钥"
$env:EMBODIED_LLM_BASE_URL = "https://api.deepseek.com"
$env:EMBODIED_LLM_MODEL = "deepseek-v4-flash"
```

首次使用先执行迁移：

```powershell
.\apps\api\.venv\Scripts\python.exe scripts\apply_migration_005.py
.\apps\api\.venv\Scripts\python.exe scripts\apply_migration_006.py
```

单条回算使用 `POST /api/v1/capability-extraction/career-units/{career_unit_id}`，
批量回算使用 `POST /api/v1/capability-extraction/batch?limit=10`。

LLM 不直接创建正式分类和能力总称。无法高置信归并的结果进入候选审核接口。完整说明见
[`docs/06_llm_capability_pipeline.md`](docs/06_llm_capability_pipeline.md)。

职业聚类在已审批能力画像之上运行，不合并单条 JD。执行
`scripts/apply_migration_010.py` 和 `scripts/apply_migration_011.py` 后，可在数据总览的“职业聚类”工作台查看正式职业簇和
人工候选。完整规则与数据外发说明见
[`docs/07_llm_career_clustering.md`](docs/07_llm_career_clustering.md)。

## 可选语义模型

```powershell
.\apps\api\.venv\Scripts\hf.exe download BAAI/bge-small-zh-v1.5 --local-dir models\bge-small-zh-v1.5
$env:EMBODIED_MODEL_DIR = (Resolve-Path models)
```

模型不提交 Git。缺少模型时系统透明降级为能力向量匹配，不会伪造语义分。

## 验证

后端测试与前端构建是开发检查命令，不代表已完成外部模型或全部平台的验证。

```powershell
cd apps\api
.\.venv\Scripts\python.exe -m pytest -q

cd ..\web
pnpm run build
```

更完整的实现说明参见 [docs/05_v4_vector_graph_implementation.md](docs/05_v4_vector_graph_implementation.md)。
