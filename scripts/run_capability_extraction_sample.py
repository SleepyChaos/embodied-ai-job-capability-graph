from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.config import load_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.llm_capability_service import CapabilityLLMService, DeepSeekClient  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the production LLM capability pipeline for selected untested JDs."
    )
    parser.add_argument("career_unit_ids", nargs="+", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    service = CapabilityLLMService(
        Database(settings.database_path),
        DeepSeekClient(
            settings.llm_api_key,
            settings.llm_base_url,
            settings.llm_model,
            settings.llm_timeout_seconds,
        ),
    )
    results = []
    for career_unit_id in args.career_unit_ids:
        try:
            result = service.extract_career_unit(career_unit_id, force=args.force)
            run = result["run"]
            results.append(
                {
                    "careerUnitId": career_unit_id,
                    "runId": run["id"],
                    "status": run["status"],
                    "attemptCount": run["attempt_count"],
                    "retryReason": run["retry_reason"],
                    "mentionCount": len(result["mentions"]),
                    "decisions": json.loads(run["automated_decision_summary"] or "{}"),
                }
            )
        except Exception as error:
            results.append(
                {
                    "careerUnitId": career_unit_id,
                    "status": "failed",
                    "error": str(error),
                }
            )
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    print(json.dumps({"items": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
