#!/bin/sh
# Compose PYTHONPATH from sibling source checkouts (no pip, no venv, no installs).
# Usage: . scripts/organism_env.sh [repo-root]   (default ~/neuruh-repos/NeuruhAI)
ROOT="${1:-$HOME/neuruh-repos/NeuruhAI}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PP="$HERE/src"
for r in neuruh-capability-registry neuruh-policy-gate neuruh-governed-exec neuruh-agent-run-manifest agent-receipt \
         neuruh-inference-health neuruh-outcome-record neuruh-outcome-calibration-ledger neuruh-learning-update-proposal \
         neuruh-promotion-gate neuruh-canonical-state-revision-authorization-contract \
         neuruh-canonical-state-revision-receipt neuruh-canonical-state-revision-ledger \
         neuruh-effective-canonical-state-resolver; do
  [ -d "$ROOT/$r/src" ] && PP="$PP:$ROOT/$r/src"
done
export PYTHONPATH="$PP"
export PYTHONDONTWRITEBYTECODE=1
echo "PYTHONPATH composed from $ROOT ($(echo "$PP" | tr ':' '\n' | wc -l | tr -d ' ') entries)"
