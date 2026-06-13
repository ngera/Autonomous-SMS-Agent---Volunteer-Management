#!/usr/bin/env bash
# Fast PR set — Layers 1, 2, 5. Target wall time ~60s.
# Gating: Layer 1 positive accuracy >= 0.95 + FP <= 0.02; Layer 2
# accuracy not down >2pp; Layer 5 zero misses.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="${REPO_ROOT}/backend:${PYTHONPATH:-}"

cd "${REPO_ROOT}"

inspect eval \
  evals/tasks/regex_routing.py \
  evals/tasks/intent_classification.py \
  evals/tasks/privacy_visibility.py \
  --model anthropic/claude-haiku-4-5 \
  --log-dir logs/pr \
  "$@"
