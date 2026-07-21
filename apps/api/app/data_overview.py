from __future__ import annotations

from collections import defaultdict
from typing import Any

from .database import Database


TABLE_GROUPS = {
    "本体与标准": {
        "capability_aliases",
        "capability_nodes",
        "capability_relations",
        "career_aliases_v3",
        "job_aliases",
        "job_categories",
        "job_category_memberships",
        "job_definition_versions",
        "job_positions",
        "ontology_versions",
    },
    "采集与岗位事实": {
        "companies",
        "data_sources",
        "ingestion_batches",
        "jd_batch_memberships",
        "jd_company_links",
        "job_postings",
        "job_posting_versions",
        "raw_jd_documents",
    },
    "能力映射与证据": {
        "jd_capability_mentions",
        "job_capability_profiles",
        "job_skill_evidence",
        "job_skill_mapping",
        "skill_capability_mappings",
        "skill_categories",
        "skill_category_memberships",
        "skill_definition_versions",
        "skill_taxonomy",
        "skills",
    },
    "向量与岗位匹配": {
        "capability_candidates",
        "career_embeddings",
        "embedding_models",
        "jd_embeddings",
        "job_match_candidates",
        "job_match_decisions",
        "vectorization_runs",
    },
    "图谱与相似分析": {
        "career_communities",
        "graph_layout_cache",
        "graph_snapshot_job_skills",
        "graph_snapshots",
        "graph_sync_runs",
        "job_similarities",
        "job_similarity_components",
        "job_similarity_explanations",
        "job_similarity_runs",
    },
    "治理与版本": {
        "change_events",
        "manual_review_tasks",
        "schema_migrations",
    },
}


TABLE_LABELS = {
    "capability_aliases": ("能力别名", "能力节点的标准别名与技术变体名称。"),
    "capability_candidates": ("候选新能力", "能力抽取后尚未进入正式本体的待审核术语。"),
    "capability_nodes": ("能力节点", "L0-L3 能力本体及节点定义。"),
    "capability_relations": ("能力关系", "能力节点之间的关联与技术变体关系。"),
    "career_aliases_v3": ("职业别名 v3", "标准职业与相似职业名称的归一化映射。"),
    "career_communities": ("职业社区", "相似职业网络的社区发现结果。"),
    "career_embeddings": ("职业语义向量", "按职业聚合并归一化后的语义向量。"),
    "change_events": ("变更事件", "本体、画像和图谱数据的变更轨迹。"),
    "companies": ("企业", "招聘企业的规范化身份信息。"),
    "data_sources": ("数据来源", "招聘平台、企业官网等来源登记。"),
    "embedding_models": ("向量模型", "语义模型版本、维度和可用状态。"),
    "graph_layout_cache": ("图谱布局缓存", "图谱节点布局的缓存结果。"),
    "graph_snapshot_job_skills": ("快照岗位技能", "图谱快照中的岗位—技能关系副本。"),
    "graph_snapshots": ("图谱快照", "可发布图谱的版本、状态和指标。"),
    "graph_sync_runs": ("图谱同步任务", "关系库到图谱快照的同步任务记录。"),
    "ingestion_batches": ("采集批次", "岗位数据批量接入与处理状态。"),
    "jd_batch_memberships": ("JD 批次归属", "原始 JD 与采集批次的关联。"),
    "jd_capability_mentions": ("JD 能力证据", "从 JD 条目抽取的能力、角色和证据句。"),
    "jd_company_links": ("JD 企业关联", "原始 JD 与规范企业的对应关系。"),
    "jd_embeddings": ("JD 语义向量", "岗位描述的模型向量及输入摘要。"),
    "job_aliases": ("岗位别名", "旧版标准岗位别名映射。"),
    "job_capability_profiles": ("职业能力画像", "职业在图谱快照中的非零能力权重。"),
    "job_categories": ("岗位分类", "六大方向和二级职业分类树。"),
    "job_category_memberships": ("岗位分类归属", "标准职业与分类节点的关联。"),
    "job_definition_versions": ("岗位定义版本", "标准职业定义的历史版本。"),
    "job_match_candidates": ("岗位匹配候选", "向量任务召回职业的排名和分项得分。"),
    "job_match_decisions": ("岗位匹配审核", "重复、归并、关联或新职业的人工决定。"),
    "job_positions": ("标准职业", "标准职业名称、方向、职责及状态。"),
    "job_posting_versions": ("招聘版本", "同一招聘岗位历次 JD 内容版本。"),
    "job_postings": ("招聘岗位", "来源侧招聘岗位身份及当前版本。"),
    "job_similarities": ("职业相似关系", "标准职业之间的综合相似边。"),
    "job_similarity_components": ("相似度分项", "语义、标题和属性兼容等扩展分数。"),
    "job_similarity_explanations": ("相似度解释", "职业相似关系的共享能力证据。"),
    "job_similarity_runs": ("相似度任务", "职业相似度批量计算的算法版本。"),
    "job_skill_evidence": ("岗位技能证据", "旧版岗位—技能映射的逐条 JD 证据。"),
    "job_skill_mapping": ("岗位技能映射", "旧版标准岗位与技能的关系。"),
    "manual_review_tasks": ("人工审核任务", "数据清洗和映射过程的审核队列。"),
    "ontology_versions": ("本体版本", "能力本体发布版本和生命周期状态。"),
    "raw_jd_documents": ("原始 JD", "采集、清洗和映射后的岗位描述原文。"),
    "schema_migrations": ("数据库迁移", "数据库结构升级版本记录。"),
    "skill_capability_mappings": ("技能能力映射", "旧技能点到新能力本体的转换关系。"),
    "skill_categories": ("技能分类", "旧版技能六大类别。"),
    "skill_category_memberships": ("技能分类归属", "技能点与技能类别的关联。"),
    "skill_definition_versions": ("技能定义版本", "旧技能定义的历史版本。"),
    "skill_taxonomy": ("技能分类树", "旧版技能分类层级。"),
    "skills": ("技能点", "旧版技能名称、类型和定义。"),
    "vectorization_runs": ("向量计算任务", "单条或批量岗位向量计算状态。"),
}


