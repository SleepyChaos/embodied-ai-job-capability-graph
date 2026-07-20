from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.app.vectorization import (  # noqa: E402
    SentenceTransformerEmbeddingProvider,
    compose_embedding_text,
    load_raw_job,
    pack_vector,
    text_hash,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill BGE JD and career embeddings in v4")
    parser.add_argument("--database", type=Path, default=PROJECT_ROOT / "embodied_ai_jobs_v4.db")
    parser.add_argument("--model-dir", type=Path, default=PROJECT_ROOT / "models")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "database" / "v4_embedding_backfill_report.json")
    args = parser.parse_args()

    provider = SentenceTransformerEmbeddingProvider(args.model_dir)
    connection = sqlite3.connect(args.database, timeout=60)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    model = connection.execute("SELECT * FROM embedding_models WHERE model_code=?", (provider.model_code,)).fetchone()
    if model is None:
        raise RuntimeError("embedding model registry row is missing")
    model_id = int(model["id"])
    raw_ids = [int(row[0]) for row in connection.execute("SELECT id FROM raw_jd_documents ORDER BY id")]
    if args.limit:
        raw_ids = raw_ids[: args.limit]
    completed = 0
    failed = 0
    for offset in range(0, len(raw_ids), args.batch_size):
        batch_ids = raw_ids[offset:offset + args.batch_size]
        texts = []
        valid_ids = []
        for raw_id in batch_ids:
            try:
                texts.append(compose_embedding_text(load_raw_job(connection, raw_id)))
                valid_ids.append(raw_id)
            except Exception as error:
                failed += 1
                connection.execute(
                    "INSERT OR REPLACE INTO jd_embeddings(raw_jd_id,model_id,input_text_hash,dimensions,status,error_message) VALUES (?,?,?,?,?,?)",
                    (raw_id, model_id, text_hash(str(raw_id)), provider.dimensions, "failed", str(error)[:500]),
                )
        if texts:
            try:
                vectors = provider.encode(texts)
                with connection:
                    for raw_id, text, vector in zip(valid_ids, texts, vectors):
                        norm = math.sqrt(sum(value * value for value in vector))
                        connection.execute(
                            """
                            INSERT OR REPLACE INTO jd_embeddings(
                                raw_jd_id,model_id,input_text_hash,dimensions,vector_blob,vector_norm,status,error_message,computed_at
                            ) VALUES (?,?,?,?,?,?, 'ready',NULL,?)
                            """, (raw_id, model_id, text_hash(text), provider.dimensions, pack_vector(vector), norm, utc_now()),
                        )
                        completed += 1
            except Exception as error:
                failed += len(valid_ids)
                with connection:
                    for raw_id, text in zip(valid_ids, texts):
                        connection.execute(
                            "INSERT OR REPLACE INTO jd_embeddings(raw_jd_id,model_id,input_text_hash,dimensions,status,error_message) VALUES (?,?,?,?,?,?)",
                            (raw_id, model_id, text_hash(text), provider.dimensions, "failed", str(error)[:500]),
                        )
        print(f"embedded {min(offset + len(batch_ids), len(raw_ids))}/{len(raw_ids)}", flush=True)

    snapshot = connection.execute("SELECT id FROM graph_snapshots WHERE status='ready' ORDER BY snapshot_at DESC,id DESC LIMIT 1").fetchone()
    snapshot_id = int(snapshot["id"])
    career_vectors: defaultdict[int, list[np.ndarray]] = defaultdict(list)
    rows = connection.execute(
        """
        SELECT r.mapped_job_id,e.vector_blob,e.dimensions
        FROM raw_jd_documents r JOIN jd_embeddings e ON e.raw_jd_id=r.id
        LEFT JOIN job_posting_versions v ON v.raw_jd_id=r.id
        LEFT JOIN job_postings p ON p.id=v.posting_id
        WHERE r.mapped_job_id IS NOT NULL AND e.model_id=? AND e.status='ready'
          AND COALESCE(p.duplicate_of_id,0)=0
        """, (model_id,),
    ).fetchall()
    for row in rows:
        career_vectors[int(row["mapped_job_id"])].append(np.frombuffer(row["vector_blob"], dtype=np.float32))
    with connection:
        connection.execute("DELETE FROM career_embeddings WHERE snapshot_id=? AND model_id=?", (snapshot_id, model_id))
        for job_id, vectors in career_vectors.items():
            centroid = np.mean(np.stack(vectors), axis=0)
            norm = float(np.linalg.norm(centroid))
            if norm <= 0:
                continue
            centroid = centroid / norm
            connection.execute(
                """
                INSERT INTO career_embeddings(snapshot_id,job_id,model_id,dimensions,vector_blob,vector_norm,source_jd_count,calculation_version,computed_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """, (snapshot_id, job_id, model_id, provider.dimensions, centroid.astype(np.float32).tobytes(), 1.0, len(vectors), "career-centroid-v1", utc_now()),
            )
        connection.execute("UPDATE embedding_models SET status='ready' WHERE id=?", (model_id,))

    latest_run = connection.execute("SELECT id FROM job_similarity_runs WHERE snapshot_id=? ORDER BY id DESC LIMIT 1", (snapshot_id,)).fetchone()
    updated_edges = 0
    if latest_run:
        run_id = int(latest_run["id"])
        centroids = {int(r["job_id"]): np.frombuffer(r["vector_blob"], dtype=np.float32) for r in connection.execute("SELECT job_id,vector_blob FROM career_embeddings WHERE snapshot_id=? AND model_id=?", (snapshot_id, model_id))}
        similarities = connection.execute("SELECT * FROM job_similarities WHERE run_id=?", (run_id,)).fetchall()
        with connection:
            for row in similarities:
                a, b = int(row["job_a_id"]), int(row["job_b_id"])
                if a not in centroids or b not in centroids:
                    continue
                semantic = float(np.dot(centroids[a], centroids[b]))
                semantic = max(0.0, min(1.0, semantic))
                total = max(0.0, min(1.0, 0.75 * float(row["score_total"]) + 0.25 * semantic))
                band = "SAME_CAREER" if total >= 0.82 else "RELATED_CAREER" if total >= 0.62 else "WEAK_RELATED"
                connection.execute("UPDATE job_similarities SET score_total=?,algorithm_version='career-sim-v4-hybrid-bge' WHERE run_id=? AND job_a_id=? AND job_b_id=?", (total, run_id, a, b))
                connection.execute("UPDATE job_similarity_components SET semantic_score=?,decision_band=? WHERE run_id=? AND job_a_id=? AND job_b_id=?", (semantic, band, run_id, a, b))
                updated_edges += 1

    report = {
        "database": str(args.database.resolve()), "model": provider.model_name, "dimensions": provider.dimensions,
        "requestedJdCount": len(raw_ids), "readyJdCount": completed, "failedJdCount": failed,
        "careerEmbeddingCount": len(career_vectors), "updatedSimilarityEdges": updated_edges,
        "snapshotId": snapshot_id, "completedAt": utc_now(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    connection.close()


if __name__ == "__main__":
    main()
