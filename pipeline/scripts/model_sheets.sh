#!/usr/bin/env bash
# Renders the 3D model contact sheets (Godot --scene=model_sheet) and pairs every cell with
# upstream's own sprite:  docs/gallery/pokemon-151-3d.png (front 3/4), pokemon-151-3d-back.png
# (the view the player's Pokemon is seen from in battle), characters-3d.png (+ -back).
#
#   UPSTREAM=/path/to/pokemon-claude-red GODOT_BIN=/opt/godot/godot4 pipeline/scripts/model_sheets.sh [WORK_DIR]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GODOT_BIN="${GODOT_BIN:-godot4}"
WORK="${1:-$(mktemp -d)}"
OUT="$ROOT/docs/gallery"
mkdir -p "$WORK/sprites" "$WORK/charsprites" "$OUT"

node "$ROOT/pipeline/scripts/bake_monsprites.js" "$WORK/sprites" 64 >/dev/null
node "$ROOT/pipeline/scripts/bake_charsprites.js" "$WORK/charsprites" >/dev/null
"$GODOT_BIN" --headless --path "$ROOT/godot" --import >/dev/null 2>&1 || true

sheet() {  # sheet OUT.png [model_sheet flags...]
  local out="$1"; shift
  xvfb-run -a -s "-screen 0 1280x1024x24" "$GODOT_BIN" --path "$ROOT/godot" --rendering-driver opengl3 \
    -- --screenshot="$out" --scene=model_sheet "$@" >"$WORK/godot.log" 2>&1 \
    || { echo "model_sheet failed:"; tail -20 "$WORK/godot.log"; exit 1; }
}

MON_IDS="$(python3 -c "import json;print(','.join(json.load(open('$ROOT/godot/assets/models/pokemon/manifest.json'))['generated']))")"
CHAR_IDS="$(python3 -c "import json;print(','.join(json.load(open('$ROOT/godot/assets/models/characters/manifest.json'))['sprites']))")"

sheet "$WORK/mon_front.png" --kind=pokemon --species="$MON_IDS" --cols=12 --cell=160
sheet "$WORK/mon_back.png" --kind=pokemon --species="$MON_IDS" --cols=12 --cell=160 --view=back
sheet "$WORK/chr_front.png" --kind=characters --species="$CHAR_IDS" --cols=10 --cell=180
sheet "$WORK/chr_back.png" --kind=characters --species="$CHAR_IDS" --cols=10 --cell=180 --view=back

C="$ROOT/pipeline/scripts/compose_model_sheet.py"
python3 "$C" "$WORK/mon_front.png" 12 160 "$WORK/sprites" front "$OUT/pokemon-151-3d.png" --ids "$MON_IDS" --out-cols 9
python3 "$C" "$WORK/mon_back.png" 12 160 "$WORK/sprites" back "$OUT/pokemon-151-3d-back.png" --ids "$MON_IDS" --out-cols 9
python3 "$C" "$WORK/chr_front.png" 10 180 "$WORK/charsprites" front "$OUT/characters-3d.png" --ids "$CHAR_IDS" --out-cols 8
python3 "$C" "$WORK/chr_back.png" 10 180 "$WORK/charsprites" back "$OUT/characters-3d-back.png" --ids "$CHAR_IDS" --out-cols 8
echo "sheets written to $OUT (work files in $WORK)"
