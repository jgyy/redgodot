#!/usr/bin/env bash
# Head close-up contact sheet of every Pokemon (model_sheet --focus=head), used to eyeball the eyes.
#   pipeline/scripts/eye_sheet.sh OUT.png [model_sheet flags, e.g. --species=A,B --cols=13 --cell=176]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$1"; shift
GODOT_BIN="${GODOT_BIN:-/opt/godot/godot4}"
LOG="$(mktemp)"
xvfb-run -a -s "-screen 0 1280x1024x24" "$GODOT_BIN" --path "$ROOT/godot" --rendering-driver opengl3 \
  -- --screenshot="$OUT" --scene=model_sheet --focus=head --cols=13 --cell=176 --yaw=-30 "$@" >"$LOG" 2>&1 \
  || { tail -20 "$LOG"; exit 1; }
tail -1 "$LOG"
