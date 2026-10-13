"""Operator-only entry point: uv run python -m app.sync_jobs arbeitnow."""

import argparse
import json

from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.services.arbeitnow import configured_registry
from app.services.job_sources import JobSyncService, SyncBlockedError


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync an explicitly enabled, authorized job source. No applications are submitted.")
    parser.add_argument("source", choices=["arbeitnow"])
    args = parser.parse_args()
    adapter = configured_registry().get(args.source)
    if adapter is None:
        parser.error("Source disabled. Set JOB_SOURCE_CONFIG=arbeitnow in the existing environment configuration.")
    with Session(get_engine(), autoflush=False) as db:
        try:
            count = JobSyncService().sync(db, adapter, complete_snapshot=True)
        except SyncBlockedError as error:
            print(json.dumps({"source": args.source, "status": "blocked", "message": str(error)}))
            return 1
        except Exception as error:
            # Keep SQL values and connection/provider secrets out of operator output.
            print(json.dumps({"source": args.source, "status": "failed", "error_type": type(error).__name__,
                              "message": "Sync did not complete. Check source health, connectivity and the six-hour cooldown; previous jobs were retained."}))
            return 1
    print(json.dumps({"source": args.source, "status": "success", "ingested": count, "complete_snapshot": adapter.snapshot_complete}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
