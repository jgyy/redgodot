#!/usr/bin/env bash
# Regenerate the rigged Pokemon glbs (+ eyes.json), then let Godot re-import and re-extract their textures.
#   SRC_ASSETS=/path/to/Pokemon-3D-api-assets pipeline/scripts/regen_pokemon.sh [--only A,B]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GODOT_BIN="${GODOT_BIN:-/opt/godot/godot4}"
if [ "$#" -eq 0 ]; then set -- --all --jobs 4; fi
python3 "$ROOT/pipeline/blender/gen_rigged_pokemon.py" -- "$@" >"${TMPDIR:-/tmp}/regen_pokemon.log" 2>&1 \
  || { tail -30 "${TMPDIR:-/tmp}/regen_pokemon.log"; exit 1; }
"$GODOT_BIN" --headless --path "$ROOT/godot" --import >/dev/null 2>&1 || true
echo "regenerated ($*)"
