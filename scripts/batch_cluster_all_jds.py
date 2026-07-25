from __future__ import annotations

import argparse
import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import urllib.request
import json

ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "data" / "embodied_ai_jobs_v4.db"
API_URL = "http://127.0.0.1:8000/api/v1/jd-pipeline/process"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("batch_cluster")


def get_pending_jd_ids(limit: int = 10) -> list[int]:
    """查询未完成能力提取或职业聚类的 JD ID 列表"""
    with sqlite3.connect(DATABASE_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id FROM career_units
            WHERE capability_extraction_status IN ('not_started', 'failed')
               OR career_clustering_status IN ('not_started', 'failed')
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [int(row[0]) for row in rows]


def get_remaining_count() -> int:
    """获取剩余未完成处理的总数据条数"""
    with sqlite3.connect(DATABASE_PATH) as conn:
        count = conn.execute(
            """
            SELECT COUNT(*) FROM career_units
            WHERE capability_extraction_status IN ('not_started', 'failed')
               OR career_clustering_status IN ('not_started', 'failed')
            """
        ).fetchone()[0]
        return int(count)


def process_single_jd(career_unit_id: int) -> dict:
    """发起单条 JD 的能力抽取+职业聚类请求"""
    payload = json.dumps({"careerUnitIds": [career_unit_id], "action": "both"}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=360) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"id": career_unit_id, "success": True, "response": data}
    except Exception as e:
        return {"id": career_unit_id, "success": False, "error": str(e)}


def run_batch(concurrency: int) -> None:
    pending_ids = get_pending_jd_ids(concurrency)
    if not pending_ids:
        logger.info("当前没有待处理的数据。")
        return

    logger.info(f"开始并发处理本批次 {len(pending_ids)} 条 JD，IDs: {pending_ids}")
    start_time = time.time()

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process_single_jd, cid): cid for cid in pending_ids}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            cid = res["id"]
            if res["success"]:
                items = res["response"].get("items", [])
                item_info = items[0] if items else {}
                cap = item_info.get("capability", "unknown")
                car = item_info.get("career", "unknown")
                logger.info(f"  [ID {cid}] 处理完成 - 能力提取: {cap}, 职业聚类: {car}")
            else:
                logger.error(f"  [ID {cid}] 处理失败 - 错误: {res['error']}")

    elapsed = time.time() - start_time
    logger.info(f"本批次处理完毕，耗时 {elapsed:.2f} 秒。")


def main() -> None:
    parser = argparse.ArgumentParser(description="定时并发批量聚类脚本")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数量 (默认 10)")
    parser.add_argument("--interval-seconds", type=int, default=300, help="轮询/批次间隔秒数 (默认 300 秒/5分钟)")
    parser.add_argument("--run-once", action="store_true", help="仅运行一轮后退出")
    args = parser.parse_args()

    logger.info("==================================================")
    logger.info("     具身智能 JD 全量并发聚类批处理任务启动      ")
    logger.info(f"   并发数: {args.concurrency} | 批次间隔: {args.interval_seconds} 秒 ({args.interval_seconds / 60:.1f} 分钟)")
    logger.info("==================================================")

    batch_index = 1
    while True:
        total_remaining = get_remaining_count()
        logger.info(f"\n--- [第 {batch_index} 轮] 当前数据库剩余待处理 JD: {total_remaining} 条 ---")
        if total_remaining == 0:
            logger.info("所有数据库中的 JD 均已完成至少一次聚类处理！脚本任务顺利结束。")
            break

        run_batch(args.concurrency)

        new_remaining = get_remaining_count()
        if new_remaining == 0:
            logger.info("所有数据库中的 JD 均已完成至少一次聚类处理！脚本任务顺利结束。")
            break

        if args.run_once:
            logger.info("单次执行模式，退出脚本。")
            break

        logger.info(f"按照设定策略，休眠 {args.interval_seconds} 秒（5 分钟）后进入下一轮批处理...")
        time.sleep(args.interval_seconds)
        batch_index += 1


if __name__ == "__main__":
    main()
