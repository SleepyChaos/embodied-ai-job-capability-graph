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


@app.get(f"{settings.api_prefix}/data-overview/tables")
def list_tables():
    """List all tables grouped by database part."""
    with database.read() as conn:
        result = []
        for group_key, group_info in TABLE_GROUPS.items():
            tables = []
            for table_name in group_info["tables"]:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                except sqlite3.OperationalError:
                    count = 0
                tables.append({
                    "name": table_name,
                    "description": TABLE_DESCRIPTIONS.get(table_name, ""),
                    "rowCount": count,
                })
            result.append({
                "key": group_key,
                "name": group_info["name"],
                "tables": tables,
            })
        return {"groups": result}


@app.get(f"{settings.api_prefix}/data-overview/tables/{{table_name}}")
def get_table_detail(
    table_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, alias="pageSize", ge=1, le=100),
):
    """Get table schema and paginated data."""
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
            })

        # Get row count
        total = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        # Get paginated data
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM {table_name} LIMIT ? OFFSET ?",
            (page_size, offset)
        ).fetchall()

        return {
            "name": table_name,
            "description": TABLE_DESCRIPTIONS.get(table_name, ""),
            "columns": columns,
            "data": [dict(row) for row in rows],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total > 0 else 0,
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

        return {
            "items": [dict(r) for r in rows],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total > 0 else 0,
            },
        }
