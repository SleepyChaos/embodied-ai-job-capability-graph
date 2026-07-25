from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "data" / "embodied_ai_jobs_v4.db"


def main():
    conn = sqlite3.connect(DATABASE_PATH)
    cap = conn.execute(
        "SELECT status, attempt_count, raw_response_json FROM capability_extraction_runs WHERE career_unit_id=10480 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    car = conn.execute(
        "SELECT status, attempt_count, raw_response_json FROM career_clustering_runs WHERE career_unit_id=10480 ORDER BY id DESC LIMIT 1"
    ).fetchone()

    print("==================== 全流程解析与诊断成果 ====================")
    print("=== 1. 能力抽取结果 ===")
    if cap and cap[2]:
        data = json.loads(cap[2])
        caps = data.get("capabilities", [])
        print(f"成功抽取能力项 {len(caps)} 条：")
        for idx, c in enumerate(caps, 1):
            print(f"{idx}. 规范名称: {c.get('proposed_canonical_name')}")
            print(f"   三段式诊断: {c.get('naming_diagnosis')}")
            print(f"   得分评估: {c.get('llm_assessment')}")
            print(f"   证据原文: {(c.get('evidence') or [{}])[0].get('text')}\n")

    print("=== 2. 职业聚类结果 ===")
    if car and car[2]:
        car_data = json.loads(car[2])
        print(f"拟定职业簇名称: {car_data.get('cluster_name')}")
        print(f"三段式取名诊断: {car_data.get('naming_diagnosis')}")
        print(f"方向分类: {car_data.get('direction')} -> {car_data.get('sub_direction')}")
        print(f"描述说明: {car_data.get('description')}")
        print(f"画像置信度: {car_data.get('profile_confidence')}, 分类置信度: {car_data.get('classification_confidence')}")
    else:
        print("职业聚类处理状态:", car[0] if car else "未开始")


if __name__ == "__main__":
    main()
