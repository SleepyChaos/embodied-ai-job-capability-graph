from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from migrate_database_v2 import copy_database, sha256_file, table_digest


DOMAINS = [
    ("CAP-L1-01", "战略与经营管理能力"),
    ("CAP-L1-02", "研究、设计与算法能力"),
    ("CAP-L1-03", "工程开发与实现能力"),
    ("CAP-L1-04", "测试、生产与供应链能力"),
    ("CAP-L1-05", "商业化、服务与支持能力"),
    ("CAP-L1-06", "职能支撑能力"),
]

L2_CATEGORIES = [
    ("CAP-L2-11", "CAP-L1-01", "战略决策与领导"),
    ("CAP-L2-12", "CAP-L1-01", "业务与项目管理"),
    ("CAP-L2-13", "CAP-L1-01", "创新与问题解决"),
    ("CAP-L2-21", "CAP-L1-02", "基础与前沿研究"),
    ("CAP-L2-22", "CAP-L1-02", "机器学习与模型开发"),
    ("CAP-L2-23", "CAP-L1-02", "视觉感知与多模态"),
    ("CAP-L2-24", "CAP-L1-02", "定位建图与状态估计"),
    ("CAP-L2-25", "CAP-L1-02", "运动规划与控制"),
    ("CAP-L2-26", "CAP-L1-02", "架构与产品设计"),
    ("CAP-L2-31", "CAP-L1-03", "软件开发"),
    ("CAP-L2-32", "CAP-L1-03", "机器人中间件与系统集成"),
    ("CAP-L2-33", "CAP-L1-03", "AI框架与计算平台"),
    ("CAP-L2-34", "CAP-L1-03", "仿真与工程工具"),
    ("CAP-L2-35", "CAP-L1-03", "嵌入式与电子开发"),
    ("CAP-L2-36", "CAP-L1-03", "机械、执行器与感知硬件"),
    ("CAP-L2-37", "CAP-L1-03", "数据工程与云原生"),
    ("CAP-L2-41", "CAP-L1-04", "测试与验证"),
    ("CAP-L2-42", "CAP-L1-04", "生产制造"),
    ("CAP-L2-43", "CAP-L1-04", "供应链与质量"),
    ("CAP-L2-51", "CAP-L1-05", "市场与品牌"),
    ("CAP-L2-52", "CAP-L1-05", "销售与业务拓展"),
    ("CAP-L2-53", "CAP-L1-05", "部署运维与客户成功"),
    ("CAP-L2-61", "CAP-L1-06", "人力资源与组织协作"),
    ("CAP-L2-62", "CAP-L1-06", "财务、法务与合规"),
    ("CAP-L2-63", "CAP-L1-06", "综合与专业支持"),
]

