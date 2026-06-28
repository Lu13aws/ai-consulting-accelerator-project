#!/usr/bin/env python3
"""
Refresh the local Organizational Memory in one command.

Re-runs the three local ingests in sequence. All are idempotent (SHA-256 dedup), so re-running
is cheap and safe — only new/changed content is re-embedded:

  1. ingest_skills.py            toolkit SKILL.md           → app_name="skills"
  2. ingest_reports_local.py     S3 weekly reports (latest) → "radar"/"competitor"/"regulatory"
  3. ingest_projects_local.py    project READMEs            → app_name="projects"

This is the on-demand "freshness" tool for local dev. Real weekly automation is a deploy/prod
concern (the platform already runs the radar pipelines on a schedule and auto-indexes to RDS).
To schedule this locally, point Windows Task Scheduler at:
    uv run python scripts/refresh_memory.py

Usage:
    uv run python scripts/refresh_memory.py
    uv run python scripts/refresh_memory.py --dry-run     # pass through to each ingest
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

STEPS: list[tuple[str, list[str]]] = [
    ("skills", ["ingest_skills.py"]),
    ("reports (latest per type)", ["ingest_reports_local.py", "--latest"]),
    ("projects", ["ingest_projects_local.py"]),
]


def main() -> None:
    passthrough = sys.argv[1:]  # e.g. --dry-run
    failed = 0
    for label, args in STEPS:
        print(f"\n{'=' * 60}\n# refresh: {label}\n{'=' * 60}")
        result = subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:], *passthrough])
        if result.returncode != 0:
            failed += 1
            print(f"  [!] {label} exited with code {result.returncode}")
    print(f"\nOrganizational Memory refresh done — {len(STEPS) - failed}/{len(STEPS)} steps ok.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
