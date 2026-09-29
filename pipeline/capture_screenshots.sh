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

# --- Title / intro / menus / dialogue (UI suite) --------------------------
# Pairs with docs/claude-red-screenshots/{001,002,092-100}-*.png. Menus use the
# reference save (--save=showcase: RED, 6-mon party, 126/75 dex, 5 badges).
shot "001-title-screen" --scene=title --title_t=100 --wait=1.5
shot "002-intro"        --scene=intro --intro_frame=505 --intro_hold=1 --wait=1.0
shot "092-start-menu"   --scene=start_menu   --save=showcase --time=night --wait=1.5
shot "093-party"        --scene=party        --save=showcase --wait=1.5
shot "094-summary"      --scene=summary      --save=showcase --wait=1.5
shot "095-bag"          --scene=bag          --save=showcase --wait=1.5
shot "096-pokedex"      --scene=pokedex      --save=showcase --wait=1.5
shot "097-trainer-card" --scene=trainer_card --save=showcase --wait=1.5
shot "098-town-map"     --scene=town_map     --save=showcase --wait=1.5
shot "099-options"      --scene=options      --save=showcase --time=night --wait=1.5
shot "100-dialogue"     --scene=dialogue     --save=showcase --time=night --wait=1.5 \
  --text="Welcome to the world of POKéMON! Every pixel here was drawn by code."

# --- Story autoload: Poké Mart (pc.js G.mart menu coords + quantity picker) ---
# No upstream reference image; these check Story's PxCanvas overlays/coords.
shot "story-mart-menu"     --scene=story_mart --step=menu     --wait=2.5
shot "story-mart-quantity" --scene=story_mart --step=quantity --wait=2.0

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
vshot 073-battle-gengar-night_shade GENGAR 121 ALAKAZAM NIGHT_SHADE grass 0.3
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