# Every legacy skill label appears exactly once in these groups. Obvious
# spelling/case duplicates are merged later by CANONICAL_OVERRIDES.
LEGACY_SKILL_GROUPS = {
    "CAP-L2-11": ["领导力"],
    "CAP-L2-12": ["跨部门", "项目管理"],
    "CAP-L2-13": ["创新思维", "问题解决"],
    "CAP-L2-21": ["因果推理", "自然语言处理", "常识推理"],
    "CAP-L2-22": [
        "simtoreal", "Sim-to-Real", "机器学习", "强化学习", "大语言模型",
        "VAE", "Transformer", "RLHF", "深度学习", "扩散模型", "循环神经网络",
        "生成对抗网络", "DPO", "卷积神经网络", "模仿学习",
    ],
    "CAP-L2-23": [
        "多模态", "实例分割", "图像分类", "语义分割", "姿态估计",
        "场景理解", "目标检测", "物体识别", "目标跟踪", "多传感器融合",
    ],
    "CAP-L2-24": [
        "VO", "视觉里程计", "vo", "vO", "Vo", "卡尔曼滤波", "粒子滤波",
        "vio", "VIO", "SLAM", "惯导", "状态估计",
    ],
    "CAP-L2-25": [
        "运动规划", "运动学", "轨迹规划", "力控与柔顺控制", "MPC", "PID控制",
        "逆运动学", "动力学", "模型预测控制", "任务规划",
    ],
    "CAP-L2-31": [
        "Swift", "Shell", "Go", "Linux", "C#", "Kotlin", "JavaScript", "Java",
        "TypeScript", "Rust", "C++", "Python",
    ],
    "CAP-L2-32": [
        "EtherCAT", "CAN总线", "profinet", "PROFINET", "Profinet", "ROS2", "ROS",
    ],
    "CAP-L2-33": [
        "tpu", "TPU", "NumPy", "numpy", "TensorFlow", "LangChain", "CUDA",
        "Hugging Face", "PyTorch", "NPU", "GPU", "PCL", "Open3D", "OpenCV",
        "Transformers", "transformers", "Eigen",
    ],
    "CAP-L2-34": ["CAD", "Isaac Sim", "MuJoCo", "CAE", "Gazebo", "MATLAB", "Simulink"],
    "CAP-L2-35": [
        "MCU", "嵌入式开发", "电路设计", "原理图", "PCB设计", "FPGA",
        "单片机", "电机驱动", "控制器",
    ],
    "CAP-L2-36": [
        "Tof", "TOF", "ToF", "传感器", "直流电机", "夹爪", "减速器",
        "伺服电机", "深度相机", "RGBD", "RGB-D", "无刷电机", "LiDAR",
        "激光雷达", "步进电机", "惯性测量", "IMU", "灵巧手", "机械臂",
    ],
    "CAP-L2-37": ["Git", "Docker", "Kubernetes"],
    "CAP-L2-41": ["有限元分析"],
    "CAP-L2-61": ["学习能力", "英语", "沟通能力", "英语沟通", "团队协作", "抗压能力"],
}

CANONICAL_OVERRIDES = {
    "simtoreal": "Sim-to-Real迁移",
    "Sim-to-Real": "Sim-to-Real迁移",
    "多模态": "多模态融合",
    "Swift": "Swift开发",
    "Shell": "Shell脚本开发",
    "tpu": "TPU加速",
    "TPU": "TPU加速",
    "Go": "Go开发",
    "NumPy": "NumPy应用",
    "numpy": "NumPy应用",
    "Linux": "Linux系统开发",
    "VO": "视觉里程计",
    "vo": "视觉里程计",
    "vO": "视觉里程计",
    "Vo": "视觉里程计",
    "C#": "C#开发",
    "Tof": "ToF传感",
    "TOF": "ToF传感",
    "ToF": "ToF传感",
    "Kotlin": "Kotlin开发",
    "JavaScript": "JavaScript开发",
    "Java": "Java开发",
    "ROS2": "ROS2开发",
    "profinet": "PROFINET集成",
    "PROFINET": "PROFINET集成",
    "Profinet": "PROFINET集成",
    "Git": "Git版本管理",
    "TypeScript": "TypeScript开发",
    "RGBD": "RGB-D视觉",
    "RGB-D": "RGB-D视觉",
    "LiDAR": "激光雷达感知",
    "激光雷达": "激光雷达感知",
    "MPC": "模型预测控制",
    "模型预测控制": "模型预测控制",
    "Rust": "Rust开发",
    "C++": "C++开发",
    "Python": "Python开发",
    "惯性测量": "IMU感知",
    "IMU": "IMU感知",
    "PCL": "PCL点云处理",
    "Open3D": "Open3D点云处理",
    "Transformers": "Hugging Face Transformers应用",
    "transformers": "Hugging Face Transformers应用",
    "vio": "视觉惯性里程计",
    "VIO": "视觉惯性里程计",
    "ROS": "ROS开发",
    "OpenCV": "OpenCV视觉开发",
    "Eigen": "Eigen数值计算",
}

