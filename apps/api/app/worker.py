from __future__ import annotations

import argparse
import socket
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from .config import load_settings
from .vectorization import VectorizationService, build_default_embedding_provider


def claim(database_path, owner: str) -> int | None:
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=10000")
    try:
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(minutes=15)).isoformat(timespec="seconds")
        with connection:
            row = connection.execute(
                """
                SELECT id FROM vectorization_runs
                WHERE status='queued' OR (status='running' AND lease_expires_at IS NOT NULL AND lease_expires_at<?)
                ORDER BY created_at,id LIMIT 1
                """, (now.isoformat(timespec="seconds"),),
            ).fetchone()
            if row is None:
                return None
            run_id = int(row["id"])
            updated = connection.execute(
                """
                UPDATE vectorization_runs SET status='running',lease_owner=?,lease_expires_at=?,updated_at=datetime('now')
                WHERE id=? AND (status='queued' OR lease_expires_at<?)
                """, (owner, expires, run_id, now.isoformat(timespec="seconds")),
            ).rowcount
            return run_id if updated else None
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-process SQLite vectorization worker")
    parser.add_argument("--once", action="store_true", help="Exit when the queue is empty")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    settings = load_settings()
    owner = f"{socket.gethostname()}:{socket.getfqdn()}"
    provider = build_default_embedding_provider()
    service = VectorizationService(settings.database_path, provider)
    while True:
        run_id = claim(settings.database_path, owner)
        if run_id is None:
            if args.once:
                return
            time.sleep(max(0.2, args.poll_seconds))
            continue
        try:
            service.process_run(run_id)
        except Exception as error:
            print(f"run {run_id} failed: {error}", flush=True)
        else:
            print(f"run {run_id} completed", flush=True)


if __name__ == "__main__":
    main()
