"""Dry-run a deterministic Daytona shard job plan JSON file."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ow_eval import run_daytona_shard_jobs_main


if __name__ == "__main__":
    raise SystemExit(run_daytona_shard_jobs_main(sys.argv[1:]))
