from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import load_settings
from .database import Database
from .import_service import ImportService


settings = load_settings()
database = Database(settings.database_path)
import_service = ImportService(database)

app = FastAPI(
    title="岗位智能分析图谱 API",
    version="0.5.0",
    description="三库架构：职业数据库、能力数据库、企业数据库",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, error: HTTPException):
    return JSONResponse(
        status_code=error.status_code,
        content={"code": f"HTTP_{error.status_code}", "message": str(error.detail), "requestId": request.state.request_id},
    )


# ============================================================
# Health
# ============================================================

@app.get(f"{settings.api_prefix}/health")
def health():
    db_health = database.health()
    return {
        "status": "ok" if db_health["status"] == "ok" else "degraded",
        "database": db_health,
    }


# ============================================================
# Data Overview (generic table browser)
# ============================================================

TABLE_GROUPS = {
    "career": {
        "name": "职业数据库",
        "tables": ["career_directions", "career_sub_directions", "career_units", "job_capability_links"],
    },
    "capability": {
        "name": "能力数据库",
        "tables": ["capability_directions", "capability_categories", "capabilities", "capability_aliases"],
    },
    "enterprise": {
        "name": "企业数据库",
        "tables": ["companies"],
    },
}

TABLE_DESCRIPTIONS = {
    "career_directions": "职业大方向（6个）",
    "career_sub_directions": "职业二级子方向（如4.1、4.2）",
    "career_units": "职业单元（JD条目）",
    "job_capability_links": "岗位-能力关联（多对多）",
    "capability_directions": "能力大方向（6个）",
    "capability_categories": "能力二级分类",
    "capabilities": "能力项（底层）",
    "capability_aliases": "能力别称/同义词",
    "companies": "企业信息",
    "import_batches": "导入批次记录",
}


