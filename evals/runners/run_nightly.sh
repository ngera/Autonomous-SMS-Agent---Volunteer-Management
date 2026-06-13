#!/usr/bin/env bash
# Nightly full set — Layers 1-5. Target wall time ~8min.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="${REPO_ROOT}/backend:${PYTHONPATH:-}"

cd "${REPO_ROOT}"

inspect eval \
  evals/tasks/regex_routing.py \
  evals/tasks/intent_classification.py \
  evals/tasks/tool_call_correctness.py \
  evals/tasks/recruiter_plan_quality.py \
  evals/tasks/privacy_visibility.py \
  --model anthropic/claude-haiku-4-5 \
  --log-dir logs/nightly \
  "$@"
