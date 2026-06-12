#!/usr/bin/env bash
# remote-setup.sh — bootstrap nightward in a remote/cloud Claude Code session.
#
# Creates an isolated venv, installs the project editable with dev extras
# (pytest + ruff + mcp), and verifies the push-gate (pytest -q && ruff check .).
#
# Usage:
#   bash scripts/remote-setup.sh            # install + verify gate
#   bash scripts/remote-setup.sh --no-verify  # install only (skip gate)
#
# Idempotent: re-running reuses the existing .venv.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERIFY=1
[ "${1:-}" = "--no-verify" ] && VERIFY=0

# --- Python (>=3.10 per pyproject) ---------------------------------------
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
echo ">> using interpreter: $("$PY" --version 2>&1) ($PY)"

# --- venv ----------------------------------------------------------------
if [ ! -d .venv ]; then
  echo ">> creating .venv"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- install -------------------------------------------------------------
echo ">> upgrading pip"
python -m pip install --quiet --upgrade pip
echo '>> installing nightward (editable) with [dev] extras'
pip install --quiet -e ".[dev]"   # dev already pulls in mcp

# --- verify gate ---------------------------------------------------------
if [ "$VERIFY" -eq 1 ]; then
  echo ">> verifying push-gate"
  pytest -q
  ruff check .
  echo ">> gate green — environment ready."
else
  echo ">> install complete (gate skipped)."
fi
