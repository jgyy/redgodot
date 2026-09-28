#!/usr/bin/env bash
# Regenerates the full feature-parity screenshot gallery under docs/gallery/.
# Requires a Godot 4.7.2 binary (path via $GODOT_BIN, default "godot4") and
# Xvfb (same headless-with-a-display setup CI uses; see .github/workflows/ci.yml
# and Main.gd's `_maybe_capture_screenshot()` for what --scene=/--map=/--time=/
# --player=/--enemy=/--level=/--pc=/--auto_move=/--move_index= do).
set -euo pipefail

GODOT_BIN="${GODOT_BIN:-godot4}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/docs/gallery"
mkdir -p "$OUT_DIR"

shot() {
  local name="$1"; shift
  echo "[capture] $name"
  xvfb-run -a "$GODOT_BIN" --path "$ROOT_DIR/godot" --rendering-driver opengl3 \
    -- --screenshot="$OUT_DIR/$name.png" "$@" >/tmp/capture_screenshots.log 2>&1 \
    || { echo "FAILED: $name"; tail -30 /tmp/capture_screenshots.log; exit 1; }
}

# --- Core scenes -------------------------------------------------------
shot "01-title"      --scene=title      --wait=1.0
shot "02-intro"       --scene=intro      --wait=1.5
shot "03-overworld"   --scene=overworld  --wait=1.5

# --- Start menu suite ----------------------------------------------------
shot "10-start-menu"   --scene=start_menu   --wait=1.5
shot "11-party"        --scene=party        --wait=1.5
shot "12-summary"      --scene=summary      --wait=1.5
shot "13-bag"          --scene=bag          --wait=1.5
shot "14-pokedex"      --scene=pokedex      --wait=1.5
shot "15-trainer-card" --scene=trainer_card --wait=1.5
shot "16-town-map"     --scene=town_map     --wait=1.5
shot "17-options"      --scene=options      --wait=1.5
shot "18-dialogue"     --scene=dialogue     --wait=1.5 --text="Hello there! Welcome to the world of POKéMON!"

# --- Wild encounter states -----------------------------------------------
shot "20-wild-intro" --scene=battle --player=SQUIRTLE --enemy=PIDGEY  --level=4  --wait=0.4
shot "21-wild-menu"  --scene=battle --player=PIKACHU  --enemy=RATTATA --level=6  --wait=1.5
shot "22-wild-fight" --scene=battle --player=CHARMANDER --enemy=ZUBAT --level=10 --auto_move=1 --wait=0.38

# --- Trained battle matchups (menu state: proves real movesets/HP/levels) --
declare -a MATCHUPS=(
  "CHARIZARD:BLASTOISE" "VENUSAUR:GENGAR" "PIKACHU:RAICHU" "ALAKAZAM:MACHAMP"
  "GYARADOS:LAPRAS" "SNORLAX:DRAGONITE" "MEWTWO:MEW" "SCYTHER:PINSIR"
  "ARCANINE:NINETALES" "ZAPDOS:MOLTRES" "STARMIE:VAPOREON" "NIDOKING:NIDOQUEEN"
)
i=30
for pair in "${MATCHUPS[@]}"; do
  player="${pair%%:*}"; enemy="${pair##*:}"
  shot "$(printf '%02d' $i)-battle-${player,,}-vs-${enemy,,}" \
    --scene=battle --player="$player" --enemy="$enemy" --level=50 --player_level=50 --wait=1.5
  i=$((i+1))
done

# --- Move VFX in flight (auto-pressed, captured mid-animation) -----------
shot "50-vfx-fire"     --scene=battle --player=CHARIZARD --enemy=SQUIRTLE --level=50 --player_level=50 --auto_move=1 --move_index=2 --wait=0.38
shot "51-vfx-electric" --scene=battle --player=PIKACHU   --enemy=GEODUDE  --level=50 --player_level=50 --auto_move=1 --wait=0.38
shot "52-vfx-grass"    --scene=battle --player=VENUSAUR  --enemy=GENGAR   --level=50 --player_level=50 --auto_move=1 --wait=0.38

# --- Locations: day/night lighting cycle across Kanto --------------------
declare -a LOCATIONS=(
  "PalletTown:day" "PalletTown:night" "OaksLab:day" "RedsHouse1F:day"
  "ViridianCity:day" "ViridianPokecenter:day" "ViridianForest:day"
  "PewterCity:day" "PewterGym:day" "MtMoon1F:day"
  "CeruleanCity:day" "CeruleanCity:night" "CeruleanGym:day" "Route24:day"
  "VermilionCity:day" "VermilionGym:day" "SSAnne1F:day" "RockTunnel1F:day"
  "LavenderTown:night" "PokemonTower3F:day"
  "CeladonCity:day" "CeladonCity:night" "CeladonGym:day" "RocketHideoutB1F:day"
  "FuchsiaCity:day" "FuchsiaGym:day" "SafariZoneCenter:day"
  "SaffronCity:day" "SaffronGym:day" "SeafoamIslands1F:day"
  "CinnabarIsland:day" "CinnabarIsland:night" "CinnabarGym:day" "PokemonMansion1F:day"
  "PowerPlant:day" "VictoryRoad1F:day" "IndigoPlateau:dusk" "CeruleanCave1F:day"
  "Route1:day" "Route11:day"
)
i=60
for entry in "${LOCATIONS[@]}"; do
  map="${entry%%:*}"; time="${entry##*:}"
  w=$(python3 -c "import json;d=json.load(open('$ROOT_DIR/godot/data/mapdata.json'));m=d['maps']['$map'];print(m['w']//2)")
  h=$(python3 -c "import json;d=json.load(open('$ROOT_DIR/godot/data/mapdata.json'));m=d['maps']['$map'];print(m['h']//2)")
  shot "$(printf '%02d' $i)-${map,,}-${time}" --scene=overworld --map="$map" --pc="$w,$h" --time="$time" --wait=1.5
  i=$((i+1))
done

# --- 3D model contact sheets (every Pokemon / character next to upstream's sprite) ----
# docs/gallery/pokemon-151-3d.png, pokemon-151-3d-back.png, characters-3d.png, characters-3d-back.png
# (needs node + UPSTREAM=/path/to/pokemon-claude-red for the reference sprites)
if [ -n "${UPSTREAM:-}" ]; then
  GODOT_BIN="$GODOT_BIN" "$ROOT_DIR/pipeline/scripts/model_sheets.sh"
else
  echo "[capture] skipping model sheets (set UPSTREAM=/path/to/pokemon-claude-red)"
fi

echo "Done. $(ls "$OUT_DIR" | wc -l) screenshots in $OUT_DIR"