# --- Overworld locations (refs 003-067, docs/claude-red-screenshots) -----------------
# Same basename as the reference. The player stands where the reference was taken (it is centred);
# --player picks the walking partner seen in the shot (--follower=none: none visible), --story=off
# shows the map without running its story enter scripts, --flash=1 = FLASH already used (Rock Tunnel).
# Maps must be baked first (pipeline/scripts/bake_maps.js) and imported (godot4 --headless --import).
shot "003-PalletTown" --scene=overworld --map=PalletTown --pc=9,8 --time=day --facing=down --player=PIKACHU --story=off --wait=1.5
shot "004-PalletTown-night" --scene=overworld --map=PalletTown --pc=9,8 --time=night --facing=down --player=BULBASAUR --story=off --wait=1.5
shot "005-RedsHouse2F" --scene=overworld --map=RedsHouse2F --pc=4,4 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "006-OaksLab" --scene=overworld --map=OaksLab --pc=5,6 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "007-Route1" --scene=overworld --map=Route1 --pc=10,18 --time=day --facing=down --player=CHARMANDER --story=off --wait=1.5
shot "008-ViridianCity" --scene=overworld --map=ViridianCity --pc=20,18 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "009-ViridianPokecenter" --scene=overworld --map=ViridianPokecenter --pc=7,4 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "010-Route22-dusk" --scene=overworld --map=Route22 --pc=20,9 --time=dusk --facing=down --player=CATERPIE --story=off --wait=1.5
shot "011-ViridianForest" --scene=overworld --map=ViridianForest --pc=12,19 --time=day --facing=down --player=PIDGEY --story=off --wait=1.5
shot "012-PewterCity" --scene=overworld --map=PewterCity --pc=20,18 --time=day --facing=down --player=GEODUDE --story=off --wait=1.5
shot "013-PewterGym" --scene=overworld --map=PewterGym --pc=4,6 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "014-Route3" --scene=overworld --map=Route3 --pc=35,9 --time=day --facing=down --player=NIDORAN_M --story=off --wait=1.5
shot "015-MtMoon1F" --scene=overworld --map=MtMoon1F --pc=20,18 --time=day --facing=down --player=CLEFAIRY --story=off --wait=1.5
shot "016-Route4-dusk" --scene=overworld --map=Route4 --pc=44,8 --time=dusk --facing=down --player=EKANS --story=off --wait=1.5
shot "017-CeruleanCity" --scene=overworld --map=CeruleanCity --pc=20,18 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "018-CeruleanCity-night" --scene=overworld --map=CeruleanCity --pc=20,18 --time=night --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "019-CeruleanGym" --scene=overworld --map=CeruleanGym --pc=5,7 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "020-Route24" --scene=overworld --map=Route24 --pc=10,18 --time=day --facing=down --player=SPEAROW --story=off --wait=1.5
shot "021-Route25-dusk" --scene=overworld --map=Route25 --pc=30,9 --time=dusk --facing=down --player=PIKACHU --story=off --wait=1.5
shot "022-Route5" --scene=overworld --map=Route5 --pc=9,17 --time=day --facing=down --player=PIDGEY --story=off --wait=1.5
shot "023-SaffronCity" --scene=overworld --map=SaffronCity --pc=24,14 --time=day --facing=down --player=FEAROW --story=off --wait=1.5
shot "024-SaffronCity-night" --scene=overworld --map=SaffronCity --pc=24,14 --time=night --facing=down --player=FEAROW --story=off --wait=1.5
shot "025-VermilionCity" --scene=overworld --map=VermilionCity --pc=20,18 --time=day --facing=down --player=WARTORTLE --story=off --wait=1.5
shot "026-VermilionCity-night" --scene=overworld --map=VermilionCity --pc=20,18 --time=day --facing=down --player=PIDGEOTTO --story=off --wait=1.5
shot "027-VermilionDock" --scene=overworld --map=VermilionDock --pc=14,2 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "028-SSAnneBow-dusk" --scene=overworld --map=SSAnneBow --pc=10,7 --time=dusk --facing=down --player=POLIWAG --story=off --wait=1.5
shot "029-VermilionGym" --scene=overworld --map=VermilionGym --pc=4,8 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "030-Route9" --scene=overworld --map=Route9 --pc=29,8 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "031-RockTunnel1F" --scene=overworld --map=RockTunnel1F --pc=20,18 --time=day --facing=down --player=ONIX --flash=1 --story=off --wait=1.5
shot "032-LavenderTown" --scene=overworld --map=LavenderTown --pc=10,9 --time=day --facing=down --player=HAUNTER --story=off --wait=1.5
shot "033-LavenderTown-night" --scene=overworld --map=LavenderTown --pc=10,9 --time=night --facing=down --player=HAUNTER --story=off --wait=1.5
shot "034-PokemonTower6F" --scene=overworld --map=PokemonTower6F --pc=9,8 --time=day --facing=down --player=GENGAR --story=off --wait=1.5
shot "035-Route8" --scene=overworld --map=Route8 --pc=30,9 --time=day --facing=down --player=PONYTA --story=off --wait=1.5
shot "036-CeladonCity" --scene=overworld --map=CeladonCity --pc=24,17 --time=day --facing=down --player=VILEPLUME --story=off --wait=1.5
shot "037-CeladonCity-night" --scene=overworld --map=CeladonCity --pc=24,17 --time=night --facing=down --player=VILEPLUME --story=off --wait=1.5
shot "038-CeladonMartRoof-dusk" --scene=overworld --map=CeladonMartRoof --pc=10,4 --time=dusk --facing=down --player=DRAGONAIR --story=off --wait=1.5
shot "039-CeladonGym" --scene=overworld --map=CeladonGym --pc=5,9 --time=day --facing=down --player=NIDOQUEEN --story=off --wait=1.5
shot "040-GameCorner" --scene=overworld --map=GameCorner --pc=10,9 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "041-RocketHideoutB1F" --scene=overworld --map=RocketHideoutB1F --pc=14,13 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "042-Route12" --scene=overworld --map=Route12 --pc=9,53 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "043-Route15-dusk" --scene=overworld --map=Route15 --pc=30,9 --time=dusk --facing=down --player=SCYTHER --story=off --wait=1.5
shot "044-FuchsiaCity" --scene=overworld --map=FuchsiaCity --pc=20,18 --time=day --facing=down --player=VENONAT --story=off --wait=1.5
shot "045-FuchsiaCity-night" --scene=overworld --map=FuchsiaCity --pc=20,18 --time=night --facing=down --player=KANGASKHAN --story=off --wait=1.5
shot "046-SafariZoneCenter" --scene=overworld --map=SafariZoneCenter --pc=14,14 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "047-SafariZoneEast" --scene=overworld --map=SafariZoneEast --pc=15,13 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "048-FuchsiaGym" --scene=overworld --map=FuchsiaGym --pc=5,9 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "049-Route18" --scene=overworld --map=Route18 --pc=25,9 --time=day --facing=down --player=DODRIO --story=off --wait=1.5
shot "050-SilphCo11F" --scene=overworld --map=SilphCo11F --pc=9,9 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "051-SaffronGym" --scene=overworld --map=SaffronGym --pc=10,9 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "052-FightingDojo" --scene=overworld --map=FightingDojo --pc=5,6 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "053-Route19" --scene=overworld --map=Route19 --pc=4,9 --time=day --facing=down --player=LAPRAS --story=off --wait=1.5
shot "054-SeafoamIslands1F" --scene=overworld --map=SeafoamIslands1F --pc=15,9 --time=day --facing=down --player=DEWGONG --story=off --wait=1.5
shot "055-SeafoamIslandsB4F" --scene=overworld --map=SeafoamIslandsB4F --pc=14,8 --time=day --facing=down --player=DEWGONG --story=off --wait=1.5
shot "056-CinnabarIsland" --scene=overworld --map=CinnabarIsland --pc=9,10 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "057-CinnabarIsland-night" --scene=overworld --map=CinnabarIsland --pc=9,10 --time=night --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "058-PokemonMansion1F" --scene=overworld --map=PokemonMansion1F --pc=15,14 --time=day --facing=down --player=PIKACHU --follower=none --wait=1.5
shot "059-CinnabarGym" --scene=overworld --map=CinnabarGym --pc=10,9 --time=day --facing=down --player=PIKACHU --follower=none --wait=1.5
shot "060-PowerPlant" --scene=overworld --map=PowerPlant --pc=20,19 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "061-Route23" --scene=overworld --map=Route23 --pc=9,71 --time=day --facing=down --player=KABUTO --story=off --wait=1.5
shot "062-VictoryRoad1F" --scene=overworld --map=VictoryRoad1F --pc=9,8 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "063-IndigoPlateau-dusk" --scene=overworld --map=IndigoPlateau --pc=10,9 --time=dusk --facing=down --player=CHARIZARD --story=off --wait=1.5
shot "064-LoreleisRoom" --scene=overworld --map=LoreleisRoom --pc=5,6 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "065-LancesRoom" --scene=overworld --map=LancesRoom --pc=10,10 --time=day --facing=down --player=PIKACHU --follower=none --story=off --wait=1.5
shot "066-ChampionsRoom" --scene=dialogue --map=ChampionsRoom --pc=5,2 --time=day --facing=up --player=PIKACHU --follower=none --text="BLUE: Hey there!" --story=off --wait=1.5
shot "067-CeruleanCave1F" --scene=overworld --map=CeruleanCave1F --pc=15,9 --time=day --facing=down --player=MEWTWO --story=off --wait=1.5