@app.get(f"{settings.api_prefix}/data-overview")
def get_data_overview():
    """Get overall database overview (matches original frontend format)."""
    with database.read() as conn:
        # Get database file info
        db_path = settings.database_path
        file_size = db_path.stat().st_size if db_path.exists() else 0
        
        # Get schema version
        schema_version = None
        try:
            row = conn.execute("SELECT version FROM schema_migrations ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                schema_version = str(row[0])
        except sqlite3.OperationalError:
            pass
        
        # Build tables list
        tables = []
        total_rows = 0
        non_empty_count = 0
        total_fks = 0
        
        for group_key, group_info in TABLE_GROUPS.items():
            for table_name in group_info["tables"]:
                try:
                    row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                except sqlite3.OperationalError:
                    row_count = 0
                
                # Get column count
                col_count = 0
                try:
                    cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                    col_count = len(cols)
                except sqlite3.OperationalError:
                    pass
                
                # Get foreign key count
                fk_count = 0
                try:
                    fks = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
                    fk_count = len(fks)
                    total_fks += fk_count
                except sqlite3.OperationalError:
                    pass
                
                total_rows += row_count
                if row_count > 0:
                    non_empty_count += 1
                
                tables.append({
                    "name": table_name,
                    "displayName": TABLE_DISPLAY_NAMES.get(table_name, table_name),
                    "description": TABLE_DESCRIPTIONS.get(table_name, ""),
                    "group": group_info["name"],
                    "rowCount": row_count,
                    "columnCount": col_count,
                    "foreignKeyCount": fk_count,
                })
        
        # Build groups
        groups = [
            {"name": info["name"], "tables": info["tables"]}
            for info in TABLE_GROUPS.values()
        ]
        
        return {
            "database": {
                "fileName": db_path.name,
                "schemaVersion": schema_version,
                "fileSizeBytes": file_size,
            },
            "summary": {
                "tableCount": len(tables),
                "nonEmptyTableCount": non_empty_count,
                "totalRows": total_rows,
                "relationshipCount": total_fks,
            },
            "groups": groups,
            "tables": tables,
        }


# Display names for tables
TABLE_DISPLAY_NAMES = {
    "career_directions": "职业方向",
    "career_sub_directions": "职业子方向",
    "career_units": "职业单元",
    "job_capability_links": "岗位能力关联",
    "capability_directions": "能力方向",
    "capability_categories": "能力分类",
    "capabilities": "能力项",
    "capability_aliases": "能力别称",
    "companies": "企业",
    "import_batches": "导入批次",
}


@app.get(f"{settings.api_prefix}/data-overview/tables/{{table_name}}")
def get_table_detail(
    table_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, alias="pageSize", ge=1, le=100),
):
    """Get table schema and paginated data (matches original frontend format)."""
    with database.read() as conn:
        # Check table exists
        table_info = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        if not table_info:
            raise HTTPException(404, f"表 {table_name} 不存在")

        # Get columns
        columns = []
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall():
            columns.append({
                "name": row["name"],
                "type": row["type"],
                "nullable": not row["notnull"],
                "primaryKey": bool(row["pk"]),
                "description": COLUMN_DESCRIPTIONS.get(table_name, {}).get(row["name"], ""),
            })

        # Get foreign keys
        foreign_keys = []
        for fk in conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall():
            foreign_keys.append({
                "fromColumn": fk["from"],
                "toTable": fk["table"],
                "toColumn": fk["to"],
            })

        # Get incoming references (tables that reference this table)
        incoming_references = []
        all_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for t in all_tables:
            other_table = t["name"]
            if other_table == table_name:
                continue
            try:
                fks = conn.execute(f"PRAGMA foreign_key_list({other_table})").fetchall()
                for fk in fks:
                    if fk["table"] == table_name:
                        incoming_references.append({
                            "table": other_table,
                            "column": fk["from"],
                            "targetColumn": fk["to"],
                        })
            except sqlite3.OperationalError:
                pass

        # Get indexes
        indexes = []
        for idx in conn.execute(f"PRAGMA index_list({table_name})").fetchall():
            idx_dict = dict(idx)
            idx_name = idx_dict["name"]
            idx_unique = bool(idx_dict["unique"])
            idx_origin = idx_dict.get("origin", "")
            idx_partial = bool(idx_dict.get("partial", 0))
            idx_columns = []
            for col in conn.execute(f"PRAGMA index_info({idx_name})").fetchall():
                idx_columns.append(col["name"])
            indexes.append({
                "name": idx_name,
                "unique": idx_unique,
                "origin": idx_origin,
                "partial": idx_partial,
                "columns": idx_columns,
            })

        # Get row count
        total = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        # Get paginated data
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM {table_name} LIMIT ? OFFSET ?",
            (page_size, offset)
        ).fetchall()

        # Build table summary
        col_count = len(columns)
        fk_count = len(foreign_keys)
        
        # Find group
        group_name = ""
        for gk, gi in TABLE_GROUPS.items():
            if table_name in gi["tables"]:
                group_name = gi["name"]
                break

        return {
            "table": {
                "name": table_name,
                "displayName": TABLE_DISPLAY_NAMES.get(table_name, table_name),
                "description": TABLE_DESCRIPTIONS.get(table_name, ""),
                "group": group_name,
                "rowCount": total,
                "columnCount": col_count,
                "foreignKeyCount": fk_count,
            },
            "columns": columns,
            "foreignKeys": foreign_keys,
            "incomingReferences": incoming_references,
            "indexes": indexes,
            "rows": [dict(row) for row in rows],
            "page": {
                "page": page,
                "pageSize": page_size,
                "total": total,
            },
        }


# Column descriptions for better understanding
COLUMN_DESCRIPTIONS = {
    "career_units": {
        "id": "主键",
        "sub_direction_id": "所属子方向ID",
        "company_id": "所属企业ID",
        "job_title": "岗位名称",
        "city": "工作城市",
        "salary": "薪资范围",
        "experience": "经验要求",
        "education": "学历要求",
        "jd_description": "JD描述",
        "semantic_vector": "语义向量（用于相似度检索）",
    },
    "capabilities": {
        "id": "主键",
        "category_id": "所属分类ID",
        "name": "能力名称",
        "description": "能力描述",
    },
    "capability_aliases": {
        "id": "主键",
        "capability_id": "所属能力ID",
        "alias": "别称",
        "alias_type": "别称类型",
    },
}


# ============================================================
# Career Database APIs
# ============================================================

@app.get(f"{settings.api_prefix}/career-directions")
def list_career_directions():
    """List all career directions with sub-directions."""
    with database.read() as conn:
        directions = conn.execute(
            "SELECT * FROM career_directions ORDER BY sort_order"
        ).fetchall()

        result = []
        for d in directions:
            sub_dirs = conn.execute(
                "SELECT * FROM career_sub_directions WHERE direction_id = ? ORDER BY sort_order",
                (d["id"],)
            ).fetchall()
            result.append({
                **dict(d),
                "subDirections": [dict(s) for s in sub_dirs],
            })
        return {"items": result}