CURATED_LEAVES = {
    "CAP-L2-11": ["战略规划", "经营决策", "技术路线决策"],
    "CAP-L2-12": ["业务分析", "研发项目管理", "生态合作管理"],
    "CAP-L2-13": ["创新管理"],
    "CAP-L2-21": ["机器人伦理与安全研究", "实验设计与科研方法"],
    "CAP-L2-26": ["系统架构设计", "产品规划", "用户研究", "人机交互设计"],
    "CAP-L2-41": ["自动化测试", "可靠性验证", "功能安全验证", "形式化验证"],
    "CAP-L2-42": ["生产工艺设计", "机器人装配与调试", "精益制造"],
    "CAP-L2-43": ["供应商管理", "质量管理", "采购与物料管理"],
    "CAP-L2-51": ["市场研究", "品牌营销", "技术内容策划"],
    "CAP-L2-52": ["解决方案销售", "渠道管理", "商务谈判"],
    "CAP-L2-53": ["现场部署", "机器人运维", "远程诊断", "客户成功", "产品培训"],
    "CAP-L2-61": ["招聘与人才配置", "绩效管理", "薪酬管理", "培训与组织发展"],
    "CAP-L2-62": ["财务分析", "预算管理", "法律合规", "知识产权管理", "风险控制"],
    "CAP-L2-63": ["IT支持", "数据安全与隐私", "标准化管理", "行政与设施管理"],
}