COMMON_COLUMN_DESCRIPTIONS = {
    "id": "本表记录的唯一标识。",
    "created_at": "记录创建时间。",
    "updated_at": "记录最后更新时间。",
    "started_at": "任务开始执行时间。",
    "completed_at": "任务完成时间。",
    "published_at": "数据或版本发布时间。",
    "valid_from": "记录开始生效的时间。",
    "valid_to": "记录停止生效的时间。",
    "status": "当前业务处理状态。",
    "review_status": "当前人工审核状态。",
    "review_note": "人工审核时填写的补充说明。",
    "reviewed_at": "完成人工审核的时间。",
    "reviewed_by": "执行人工审核的人员。",
    "reviewer": "审核决定的操作人员。",
    "description": "该记录的业务说明文本。",
    "source": "该记录的数据来源。",
    "source_type": "数据来源的类型。",
    "confidence": "数据可信度，通常取值为 0 到 1。",
    "confidence_score": "综合可信度评分。",
    "weight": "关系或画像中的计算权重。",
    "importance": "能力或技能的重要程度。",
    "progress": "任务当前完成进度。",
    "priority": "任务处理优先级。",
    "version": "记录采用的版本号。",
    "version_no": "同一对象的顺序版本号。",
    "is_active": "标记数据来源是否启用。",
    "is_current": "标记是否为当前有效版本。",
    "is_primary": "标记是否为主要归属或主要别名。",
    "is_verified": "标记记录是否已经核验。",
    "is_human_verified": "标记证据是否经过人工核验。",
    "is_baseline": "标记快照是否为基线版本。",
    "is_emerging": "标记职业或技能是否属于新兴方向。",
    "applied": "标记审核决定是否已经应用。",
    "applied_at": "审核决定实际应用的时间。",
    "normalized": "标记向量是否已经归一化。",
    "normalized_name": "用于匹配和去重的规范化名称。",
    "normalized_alias": "用于匹配和去重的规范化别名。",
    "error_message": "任务失败或异常时的错误信息。",
    "warning": "计算任务产生的警告说明。",
    "warning_json": "以 JSON 格式保存的警告列表。",
    "config_json": "以 JSON 格式保存的任务配置。",
    "input_json": "以 JSON 格式保存的任务输入。",
    "payload_json": "以 JSON 格式保存的任务业务数据。",
    "report_json": "以 JSON 格式保存的处理报告。",
    "metrics_json": "以 JSON 格式保存的图谱指标。",
    "explanation_json": "以 JSON 格式保存的匹配解释。",
    "old_value_json": "变更前字段值的 JSON 记录。",
    "new_value_json": "变更后字段值的 JSON 记录。",
    "vector_blob": "以 float32 二进制形式保存的语义向量。",
    "vector_norm": "语义向量的范数。",
    "dimensions": "语义向量的维度数量。",
    "content_hash": "岗位内容的哈希摘要，用于去重。",
    "input_text_hash": "向量输入文本的哈希摘要。",
    "source_sha256": "来源文件的 SHA-256 摘要。",
    "source_db_sha256": "生成快照时来源数据库的 SHA-256 摘要。",
    "model_sha256": "向量模型文件的 SHA-256 摘要。",
    "source_url": "数据来源的访问地址。",
    "fetch_url": "采集该岗位信息的网页地址。",
    "canonical_url": "招聘岗位的规范化网页地址。",
    "raw_content": "未经结构化处理的原始岗位正文。",
    "raw_metadata": "采集时保留的原始元数据。",
    "raw_title": "数据来源中的原始岗位名称。",
    "jd_responsibilities": "从 JD 中提取的岗位职责。",
    "jd_requirements": "从 JD 中提取的任职要求。",
    "jd_nice_to_have": "从 JD 中提取的优先或加分条件。",
    "jd_benefits": "从 JD 中提取的福利待遇。",
    "education_requirement": "岗位要求的学历条件。",
    "experience_requirement": "岗位要求的工作经验。",
    "salary_min": "岗位薪资范围的最低值。",
    "salary_max": "岗位薪资范围的最高值。",
    "evidence_text": "支持能力或技能判断的原文片段。",
    "evidence_role": "证据在 JD 中承担的语义角色。",
    "extraction_method": "证据或能力的抽取方法。",
    "classification_method": "岗位分类采用的方法。",
    "decision": "人工确认的岗位匹配决定。",
    "suggestion": "系统给出的岗位匹配建议。",
    "reason": "产生关联或审核任务的原因。",
    "explanation": "变更事件的详细解释。",
    "x": "图谱节点的横向坐标。",
    "y": "图谱节点的纵向坐标。",
}


