#!/usr/bin/env bash
# Thin wrapper around `--scene=model_sheet` (any flags): pipeline/scripts/mon_sheet.sh OUT.png --species=A,B --cell=300
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$1"; shift
LOG="$(mktemp)"
xvfb-run -a -s "-screen 0 1280x1024x24" "${GODOT_BIN:-/opt/godot/godot4}" --path "$ROOT/godot" --rendering-driver opengl3 \
  -- --screenshot="$OUT" --scene=model_sheet "$@" >"$LOG" 2>&1 || { tail -20 "$LOG"; exit 1; }
tail -1 "$LOG"
