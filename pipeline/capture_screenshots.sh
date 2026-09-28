#!/usr/bin/env bash
# Regenerates the full feature-parity screenshot gallery under docs/gallery/.
# Requires a Godot 4.7.2 binary (path via $GODOT_BIN, default "godot4") and
# Xvfb (same headless-with-a-display setup CI uses; see .github/workflows/ci.yml
# and Main.gd's `_maybe_capture_screenshot()` / `_setup_battle()` for the flags).
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

# --- Battle (refs 068-091, docs/claude-red-screenshots) -------------------
# Each move shot freezes the player's move animation at --vfx_t of its length
# (like upstream tools/vfxsheet.js); --player_maxhp picks the HP DV so the
# numbers match the reference. See Main.gd _setup_battle() for every flag.
vshot() { # basename player maxhp enemy move env vfx_t [extra flags]
  local name=$1 pl=$2 hp=$3 en=$4 mv=$5 env=$6 t=$7; shift 7
  shot "$name" --scene=battle --wait=0.3 --player="$pl" --player_level=50 --player_maxhp="$hp" \
    --enemy="$en" --level=50 --env="$env" --state=vfx --move="$mv" --vfx_t="$t" "$@"
}
vshot 068-battle-charizard-flamethrower CHARIZARD 140 BLASTOISE FLAMETHROWER grass 0.4
vshot 069-battle-pikachu-thunderbolt PIKACHU 105 GYARADOS THUNDERBOLT water 0.12
vshot 070-battle-blastoise-hydro_pump BLASTOISE 146 ARCANINE HYDRO_PUMP grass 0.4
vshot 071-battle-venusaur-solarbeam VENUSAUR 140 GOLEM SOLARBEAM grass 0.45
vshot 072-battle-alakazam-psychic ALAKAZAM 123 MACHAMP PSYCHIC_M grass 0.35
vshot 073-battle-gengar-night_shade GENGAR 121 ALAKAZAM NIGHT_SHADE grass 0.3 --time=night
vshot 074-battle-lapras-blizzard LAPRAS 195 DRAGONITE BLIZZARD ice 0.45
vshot 075-battle-dragonite-hyper_beam DRAGONITE 164 LAPRAS HYPER_BEAM grass 0.45
vshot 076-battle-jolteon-thunder JOLTEON 132 VAPOREON THUNDER grass 0.4
vshot 077-battle-machamp-submission MACHAMP 163 SNORLAX SUBMISSION grass 0.2
vshot 078-battle-arcanine-fire_blast ARCANINE 151 VENUSAUR FIRE_BLAST grass 0.55
vshot 079-battle-gyarados-surf GYARADOS 165 CHARIZARD SURF water 0.5
vshot 080-battle-snorlax-body_slam SNORLAX 231 MEWTWO BODY_SLAM grass 0.2
vshot 081-battle-mewtwo-psychic MEWTWO 180 MEW PSYCHIC_M grass 0.5
vshot 082-battle-nidoking-earthquake NIDOKING 141 RHYDON EARTHQUAKE grass 0.55
vshot 083-battle-scyther-swords_dance SCYTHER 140 PARASECT SWORDS_DANCE grass 0.2
vshot 084-battle-zapdos-drill_peck ZAPDOS 164 ARTICUNO DRILL_PECK ice 0.2
vshot 085-battle-moltres-fire_spin MOLTRES 150 ZAPDOS FIRE_SPIN grass 0.45
vshot 086-battle-butterfree-sleep_powder BUTTERFREE 131 BEEDRILL SLEEP_POWDER grass 0.3
vshot 087-battle-starmie-bubblebeam STARMIE 133 ELECTRODE BUBBLEBEAM water 0.35
shot 088-wild-pidgey-intro --scene=battle --wait=0.3 --player=SQUIRTLE --player_level=5 --enemy=PIDGEY --level=5 --env=grass --state=intro
shot 089-wild-pikachu-menu --scene=battle --wait=0.3 --player=SQUIRTLE --player_level=30 --player_maxhp=68 --enemy=PIKACHU --level=6 \
  --env=forest --state=message --text="SQUIRTLE used BUBBLE!" --enemy_hp=0.93
shot 090-wild-zubat-fight --scene=battle --wait=0.3 --player=BULBASAUR --player_level=30 --player_maxhp=74 --enemy=ZUBAT --level=10 \
  --env=cave --state=message --text="Wild ZUBAT used SUPERSONIC!"
shot 091-wild-missingno-menu --scene=battle --wait=0.3 --player=CHARIZARD --player_level=30 --player_maxhp=94 --enemy=MISSINGNO --level=80 \
  --env=beach --state=message --text="Wild MISSINGNO.'s ATTACK fell!" --waiting=1
# extra battle states (not in the reference set)
shot 200-battle-action-menu --scene=battle --wait=0.3 --player=PIKACHU --player_level=12 --enemy=RATTATA --level=6 --env=grass --state=menu
shot 201-battle-move-menu --scene=battle --wait=0.3 --player=CHARIZARD --player_level=50 --enemy=BLASTOISE --level=50 --env=grass --state=moves
shot 202-battle-trainer-brock --scene=battle --wait=4.0 --player=BLASTOISE --player_level=40 --trainer=BROCK:1 --env=gym --autoplay=1

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

echo "Done. $(ls "$OUT_DIR" | wc -l) screenshots in $OUT_DIR"