FIELD_TERMS = {
    "accepted": "接受记录",
    "action": "处理动作",
    "algorithm": "算法",
    "alias": "别名",
    "assigned": "分配",
    "attempt": "尝试",
    "batch": "批次",
    "candidate": "候选",
    "calculation": "计算",
    "capability": "能力",
    "career": "职业",
    "category": "分类",
    "change": "变更",
    "char": "字符位置",
    "city": "城市",
    "classification": "分类",
    "clean": "清洗",
    "code": "编码",
    "community": "社区",
    "company": "企业",
    "compatibility": "兼容性",
    "computed": "计算",
    "confidence": "置信度",
    "content": "内容",
    "contribution": "贡献度",
    "core": "核心",
    "count": "数量",
    "coverage": "覆盖度",
    "credibility": "可信度",
    "cross": "跨域",
    "current": "当前",
    "data": "数据",
    "decision": "决定",
    "demand": "需求",
    "difficulty": "难度",
    "display": "显示",
    "distance": "距离",
    "duplicate": "重复记录",
    "education": "学历",
    "element": "图元素",
    "emergence": "新兴程度",
    "entity": "实体",
    "evidence": "证据",
    "experience": "经验",
    "external": "外部岗位",
    "extraction": "抽取",
    "fetch": "采集",
    "fetched": "采集",
    "field": "字段",
    "filter": "筛选条件",
    "first": "首次",
    "freshness": "新鲜度",
    "graph": "图谱",
    "hallucination": "幻觉检测",
    "hierarchy": "层级",
    "id": "标识",
    "ids": "标识列表",
    "idempotency": "幂等",
    "identity": "身份识别",
    "input": "输入",
    "job": "职业",
    "jd": "岗位描述",
    "language": "语言",
    "last": "最近",
    "layout": "布局",
    "learning": "学习",
    "lease": "任务租约",
    "level": "层级",
    "mapped": "映射职业",
    "mapping": "映射",
    "matched": "匹配",
    "membership": "归属",
    "mention": "提及",
    "method": "方法",
    "mode": "运行模式",
    "model": "模型",
    "name": "名称",
    "node": "节点",
    "nodes": "节点",
    "observed": "观测",
    "ontology": "本体版本",
    "owner": "持有者",
    "parent": "父级",
    "pairs": "配对",
    "plagiarism": "文本重复",
    "posting": "招聘岗位",
    "prerequisites": "前置技能",
    "proficiency": "熟练度",
    "provider": "提供方",
    "province": "省份",
    "published": "发布",
    "rank": "排名",
    "raw": "原始岗位",
    "reject": "拒绝",
    "rejected": "拒绝记录",
    "related": "相关",
    "relation": "关系",
    "resolution": "处理结果",
    "resolved": "解决",
    "retained": "保留",
    "review": "审核",
    "role": "角色",
    "run": "运行任务",
    "salary": "薪资",
    "score": "评分",
    "segment": "文本分段",
    "semantic": "语义",
    "seniority": "职级",
    "shared": "共享",
    "skill": "技能",
    "skills": "技能",
    "snapshot": "图谱快照",
    "sort": "排序",
    "source": "来源",
    "standardization": "标准化",
    "suggested": "建议",
    "target": "目标",
    "taxonomy": "分类树",
    "threshold": "阈值",
    "title": "岗位名称",
    "tools": "工具",
    "trend": "趋势",
    "type": "类型",
    "typical": "典型",
    "usage": "使用",
    "vector": "向量",
    "verified": "核验",
    "version": "版本",
    "warning": "警告",
    "weight": "权重",
    "a": "职业甲",
    "appeared": "出现",
    "at": "时间",
    "available": "可用",
    "b": "职业乙",
    "band": "分数区间",
    "by": "执行者",
    "changed": "变更",
    "config": "配置",
    "created": "创建",
    "description": "说明",
    "domain": "领域",
    "edges": "关系边",
    "en": "英文",
    "end": "结束位置",
    "est": "估算",
    "expires": "到期",
    "file": "文件",
    "flags": "标记",
    "frequency": "频次",
    "from": "来源",
    "hash": "哈希摘要",
    "hours": "小时",
    "icon": "图标",
    "identified": "识别",
    "is": "是否",
    "key": "键",
    "keywords": "关键词",
    "kind": "种类",
    "label": "标签",
    "levels": "职级列表",
    "llm": "大语言模型",
    "metric": "度量方式",
    "no": "序号",
    "note": "备注",
    "of": "关联对象",
    "order": "顺序",
    "paper": "论文",
    "path": "路径",
    "pinned": "固定",
    "reason": "原因",
    "required": "要求",
    "responsibilities": "职责",
    "reviewed": "审核",
    "revision": "修订版本",
    "row": "数据行",
    "scenarios": "应用场景",
    "seen": "发现",
    "start": "开始位置",
    "status": "状态",
    "task": "任务",
    "text": "文本",
    "to": "目标",
    "total": "总计",
    "updated": "更新",
    "validated": "交叉验证",
    "written": "写入",
    "l1": "一级",
    "l2": "二级",
    "l3": "三级",
    "cosine": "余弦相似度",
    "jaccard": "交并比",
}


