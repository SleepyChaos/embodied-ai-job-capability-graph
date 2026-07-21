from __future__ import annotations

import sqlite3
import uuid
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from .config import load_settings
from .data_overview import DataOverviewRepository
from .database import Database
from .repository import KnowledgeGraphRepository
from .v4_repository import V4Repository
from .vectorization import VectorizationService, build_default_embedding_provider


settings = load_settings()
database = Database(settings.database_path)
repository = KnowledgeGraphRepository(database)
v4_repository = V4Repository(database)
data_overview_repository = DataOverviewRepository(database)

app = FastAPI(
    title="具身智能岗位能力图谱 API",
    version="0.4.0",
    description="读取 SQLite v4 事实库，提供能力/职业双图谱、岗位向量计算与人工审核。",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ManualJob(BaseModel):
    company: str = ""
    title: str = Field(min_length=1, max_length=200)
    responsibilities: str = ""
    requirements: str = ""
    niceToHave: str = ""
    location: str = ""
    seniority: str = ""


class VectorizationRequest(BaseModel):
    source: Literal["manual", "raw_jd", "batch"] = "manual"
    rawJdId: int | None = None
    batchId: int | None = None
    job: ManualJob | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if self.source == "manual" and self.job is None:
            raise ValueError("manual source requires job")
        if self.source == "raw_jd" and self.rawJdId is None:
            raise ValueError("raw_jd source requires rawJdId")
        return self


class MatchDecisionRequest(BaseModel):
    runId: int
    candidateId: int | None = None
    decision: Literal["POSTING_VERSION", "EXACT_DUPLICATE", "SAME_CAREER", "RELATED_CAREER", "NEW_CAREER_CANDIDATE", "INSUFFICIENT_EVIDENCE", "REJECT"]
    targetJobId: int | None = None
    categoryL1: str | None = None
    categoryL2: str | None = None
    reviewer: str = "local-admin"
    note: str | None = None


class CapabilityDecisionRequest(BaseModel):
    status: Literal["approved", "rejected", "needs_revision"]
    capabilityId: int | None = None
    reviewer: str = "local-admin"
    note: str | None = None


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(401, "管理员令牌无效")


def process_vectorization_run(run_id: int) -> None:
    provider = build_default_embedding_provider()
    VectorizationService(settings.database_path, provider).process_run(run_id)


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


@app.get(f"{settings.api_prefix}/health")
def health():
    fact_store = database.health()
    status = "ok" if fact_store["status"] == "ok" else "degraded"
    return {"status": status, "factStore": fact_store, "graphStore": "sqlite-fallback"}


@app.get(f"{settings.api_prefix}/data-overview/tables")
def data_overview_tables():
    return data_overview_repository.overview()


@app.get(f"{settings.api_prefix}/data-overview/tables/{{table_name}}")
def data_overview_table(
    table_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, alias="pageSize", ge=1, le=100),
):
    try:
        return data_overview_repository.table_detail(table_name, page, page_size)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@app.get(f"{settings.api_prefix}/jobs")
def list_jobs(
    q: str | None = Query(default=None, max_length=100),
    category: str | None = None,
    emerging: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
):
    return repository.list_jobs(q, category, emerging, page, page_size)


@app.get(f"{settings.api_prefix}/jobs/{{job_id}}")
def get_job(job_id: int):
    result = repository.get_job(job_id)
    if result is None:
        raise HTTPException(404, "岗位不存在")
    return result


