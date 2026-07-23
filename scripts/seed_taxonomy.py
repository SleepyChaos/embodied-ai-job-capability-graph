"""Seed the career and capability taxonomy hierarchies.

Populates:
- career_directions (6 entries)
- career_sub_directions (~18 entries)
- capability_directions (6 entries)
- capability_categories (~18 entries)

Usage:
    python scripts/seed_taxonomy.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "embodied_ai_jobs_v4.db"

# ============================================================
# Career taxonomy (from 具身智能产业人才图谱 1.0)
# ============================================================

CAREER_DIRECTIONS = [
    ("D1", "战略与管理", 1),
    ("D2", "研究、设计与算法", 2),
    ("D3", "工程开发与实现", 3),
    ("D4", "测试、生产与供应链", 4),
    ("D5", "商业化、服务与支持", 5),
    ("D6", "职能支撑平台", 6),
]

CAREER_SUB_DIRECTIONS = [
    # D1: 战略与管理
    ("D1", "1.1", "核心决策层", 1),
    ("D1", "1.2", "战略与业务管理", 2),
    ("D1", "1.3", "核心职能管理", 3),
    # D2: 研究、设计与算法
    ("D2", "2.1", "基础与前沿研究", 1),
    ("D2", "2.2", "算法与智能", 2),
    ("D2", "2.3", "架构与产品设计", 3),
    # D3: 工程开发与实现
    ("D3", "3.1", "软件与仿真开发", 1),
    ("D3", "3.2", "硬件开发", 2),
    ("D3", "3.3", "系统集成与数据运维", 3),
    # D4: 测试、生产与供应链
    ("D4", "4.1", "测试与验证", 1),
    ("D4", "4.2", "生产制造", 2),
    ("D4", "4.3", "供应链与质量", 3),
    # D5: 商业化、服务与支持
    ("D5", "5.1", "市场营销", 1),
    ("D5", "5.2", "销售与业务拓展", 2),
    ("D5", "5.3", "部署、运维与客户成功", 3),
    # D6: 职能支撑平台
    ("D6", "6.1", "人力资源", 1),
    ("D6", "6.2", "财务与法务", 2),
    ("D6", "6.3", "综合与专业支持", 3),
]

# ============================================================
# Capability taxonomy (same 6 directions, different categories)
# ============================================================

CAPABILITY_DIRECTIONS = [
    ("CD1", "战略与管理能力", 1),
    ("CD2", "研究与算法能力", 2),
    ("CD3", "工程开发能力", 3),
    ("CD4", "测试与生产能力", 4),
    ("CD5", "商业化与服务能力", 5),
    ("CD6", "职能支撑能力", 6),
]

CAPABILITY_CATEGORIES = [
    # CD1: 战略与管理能力
    ("CD1", "C1.1", "战略规划与决策", 1),
    ("CD1", "C1.2", "组织与运营管理", 2),
    ("CD1", "C1.3", "项目与资源管理", 3),
    # CD2: 研究与算法能力
    ("CD2", "C2.1", "基础科学研究", 1),
    ("CD2", "C2.2", "机器学习与AI算法", 2),
    ("CD2", "C2.3", "系统架构与设计", 3),
    # CD3: 工程开发能力
    ("CD3", "C3.1", "软件工程", 1),
    ("CD3", "C3.2", "硬件与电子工程", 2),
    ("CD3", "C3.3", "系统集成与运维", 3),
    # CD4: 测试与生产能力
    ("CD4", "C4.1", "测试与质量保证", 1),
    ("CD4", "C4.2", "制造工艺与工程", 2),
    ("CD4", "C4.3", "供应链管理", 3),
    # CD5: 商业化与服务能力
    ("CD5", "C5.1", "市场与品牌", 1),
    ("CD5", "C5.2", "销售与客户管理", 2),
    ("CD5", "C5.3", "技术支持与服务", 3),
    # CD6: 职能支撑能力
    ("CD6", "C6.1", "人力资源与组织发展", 1),
    ("CD6", "C6.2", "财务与法务合规", 2),
    ("CD6", "C6.3", "行政与专业支持", 3),
]


def seed_taxonomy(db_path: Path) -> None:
    """Insert taxonomy seed data into the database."""
    if not db_path.exists():
        print(f"Error: Database file not found at {db_path}")
        print("Run the migration script first to create the database.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    try:
        # Check if data already exists
        count = conn.execute("SELECT COUNT(*) FROM career_directions").fetchone()[0]
        if count > 0:
            print(f"Career directions already seeded ({count} entries). Skipping.")
            return

        # Insert career directions
        print("Inserting career directions...")
        direction_ids: dict[str, int] = {}
        for code, name, sort_order in CAREER_DIRECTIONS:
            cursor = conn.execute(
                "INSERT INTO career_directions (code, name, sort_order) VALUES (?, ?, ?)",
                (code, name, sort_order),
            )
            direction_ids[code] = cursor.lastrowid
        print(f"  Inserted {len(CAREER_DIRECTIONS)} career directions")

        # Insert career sub-directions
        print("Inserting career sub-directions...")
        for dir_code, code, name, sort_order in CAREER_SUB_DIRECTIONS:
            conn.execute(
                "INSERT INTO career_sub_directions (direction_id, code, name, sort_order) VALUES (?, ?, ?, ?)",
                (direction_ids[dir_code], code, name, sort_order),
            )
        print(f"  Inserted {len(CAREER_SUB_DIRECTIONS)} career sub-directions")

        # Insert capability directions
        print("Inserting capability directions...")
        cap_direction_ids: dict[str, int] = {}
        for code, name, sort_order in CAPABILITY_DIRECTIONS:
            cursor = conn.execute(
                "INSERT INTO capability_directions (code, name, sort_order) VALUES (?, ?, ?)",
                (code, name, sort_order),
            )
            cap_direction_ids[code] = cursor.lastrowid
        print(f"  Inserted {len(CAPABILITY_DIRECTIONS)} capability directions")

        # Insert capability categories
        print("Inserting capability categories...")
        for dir_code, code, name, sort_order in CAPABILITY_CATEGORIES:
            conn.execute(
                "INSERT INTO capability_categories (direction_id, code, name, sort_order) VALUES (?, ?, ?, ?)",
                (cap_direction_ids[dir_code], code, name, sort_order),
            )
        print(f"  Inserted {len(CAPABILITY_CATEGORIES)} capability categories")

        conn.commit()
        print("\nTaxonomy seeding completed successfully!")

        # Print summary
        for table in ["career_directions", "career_sub_directions",
                       "capability_directions", "capability_categories"]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count} rows")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    seed_taxonomy(DB_PATH)