def _field_label(column_name: str) -> str:
    return "".join(FIELD_TERMS.get(part, part.upper()) for part in column_name.split("_"))


def _column_description(
    column_name: str,
    primary_key_position: int,
    foreign_keys: list[dict[str, Any]],
) -> str:
    if primary_key_position:
        return COMMON_COLUMN_DESCRIPTIONS.get(column_name, "本表记录的主键标识。")
    if foreign_keys:
        target_names = []
        for foreign_key in foreign_keys:
            target_table = str(foreign_key["table"])
            target_names.append(TABLE_LABELS.get(target_table, (target_table, ""))[0])
        targets = "、".join(dict.fromkeys(target_names))
        return f"关联“{targets}”表的记录标识。"
    if column_name in COMMON_COLUMN_DESCRIPTIONS:
        return COMMON_COLUMN_DESCRIPTIONS[column_name]

    label = _field_label(column_name)
    if column_name.startswith("is_"):
        return f"标记记录是否满足“{_field_label(column_name[3:])}”条件。"
    if column_name.endswith("_at"):
        return f"记录{_field_label(column_name[:-3])}的时间。"
    if column_name.endswith("_count"):
        return f"记录{_field_label(column_name[:-6])}的数量。"
    if column_name.endswith(("_score", "_confidence", "_weight")):
        return f"记录{label}，通常取值为 0 到 1。"
    if column_name.endswith("_json"):
        return f"以 JSON 格式保存{_field_label(column_name[:-5])}。"
    if column_name.endswith(("_hash", "_sha256")):
        return f"用于校验和去重的{label}。"
    if column_name.endswith("_url"):
        return f"记录{_field_label(column_name[:-4])}的访问地址。"
    if column_name.endswith("_id"):
        return f"记录{_field_label(column_name[:-3])}的标识。"
    if column_name.endswith("_name"):
        return f"记录{_field_label(column_name[:-5])}的名称。"
    if column_name.endswith("_code"):
        return f"记录{_field_label(column_name[:-5])}的稳定编码。"
    if column_name.endswith("_type"):
        return f"记录{_field_label(column_name[:-5])}的类型。"
    return f"记录本表的{label}信息。"


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _type_category(declared_type: str) -> str:
    normalized = declared_type.upper()
    if "INT" in normalized:
        return "integer"
    if any(token in normalized for token in ("CHAR", "CLOB", "TEXT")):
        return "text"
    if "BLOB" in normalized or not normalized:
        return "blob"
    if any(token in normalized for token in ("REAL", "FLOA", "DOUB")):
        return "real"
    return "numeric"


