from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from array import array
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Protocol, Sequence


ROLE_WEIGHTS = {
    "required": 1.00,
    "title": 0.95,
    "responsibility": 0.80,
    "preferred": 0.55,
    "body": 0.30,
}

MATCH_WEIGHTS = {
    "capability": 0.45,
    "semantic": 0.25,
    "core_jaccard": 0.15,
    "title": 0.10,
    "compatibility": 0.05,
}


def normalize_label(value: str | None) -> str:
    if not value:
        return ""
    return "".join(
        ch for ch in value.strip().casefold()
        if ch.isalnum() or ch in {"+", "#"} or "\u4e00" <= ch <= "\u9fff"
    )


def normalize_sparse(values: dict[int, float]) -> dict[int, float]:
    norm = math.sqrt(sum(value * value for value in values.values()))
    if norm <= 0:
        return {}
    return {key: value / norm for key, value in values.items() if value > 0}


def cosine_sparse(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    value = sum(weight * right.get(key, 0.0) for key, weight in left.items())
    return max(0.0, min(1.0, value))


def jaccard(left: set[int], right: set[int]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def pack_vector(values: Sequence[float]) -> bytes:
    return array("f", [float(value) for value in values]).tobytes()


def unpack_vector(blob: bytes) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    return list(values)


def dense_cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compose_embedding_text(job: dict[str, object]) -> str:
    return "\n".join(
        (
            f"岗位名称：{job.get('title') or ''}",
            f"岗位职责：{job.get('responsibilities') or ''}",
            f"任职要求：{job.get('requirements') or ''}",
            f"优先条件：{job.get('niceToHave') or job.get('nice_to_have') or ''}",
        )
    ).strip()


class EmbeddingUnavailable(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    model_code: str
    dimensions: int

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerEmbeddingProvider:
    model_code = "bge-small-zh-v1.5"
    model_name = "BAAI/bge-small-zh-v1.5"
    dimensions = 512

    def __init__(self, cache_dir: Path | None = None, local_files_only: bool = False) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise EmbeddingUnavailable("sentence-transformers is not installed") from error
        kwargs: dict[str, object] = {}
        local_model_dir = cache_dir / self.model_code if cache_dir else None
        model_reference = str(local_model_dir) if local_model_dir and (local_model_dir / "config.json").exists() else self.model_name
        if cache_dir and model_reference == self.model_name:
            kwargs["cache_folder"] = str(cache_dir)
        if local_files_only:
            kwargs["local_files_only"] = True
        try:
            self._model = SentenceTransformer(model_reference, **kwargs)
        except Exception as error:  # model loading has many provider-specific errors
            raise EmbeddingUnavailable(str(error)) from error

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        values = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(item) for item in row] for row in values]


@dataclass(frozen=True)
class CapabilityEvidence:
    capability_id: int
    capability_name: str
    evidence_role: str
    evidence_text: str
    extraction_confidence: float
    mapping_confidence: float
    evidence_weight: float


@dataclass(frozen=True)
class CapabilityProfile:
    l3: dict[int, float]
    l2: dict[int, float]
    l1: dict[int, float]
    evidence: list[CapabilityEvidence]


class CapabilityLexicon:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.nodes: dict[int, sqlite3.Row] = {
            int(row["id"]): row
            for row in connection.execute(
                "SELECT id,parent_id,capability_name,level,node_kind,confidence FROM capability_nodes WHERE status='active'"
            )
        }
        self.variant_targets: dict[int, int] = {
            int(row["source_capability_id"]): int(row["target_capability_id"])
            for row in connection.execute(
                "SELECT source_capability_id,target_capability_id FROM capability_relations WHERE relation_type='VARIANT_OF'"
            )
        }
        labels: list[tuple[str, str, int, float]] = []
        for node_id, row in self.nodes.items():
            if int(row["level"]) != 3:
                continue
            labels.append((str(row["capability_name"]), normalize_label(row["capability_name"]), node_id, float(row["confidence"])))
        for row in connection.execute(
            """
            SELECT a.alias_name,a.normalized_alias,a.capability_id,a.confidence
            FROM capability_aliases a
            JOIN capability_nodes c ON c.id=a.capability_id
            WHERE c.level=3 AND c.status='active' AND a.review_status<>'rejected'
            """
        ):
            labels.append((str(row["alias_name"]), str(row["normalized_alias"]), int(row["capability_id"]), float(row["confidence"])))
        unique: dict[tuple[str, int], tuple[str, str, int, float]] = {}
        for label in labels:
            unique[(label[1], label[2])] = label
        self.labels = sorted(unique.values(), key=lambda item: len(item[1]), reverse=True)

    def canonical_id(self, capability_id: int) -> int:
        seen: set[int] = set()
        current = capability_id
        while current in self.variant_targets and current not in seen:
            seen.add(current)
            current = self.variant_targets[current]
        return current

    @staticmethod
    def _contains(clause: str, normalized_clause: str, raw_label: str, normalized_label: str) -> bool:
        if not normalized_label:
            return False
        if raw_label.isascii():
            escaped = re.escape(raw_label)
            return re.search(rf"(?<![A-Za-z0-9+#]){escaped}(?![A-Za-z0-9+#])", clause, re.IGNORECASE) is not None
        return normalized_label in normalized_clause

    def extract(self, job: dict[str, object]) -> CapabilityProfile:
        sections = (
            ("title", str(job.get("title") or "")),
            ("responsibility", str(job.get("responsibilities") or "")),
            ("required", str(job.get("requirements") or "")),
            ("preferred", str(job.get("niceToHave") or job.get("nice_to_have") or "")),
            ("body", str(job.get("body") or "")),
        )
        evidences: list[CapabilityEvidence] = []
        seen: set[tuple[int, str, str]] = set()
        for role, text in sections:
            if not text.strip():
                continue
            clauses = [part.strip() for part in re.split(r"[\n\r。；;]+", text) if part.strip()]
            for clause in clauses:
                normalized_clause = normalize_label(clause)
                for raw_label, normalized, capability_id, mapping_confidence in self.labels:
                    if not self._contains(clause, normalized_clause, raw_label, normalized):
                        continue
                    canonical_id = self.canonical_id(capability_id)
                    key = (canonical_id, role, clause)
                    if key in seen:
                        continue
                    seen.add(key)
                    confidence = 0.98 if raw_label == self.nodes[capability_id]["capability_name"] else 0.90
                    weight = ROLE_WEIGHTS[role] * confidence * mapping_confidence
                    canonical = self.nodes[canonical_id]
                    evidences.append(CapabilityEvidence(
                        capability_id=canonical_id,
                        capability_name=str(canonical["capability_name"]),
                        evidence_role=role,
                        evidence_text=clause[:500],
                        extraction_confidence=confidence,
                        mapping_confidence=mapping_confidence,
                        evidence_weight=max(0.0, min(1.0, weight)),
                    ))

        products: dict[int, float] = {}
        for evidence in evidences:
            products[evidence.capability_id] = products.get(evidence.capability_id, 1.0) * (1.0 - evidence.evidence_weight)
        l3 = normalize_sparse({key: 1.0 - product for key, product in products.items()})
        l2_raw: dict[int, float] = {}
        l1_raw: dict[int, float] = {}
        for capability_id, value in l3.items():
            parent_id = int(self.nodes[capability_id]["parent_id"])
            domain_id = int(self.nodes[parent_id]["parent_id"])
            l2_raw[parent_id] = l2_raw.get(parent_id, 0.0) + value
            l1_raw[domain_id] = l1_raw.get(domain_id, 0.0) + value
        return CapabilityProfile(
            l3=l3,
            l2=normalize_sparse(l2_raw),
            l1=normalize_sparse(l1_raw),
            evidence=evidences,
        )


def load_raw_job(connection: sqlite3.Connection, raw_jd_id: int) -> dict[str, object]:
    row = connection.execute("SELECT * FROM raw_jd_documents WHERE id=?", (raw_jd_id,)).fetchone()
    if row is None:
        raise LookupError(f"raw JD not found: {raw_jd_id}")
    return {
        "company": row["company_name"],
        "title": row["raw_title"],
        "responsibilities": row["jd_responsibilities"],
        "requirements": row["jd_requirements"],
        "niceToHave": row["jd_nice_to_have"],
        "body": row["raw_content"],
        "location": row["city"] or row["province"],
        "seniority": row["experience_requirement"],
    }


def profile_from_rows(
    rows: Sequence[sqlite3.Row],
    nodes: dict[int, sqlite3.Row],
) -> CapabilityProfile:
    l3 = normalize_sparse({int(row["capability_id"]): float(row["weight"]) for row in rows})
    l2_raw: dict[int, float] = {}
    l1_raw: dict[int, float] = {}
    for capability_id, value in l3.items():
        node = nodes.get(capability_id)
        if node is None or node["parent_id"] is None:
            continue
        parent_id = int(node["parent_id"])
        parent = nodes.get(parent_id)
        if parent is None or parent["parent_id"] is None:
            continue
        domain_id = int(parent["parent_id"])
        l2_raw[parent_id] = l2_raw.get(parent_id, 0.0) + value
        l1_raw[domain_id] = l1_raw.get(domain_id, 0.0) + value
    return CapabilityProfile(l3, normalize_sparse(l2_raw), normalize_sparse(l1_raw), [])


def capability_similarity(query: CapabilityProfile, candidate: CapabilityProfile) -> tuple[float, float, float, float]:
    l3 = cosine_sparse(query.l3, candidate.l3)
    l2 = cosine_sparse(query.l2, candidate.l2)
    l1 = cosine_sparse(query.l1, candidate.l1)
    return 0.70 * l3 + 0.20 * l2 + 0.10 * l1, l3, l2, l1


def match_suggestion(score: float, l3: float, coverage: float, capability_count: int) -> str:
    if capability_count < 3 and score < 0.62:
        return "INSUFFICIENT_EVIDENCE"
    if score >= 0.82 and l3 >= 0.72 and coverage >= 0.50:
        return "SAME_CAREER"
    if score >= 0.62:
        return "RELATED_CAREER"
    return "NEW_CAREER_CANDIDATE"


class VectorizationService:
    def __init__(
        self,
        database_path: Path,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.database_path = database_path
        self.embedding_provider = embedding_provider

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def process_run(self, run_id: int) -> None:
        connection = self._connect()
        try:
            run = connection.execute("SELECT * FROM vectorization_runs WHERE id=?", (run_id,)).fetchone()
            if run is None:
                raise LookupError(f"vectorization run not found: {run_id}")
            if run["status"] in {"succeeded", "partial", "cancelled"}:
                return
            with connection:
                connection.execute(
                    """
                    UPDATE vectorization_runs
                    SET status='running',progress=0.05,attempt_count=attempt_count+1,
                        started_at=COALESCE(started_at,datetime('now')),updated_at=datetime('now'),error_message=NULL
                    WHERE id=?
                    """,
                    (run_id,),
                )

            payload = json.loads(run["input_json"])
            if run["source_type"] == "raw_jd":
                job = load_raw_job(connection, int(run["raw_jd_id"]))
            else:
                job = dict(payload.get("job") or {})
            lexicon = CapabilityLexicon(connection)
            query_profile = lexicon.extract(job)
            query_text = compose_embedding_text(job)
            semantic_vector: list[float] | None = None
            warnings: list[str] = []
            if self.embedding_provider:
                semantic_vector = self.embedding_provider.encode([query_text])[0]
            else:
                warnings.append("本地语义模型不可用，本次按能力画像、标题和结构化字段降级计算。")

            latest_snapshot = connection.execute(
                "SELECT id FROM graph_snapshots WHERE status='ready' ORDER BY snapshot_at DESC,id DESC LIMIT 1"
            ).fetchone()
            if latest_snapshot is None:
                raise RuntimeError("no ready graph snapshot")
            snapshot_id = int(latest_snapshot["id"])
            nodes = lexicon.nodes
            job_rows = connection.execute(
                """
                SELECT j.id,j.job_name,j.category_l1,j.category_l2,j.seniority_levels,
                       p.capability_id,p.weight
                FROM job_positions j
                LEFT JOIN job_capability_profiles p ON p.job_id=j.id AND p.snapshot_id=?
                ORDER BY j.id,p.weight DESC
                """,
                (snapshot_id,),
            ).fetchall()
            grouped: dict[int, list[sqlite3.Row]] = {}
            jobs: dict[int, sqlite3.Row] = {}
            for row in job_rows:
                job_id = int(row["id"])
                jobs[job_id] = row
                if row["capability_id"] is not None:
                    grouped.setdefault(job_id, []).append(row)

            career_dense: dict[int, list[float]] = {}
            if semantic_vector is not None:
                model = connection.execute(
                    "SELECT id FROM embedding_models WHERE model_code=?",
                    (self.embedding_provider.model_code,),
                ).fetchone()
                if model:
                    for row in connection.execute(
                        """
                        SELECT job_id,vector_blob FROM career_embeddings
                        WHERE snapshot_id=? AND model_id=?
                        """,
                        (snapshot_id, int(model["id"])),
                    ):
                        career_dense[int(row["job_id"])] = unpack_vector(row["vector_blob"])

            capability_names = {
                int(row["id"]): str(row["capability_name"])
                for row in connection.execute("SELECT id,capability_name FROM capability_nodes")
            }
            scores: list[dict[str, object]] = []
            for job_id, career_row in jobs.items():
                candidate_profile = profile_from_rows(grouped.get(job_id, []), nodes)
                cap_score, l3, l2, l1 = capability_similarity(query_profile, candidate_profile)
                query_core = {key for key, value in query_profile.l3.items() if value >= 0.20}
                candidate_core = {key for key, value in candidate_profile.l3.items() if value >= 0.20}
                core_score = jaccard(query_core, candidate_core)
                title_score = SequenceMatcher(
                    None,
                    normalize_label(str(job.get("title") or "")),
                    normalize_label(str(career_row["job_name"])),
                ).ratio()
                compatibility = 1.0
                semantic_score: float | None = None
                if semantic_vector is not None and job_id in career_dense:
                    semantic_score = dense_cosine(semantic_vector, career_dense[job_id])

                components: dict[str, float] = {
                    "capability": cap_score,
                    "core_jaccard": core_score,
                    "title": title_score,
                    "compatibility": compatibility,
                }
                if semantic_score is not None:
                    components["semantic"] = semantic_score
                active_weight = sum(MATCH_WEIGHTS[key] for key in components)
                total = sum(MATCH_WEIGHTS[key] * value for key, value in components.items()) / active_weight
                coverage = min(1.0, len(query_profile.l3) / 6.0)
                shared_ids = sorted(
                    set(query_profile.l3) & set(candidate_profile.l3),
                    key=lambda key: query_profile.l3[key] * candidate_profile.l3[key],
                    reverse=True,
                )
                missing_ids = sorted(
                    set(candidate_profile.l3) - set(query_profile.l3),
                    key=lambda key: candidate_profile.l3[key],
                    reverse=True,
                )
                new_ids = sorted(
                    set(query_profile.l3) - set(candidate_profile.l3),
                    key=lambda key: query_profile.l3[key],
                    reverse=True,
                )
                scores.append({
                    "job_id": job_id,
                    "job_name": career_row["job_name"],
                    "score": max(0.0, min(1.0, total)),
                    "capability": cap_score,
                    "l3": l3,
                    "l2": l2,
                    "l1": l1,
                    "semantic": semantic_score,
                    "core": core_score,
                    "title": title_score,
                    "compatibility": compatibility,
                    "coverage": coverage,
                    "shared": [capability_names[key] for key in shared_ids[:8]],
                    "missing": [capability_names[key] for key in missing_ids[:8]],
                    "new": [capability_names[key] for key in new_ids[:8]],
                })
            scores.sort(key=lambda item: (-float(item["score"]), str(item["job_name"])))
            top = scores[:10]

            with connection:
                connection.execute("DELETE FROM job_match_candidates WHERE run_id=?", (run_id,))
                for rank, item in enumerate(top, start=1):
                    suggestion = match_suggestion(
                        float(item["score"]),
                        float(item["l3"]),
                        float(item["coverage"]),
                        len(query_profile.l3),
                    )
                    connection.execute(
                        """
                        INSERT INTO job_match_candidates(
                            run_id,candidate_job_id,rank_no,suggestion,score_total,
                            capability_score,capability_l3_cosine,capability_l2_cosine,
                            capability_l1_cosine,semantic_score,core_jaccard,title_score,
                            compatibility_score,coverage,shared_capability_count,
                            threshold_version,explanation_json
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            run_id,
                            item["job_id"],
                            rank,
                            suggestion,
                            item["score"],
                            item["capability"],
                            item["l3"],
                            item["l2"],
                            item["l1"],
                            item["semantic"],
                            item["core"],
                            item["title"],
                            item["compatibility"],
                            item["coverage"],
                            len(item["shared"]),
                            "match-threshold-v1",
                            json.dumps({
                                "sharedCapabilities": item["shared"],
                                "missingCapabilities": item["missing"],
                                "newCapabilities": item["new"],
                            }, ensure_ascii=False),
                        ),
                    )
                domain_summary = []
                for domain_id, weight in sorted(query_profile.l1.items(), key=lambda item: item[1], reverse=True):
                    domain_summary.append({
                        "id": domain_id,
                        "name": nodes[domain_id]["capability_name"],
                        "weight": weight,
                    })
                payload["resultSummary"] = {
                    "domainVector": domain_summary,
                    "topCapabilities": [
                        {
                            "id": capability_id,
                            "name": capability_names[capability_id],
                            "weight": weight,
                        }
                        for capability_id, weight in sorted(query_profile.l3.items(), key=lambda item: item[1], reverse=True)[:15]
                    ],
                    "evidenceCount": len(query_profile.evidence),
                }
                connection.execute(
                    """
                    UPDATE vectorization_runs
                    SET input_json=?,status=?,semantic_available=?,capability_count=?,
                        candidate_count=?,progress=1,warning_json=?,completed_at=datetime('now'),
                        updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (
                        json.dumps(payload, ensure_ascii=False),
                        "succeeded" if semantic_vector is not None else "partial",
                        1 if semantic_vector is not None else 0,
                        len(query_profile.l3),
                        len(top),
                        json.dumps(warnings, ensure_ascii=False),
                        run_id,
                    ),
                )
        except Exception as error:
            with connection:
                connection.execute(
                    """
                    UPDATE vectorization_runs
                    SET status='failed',error_message=?,completed_at=datetime('now'),updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (str(error)[:1000], run_id),
                )
            raise
        finally:
            connection.close()


def build_default_embedding_provider() -> EmbeddingProvider | None:
    if os.getenv("EMBODIED_DISABLE_EMBEDDINGS", "0") == "1":
        return None
    cache = os.getenv("EMBODIED_MODEL_DIR")
    local_only = os.getenv("EMBODIED_MODEL_LOCAL_ONLY", "0") == "1"
    cache_path = Path(cache).resolve() if cache else Path(__file__).resolve().parents[3] / "models"
    if local_only and not any(cache_path.rglob("model.safetensors")) and not any(cache_path.rglob("pytorch_model.bin")):
        return None
    try:
        return SentenceTransformerEmbeddingProvider(
            cache_path,
            local_files_only=local_only,
        )
    except EmbeddingUnavailable:
        return None