VARIANTS = [
    ("C++17开发", "C++开发"),
    ("C++20开发", "C++开发"),
    ("C++23开发", "C++开发"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_label(value: str) -> str:
    # Keep symbols that are part of a technology's identity. Removing them would
    # collapse C++, C# and C into the same alias key.
    return "".join(
        ch
        for ch in value.strip().casefold()
        if ch.isalnum() or ch in {"+", "#"} or "\u4e00" <= ch <= "\u9fff"
    )


def source_tables(connection: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        if row[0] != "schema_migrations"
    ]


def snapshot_tables(connection: sqlite3.Connection, tables: list[str]) -> dict[str, dict[str, object]]:
    return {
        table: {
            "count": connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
            "digest": table_digest(connection, table),
        }
        for table in tables
    }


def insert_node(
    connection: sqlite3.Connection,
    ontology_id: int,
    code: str,
    name: str,
    level: int,
    kind: str,
    parent_id: int | None,
    sort_order: int,
    now: str,
    *,
    source_type: str,
    confidence: float,
    review_status: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO capability_nodes(
            ontology_version_id, parent_id, capability_code, capability_name,
            level, node_kind, sort_order, source_type, confidence,
            review_status, valid_from
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            ontology_id,
            parent_id,
            code,
            name,
            level,
            kind,
            sort_order,
            source_type,
            confidence,
            review_status,
            now,
        ),
    )
    return int(cursor.lastrowid)


def seed_ontology(connection: sqlite3.Connection, now: str) -> dict[str, object]:
    connection.execute(
        """
        INSERT INTO ontology_versions(
            version_code, version_name, status, source_type, description,
            is_current, created_at
        ) VALUES (
            'capability-ontology-v1',
            '具身智能能力本体初始版',
            'reviewing',
            'hybrid',
            '六大能力方向、旧技能规范化和专家补充能力；所有三级能力等待人工复核',
            1,
            ?
        )
        """,
        (now,),
    )
    ontology_id = int(connection.execute(
        "SELECT id FROM ontology_versions WHERE version_code='capability-ontology-v1'"
    ).fetchone()[0])

    code_to_id: dict[str, int] = {}
    root_id = insert_node(
        connection, ontology_id, "CAP-ROOT", "具身智能", 0, "root", None, 0, now,
        source_type="talent_map", confidence=1.0, review_status="approved",
    )
    code_to_id["CAP-ROOT"] = root_id

    for order, (code, name) in enumerate(DOMAINS, start=1):
        code_to_id[code] = insert_node(
            connection, ontology_id, code, name, 1, "domain", root_id, order, now,
            source_type="talent_map", confidence=0.95, review_status="approved",
        )

    for order, (code, parent_code, name) in enumerate(L2_CATEGORIES, start=1):
        code_to_id[code] = insert_node(
            connection, ontology_id, code, name, 2, "category", code_to_id[parent_code], order, now,
            source_type="expert_seed", confidence=0.75, review_status="pending",
        )

    raw_rows = connection.execute("SELECT id, skill_name FROM skills ORDER BY id").fetchall()
    raw_names = {row[1] for row in raw_rows}
    grouped_names = [name for names in LEGACY_SKILL_GROUPS.values() for name in names]
    missing_from_groups = sorted(raw_names - set(grouped_names))
    unknown_in_groups = sorted(set(grouped_names) - raw_names)
    duplicate_group_entries = sorted(name for name in set(grouped_names) if grouped_names.count(name) > 1)
    if missing_from_groups or unknown_in_groups or duplicate_group_entries:
        raise RuntimeError(
            "Legacy skill classification is incomplete: "
            f"missing={missing_from_groups}, unknown={unknown_in_groups}, duplicates={duplicate_group_entries}"
        )

    canonical_to_node: dict[str, int] = {}
    raw_to_canonical: dict[str, str] = {}
    leaf_order: defaultdict[str, int] = defaultdict(int)
    leaf_seq = 1
    for l2_code, names in LEGACY_SKILL_GROUPS.items():
        for raw_name in names:
            canonical_name = CANONICAL_OVERRIDES.get(raw_name, raw_name)
            raw_to_canonical[raw_name] = canonical_name
            if canonical_name in canonical_to_node:
                continue
            leaf_order[l2_code] += 1
            code = f"CAP-L3-{leaf_seq:04d}"
            leaf_seq += 1
            canonical_to_node[canonical_name] = insert_node(
                connection,
                ontology_id,
                code,
                canonical_name,
                3,
                "variant" if canonical_name == "ROS2开发" else "capability",
                code_to_id[l2_code],
                leaf_order[l2_code],
                now,
                source_type="legacy_skill",
                confidence=0.70,
                review_status="pending",
            )

    curated_count = 0
    for l2_code, names in CURATED_LEAVES.items():
        for name in names:
            if name in canonical_to_node:
                continue
            leaf_order[l2_code] += 1
            code = f"CAP-L3-{leaf_seq:04d}"
            leaf_seq += 1
            canonical_to_node[name] = insert_node(
                connection,
                ontology_id,
                code,
                name,
                3,
                "capability",
                code_to_id[l2_code],
                leaf_order[l2_code],
                now,
                source_type="expert_seed",
                confidence=0.55,
                review_status="pending",
            )
            curated_count += 1

    variant_count = 0
    for variant_name, parent_capability_name in VARIANTS:
        parent_node = connection.execute(
            "SELECT parent_id FROM capability_nodes WHERE id=?",
            (canonical_to_node[parent_capability_name],),
        ).fetchone()
        if parent_node is None:
            raise RuntimeError(f"Variant parent is missing: {parent_capability_name}")
        l2_id = int(parent_node[0])
        l2_code = connection.execute(
            "SELECT capability_code FROM capability_nodes WHERE id=?", (l2_id,)
        ).fetchone()[0]
        leaf_order[l2_code] += 1
        code = f"CAP-L3-{leaf_seq:04d}"
        leaf_seq += 1
        variant_id = insert_node(
            connection,
            ontology_id,
            code,
            variant_name,
            3,
            "variant",
            l2_id,
            leaf_order[l2_code],
            now,
            source_type="expert_seed",
            confidence=0.70,
            review_status="pending",
        )
        canonical_to_node[variant_name] = variant_id
        connection.execute(
            """
            INSERT INTO capability_relations(
                source_capability_id, target_capability_id, relation_type,
                weight, confidence, source_type, review_status
            ) VALUES (?,?,'VARIANT_OF',1.0,0.70,'expert_seed','pending')
            """,
            (variant_id, canonical_to_node[parent_capability_name]),
        )
        variant_count += 1

    # ROS2 is a meaningful platform generation rather than a spelling alias.
    connection.execute(
        """
        INSERT INTO capability_relations(
            source_capability_id, target_capability_id, relation_type,
            weight, confidence, source_type, review_status
        ) VALUES (?,?,'VARIANT_OF',1.0,0.85,'legacy_skill','pending')
        """,
        (canonical_to_node["ROS2开发"], canonical_to_node["ROS开发"]),
    )

    for raw_name, canonical_name in raw_to_canonical.items():
        capability_id = canonical_to_node[canonical_name]
        if normalize_label(raw_name) != normalize_label(canonical_name) or raw_name != canonical_name:
            if raw_name.isascii() and len(raw_name) <= 12:
                alias_type = "abbreviation"
            elif raw_name.casefold() == canonical_name.casefold():
                alias_type = "spelling"
            else:
                alias_type = "legacy_label"
            connection.execute(
                """
                INSERT OR IGNORE INTO capability_aliases(
                    capability_id, alias_name, normalized_alias, alias_type,
                    source, usage_frequency, confidence, review_status
                ) VALUES (?,?,?,?,?,?,?,'pending')
                """,
                (
                    capability_id,
                    raw_name,
                    normalize_label(raw_name),
                    alias_type,
                    "legacy_skills",
                    1,
                    0.85,
                ),
            )

    for skill_id, raw_name in raw_rows:
        canonical_name = raw_to_canonical[raw_name]
        mapping_type = "variant" if canonical_name == "ROS2开发" else "exact"
        connection.execute(
            """
            INSERT INTO skill_capability_mappings(
                skill_id, capability_id, mapping_type, method,
                confidence, is_primary, review_status, review_note
            ) VALUES (?,?,?,?,?,1,'pending',?)
            """,
            (
                skill_id,
                canonical_to_node[canonical_name],
                mapping_type,
                "legacy_seed",
                0.85 if mapping_type == "variant" else 0.90,
                "v3 initial normalization; requires human ontology review",
            ),
        )

    for row in connection.execute(
        "SELECT job_id, alias_name, alias_source, usage_frequency FROM job_aliases ORDER BY id"
    ):
        alias_name = row[1]
        alias_type = "translation" if alias_name.isascii() and any(ch.isalpha() for ch in alias_name) else "legacy_label"
        connection.execute(
            """
            INSERT OR IGNORE INTO career_aliases_v3(
                job_id, alias_name, normalized_alias, alias_type,
                source, usage_frequency, confidence, review_status
            ) VALUES (?,?,?,?,?,?,0.85,'pending')
            """,
            (
                row[0],
                alias_name,
                normalize_label(alias_name),
                alias_type,
                row[2] or "legacy_job_alias",
                row[3] or 0,
            ),
        )

    return {
        "ontology_id": ontology_id,
        "code_to_id": code_to_id,
        "canonical_to_node": canonical_to_node,
        "legacy_canonical_count": len(set(raw_to_canonical.values())),
        "curated_count": curated_count,
        "variant_count": variant_count + 1,
    }


def seed_profiles(connection: sqlite3.Connection, now: str) -> dict[str, object]:
    snapshot_id = int(connection.execute(
        "SELECT id FROM graph_snapshots WHERE status='ready' ORDER BY snapshot_at DESC, id DESC LIMIT 1"
    ).fetchone()[0])

    rows = connection.execute(
        """
        SELECT
            m.id AS mapping_id, m.job_id, scm.capability_id,
            m.confidence AS legacy_confidence, scm.confidence AS mapping_confidence
        FROM v_job_skill_current m
        JOIN skill_capability_mappings scm
          ON scm.skill_id=m.skill_id AND scm.is_primary=1
        ORDER BY m.job_id, scm.capability_id, m.id
        """
    ).fetchall()
    groups: defaultdict[tuple[int, int], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        groups[(int(row[1]), int(row[2]))].append(row)

    covered_jobs = sorted({job_id for job_id, _ in groups})
    capability_df: defaultdict[int, int] = defaultdict(int)
    for _, capability_id in groups:
        capability_df[capability_id] += 1
    n_jobs = len(covered_jobs)
    idf = {
        capability_id: math.log((n_jobs + 1) / (df + 1)) + 1.0
        for capability_id, df in capability_df.items()
    }
    max_idf = max(idf.values(), default=1.0)

    for (job_id, capability_id), mapping_rows in groups.items():
        mapping_ids = [int(row[0]) for row in mapping_rows]
        placeholders = ",".join("?" for _ in mapping_ids)
        evidence = connection.execute(
            f"""
            SELECT COUNT(DISTINCT e.jd_id), COUNT(DISTINCT r.source_id)
            FROM job_skill_evidence e
            JOIN raw_jd_documents r ON r.id=e.jd_id
            WHERE e.mapping_id IN ({placeholders})
            """,
            mapping_ids,
        ).fetchone()
        jd_count = int(evidence[0] or 0)
        source_count = int(evidence[1] or 0)
        confidence = sum(float(row[3] or 0.5) * float(row[4]) for row in mapping_rows) / len(mapping_rows)
        # IDF supplies differentiation that the legacy constant weights lack.
        weight = min(1.0, 0.25 + 0.75 * (idf[capability_id] / max_idf))
        connection.execute(
            """
            INSERT INTO job_capability_profiles(
                snapshot_id, job_id, capability_id, importance,
                mention_count, jd_count, source_count, weight, confidence,
                evidence_count, calculation_version, review_status, valid_from
            ) VALUES (?,?,?,'unspecified',?,?,?,?,?,?,'cap-profile-v1-idf','pending',?)
            """,
            (
                snapshot_id,
                job_id,
                capability_id,
                len(mapping_rows),
                jd_count,
                source_count,
                round(weight, 6),
                round(min(1.0, confidence), 6),
                jd_count,
                now,
            ),
        )

    return {
        "snapshot_id": snapshot_id,
        "covered_jobs": covered_jobs,
        "profile_count": len(groups),
        "capability_df": dict(capability_df),
    }


def cosine(a: dict[int, float], b: dict[int, float]) -> float:
    shared = set(a) & set(b)
    dot = sum(a[key] * b[key] for key in shared)
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def weighted_jaccard(a: dict[int, float], b: dict[int, float]) -> float:
    keys = set(a) | set(b)
    denominator = sum(max(a.get(key, 0.0), b.get(key, 0.0)) for key in keys)
    if not denominator:
        return 0.0
    return sum(min(a.get(key, 0.0), b.get(key, 0.0)) for key in keys) / denominator


def seed_similarities(
    connection: sqlite3.Connection,
    now: str,
    snapshot_id: int,
    top_k: int,
    threshold: float,
) -> dict[str, object]:
    vectors: defaultdict[int, dict[int, float]] = defaultdict(dict)
    capability_category: dict[int, int] = {}
    for row in connection.execute(
        """
        SELECT p.job_id, p.capability_id, p.weight, c.parent_id
        FROM job_capability_profiles p
        JOIN capability_nodes c ON c.id=p.capability_id
        WHERE p.snapshot_id=?
        """,
        (snapshot_id,),
    ):
        vectors[int(row[0])][int(row[1])] = float(row[2])
        capability_category[int(row[1])] = int(row[3])

    jd_counts = {
        int(row[0]): int(row[1])
        for row in connection.execute(
            """
            SELECT mapped_job_id, COUNT(*)
            FROM raw_jd_documents
            WHERE mapped_job_id IS NOT NULL AND clean_status='cleaned'
            GROUP BY mapped_job_id
            """
        )
    }

    candidates: list[dict[str, object]] = []
    for job_a, job_b in itertools.combinations(sorted(vectors), 2):
        vector_a = vectors[job_a]
        vector_b = vectors[job_b]
        shared = set(vector_a) & set(vector_b)
        cos = cosine(vector_a, vector_b)
        jac = weighted_jaccard(vector_a, vector_b)
        categories_a = {capability_category[key] for key in vector_a}
        categories_b = {capability_category[key] for key in vector_b}
        category_union = categories_a | categories_b
        hierarchy = len(categories_a & categories_b) / len(category_union) if category_union else 0.0
        score = 0.70 * cos + 0.20 * jac + 0.10 * hierarchy
        coverage_a = min(1.0, math.log1p(jd_counts.get(job_a, 0)) / math.log1p(20))
        coverage_b = min(1.0, math.log1p(jd_counts.get(job_b, 0)) / math.log1p(20))
        contributions = sorted(
            ((capability_id, vector_a[capability_id] * vector_b[capability_id]) for capability_id in shared),
            key=lambda item: (-item[1], item[0]),
        )
        total_contribution = sum(value for _, value in contributions) or 1.0
        candidates.append(
            {
                "job_a": job_a,
                "job_b": job_b,
                "score": score,
                "cosine": cos,
                "jaccard": jac,
                "hierarchy": hierarchy,
                "shared": len(shared),
                "coverage_a": coverage_a,
                "coverage_b": coverage_b,
                "contributions": [
                    (capability_id, value / total_contribution)
                    for capability_id, value in contributions[:8]
                ],
            }
        )

    incident: defaultdict[int, list[dict[str, object]]] = defaultdict(list)
    for candidate in candidates:
        incident[int(candidate["job_a"])].append(candidate)
        incident[int(candidate["job_b"])].append(candidate)
    selected_keys: set[tuple[int, int]] = set()
    for job_id, job_candidates in incident.items():
        ranked = sorted(
            (item for item in job_candidates if float(item["score"]) >= threshold),
            key=lambda item: (-float(item["score"]), int(item["job_a"]), int(item["job_b"])),
        )
        for item in ranked[:top_k]:
            selected_keys.add((int(item["job_a"]), int(item["job_b"])))
    retained = [
        item for item in candidates
        if (int(item["job_a"]), int(item["job_b"])) in selected_keys
    ]

    algorithm_version = "career-sim-v1-idf-topk"
    warning = (
        "Similarity is derived from legacy evidence with incomplete job coverage; "
        "all results remain pending human review."
    )
    cursor = connection.execute(
        """
        INSERT INTO job_similarity_runs(
            snapshot_id, algorithm_version, config_json, job_count,
            candidate_pairs, retained_pairs, status, warning, created_at
        ) VALUES (?,?,?,?,?,?,'succeeded',?,?)
        """,
        (
            snapshot_id,
            algorithm_version,
            json.dumps(
                {
                    "formula": {"cosine": 0.70, "weighted_jaccard": 0.20, "hierarchy": 0.10},
                    "top_k": top_k,
                    "threshold": threshold,
                    "profile_version": "cap-profile-v1-idf",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            len(vectors),
            len(candidates),
            len(retained),
            warning,
            now,
        ),
    )
    run_id = int(cursor.lastrowid)

    for item in sorted(retained, key=lambda value: (int(value["job_a"]), int(value["job_b"]))):
        connection.execute(
            """
            INSERT INTO job_similarities(
                run_id, snapshot_id, job_a_id, job_b_id, score_total,
                capability_cosine, core_jaccard, hierarchy_score,
                shared_capability_count, coverage_a, coverage_b,
                algorithm_version, review_status, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'pending',?)
            """,
            (
                run_id,
                snapshot_id,
                item["job_a"],
                item["job_b"],
                round(float(item["score"]), 6),
                round(float(item["cosine"]), 6),
                round(float(item["jaccard"]), 6),
                round(float(item["hierarchy"]), 6),
                item["shared"],
                round(float(item["coverage_a"]), 6),
                round(float(item["coverage_b"]), 6),
                algorithm_version,
                now,
            ),
        )
        for rank_no, (capability_id, contribution) in enumerate(item["contributions"], start=1):
            connection.execute(
                """
                INSERT INTO job_similarity_explanations(
                    run_id, job_a_id, job_b_id, capability_id,
                    contribution, rank_no, created_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    item["job_a"],
                    item["job_b"],
                    capability_id,
                    round(float(contribution), 6),
                    rank_no,
                    now,
                ),
            )

    return {
        "run_id": run_id,
        "algorithm_version": algorithm_version,
        "candidate_pairs": len(candidates),
        "retained_pairs": len(retained),
        "threshold": threshold,
        "top_k": top_k,
    }


def migrate(source: Path, target: Path, migration_sql: Path, report_path: Path) -> dict[str, object]:
    if target.exists():
        raise FileExistsError(f"Target already exists: {target}. Refusing to overwrite it.")
    if not source.exists():
        raise FileNotFoundError(source)

    source_hash = sha256_file(source)
    copy_database(source, target)
    now = utc_now()

    with sqlite3.connect(source) as src:
        src.row_factory = sqlite3.Row
        preserved_tables = source_tables(src)
        before = snapshot_tables(src, preserved_tables)
    src.close()

    with sqlite3.connect(target) as dst:
        dst.row_factory = sqlite3.Row
        dst.execute("PRAGMA foreign_keys=ON")
        dst.executescript(migration_sql.read_text(encoding="utf-8"))
        with dst:
            ontology = seed_ontology(dst, now)
            profiles = seed_profiles(dst, now)
            similarities = seed_similarities(
                dst,
                now,
                int(profiles["snapshot_id"]),
                top_k=4,
                threshold=0.35,
            )
            dst.execute(
                """
                INSERT INTO schema_migrations(version, description, source_sha256)
                VALUES (
                    '3.0.0',
                    'Add capability ontology, normalized job capability profiles, and explainable career similarity',
                    ?
                )
                """,
                (source_hash,),
            )

        after = snapshot_tables(dst, preserved_tables)
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = [tuple(row) for row in dst.execute("PRAGMA foreign_key_check")]
        counts = {
            name: dst.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            for name in (
                "ontology_versions",
                "capability_nodes",
                "capability_aliases",
                "capability_relations",
                "skill_capability_mappings",
                "career_aliases_v3",
                "job_capability_profiles",
                "job_similarity_runs",
                "job_similarities",
                "job_similarity_explanations",
            )
        }
        levels = {
            str(row[0]): row[1]
            for row in dst.execute("SELECT level,COUNT(*) FROM capability_nodes GROUP BY level ORDER BY level")
        }
        review_statuses = {
            row[0]: row[1]
            for row in dst.execute(
                "SELECT review_status,COUNT(*) FROM capability_nodes GROUP BY review_status ORDER BY review_status"
            )
        }
    # sqlite3.Connection's context manager commits/rolls back but does not close.
    # Close explicitly before hashing so the report describes the final on-disk file.
    dst.close()

    unchanged = before == after
    report: dict[str, object] = {
        "source": str(source),
        "target": str(target),
        "source_sha256": source_hash,
        "target_sha256": sha256_file(target),
        "preserved_tables_unchanged": unchanged,
        "preserved_table_count": len(preserved_tables),
        "preserved_before": before,
        "preserved_after": after,
        "ontology": {
            "legacy_canonical_count": ontology["legacy_canonical_count"],
            "curated_count": ontology["curated_count"],
            "variant_count": ontology["variant_count"],
            "levels": levels,
            "review_statuses": review_statuses,
        },
        "profiles": {
            "covered_job_count": len(profiles["covered_jobs"]),
            "profile_count": profiles["profile_count"],
        },
        "similarities": similarities,
        "v3_counts": counts,
        "integrity_check": integrity,
        "foreign_key_errors": foreign_key_errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not unchanged or integrity != "ok" or foreign_key_errors:
        raise RuntimeError("v3 migration verification failed; see report")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a non-destructive v3 capability/career graph database")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = migrate(
        args.source.resolve(),
        args.target.resolve(),
        args.migration.resolve(),
        args.report.resolve(),
    )
    print(json.dumps(
        {
            "target": report["target"],
            "preserved_tables_unchanged": report["preserved_tables_unchanged"],
            "integrity_check": report["integrity_check"],
            "foreign_key_error_count": len(report["foreign_key_errors"]),
            "v3_counts": report["v3_counts"],
            "ontology": report["ontology"],
            "profiles": report["profiles"],
            "similarities": report["similarities"],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