def _preview_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"kind": "blob", "bytes": len(value)}
    if isinstance(value, str) and len(value) > 800:
        return value[:800] + "…"
    return value


class DataOverviewRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _tables(connection) -> list[str]:
        return [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]

    @staticmethod
    def _group(table_name: str) -> str:
        for group, members in TABLE_GROUPS.items():
            if table_name in members:
                return group
        return "其他"

    @staticmethod
    def _label(table_name: str) -> tuple[str, str]:
        return TABLE_LABELS.get(table_name, (table_name, "数据库业务表。"))

    @staticmethod
    def _foreign_keys(connection, table_name: str) -> list[dict[str, Any]]:
        quoted = _quote_identifier(table_name)
        return [
            {
                "id": int(row[0]),
                "sequence": int(row[1]),
                "table": str(row[2]),
                "column": str(row[4]) if row[4] is not None else None,
                "from": str(row[3]),
                "onUpdate": str(row[5]),
                "onDelete": str(row[6]),
            }
            for row in connection.execute(f"PRAGMA foreign_key_list({quoted})").fetchall()
        ]

    @staticmethod
    def _indexes(connection, table_name: str) -> tuple[list[dict[str, Any]], set[str]]:
        quoted = _quote_identifier(table_name)
        indexes: list[dict[str, Any]] = []
        unique_columns: set[str] = set()
        for row in connection.execute(f"PRAGMA index_list({quoted})").fetchall():
            index_name = str(row[1])
            columns = [
                str(info[2])
                for info in connection.execute(
                    f"PRAGMA index_info({_quote_identifier(index_name)})"
                ).fetchall()
                if info[2] is not None
            ]
            is_unique = bool(row[2])
            if is_unique and len(columns) == 1:
                unique_columns.add(columns[0])
            indexes.append(
                {
                    "name": index_name,
                    "unique": is_unique,
                    "origin": str(row[3]),
                    "partial": bool(row[4]),
                    "columns": columns,
                }
            )
        return indexes, unique_columns

    def overview(self) -> dict[str, Any]:
        with self.database.read() as connection:
            table_names = self._tables(connection)
            tables = []
            total_rows = 0
            relationship_count = 0
            for table_name in table_names:
                quoted = _quote_identifier(table_name)
                row_count = int(connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
                column_count = len(connection.execute(f"PRAGMA table_info({quoted})").fetchall())
                foreign_keys = self._foreign_keys(connection, table_name)
                display_name, description = self._label(table_name)
                tables.append(
                    {
                        "name": table_name,
                        "displayName": display_name,
                        "description": description,
                        "group": self._group(table_name),
                        "rowCount": row_count,
                        "columnCount": column_count,
                        "foreignKeyCount": len(foreign_keys),
                    }
                )
                total_rows += row_count
                relationship_count += len(foreign_keys)
            version_row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        group_order = list(TABLE_GROUPS) + ["其他"]
        grouped = defaultdict(list)
        for table in tables:
            grouped[table["group"]].append(table["name"])
        return {
            "database": {
                "fileName": self.database.path.name,
                "schemaVersion": version_row[0] if version_row else None,
                "fileSizeBytes": self.database.path.stat().st_size,
            },
            "summary": {
                "tableCount": len(tables),
                "nonEmptyTableCount": sum(1 for table in tables if table["rowCount"] > 0),
                "totalRows": total_rows,
                "relationshipCount": relationship_count,
            },
            "groups": [
                {"name": group, "tables": grouped[group]}
                for group in group_order
                if grouped[group]
            ],
            "tables": tables,
        }

    def table_detail(self, table_name: str, page: int, page_size: int) -> dict[str, Any]:
        with self.database.read() as connection:
            table_names = self._tables(connection)
            if table_name not in table_names:
                raise LookupError("数据表不存在")
            quoted = _quote_identifier(table_name)
            foreign_keys = self._foreign_keys(connection, table_name)
            foreign_keys_by_column: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
            for foreign_key in foreign_keys:
                foreign_keys_by_column[foreign_key["from"]].append(foreign_key)
            indexes, unique_columns = self._indexes(connection, table_name)
            columns = []
            primary_key_columns = []
            for row in connection.execute(f"PRAGMA table_info({quoted})").fetchall():
                name = str(row[1])
                pk_position = int(row[5])
                if pk_position:
                    primary_key_columns.append((pk_position, name))
                columns.append(
                    {
                        "position": int(row[0]),
                        "name": name,
                        "description": _column_description(
                            name,
                            pk_position,
                            foreign_keys_by_column[name],
                        ),
                        "declaredType": str(row[2] or ""),
                        "typeCategory": _type_category(str(row[2] or "")),
                        "nullable": not bool(row[3]) and not bool(pk_position),
                        "defaultValue": row[4],
                        "primaryKeyPosition": pk_position or None,
                        "unique": name in unique_columns,
                        "foreignKeys": foreign_keys_by_column[name],
                    }
                )
            incoming = []
            for source_table in table_names:
                for foreign_key in self._foreign_keys(connection, source_table):
                    if foreign_key["table"] == table_name:
                        incoming.append(
                            {
                                "table": source_table,
                                "column": foreign_key["from"],
                                "targetColumn": foreign_key["column"],
                            }
                        )
            row_count = int(connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
            order_clause = ""
            if primary_key_columns:
                ordered_keys = [name for _, name in sorted(primary_key_columns)]
                order_clause = " ORDER BY " + ",".join(_quote_identifier(name) for name in ordered_keys)
            offset = (page - 1) * page_size
            rows = connection.execute(
                f"SELECT * FROM {quoted}{order_clause} LIMIT ? OFFSET ?", (page_size, offset)
            ).fetchall()
            display_name, description = self._label(table_name)
        return {
            "table": {
                "name": table_name,
                "displayName": display_name,
                "description": description,
                "group": self._group(table_name),
                "rowCount": row_count,
                "columnCount": len(columns),
                "foreignKeyCount": len(foreign_keys),
            },
            "columns": columns,
            "foreignKeys": foreign_keys,
            "incomingReferences": incoming,
            "indexes": indexes,
            "rows": [
                {key: _preview_value(value) for key, value in dict(row).items()}
                for row in rows
            ],
            "page": {"page": page, "pageSize": page_size, "total": row_count},
        }