# --- Additions: rigged Pokemon, transitions, physics/ambient, 3D ground items ----------
shot "110-wtp-quiz" --scene=wtp --wait=1.5
shot "111-fireflies-route1-night" --scene=overworld --map=Route1 --pc=10,20 --time=night --facing=down --player=PIKACHU --follower=none --story=off --wait=2.5
for kind in wild trainer boss; do
  shot "112-transition-$kind-a" --scene=battle --state=transition --snap="$OUT_DIR/003-PalletTown.png" --tkind=$kind --vfx_t=0.55 --wait=0.3
  shot "112-transition-$kind-b" --scene=battle --state=transition --snap="$OUT_DIR/003-PalletTown.png" --tkind=$kind --vfx_t=0.85 --wait=0.3
done
shot "113-oaks-lab-pokedex" --scene=overworld --map=OaksLab --pc=3,4 --time=day --facing=up --story=off --wait=1.5
shot "114-museum-old-amber" --scene=overworld --map=Museum1F --pc=16,4 --time=day --facing=up --follower=none --story=off --wait=1.5
shot "115-mtmoon-fossils" --scene=overworld --map=MtMoonB2F --pc=12,8 --time=day --facing=up --follower=none --story=off --wait=1.5
shot "116-viridian-gym-spinners" --scene=overworld --map=ViridianGym --pc=16,15 --time=day --facing=up --follower=none --story=off --wait=1.5

