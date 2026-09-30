#!/usr/bin/env bash
# Head close-ups of every species in N sheets:  pipeline/scripts/eye_batches.sh OUT_PREFIX [per_sheet=30] [cell=300] [cols=6] [extra model_sheet flags]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREFIX="$1"; PER="${2:-30}"; CELL="${3:-300}"; COLS="${4:-6}"; shift 4 2>/dev/null || shift $#
IDS=$(python3 -c "import json;print(' '.join(json.load(open('$ROOT/godot/assets/models/pokemon/manifest.json'))['generated']))")
set -- "$@"
i=0; n=0; batch=""
for id in $IDS; do
  batch="$batch,$id"; i=$((i+1))
  if [ "$i" -ge "$PER" ]; then
    n=$((n+1)); "$ROOT/pipeline/scripts/eye_sheet.sh" "${PREFIX}${n}.png" --species="${batch#,}" --cols="$COLS" --cell="$CELL" "$@" >/dev/null
    i=0; batch=""
  fi
done
if [ -n "$batch" ]; then n=$((n+1)); "$ROOT/pipeline/scripts/eye_sheet.sh" "${PREFIX}${n}.png" --species="${batch#,}" --cols="$COLS" --cell="$CELL" "$@" >/dev/null; fi
echo "wrote $n sheets ${PREFIX}*.png"
