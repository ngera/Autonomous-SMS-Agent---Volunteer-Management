"""Production-replay harvester.

Pulls a stratified weekly sample from agent_call_log + conversation,
redacts PII, drops the result under
`evals/datasets/production_replay/YYYY-WW.jsonl`.

Run weekly via cron OR on-demand:

    PYTHONPATH=backend python evals/runners/harvest_production.py

Stratification (per the plan):
  - 30 successful volunteer signups
  - 10 admin command threads
  - 10 conversations that hit Sonnet (the long tail)
  - 5  conversations with thumbs_down (hallucination flags)

PII redaction:
  - phone +1XXXXXXXXXX -> +1555-***-NNNN  (last 4 swapped to sequence)
  - first/last names    -> Volunteer N

Phase 2 will plug into the real DB. This stub writes a tiny synthetic
sample so weekly runs at least exercise the eval plumbing.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

OUT_DIR = REPO_ROOT / "evals" / "datasets" / "production_replay"


def _iso_week_tag(now: _dt.date | None = None) -> str:
    now = now or _dt.date.today()
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _synthetic_sample() -> list[dict]:
    return [
        {
            "id": "stub-001",
            "input": "is the food drive saturday open",
            "target": "ok",
            "metadata": {
                "historical_reply": "Yes — saturday 9-12. Want to sign up?",
                "category": "successful_signup",
            },
        },
        {
            "id": "stub-002",
            "input": "start planning for the gala",
            "target": "ok",
            "metadata": {
                "historical_reply": "Drafting muster plan for the gala. Hold on.",
                "category": "admin_command",
            },
        },
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = _synthetic_sample()
    out = OUT_DIR / f"{_iso_week_tag()}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for row in sample:
            fh.write(json.dumps(row) + "\n")
    print(f"Wrote {len(sample)} samples to {out}")


if __name__ == "__main__":
    main()
