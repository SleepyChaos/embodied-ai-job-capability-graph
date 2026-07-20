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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from app.vectorization import (  # noqa: E402
    CapabilityLexicon,
    cosine_sparse,
    jaccard,
    load_raw_job,
    normalize_sparse,
)


SNAPSHOT_CODE = "v4-dictionary-backfill-001"
ALGORITHM_VERSION = "career-sim-v4-capability-backfill"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hierarchy_vectors(
    l3: dict[int, float],
    nodes: dict[int, sqlite3.Row],
) -> tuple[dict[int, float], dict[int, float]]:
    l2: dict[int, float] = {}
    l1: dict[int, float] = {}
    for capability_id, value in l3.items():
        parent_id = int(nodes[capability_id]["parent_id"])
        domain_id = int(nodes[parent_id]["parent_id"])
        l2[parent_id] = l2.get(parent_id, 0.0) + value
        l1[domain_id] = l1.get(domain_id, 0.0) + value
    return normalize_sparse(l2), normalize_sparse(l1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill v4 JD capability evidence and career profiles")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    database = args.database.resolve()
    now = utc_now()
    connection = sqlite3.connect(database, timeout=60)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")

    try:
        lexicon = CapabilityLexicon(connection)
        raw_rows = connection.execute(
            """
            SELECT id,source_id,mapped_job_id
            FROM raw_jd_documents
            WHERE clean_status<>'rejected'
            ORDER BY id
            """
        ).fetchall()
        with connection:
            connection.execute("DELETE FROM jd_capability_mentions")

        products: defaultdict[tuple[int, int], float] = defaultdict(lambda: 1.0)
        mention_counts: defaultdict[tuple[int, int], int] = defaultdict(int)
        jd_sets: defaultdict[tuple[int, int], set[int]] = defaultdict(set)
        source_sets: defaultdict[tuple[int, int], set[int]] = defaultdict(set)
        confidence_sums: defaultdict[tuple[int, int], float] = defaultdict(float)
        roles: defaultdict[tuple[int, int], set[str]] = defaultdict(set)
        mentioned_jobs: set[int] = set()
        evidence_count = 0

        for raw in raw_rows:
            raw_id = int(raw["id"])
            profile = lexicon.extract(load_raw_job(connection, raw_id))
            if raw["mapped_job_id"] is not None and profile.evidence:
                mentioned_jobs.add(int(raw["mapped_job_id"]))
            with connection:
                for evidence in profile.evidence:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO jd_capability_mentions(
                            raw_jd_id,capability_id,evidence_role,evidence_text,
                            extraction_method,role_weight,extraction_confidence,
                            mapping_confidence,evidence_weight,review_status
                        ) VALUES (?,?,?,?,?,?,?,?,?,'pending')
                        """,
                        (
                            raw_id,
                            evidence.capability_id,
                            evidence.evidence_role,
                            evidence.evidence_text,
                            "dictionary",
                            {
                                "required": 1.0,
                                "title": 0.95,
                                "responsibility": 0.80,
                                "preferred": 0.55,
                                "body": 0.30,
                            }[evidence.evidence_role],
                            evidence.extraction_confidence,
                            evidence.mapping_confidence,
                            evidence.evidence_weight,
                        ),
                    )
                    evidence_count += 1
                    if raw["mapped_job_id"] is None:
                        continue
                    key = (int(raw["mapped_job_id"]), evidence.capability_id)
                    products[key] *= 1.0 - evidence.evidence_weight
                    mention_counts[key] += 1
                    jd_sets[key].add(raw_id)
                    if raw["source_id"] is not None:
                        source_sets[key].add(int(raw["source_id"]))
                    confidence_sums[key] += evidence.extraction_confidence * evidence.mapping_confidence
                    roles[key].add(evidence.evidence_role)

        job_count = connection.execute("SELECT COUNT(*) FROM job_positions").fetchone()[0]
        df: defaultdict[int, int] = defaultdict(int)
        for job_id, capability_id in products:
            if products[(job_id, capability_id)] < 1.0:
                df[capability_id] += 1

        raw_weights: defaultdict[int, dict[int, float]] = defaultdict(dict)
        for (job_id, capability_id), product in products.items():
            aggregated = 1.0 - product
            idf = math.log((job_count + 1) / (df[capability_id] + 1)) + 1.0
            raw_weights[job_id][capability_id] = aggregated * idf
        normalized_weights = {job_id: normalize_sparse(values) for job_id, values in raw_weights.items()}

        with connection:
            existing = connection.execute(
                "SELECT id FROM graph_snapshots WHERE snapshot_code=?",
                (SNAPSHOT_CODE,),
            ).fetchone()
            if existing:
                snapshot_id = int(existing["id"])
                connection.execute("DELETE FROM job_capability_profiles WHERE snapshot_id=?", (snapshot_id,))
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO graph_snapshots(
                        snapshot_code,snapshot_name,snapshot_at,source_db_sha256,
                        status,is_baseline,metrics_json
                    ) VALUES (?,?,?,?, 'ready',0,'{}')
                    """,
                    (SNAPSHOT_CODE, "v4 全量JD能力词典回算", now, sha256_file(database)),
                )
                snapshot_id = int(cursor.lastrowid)

            profile_count = 0
            for job_id, values in normalized_weights.items():
                for capability_id, weight in values.items():
                    key = (job_id, capability_id)
                    role_set = roles[key]
                    importance = "required" if "required" in role_set else ("preferred" if "preferred" in role_set else "unspecified")
                    confidence = confidence_sums[key] / max(1, mention_counts[key])
                    connection.execute(
                        """
                        INSERT INTO job_capability_profiles(
                            snapshot_id,job_id,capability_id,importance,
                            mention_count,jd_count,source_count,weight,confidence,
                            evidence_count,calculation_version,review_status,valid_from
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending',?)
                        """,
                        (
                            snapshot_id,
                            job_id,
                            capability_id,
                            importance,
                            mention_counts[key],
                            len(jd_sets[key]),
                            len(source_sets[key]),
                            weight,
                            max(0.0, min(1.0, confidence)),
                            mention_counts[key],
                            "capability-profile-v4-dictionary-idf",
                            now,
                        ),
                    )
                    profile_count += 1

            connection.execute(
                "UPDATE graph_snapshots SET metrics_json=? WHERE id=?",
                (json.dumps({
                    "rawJdCount": len(raw_rows),
                    "profiledJobCount": len(normalized_weights),
                    "capabilityEvidenceCount": evidence_count,
                    "profileCount": profile_count,
                    "method": "dictionary+idf",
                }, ensure_ascii=False), snapshot_id),
            )

            old_run = connection.execute(
                "SELECT id FROM job_similarity_runs WHERE snapshot_id=? AND algorithm_version=?",
                (snapshot_id, ALGORITHM_VERSION),
            ).fetchone()
            if old_run:
                connection.execute("DELETE FROM job_similarity_runs WHERE id=?", (old_run["id"],))

            profiles: dict[int, dict[int, float]] = {}
            for row in connection.execute(
                "SELECT job_id,capability_id,weight FROM job_capability_profiles WHERE snapshot_id=?",
                (snapshot_id,),
            ):
                profiles.setdefault(int(row["job_id"]), {})[int(row["capability_id"])] = float(row["weight"])
            hierarchy = {
                job_id: hierarchy_vectors(values, lexicon.nodes)
                for job_id, values in profiles.items()
            }
            all_pairs: list[dict[str, object]] = []
            job_ids = sorted(profiles)
            for index, job_a in enumerate(job_ids):
                for job_b in job_ids[index + 1:]:
                    l3 = cosine_sparse(profiles[job_a], profiles[job_b])
                    l2 = cosine_sparse(hierarchy[job_a][0], hierarchy[job_b][0])
                    l1 = cosine_sparse(hierarchy[job_a][1], hierarchy[job_b][1])
                    hierarchy_score = 0.67 * l2 + 0.33 * l1
                    core_a = set(sorted(profiles[job_a], key=profiles[job_a].get, reverse=True)[:8])
                    core_b = set(sorted(profiles[job_b], key=profiles[job_b].get, reverse=True)[:8])
                    core = jaccard(core_a, core_b)
                    score = 0.70 * l3 + 0.20 * core + 0.10 * hierarchy_score
                    shared = sorted(
                        set(profiles[job_a]) & set(profiles[job_b]),
                        key=lambda capability_id: profiles[job_a][capability_id] * profiles[job_b][capability_id],
                        reverse=True,
                    )
                    all_pairs.append({
                        "a": job_a,
                        "b": job_b,
                        "l3": l3,
                        "l2": l2,
                        "l1": l1,
                        "hierarchy": hierarchy_score,
                        "core": core,
                        "score": score,
                        "shared": shared,
                    })

            by_job: defaultdict[int, list[dict[str, object]]] = defaultdict(list)
            for pair in all_pairs:
                by_job[int(pair["a"])].append(pair)
                by_job[int(pair["b"])].append(pair)
            retained_keys: set[tuple[int, int]] = set()
            for pairs in by_job.values():
                for pair in sorted(pairs, key=lambda item: float(item["score"]), reverse=True)[:4]:
                    if float(pair["score"]) >= 0.25:
                        retained_keys.add((int(pair["a"]), int(pair["b"])))
            retained = [pair for pair in all_pairs if (int(pair["a"]), int(pair["b"])) in retained_keys]

            run_cursor = connection.execute(
                """
                INSERT INTO job_similarity_runs(
                    snapshot_id,algorithm_version,config_json,job_count,
                    candidate_pairs,retained_pairs,status,warning
                ) VALUES (?,?,?,?,?,?,'succeeded',?)
                """,
                (
                    snapshot_id,
                    ALGORITHM_VERSION,
                    json.dumps({"topK": 4, "threshold": 0.25, "semantic": False}),
                    len(job_ids),
                    len(all_pairs),
                    len(retained),
                    "语义向量未参与本次全量回算；相似边等待人工抽样审核。",
                ),
            )
            run_id = int(run_cursor.lastrowid)
            for pair in retained:
                job_a = int(pair["a"])
                job_b = int(pair["b"])
                shared = list(pair["shared"])
                coverage_a = len(shared) / max(1, len(profiles[job_a]))
                coverage_b = len(shared) / max(1, len(profiles[job_b]))
                connection.execute(
                    """
                    INSERT INTO job_similarities(
                        run_id,snapshot_id,job_a_id,job_b_id,score_total,
                        capability_cosine,core_jaccard,hierarchy_score,
                        shared_capability_count,coverage_a,coverage_b,
                        algorithm_version,review_status
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'pending')
                    """,
                    (
                        run_id,
                        snapshot_id,
                        job_a,
                        job_b,
                        pair["score"],
                        pair["l3"],
                        pair["core"],
                        pair["hierarchy"],
                        len(shared),
                        min(1.0, coverage_a),
                        min(1.0, coverage_b),
                        ALGORITHM_VERSION,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO job_similarity_components(
                        run_id,job_a_id,job_b_id,semantic_score,title_score,
                        compatibility_score,threshold_version,decision_band
                    ) VALUES (?,?,?,NULL,0,1,'match-threshold-v1','capability_baseline')
                    """,
                    (run_id, job_a, job_b),
                )
                for rank, capability_id in enumerate(shared[:8], start=1):
                    contribution = profiles[job_a][capability_id] * profiles[job_b][capability_id]
                    connection.execute(
                        """
                        INSERT INTO job_similarity_explanations(
                            run_id,job_a_id,job_b_id,capability_id,contribution,rank_no
                        ) VALUES (?,?,?,?,?,?)
                        """,
                        (run_id, job_a, job_b, capability_id, min(1.0, contribution), rank),
                    )

        report = {
            "database": str(database),
            "snapshotCode": SNAPSHOT_CODE,
            "snapshotId": snapshot_id,
            "rawJdCount": len(raw_rows),
            "evidenceCount": connection.execute("SELECT COUNT(*) FROM jd_capability_mentions").fetchone()[0],
            "profiledJobCount": len(normalized_weights),
            "unprofiledJobCount": job_count - len(normalized_weights),
            "profileCount": connection.execute(
                "SELECT COUNT(*) FROM job_capability_profiles WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()[0],
            "similarityRunId": run_id,
            "candidatePairs": len(all_pairs),
            "retainedPairs": len(retained),
            "integrity": connection.execute("PRAGMA integrity_check").fetchone()[0],
            "foreignKeyErrors": [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")],
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
