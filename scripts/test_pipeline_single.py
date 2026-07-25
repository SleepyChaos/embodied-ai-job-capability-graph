from __future__ import annotations

import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import Database
from app.config import load_settings
from app.llm_capability_service import CapabilityLLMService, DeepSeekClient
from app.career_clustering_service import CareerClusteringService


def main():
    settings = load_settings()
    db_path = (ROOT / "data" / "embodied_ai_jobs_v4.db").resolve()
    db = Database(db_path)
    client = DeepSeekClient(
        settings.llm_api_key,
        settings.llm_base_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
    )
    cap_service = CapabilityLLMService(db, client)
    car_service = CareerClusteringService(db, client)

    job_id = 10480
    print(f"=== 开始全流程测试全新岗位 (ID: {job_id}) ===")
    start_t = time.time()

    print("1. 正在执行能力抽取 (DeepSeek-v4-pro + 三段式诊断)...")
    cap_res = cap_service.extract_career_unit(job_id, force=True)
    cap_status = cap_res.get("run", {}).get("status")
    cap_attempts = cap_res.get("run", {}).get("attempt_count")
    print(f"   能力抽取完成，耗时 {time.time() - start_t:.1f} 秒，状态: {cap_status}，尝试次数: {cap_attempts}")

    t1 = time.time()
    print("2. 正在执行职业聚类 (DeepSeek-v4-pro + Self-Refine 反馈重试)...")
    car_res = car_service.cluster_career_unit(job_id, force=True)
    car_status = car_res.get("run", {}).get("status")
    car_attempts = car_res.get("run", {}).get("attempt_count")
    print(f"   职业聚类完成，耗时 {time.time() - t1:.1f} 秒，状态: {car_status}，尝试次数: {car_attempts}")

    print("\n==================== 📊 全流程解析与诊断成果 ====================")
    capabilities_detail = []
    for c in cap_res.get("extractedCapabilities", []):
        capabilities_detail.append({
            "proposedCanonicalName": c.get("proposedCanonicalName"),
            "namingDiagnosis": c.get("namingDiagnosis"),
            "confidence": f"抽取={c.get('llmAssessment', {}).get('extractionConfidence')}, 分类={c.get('llmAssessment', {}).get('classificationConfidence')}"
        })

    cluster_info = car_res.get("candidate") or car_res.get("cluster") or {}
    raw_response = car_res.get("run", {}).get("rawResponse") or {}

    output = {
        "jobId": job_id,
        "totalElapsedSeconds": round(time.time() - start_t, 2),
        "capabilities": capabilities_detail,
        "clusterResult": {
            "clusterName": cluster_info.get("name") or cluster_info.get("clusterName") or raw_response.get("cluster_name"),
            "namingDiagnosis": cluster_info.get("namingDiagnosis") or raw_response.get("naming_diagnosis"),
            "direction": cluster_info.get("directionName") or (raw_response.get("direction") or {}).get("name"),
            "subDirection": cluster_info.get("subDirectionName") or (raw_response.get("sub_direction") or {}).get("name"),
            "reasoning": cluster_info.get("reasoning") or raw_response.get("reasoning"),
            "attemptCount": car_res.get("run", {}).get("attemptCount"),
        }
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