@app.get(f"{settings.api_prefix}/career-units")
def list_career_units(
    q: str | None = Query(default=None, max_length=100),
    sub_direction_id: int | None = Query(default=None, alias="subDirectionId"),
    company_id: int | None = Query(default=None, alias="companyId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
):
    """List career units with filtering and pagination."""
    with database.read() as conn:
        conditions = []
        params: list[Any] = []

        if q:
            conditions.append("(cu.job_title LIKE ? OR cu.jd_description LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])
        if sub_direction_id:
            conditions.append("cu.sub_direction_id = ?")
            params.append(sub_direction_id)
        if company_id:
            conditions.append("cu.company_id = ?")
            params.append(company_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        total = conn.execute(
            f"SELECT COUNT(*) FROM career_units cu {where}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(f"""
            SELECT cu.*, c.name as company_name,
                   csd.name as sub_direction_name, csd.code as sub_direction_code,
                   cd.name as direction_name
            FROM career_units cu
            LEFT JOIN companies c ON c.id = cu.company_id
            LEFT JOIN career_sub_directions csd ON csd.id = cu.sub_direction_id
            LEFT JOIN career_directions cd ON cd.id = csd.direction_id
            {where}
            ORDER BY cu.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [page_size, offset]).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total > 0 else 0,
            },
        }


@app.get(f"{settings.api_prefix}/career-units/{{unit_id}}")
def get_career_unit(unit_id: int):
    """Get career unit detail with capability links."""
    with database.read() as conn:
        row = conn.execute("""
            SELECT cu.*, c.name as company_name,
                   csd.name as sub_direction_name, csd.code as sub_direction_code,
                   cd.name as direction_name
            FROM career_units cu
            LEFT JOIN companies c ON c.id = cu.company_id
            LEFT JOIN career_sub_directions csd ON csd.id = cu.sub_direction_id
            LEFT JOIN career_directions cd ON cd.id = csd.direction_id
            WHERE cu.id = ?
        """, (unit_id,)).fetchone()

        if not row:
            raise HTTPException(404, "职业单元不存在")

        # Get capability links
        links = conn.execute("""
            SELECT jcl.*, ca.alias_name, cap.name as capability_name,
                   cc.name as category_name
            FROM job_capability_links jcl
            JOIN capability_aliases ca ON ca.id = jcl.capability_alias_id
            JOIN capabilities cap ON cap.id = ca.capability_id
            LEFT JOIN capability_categories cc ON cc.id = cap.category_id
            WHERE jcl.career_unit_id = ?
            ORDER BY jcl.confidence DESC
        """, (unit_id,)).fetchall()

        return {
            **dict(row),
            "capabilityLinks": [dict(l) for l in links],
        }


# ============================================================
# Capability Database APIs
# ============================================================

@app.get(f"{settings.api_prefix}/capability-directions")
def list_capability_directions():
    """List all capability directions with categories."""
    with database.read() as conn:
        directions = conn.execute(
            "SELECT * FROM capability_directions ORDER BY sort_order"
        ).fetchall()

        result = []
        for d in directions:
            categories = conn.execute(
                "SELECT * FROM capability_categories WHERE direction_id = ? ORDER BY sort_order",
                (d["id"],)
            ).fetchall()
            result.append({
                **dict(d),
                "categories": [dict(c) for c in categories],
            })
        return {"items": result}


@app.get(f"{settings.api_prefix}/capabilities")
def list_capabilities(
    q: str | None = Query(default=None, max_length=100),
    category_id: int | None = Query(default=None, alias="categoryId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
):
    """List capabilities with filtering."""
    with database.read() as conn:
        conditions = []
        params: list[Any] = []

        if q:
            conditions.append("(cap.name LIKE ? OR cap.code LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])
        if category_id:
            conditions.append("cap.category_id = ?")
            params.append(category_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        total = conn.execute(
            f"SELECT COUNT(*) FROM capabilities cap {where}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(f"""
            SELECT cap.*, cc.name as category_name, cc.code as category_code,
                   cd.name as direction_name
            FROM capabilities cap
            LEFT JOIN capability_categories cc ON cc.id = cap.category_id
            LEFT JOIN capability_directions cd ON cd.id = cc.direction_id
            {where}
            ORDER BY cap.sort_order, cap.name
            LIMIT ? OFFSET ?
        """, params + [page_size, offset]).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total > 0 else 0,
            },
        }


@app.get(f"{settings.api_prefix}/capabilities/{{capability_id}}")
def get_capability(capability_id: int):
    """Get capability detail with aliases."""
    with database.read() as conn:
        row = conn.execute("""
            SELECT cap.*, cc.name as category_name, cd.name as direction_name
            FROM capabilities cap
            LEFT JOIN capability_categories cc ON cc.id = cap.category_id
            LEFT JOIN capability_directions cd ON cd.id = cc.direction_id
            WHERE cap.id = ?
        """, (capability_id,)).fetchone()

        if not row:
            raise HTTPException(404, "能力项不存在")

        aliases = conn.execute(
            "SELECT * FROM capability_aliases WHERE capability_id = ? ORDER BY confidence DESC",
            (capability_id,)
        ).fetchall()

        return {
            **dict(row),
            "aliases": [dict(a) for a in aliases],
        }


@app.get(f"{settings.api_prefix}/capability-tree")
def get_capability_tree():
    """Get capability tree data for radial tree visualization.
    
    Returns a tree structure:
    - Root (virtual)
      - Direction (能力方向, level 1)
        - Category (能力分类, level 2)
          - Capability (能力项, level 3)
    """
    # Color palette for directions
    direction_colors = [
        "#2F6BFF",  # 品牌蓝
        "#16A37B",  # 成功绿
        "#E67E22",  # 橙色
        "#9B59B6",  # 紫色
        "#E74C3C",  # 红色
        "#1ABC9C",  # 青色
    ]
    
    with database.read() as conn:
        # Get all directions
        directions = conn.execute(
            "SELECT * FROM capability_directions ORDER BY sort_order"
        ).fetchall()
        
        nodes = []
        edges = []
        
        # Add virtual root node
        root_id = "capability-root"
        nodes.append({
            "id": root_id,
            "type": "capability",
            "data": {
                "databaseId": 0,
                "label": "能力图谱",
                "level": 0,
                "kind": "root",
                "color": "#2F6BFF",
            }
        })
        
        for idx, direction in enumerate(directions):
            direction_id = f"direction:{direction['id']}"
            direction_color = direction_colors[idx % len(direction_colors)]
            
            # Add direction node (level 1)
            nodes.append({
                "id": direction_id,
                "type": "capability",
                "data": {
                    "databaseId": direction["id"],
                    "label": direction["name"],
                    "code": direction["code"],
                    "level": 1,
                    "kind": "direction",
                    "color": direction_color,
                }
            })
            
            # Add edge from root to direction
            edges.append({
                "id": f"edge-root-{direction['id']}",
                "source": root_id,
                "target": direction_id,
                "type": "PARENT_OF",
                "data": {"weight": 1.0}
            })
            
            # Get categories for this direction
            categories = conn.execute(
                "SELECT * FROM capability_categories WHERE direction_id = ? ORDER BY sort_order",
                (direction["id"],)
            ).fetchall()
            
            for category in categories:
                category_id = f"category:{category['id']}"
                
                # Add category node (level 2)
                nodes.append({
                    "id": category_id,
                    "type": "capability",
                    "data": {
                        "databaseId": category["id"],
                        "label": category["name"],
                        "code": category["code"],
                        "level": 2,
                        "kind": "category",
                        "color": direction_color,
                    }
                })
                
                # Add edge from direction to category
                edges.append({
                    "id": f"edge-direction-{direction['id']}-category-{category['id']}",
                    "source": direction_id,
                    "target": category_id,
                    "type": "PARENT_OF",
                    "data": {"weight": 1.0}
                })
                
                # Get capabilities for this category
                capabilities = conn.execute("""
                    SELECT cap.*, 
                           (SELECT COUNT(*) FROM capability_aliases WHERE capability_id = cap.id) as alias_count,
                           (SELECT COUNT(*) FROM job_capability_links WHERE capability_alias_id IN 
                               (SELECT id FROM capability_aliases WHERE capability_id = cap.id)) as job_count
                    FROM capabilities cap
                    WHERE cap.category_id = ?
                    ORDER BY cap.sort_order, cap.name
                """, (category["id"],)).fetchall()
                
                for cap in capabilities:
                    cap_id = f"capability:{cap['id']}"
                    
                    # Add capability node (level 3)
                    nodes.append({
                        "id": cap_id,
                        "type": "capability",
                        "data": {
                            "databaseId": cap["id"],
                            "label": cap["name"],
                            "code": cap["code"],
                            "level": 3,
                            "kind": "capability",
                            "color": direction_color,
                            "aliasCount": cap["alias_count"],
                            "jobCount": cap["job_count"],
                        }
                    })
                    
                    # Add edge from category to capability
                    edges.append({
                        "id": f"edge-category-{category['id']}-capability-{cap['id']}",
                        "source": category_id,
                        "target": cap_id,
                        "type": "PARENT_OF",
                        "data": {"weight": 1.0}
                    })
        
        return {
            "schemaVersion": "2",
            "graphType": "capability",
            "nodes": nodes,
            "edges": edges,
            "combos": [],
            "meta": {
                "partial": False,
                "stale": False,
                "coverage": 1.0,
                "warnings": [],
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
            }
        }


# ============================================================
# Enterprise Database APIs
# ============================================================

@app.get(f"{settings.api_prefix}/companies")
def list_companies(
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
):
    """List companies with pagination."""
    with database.read() as conn:
        conditions = []
        params: list[Any] = []

        if q:
            conditions.append("(name LIKE ? OR display_name LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        total = conn.execute(
            f"SELECT COUNT(*) FROM companies {where}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(f"""
            SELECT c.*,
                   (SELECT COUNT(*) FROM career_units cu WHERE cu.company_id = c.id) as job_count
            FROM companies c
            {where}
            ORDER BY c.name
            LIMIT ? OFFSET ?
        """, params + [page_size, offset]).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total > 0 else 0,
            },
        }


@app.get(f"{settings.api_prefix}/companies/{{company_id}}")
def get_company(company_id: int):
    """Get company detail with associated career units."""
    with database.read() as conn:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        if not row:
            raise HTTPException(404, "企业不存在")

        units = conn.execute("""
            SELECT cu.id, cu.job_title, cu.city, cu.salary, cu.created_at
            FROM career_units cu
            WHERE cu.company_id = ?
            ORDER BY cu.created_at DESC
            LIMIT 50
        """, (company_id,)).fetchall()

        return {
            **dict(row),
            "careerUnits": [dict(u) for u in units],
        }


# ============================================================
# Import APIs
# ============================================================

@app.post(f"{settings.api_prefix}/import/xlsx", status_code=202)
async def import_xlsx(
    file: UploadFile = File(...),
    sub_direction_id: int | None = Query(default=None, alias="subDirectionId"),
):
    """Upload and import an XLSX file."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(400, "仅支持 .xlsx 格式文件")

    # Save uploaded file to temp location
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / file.filename

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Run import
        result = import_service.import_xlsx(temp_path, sub_direction_id)

        return {
            "batchId": result.batch_id,
            "batchCode": result.batch_code,
            "status": "completed" if result.fail_count == 0 else "completed_with_errors",
            "statistics": {
                "total": result.total_count,
                "success": result.success_count,
                "skipped": result.skip_count,
                "failed": result.fail_count,
                "capabilitiesCreated": result.capabilities_created,
                "aliasesCreated": result.aliases_created,
            },
            "errors": result.errors[:10],  # Limit error details
        }
    finally:
        # Cleanup temp file
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.get(f"{settings.api_prefix}/import/status/{{batch_id}}")
def get_import_status(batch_id: int):
    """Get import batch status."""
    result = import_service.get_import_status(batch_id)
    if result is None:
        raise HTTPException(404, "导入批次不存在")
    return result


def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def dict_to_camel(d: dict) -> dict:
    """Convert dict keys from snake_case to camelCase."""
    return {to_camel_case(k): v for k, v in d.items()}


@app.get(f"{settings.api_prefix}/import/history")
@app.get(f"{settings.api_prefix}/import/batches")
def list_import_batches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
):
    """List import batches."""
    with database.read() as conn:
        total = conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute("""
            SELECT * FROM import_batches
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (page_size, offset)).fetchall()

        items = []
        for r in rows:
            item = dict_to_camel(dict(r))
            # Map source_file to sourceFilename
            if "sourceFile" in item:
                item["sourceFilename"] = item.pop("sourceFile")
            items.append(item)

        return {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total > 0 else 0,
            },
        }
