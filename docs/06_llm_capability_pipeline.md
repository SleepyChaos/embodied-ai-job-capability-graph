# LLM 能力抽取与治理管道

## 目标

将职业单元的 JD 描述转换为可追溯的能力数据，层级为：

```text
能力别称 → 能力总称 → 二级能力分类 → 六大一级能力方向
```

## 处理过程

1. 从 `career_units` 读取岗位名称、JD 描述和其他信息。
2. 向 DeepSeek 注入六大一级方向及当前二级分类。
   每个方向和分类都包含简洁的业务定义，模型不能只根据名称猜测边界。
3. 使用 JSON Output 获取能力名称、描述、分类、要求等级和原文证据。
4. 后端校验一级方向枚举、二级分类父子关系、数值范围和证据原文。
5. 先按规范化别称精确匹配正式能力。
6. 未命中时，以同一二级分类中的能力总称作为候选，请 LLM 判断：
   `same`、`broader`、`narrower`、`related` 或 `different`。
7. 任一关键可信度低于 0.80 时重做对应判断，最多三次。
8. 所有关键可信度均达到 0.90 时，`same` 自动归并，非 `same` 自动创建新总称。
9. 没有低于 0.80、但至少一项处于 0.80～0.8999 时进入人工审核。
10. 连续三次仍低于 0.80 时，在 JD 主记录上标记能力提取失败并保存原因。
11. 审核通过后才写入正式能力表和 `job_capability_links`。

`career_units.capability_extraction_status` 保存
`not_started / processing / review / succeeded / failed`，失败原因和时间分别写入
`capability_extraction_failure_reason` 与 `capability_extraction_status_at`。

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 空 | DeepSeek API 密钥，不得提交 Git |
| `EMBODIED_LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容接口根地址 |
| `EMBODIED_LLM_MODEL` | `deepseek-v4-flash` | 抽取与等价判断模型 |
| `EMBODIED_LLM_TIMEOUT_SECONDS` | `120` | 单次请求超时 |

## 从旧机械能力库重建

先应用能力分类描述迁移，再重置旧能力层：

```powershell
.\apps\api\.venv\Scripts\python.exe scripts\apply_migration_006.py
.\apps\api\.venv\Scripts\python.exe scripts\reset_capability_ontology.py
```

重置脚本会先创建 `data/embodied_ai_jobs_v4.db-before-llm-rebuild`，
然后清空旧能力总称、别称、岗位关联和抽取候选。六大方向、18个二级分类、
职业单元、JD原文和企业数据不受影响。

## API

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/capability-extraction/status` | 查看模型配置状态 |
| POST | `/api/v1/capability-extraction/career-units/{id}` | 回算单条职业单元 |
| POST | `/api/v1/capability-extraction/batch?limit=10` | 回算一批未处理职业单元 |
| GET | `/api/v1/capability-extraction/runs/{id}` | 查看抽取任务和能力提及 |
| GET | `/api/v1/capability-governance/pending/{kind}` | 查看待审核候选 |
| POST | `/api/v1/capability-governance/categories/{id}/review` | 审核二级分类候选 |
| POST | `/api/v1/capability-governance/capabilities/{id}/review` | 审核能力总称候选 |

`kind` 可取 `categories`、`capabilities` 或 `normalizations`。

分类审核请求示例：

```json
{
  "decision": "approve",
  "approvedName": "机器人模型部署与优化",
  "reviewNote": "审核说明"
}
```

能力候选可使用 `approve` 创建新总称，使用 `merge` 并提供
`targetCapabilityId` 归入已有总称，或使用 `reject` 拒绝。

## 安全与可追溯性

- JD 被明确标记为不可信输入，不能改变系统规则。
- 每项能力必须提供能在 JD 中逐字定位的证据。
- 保存模型名、Prompt 版本、输入哈希、原始 JSON、Token 用量和错误信息。
- 相同输入、模型和 Prompt 版本默认复用已有成功任务。
- API 密钥只从进程环境读取，不写数据库和日志。