@app.get(f"{settings.api_prefix}/skills")
def list_skills(
    q: str | None = Query(default=None, max_length=100),
    skill_type: str | None = Query(default=None, alias="skillType"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
):
    return repository.list_skills(q, skill_type, page, page_size)


@app.get(f"{settings.api_prefix}/graph/snapshots")
def list_snapshots():
    return repository.list_snapshots()


@app.get(f"{settings.api_prefix}/graph/overview")
def graph_overview(
    aggregation: str = Query(default="category", pattern="^(category|job|none)$"),
    max_nodes: int = Query(default=500, alias="maxNodes", ge=1, le=2000),
    max_edges: int = Query(default=1000, alias="maxEdges", ge=1, le=5000),
):
    return repository.overview(aggregation, max_nodes, max_edges)


@app.get(f"{settings.api_prefix}/graph/neighborhood")
def graph_neighborhood(
    node: str,
    depth: int = Query(default=1, ge=1, le=3),
    max_nodes: int = Query(default=80, alias="maxNodes", ge=1, le=500),
    max_edges: int = Query(default=160, alias="maxEdges", ge=1, le=1000),
):
    result = repository.neighborhood(node, depth, max_nodes, max_edges)
    if result is None:
        raise HTTPException(404, "图谱节点不存在")
    return result


@app.get(f"{settings.api_prefix}/evidence")
def list_evidence(
    mapping_id: int | None = Query(default=None, alias="mappingId", ge=1),
    job_id: int | None = Query(default=None, alias="jobId", ge=1),
    skill_id: int | None = Query(default=None, alias="skillId", ge=1),
    verified: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
):
    return repository.list_evidence(mapping_id, job_id, skill_id, verified, page, page_size)


@app.get(f"{settings.api_prefix}/evidence/{{evidence_id}}")
def get_evidence(evidence_id: int):
    result = repository.get_evidence(evidence_id)
    if result is None:
        raise HTTPException(404, "证据不存在")
    return result


@app.get(f"{settings.api_prefix}/capability-graph/tree")
def capability_graph_tree(
    root_id: int | None = Query(default=None, alias="rootId", ge=1),
    depth: int = Query(default=3, ge=1, le=4),
):
    try:
        return v4_repository.capability_graph(root_id, depth)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@app.get(f"{settings.api_prefix}/capabilities/search")
def capability_search(q: str = Query(min_length=1, max_length=100), limit: int = Query(default=20, ge=1, le=100)):
    return {"items": v4_repository.search_capabilities(q, limit)}


@app.get(f"{settings.api_prefix}/capabilities/{{capability_id}}")
def capability_detail(capability_id: int):
    result = v4_repository.capability_detail(capability_id)
    if result is None:
        raise HTTPException(404, "能力节点不存在")
    return result


@app.get(f"{settings.api_prefix}/capabilities/{{capability_id}}/relations")
def capability_relations(capability_id: int):
    return {"items": v4_repository.capability_relations(capability_id)}


@app.get(f"{settings.api_prefix}/capabilities/{{capability_id}}/jobs")
def capability_jobs(capability_id: int):
    return {"items": v4_repository.capability_jobs(capability_id)}


@app.get(f"{settings.api_prefix}/career-graph/overview")
def career_graph_overview(
    top_k: int = Query(default=4, alias="topK", ge=1, le=12),
    threshold: float = Query(default=0.25, ge=0, le=1),
):
    return v4_repository.career_graph(top_k, threshold)


@app.get(f"{settings.api_prefix}/career-graph/jobs/{{job_id}}")
def career_graph_job(job_id: int, top_k: int = Query(default=8, alias="topK", ge=1, le=20)):
    result = v4_repository.job_focus(job_id, top_k)
    if result is None:
        raise HTTPException(404, "职业不存在")
    return result


@app.get(f"{settings.api_prefix}/jobs/{{job_id}}/similarities")
def job_similarities(job_id: int, top_k: int = Query(default=8, alias="topK", ge=1, le=20)):
    result = v4_repository.job_focus(job_id, top_k)
    if result is None:
        raise HTTPException(404, "职业不存在")
    return {"job": result["job"], "snapshot": result["snapshot"], "items": result["neighbors"]}


@app.get(f"{settings.api_prefix}/job-similarities/{{job_a}}/{{job_b}}")
def job_similarity(job_a: int, job_b: int):
    result = v4_repository.similarity_detail(job_a, job_b)
    if result is None:
        raise HTTPException(404, "职业相似关系不存在")
    return result


@app.get(f"{settings.api_prefix}/career-communities")
def career_communities():
    return v4_repository.career_communities()


@app.post(f"{settings.api_prefix}/vectorization/runs", status_code=202)
def create_vectorization_run(
    request: VectorizationRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    payload = request.model_dump()
    run_id, created = v4_repository.create_run(payload, idempotency_key)
    if created and settings.inline_worker:
        background_tasks.add_task(process_vectorization_run, run_id)
    return {"runId": run_id, "status": "queued" if created else "existing", "created": created}


@app.get(f"{settings.api_prefix}/vectorization/runs/{{run_id}}")
def get_vectorization_run(run_id: int):
    result = v4_repository.run_result(run_id)
    if result is None:
        raise HTTPException(404, "向量任务不存在")
    return result


@app.get(f"{settings.api_prefix}/vectorization/runs/{{run_id}}/matches")
def get_vectorization_matches(run_id: int):
    result = v4_repository.run_result(run_id)
    if result is None:
        raise HTTPException(404, "向量任务不存在")
    return {"runId": run_id, "status": result["status"], "items": result["candidates"], "summary": result["resultSummary"]}


@app.post(f"{settings.api_prefix}/job-match-decisions", status_code=201)
def create_match_decision(request: MatchDecisionRequest, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    try:
        decision_id = v4_repository.decide_match(request.model_dump())
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except sqlite3.IntegrityError as error:
        raise HTTPException(409, "该任务已经完成审核") from error
    return {"decisionId": decision_id, "status": "recorded"}


@app.get(f"{settings.api_prefix}/capability-candidates")
def list_capability_candidates(status: str = Query(default="pending", pattern="^(pending|approved|rejected|needs_revision)$")):
    return {"items": v4_repository.capability_candidates(status)}


@app.post(f"{settings.api_prefix}/capability-candidates/{{candidate_id}}/decision")
def decide_capability_candidate(candidate_id: int, request: CapabilityDecisionRequest, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    try:
        v4_repository.decide_capability_candidate(candidate_id, request.model_dump())
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    return {"candidateId": candidate_id, "status": request.status}
