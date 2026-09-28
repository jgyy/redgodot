# redgodot

A Godot 4 / 3D reimagining of **[Pokémon Claude Red](https://github.com/levy-street/pokemon-claude-red)**
— a from-scratch, zero-image-files Pokémon Red remake originally built entirely
out of procedural 2D pixel art. This project ports its real game data (all 151
species, all 165 moves, the full type chart, all 223 Kanto maps, the full cast)
into a real Godot 4 project, and turns its 2D vector art definitions into actual
3D models, materials and animations using **headless Blender** — no manual
modelling, no downloaded assets, no original game images anywhere in this repo.

Fan project, unofficial, not affiliated with Nintendo / Game Freak / Creatures
Inc., built for educational purposes on top of the openly-published
[pokemon-claude-red](https://github.com/levy-street/pokemon-claude-red) source.
Code in this repository is MIT licensed (see `LICENSE`); no original game
assets from Nintendo's Pokémon Red are included or redistributed.

**Tooling:** [Godot 4.7.2](https://godotengine.org/download) (headless,
`--headless --rendering-driver opengl3`) and **Blender 5.2.2** (headless, via
the official [`bpy` PyPI package](https://pypi.org/project/bpy/) — no GUI
ever). Both are the newest versions actually reachable from the sandbox this
was built in, which blocks `blender.org` at the network-policy level; see
`pipeline/README.md` for the exact story and how to run the same scripts
against a newer standalone Blender if yours can reach it.

## What this actually is (read this before the screenshots)

Converting a ~27k-line, 151-species, 223-map game to bespoke, hand-authored 3D
art is a multi-month project. This is a **real, working vertical slice** with a
**complete data foundation**, not a mockup:

| Layer | Status |
|---|---|
| Game data (species, moves, type chart, maps, cast) | **Complete** — 151/151 species, 165/165 moves, 223/223 maps, ported verbatim from the source's real data tables |
| 3D models (headless Blender 5.0.1 pipeline) | **151/151 Pokemon species generated, 0 fallbacks** (real per-species geometry, materials, and Idle/Walk/Attack animations built from each species' actual vector-art data + Pokedex height) + a rigged/tintable humanoid character base + a 14-piece overworld tile kit + 9 battle VFX meshes — see `godot/assets/models/*/manifest.json` for exact per-asset detail |
| Overworld (3D, tile-accurate movement/collision/warps/encounters) | **Working** for all 223 maps via a generic tile classifier (pass/grass/door/counter lists from the real tileset data), with the real per-map NPC/prop placements (`mapdata.json` `objs`) now rendered as tinted humanoid models and interactable |
| Day/night cycle | **Working** — `GameState` runs an in-game clock (`time_period()` → day/dusk/night) that `LightingRig` applies continuously to the overworld's sun + sky; Title/Battle use fixed presets |
| Dialogue | **Working** — a reusable `DialogueBox` overlay, driven for NPCs/signs by `DialogueText` (curated per-archetype flavor lines, since the upstream source's actual string table for `mapdata.json`'s `textLabel` keys was never extracted into this repo — see `DialogueText.gd`'s header), plus a Professor-Oak `Intro` scene ahead of Title |
| Start Menu suite | **Working** — POKéDEX (151-species dex with seen/own tracking + a live 3D preview), POKéMON (party list → Summary's INFO/STATS/MOVES tabs, also with a live 3D preview), ITEM (real bag data, and the TOWN MAP item opens a Town Map laid out by BFS-walking the real map-connection graph), the player's Trainer Card (name/ID/money/badges), Options, and Save (`user://save.json`) |
| Battle system | **Working** — upstream's Gen-1 engine ported to `BattleEngine.gd` (all 165 moves' effects, status, stat stages, trainer AI and items, switching, catching with the shake math, EXP / level-up / move learning, evolution, prize money, ghost / Safari / old-man-demo battles); 15 Blender-generated 3D environments; pixel-exact HUD; every move animated in 3D (`BattleVfx.gd`) |
| Trainer battles, catching | **Working** — `await SceneRouter.battle({kind:"trainer", trainer_class, party_index, ...})`; caught Pokémon go to the party or the PC box |

If a Pokémon or map looks simple, it's using the honest fallback path
(a colored primitive) rather than pretending — every part of the pipeline
either uses the real per-species/per-map data or visibly falls back, there's no
placeholder pretending to be final art.

## Screenshots

*(Captured headlessly via `xvfb-run godot --rendering-driver opengl3`, the same
command the CI workflow runs — these are real, in-engine screenshots of the
actual Blender-generated models, not mockups. `docs/screenshots/*.png` are
CI's own 3-scene smoke set; `docs/gallery/*.png` is the full feature-parity
set below, regenerated with `pipeline/capture_screenshots.sh` — see
[Taking your own screenshots](#taking-your-own-screenshots).)*

| Title | Overworld (Pallet Town) | Battle (real Squirtle vs. Pidgey) |
|---|---|---|
| ![Title screen](docs/screenshots/title.png) | ![Overworld](docs/screenshots/overworld.png) | ![Battle](docs/screenshots/battle.png) |

### Start Menu suite

| Start Menu | Party → Summary | Bag | Pokedex |
|---|---|---|---|
| ![Start menu](docs/gallery/10-start-menu.png) | ![Summary](docs/gallery/12-summary.png) | ![Bag](docs/gallery/13-bag.png) | ![Pokedex](docs/gallery/14-pokedex.png) |

| Trainer Card | Town Map | Options | Dialogue |
|---|---|---|---|
| ![Trainer card](docs/gallery/15-trainer-card.png) | ![Town map](docs/gallery/16-town-map.png) | ![Options](docs/gallery/17-options.png) | ![Dialogue](docs/gallery/18-dialogue.png) |

### Battle (3D parity with upstream refs 068-091)

Every battle reference in `docs/claude-red-screenshots/` has a same-named 3D
capture in `docs/gallery/` (same matchup, level, HP, move, environment and UI).

| Flamethrower (grass) | Thunderbolt (sea) | Blizzard (ice cave) |
|---|---|---|
| ![068](docs/gallery/068-battle-charizard-flamethrower.png) | ![069](docs/gallery/069-battle-pikachu-thunderbolt.png) | ![074](docs/gallery/074-battle-lapras-blizzard.png) |

| Hydro Pump | Solarbeam | Wild intro | Wild MISSINGNO. (beach) |
|---|---|---|---|
| ![070](docs/gallery/070-battle-blastoise-hydro_pump.png) | ![071](docs/gallery/071-battle-venusaur-solarbeam.png) | ![088](docs/gallery/088-wild-pidgey-intro.png) | ![091](docs/gallery/091-wild-missingno-menu.png) |

### Day/night lighting cycle, same location

| Pallet Town — day | Pallet Town — night |
|---|---|
| ![Pallet Town day](docs/gallery/60-pallettown-day.png) | ![Pallet Town night](docs/gallery/61-pallettown-night.png) |

`docs/gallery/` also has day/night/dusk pairs for Cerulean City, Celadon
City, and Cinnabar Island, plus 30+ more locations across Kanto (routes,
gyms, caves, Team Rocket's hideout, the Safari Zone, Indigo Plateau, Victory
Road, the post-game Cerulean Cave, and more) proving all 223 maps still
render and are still fully navigable with everything above added.

## Architecture

```mermaid
flowchart TB
    subgraph Autoloads["Autoload singletons"]
        GameData["GameData\n(pokedex, moves, type chart,\nmaps, cast — loaded once from JSON)"]
        GameState["GameState\n(party, position, bag, badges,\nday/night clock, seen/caught dex,\nsave/load)"]
        SceneRouter["SceneRouter\n(swaps the active scene)"]
    end

    subgraph Scenes
        Intro["Intro.tscn\nOak's opening lines"]
        Title["Title.tscn\nstarter pick"]
        Overworld["Overworld.tscn\nMapLoader + Player + camera\n+ StartMenu + DialogueBox"]
        Battle["Battle.tscn\nPokemonActor x2 + turn loop\n+ nameplates + move VFX"]
    end

    Intro -- "finished" --> SceneRouter
    SceneRouter -- goto_title --> Title
    Title -- "new_game()" --> SceneRouter
    SceneRouter -- goto_overworld --> Overworld
    Overworld -- "wild encounter" --> SceneRouter
    SceneRouter -- start_battle --> Battle
    Battle -- "won / ran / wiped" --> SceneRouter
    SceneRouter -- goto_overworld --> Overworld

    GameData -.read-only.-> Overworld
    GameData -.read-only.-> Battle
    GameState <-.party / position / clock.-> Overworld
    GameState <-.party HP/XP.-> Battle
```

### Start Menu navigation

Every sub-screen below is its own `Control`, instantiated once by `StartMenu`
and toggled by `visible` (the `PartyMenu` overlay convention every screen in
this project follows — see `godot/scripts/ui/*.gd`), not a scene swap:

```mermaid
flowchart LR
    Overworld(["Overworld\n(menu key)"]) --> Start["StartMenu"]
    Start -->|POKéDEX| Dex["PokedexMenu\n151 species, seen/own,\nlive 3D preview"]
    Start -->|POKéMON| Party["PartyMenu"]
    Party -->|select a mon| Summary["SummaryScreen\nINFO / STATS / MOVES"]
    Start -->|ITEM| Bag["BagMenu\nreal item data"]
    Bag -->|select TOWN MAP| Town["TownMap\nBFS-laid-out from\nreal map conns"]
    Start -->|"<player name>"| Card["TrainerCard"]
    Start -->|OPTION| Opt["OptionsMenu"]
    Start -->|SAVE| Save[("user://save.json")]
    Dex -.cancel.-> Start
    Party -.cancel.-> Start
    Summary -.cancel.-> Party
    Bag -.cancel.-> Start
    Town -.cancel.-> Bag
    Card -.cancel.-> Start
    Opt -.cancel.-> Start
```

### Day/night cycle

```mermaid
flowchart LR
    Clock["GameState.clock_minutes\n(advances every _process)"] --> Period{"time_period()"}
    Period -->|"6:00–18:00"| Day["day"]
    Period -->|"18:00–20:00\nor 5:00–6:00"| Dusk["dusk"]
    Period -->|else| Night["night"]
    Day & Dusk & Night --> Rig["LightingRig.apply()\nsun energy/color,\nsky + ambient color"]
    Rig --> Sun["Overworld's DirectionalLight3D"]
    Rig --> Env["Overworld's WorldEnvironment"]
```

## Data & asset pipeline

```mermaid
flowchart LR
    A["pokemon-claude-red\n(JS source)"] -->|"Node: stub G, eval, dump JSON"| B["pipeline/extracted/*.json\npokedata · mapdata · mons · cast · chars"]
    B -->|copied as-is| D["godot/data/*.json\n(runtime game data)"]
    B -->|"headless Blender (bpy)\nprimitives -> mesh, pal -> material,\ngroups -> armature, Idle/Walk/Attack"| C["godot/assets/models/**/*.glb\npokemon · characters · tiles · vfx"]
    D --> E["Godot 4 project"]
    C --> E
```

See `pipeline/README.md` for the exact commands and the primitive-to-mesh
mapping (ellipsoid → sphere, tapered capsule → capsule mesh, flat polygon →
extruded fin, etc).

## Overworld tile classification

The original game's 223 maps are tile-grid data (`pass`/`grass`/`doors`/`counters`
id lists per tileset — the same lists the original engine used for collision).
Rather than requiring bespoke art per tile id per tileset, every map is built
from one shared, Blender-generated tile kit classified generically:

```mermaid
flowchart TD
    cell["map cell value\n(from the real tile grid)"] --> chk{"which list is it in?"}
    chk -->|"== tileset.grass id"| grass["Tall grass\nwalkable + rolls wild encounter"]
    chk -->|"in tileset.doors"| door["Door / warp tile"]
    chk -->|"in tileset.counters"| counter["Counter (shop/PC)\nwalkable"]
    chk -->|"in tileset.pass"| floor["Floor\nwalkable"]
    chk -->|"none of the above"| block["Blocking prop\n(tree / wall)"]
```

## Battle flow

```mermaid
stateDiagram-v2
    [*] --> ActionMenu: wild Pokemon appears
    ActionMenu --> ResolveTurn: FIGHT
    ActionMenu --> Fled: RUN (wild only)
    ResolveTurn --> ActionMenu: both sides survive
    ResolveTurn --> EnemyFainted: enemy HP <= 0
    ResolveTurn --> PlayerFainted: player HP <= 0
    PlayerFainted --> ActionMenu: another healthy party mon
    PlayerFainted --> PartyWiped: no healthy mon left
    EnemyFainted --> Victory
    Victory --> [*]
    Fled --> [*]
    PartyWiped --> [*]
```

`BattleMath.gd` ports the original's `calcDamage` step-for-step: the same
`floor(floor(floor(2L/5+2)*power*atk/def)/50)` core, the same STAB (`x1.5`),
the same type-chart lookup, the same crit rule (`floor(spd/2)/256`, doubling
level on a hit), and the same `217..255/255` final random factor.

## Running it

Requires the [Godot 4.7+ engine](https://godotengine.org/download) (this repo
targets Godot 4.7.2).

```sh
godot --path godot --import   # first run only: import assets
godot --path godot            # play
```

Controls: arrow keys / WASD to move, Space/Enter to confirm (also talks to
the NPC or sign you're facing), Escape/X to cancel, Enter to open the Start
Menu.

### Running tests

```sh
godot --headless --path godot --import
godot --headless --path godot -- --run-tests
```

48 assertions cover the ported damage formula (including a same-seed crit vs.
non-crit comparison), the type chart, data loading (151 species / 223 maps),
map tile classification, the wild-encounter slot table, the day/night clock
and `LightingRig` presets, `DialogueText` resolution, and `GameState`
save/load round-tripping — see `godot/scripts/util/TestSuite.gd`.

### Taking your own screenshots

```sh
xvfb-run godot --path godot --rendering-driver opengl3 \
  -- --screenshot=/tmp/out.png --scene=overworld --wait=1.5
```

`--scene=` accepts `title`, `intro`, `overworld`, `battle`, or any Start Menu
screen (`start_menu`, `party`, `summary`, `bag`, `pokedex`, `trainer_card`,
`town_map`, `options`, `dialogue`). Optional flags layer on top:
`--map=MapName --pc=x,y --time=day|dusk|night` (overworld location + lighting),
`--player=SPECIES --player_level=N --enemy=SPECIES --level=N` (battle
matchup), `--auto_move=1 --move_index=N` (press a move without simulated
input, so `--wait` can land mid-VFX), `--text="..."` (dialogue's line).

`pipeline/capture_screenshots.sh` (`GODOT_BIN=/path/to/godot4 bash
pipeline/capture_screenshots.sh`) regenerates the entire `docs/gallery/`
set above from these flags in one pass.

## Regenerating the 3D assets

See `pipeline/README.md`. In short: `node pipeline/scripts/extract_*.js`, then
`blender --background --python pipeline/blender/gen_*.py`. Both are fully
deterministic and re-runnable against a fresh clone of the source repo.

## Roadmap / not yet implemented

- Trainer battles (multi-mon parties, switching) — data is extracted and ready
  (`pokedata.json` `trainerClasses`/`parties`), turn-loop support is the
  remaining work.
- Catching and the PC (item/bag data and the Bag screen exist; the Poké Ball
  "throw" interaction in battle and box storage don't yet).
- The real upstream dialogue *strings* — `mapdata.json`'s `objs`/`signs` only
  ever carried stable label keys (`textLabel`), never the English text those
  labels point to (see `pipeline/README.md`); NPCs/signs are now interactable
  and DialogueBox is fully wired, but `DialogueText.gd` resolves curated
  per-archetype flavor lines rather than each NPC's actual unique line. A
  proper fix means extracting the upstream source's real string table into a
  new `godot/data/text.json` via a new `pipeline/scripts/extract_text.js`.
- Per-character mesh variety (hats, dresses, hairstyles) beyond the single
  base humanoid + material-tint approach documented in
  `godot/assets/models/characters/manifest.json` — this now also covers the
  73 `cast.json` NPC archetypes rendered in the overworld, not just the
  player.
- Distinguishing tree/wall/water visually per tile id (currently one generic
  "blocking" prop for anything outside a tileset's `pass` list) — this
  affects building interiors most visibly, since they render with the same
  fallback as an outdoor tree line.
- NPC movement (`objs.move == "WALK"` is present in the source data but NPCs
  are currently static).