# 18 baked clips per Pokemon: rows = Idle / Walk / Attack / Special / Hurt / Faint / Hop / Roar sampled mid-clip
ANIM_MONS="PIKACHU,CHARIZARD,SQUIRTLE,BULBASAUR,EEVEE,MEOWTH,GYARADOS,MACHAMP"
i=0
for clip in "Idle 0.0" "Walk 0.25" "Attack 0.45" "Special 0.75" "Hurt 0.2" "Faint 1.1" "Hop 0.4" "Roar 0.45"; do
  set -- $clip
  shot "anim-row-$i" --scene=model_sheet --kind=pokemon --species="$ANIM_MONS" --cols=8 --cell=170 --anim="$1" --anim_t="$2" --wait=1
  i=$((i + 1))
done
python3 "$ROOT_DIR/pipeline/scripts/stitch_rows.py" "$OUT_DIR/pokemon-animations.png" "$OUT_DIR"/anim-row-*.png
rm -f "$OUT_DIR"/anim-row-*.png

# --- Character creator, custom player looks, NPC gestures ---------------------------------
shot "120-creator-boy"    --scene=creator --gender=boy  --row=0 --wait=2
shot "121-creator-girl"   --scene=creator --gender=girl --row=3 --wait=2
shot "122-creator-random" --scene=creator --random=1 --seed=3 --row=8 --wait=2
shot "123-overworld-custom-look" --scene=overworld --map=PalletTown --pc=10,9 --look=random --seed=21 --follower=none --wait=2
shot "124-battle-custom-look" --scene=battle --look=girl --wait=1.5
NPC_CAST="oak,misty,brock,nurse,youngster,rocket,sailor,lass"
i=0
for clip in "Nod 0.1" "Think 0.5" "Laugh 0.1" "Bow 0.5" "Point 0.5" "Surprised 0.15" "Salute 0.5" "Stretch 0.5" "Dance 0.15" "Sad 0.5" "Shiver 0.1" "Sleep 0.5"; do
  set -- $clip
  shot "gesture-row-$(printf %02d $i)" --scene=model_sheet --kind=characters --species="$NPC_CAST" --cols=8 --cell=150 --anim="$1" --anim_t="$2" --yaw=-20 --wait=1
  i=$((i + 1))
done
python3 "$ROOT_DIR/pipeline/scripts/stitch_rows.py" "$OUT_DIR/npc-gestures.png" "$OUT_DIR"/gesture-row-*.png
rm -f "$OUT_DIR"/gesture-row-*.png

# --- 3D model contact sheets (every Pokemon / character next to upstream's sprite) ----
# docs/gallery/pokemon-151-3d.png, pokemon-151-3d-back.png, characters-3d.png, characters-3d-back.png
# (needs node + UPSTREAM=/path/to/pokemon-claude-red for the reference sprites)
if [ -n "${UPSTREAM:-}" ]; then
  GODOT_BIN="$GODOT_BIN" "$ROOT_DIR/pipeline/scripts/model_sheets.sh"
else
  echo "[capture] skipping model sheets (set UPSTREAM=/path/to/pokemon-claude-red)"
fi

echo "Done. $(ls "$OUT_DIR" | wc -l) screenshots in $OUT_DIR"
