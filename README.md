# redgodot

A Godot 4 / **3D** port of **[Pokémon Claude Red](https://github.com/levy-street/pokemon-claude-red)**
— the from-scratch, zero-image-files Pokémon Red remake whose every sprite,
tile, building, battle effect and song is drawn or played by code. redgodot
keeps that rule: nothing here is hand-modelled or downloaded. The world,
Pokémon, trainers, battle stages and effects are generated from upstream's own
data and procedural painters by **headless Blender** and a Node bake of the
upstream renderer, then assembled into real 3D in Godot.

Fan project, unofficial, not affiliated with Nintendo / Game Freak / Creatures
Inc., built for educational purposes on top of the openly-published
[pokemon-claude-red](https://github.com/levy-street/pokemon-claude-red) source.
Code in this repository is MIT licensed (see `LICENSE`); no original game
assets from Nintendo's Pokémon Red are included or redistributed.

**Tooling:** [Godot 4.7.2](https://godotengine.org/download) (the
Compatibility / `opengl3` renderer, headless for CI) and **Blender 5.0.1**
headless via the official [`bpy` PyPI package](https://pypi.org/project/bpy/)
— no GUI, ever. Node 22 runs the upstream game headlessly for the bakes.

## 2D → 3D, side by side

`docs/claude-red-screenshots/` holds 100 reference frames rendered by the 2D
game (its 320×180 framebuffer ×3). Every one of them has a same-named 3D
capture in `docs/gallery/`, rendered by `pipeline/capture_screenshots.sh`
with the same map, position, time of day, party, matchup, move and menu.

| Claude Red (2D) | redgodot (3D) |
|---|---|
| ![](docs/claude-red-screenshots/001-title-screen.png) | ![](docs/gallery/001-title-screen.png) |
| ![](docs/claude-red-screenshots/003-PalletTown.png) | ![](docs/gallery/003-PalletTown.png) |
| ![](docs/claude-red-screenshots/004-PalletTown-night.png) | ![](docs/gallery/004-PalletTown-night.png) |
| ![](docs/claude-red-screenshots/006-OaksLab.png) | ![](docs/gallery/006-OaksLab.png) |
| ![](docs/claude-red-screenshots/017-CeruleanCity.png) | ![](docs/gallery/017-CeruleanCity.png) |
| ![](docs/claude-red-screenshots/027-VermilionDock.png) | ![](docs/gallery/027-VermilionDock.png) |
| ![](docs/claude-red-screenshots/037-CeladonCity-night.png) | ![](docs/gallery/037-CeladonCity-night.png) |
| ![](docs/claude-red-screenshots/063-IndigoPlateau-dusk.png) | ![](docs/gallery/063-IndigoPlateau-dusk.png) |
| ![](docs/claude-red-screenshots/068-battle-charizard-flamethrower.png) | ![](docs/gallery/068-battle-charizard-flamethrower.png) |
| ![](docs/claude-red-screenshots/074-battle-lapras-blizzard.png) | ![](docs/gallery/074-battle-lapras-blizzard.png) |
| ![](docs/claude-red-screenshots/079-battle-gyarados-surf.png) | ![](docs/gallery/079-battle-gyarados-surf.png) |
| ![](docs/claude-red-screenshots/088-wild-pidgey-intro.png) | ![](docs/gallery/088-wild-pidgey-intro.png) |
| ![](docs/claude-red-screenshots/091-wild-missingno-menu.png) | ![](docs/gallery/091-wild-missingno-menu.png) |
| ![](docs/claude-red-screenshots/092-start-menu.png) | ![](docs/gallery/092-start-menu.png) |
| ![](docs/claude-red-screenshots/093-party.png) | ![](docs/gallery/093-party.png) |
| ![](docs/claude-red-screenshots/094-summary.png) | ![](docs/gallery/094-summary.png) |

The other 84 pairs (every town and route, gyms, caves, the S.S. Anne, Safari
Zone, Silph Co., Pokémon Tower, the Elite Four rooms, every battle move
reference, bag, Pokédex, trainer card, town map, options, dialogue, intro)
are in the same two folders under the same file names.

### All 151 Pokémon (+ MISSINGNO.) in 3D

Each cell: upstream's sprite, then the generated 3D model. Back views (what
you see of your own Pokémon in battle) are in
[`pokemon-151-3d-back.png`](docs/gallery/pokemon-151-3d-back.png); the 60
trainer/NPC models in [`characters-3d.png`](docs/gallery/characters-3d.png).

![All 151 Pokémon in 3D next to their upstream sprites](docs/gallery/pokemon-151-3d.png)

## Visual overhaul: models, animation, effects

A full art pass over every generated asset, all still produced by headless Blender / procedural code (no
downloaded or hand-sculpted files). Reference for every character and Pokémon was looked up online
(`pipeline/data/species_looks.json`, `pipeline/data/character_looks.json` record the findings and sources) and
those notes now *drive* the generators.

| | Before | After |
|---|---|---|
| **Pokémon** (12 of 152) | ![](docs/showcase/before-mons.png) | ![](docs/showcase/after-mons.png) |
| **Trainers / NPCs** | ![](docs/showcase/before-chars.png) | ![](docs/showcase/after-chars.png) |
| **Town** (Pallet) | ![](docs/showcase/before-pallet.png) | ![](docs/showcase/after-pallet.png) |
| **Forest** | ![](docs/showcase/before-forest.png) | ![](docs/showcase/after-forest.png) |
| **Battle + effects** | ![](docs/showcase/before-battle.png) | ![](docs/showcase/after-battle.png) |
| **Buildings** (Cerulean) | ![](docs/showcase/bld-legacy-cerulean.png) | ![](docs/showcase/bld-new-cerulean.png) |
| **Buildings** (Pewter) | ![](docs/showcase/bld-legacy-pewter.png) | ![](docs/showcase/bld-new-pewter.png) |

Full galleries: [all 151 + MISSINGNO. next to upstream's sprites](docs/gallery/pokemon-151-3d.png) ·
[back views](docs/gallery/pokemon-151-3d-back.png) · [60 characters](docs/gallery/characters-3d.png) ·
[character back views](docs/gallery/characters-3d-back.png) · 109 gameplay frames in `docs/gallery/`.

### Pokémon (151 + MISSINGNO.)

```mermaid
flowchart LR
    W["Online lookups\n(WebSearch: shape, colours,\nfeatures, gait)"] --> L["species_looks.json"]
    U["upstream 2D part lists\n(mons.json, 64×64 sprite space)"] --> F
    L --> F["species_fixes.py +\nfixes_dex001_050 / 051_100 / 101_151\nadd hands, feet, ears, wings, flames,\nshells, fix proportions"]
    F --> G["monparts + monfield\nall groups → ONE SDF grid,\nfilleted smooth-union → surface nets"]
    G --> T["monraster\n3×3 super-sampled atlas, AA edges,\nglossy eyes, fur/scale micro-detail,\nbaked AO → COLOR_0"]
    G --> R["monrig\nbone tree + tail/neck/ear chains,\nsmooth 4-influence skin weights"]
    R --> A["monanim\narchetype gaits, 13 attack styles,\nspring hurt, topple faint,\nseamless Idle/Walk loops"]
    T --> X["glb + WebP atlas"]
    A --> X
    X --> S["toon.gdshader\ncel ramp + vertex AO"]
```

* **Anatomy** – every species was re-authored against its real design: the three starters and their lines (shells,
  scutes, flame tails, wings, flower buds), Pikachu/Raichu, the Eeveelutions, Gengar, Alakazam, Machamp, the legendary
  birds, Mewtwo, Mew, … with real hands, toed feet, claws, ears with inner colour, horns and expressions.
* **Surfaces** – one watertight blended surface instead of stacked balloon tubes, tubes/plates with a minimum
  thickness, smoothed strokes for tails and serpents; 5–11 k triangles each.
* **Textures** – super-sampled anti-aliased atlases (no pixel stairs), belly gradients, per-archetype fur / scale /
  rock / plant micro-detail, glossy irises with glints, baked ambient occlusion so limbs read against bodies.
* **Skeleton and skinning** – parented bone trees with tail, neck, tentacle and serpent chains and smooth blended
  weights, so joints bend instead of shearing.
* **Animation** – `Idle`, `Walk`, `Attack`, `Hurt`, `Faint`, `Special` per archetype: alternating biped steps,
  diagonal quadruped gait, travelling waves for serpents and fish, flapping wings, hovering floaters, squash-and-stretch
  hops, crab scuttle; tails/ears follow through; `Idle`/`Walk` are seamless (last key == first key on every channel,
  checked by `pipeline/blender/check_pokemon_anims.py`).

### Trainers and NPCs (60)

```mermaid
flowchart LR
    C["character_looks.json\n(hair, headwear, outfit, face, extras)"] --> K["char_* kit\ntorso · limbs · hands · shoes\n~14 hair styles · hats · outfits"]
    K --> P["char_paint\n256² atlas per character:\ncloth, hair strands, irises,\nblush, emblems, baked AO"]
    K --> Q["char_rig + char_anim\nfull humanoid skeleton,\nsmooth weights, 2-bone leg IK"]
    Q --> Z["Idle · Walk · Run · Talk · Wave · Cheer\n16-frame gait = exactly one cell"]
```

Every character is now recognisable as themselves: Brock's squint and spikes, Misty's side ponytail, Oak's lab coat
with lapels, Team Rocket's **R**, the nurse's cap and apron, Blaine's glasses, Lorelei's shades, …

### Environment and buildings

```mermaid
flowchart TB
    A["baked 2D atlases\n(upstream terrain painter)"] --> W
    subgraph Blender
        E1["env_textures / env_kit\n16 seamless procedural textures"] --> E2["env_tiles · env_props\n13 tiles + 30 props"]
        E1 --> E3["env_buildings\nwindow, shutter, door, awning,\ngym pillars, dormer, chimney"]
        E1 --> E4["env_bg · env_bgprops\n15 battle stages + platforms + set dressing"]
    end
    subgraph Godot
        W["WorldBuilder"] --> B["BuildingBuilder\nhip roofs with overhang, modelled shingles,\nridge caps, plinths, trim, sills"]
        W --> D["GroundDetail\ngrass/pebble/pavement detail,\nwater caustics, contact shadows"]
        W --> PK["PropKit\nMultiMesh props with tint, lean, wind sway"]
        E4 --> BS["BattleStage\nworld-space ground shader"]
    end
    E2 --> W
    E3 --> B
```

Houses, Pokémon Centers, Marts and Gyms are real 3D volumes whose colours are sampled from each building's own baked
sprite; fences, signs, beds, barrels, statues, braziers, flowers and rocks are 3D props; trees have rooted trunks and
sway; chimneys smoke. `BLD_LEGACY=1` switches back to the old flat buildings for comparisons.

### Continuous motion

Walking used to drop to `Idle` and restart `Walk` from phase 0 on **every cell**, with no blending, a stepped bob and a
rigidly attached camera. Now:

```mermaid
sequenceDiagram
    participant In as d-pad
    participant A as OwActor
    participant P as AnimationPlayer
    participant C as Camera (critically damped spring)
    In->>A: hold → (chained steps)
    A->>P: play Walk (once), crossfade 0.12 s
    loop every frame, whatever the frame rate
        A->>A: spend leftover step time moving (no idle frame between cells)
        A->>P: speed_scale = clip_len × velocity / gait_cells
        A->>C: target = position + ½ velocity
    end
    In->>A: release
    A->>P: crossfade Walk → Idle (eased stop, exact cell landing)
    C-->>C: settle with 0 overshoot
```

Measured with `--scene=motion_lab` (12 chained steps in Pallet Town, simulated d-pad, final assets):

| | Before | After |
|---|---|---|
| `Walk` clip starts | 12 | **1** |
| Min speed (cells/s, nominal 3.75) | 1.5 (stall every cell) | **3.69** |
| Max speed change / frame | 2.25 | **0.11** |
| Camera overshoot when stopping | – (rigid) | **0.000** cells |
| Turning | snapped | ≤ 1.9° / frame, shortest arc |

![Walk strip: player with Charmander following](docs/showcase/walk-strip-player.png)

Other motion changes: ledge hops with crouch / stretch / landing squash and dust puffs, water ripples while surfing,
grass-blade bursts, footstep dust, follower Pokémon with a continuous bob, blended 60 Hz battle ticks (no stutter on
90/144 Hz displays), eased send-out / recall / faint / evolution.

### Special effects

Procedural soft-glow, ring, streak and twinkle textures; shockwave rings, radial streaks and ribbon trails; charge-up
glows before beams and projectiles; stronger impacts (flash, star, ring, sparks, decaying shake) with extra emphasis on
super-effective / resisted hits; reworked recipes for flamethrower, ember, fire blast, water gun, hydro pump, surf, the
thunder family, solar beam, hyper beam, ice beam, blizzard, psychic, night shade, earthquake, explosion and the powders;
status effects (poison, burn, paralysis, sleep, freeze, confusion), stat-up/down arrows with aura, level-up sparkle,
faint dust and an evolution halo. VFX props are bevelled, shaded meshes (`pipeline/blender/gen_vfx.py`).
Inspect any of it with `--scene=vfx_sheet`.

## What's in it

| Area | Status |
|---|---|
| **World** | All 223 maps, collision exactly like upstream's `GameMap` (quads → collision tile, pass/grass/water/door/warp lists, ledges, pair collisions, connections). Ground baked by upstream's own terrain painter; buildings, trees, furniture and props are real 3D meshes UV-mapped to upstream's paint, so they read like the sprites from the game camera. Animated water, flowers and tall grass; day/dusk/night with lit windows and light pools; cave darkness, Flash; follower Pokémon; wandering NPCs. |
| **Pokémon** | 151 + MISSINGNO., generated from upstream's primitive art and per-species anatomy fixes researched online: one blended SDF surface per Pokémon with real hands/feet/ears/wings, super-sampled AA albedo + baked AO, cel shading with upstream's hue-shifted ramp, outlines, smooth-skinned rigs with tail/neck chains and archetype-specific Idle/Walk/Attack/Hurt/Faint/Special animations. |
| **Trainers / NPCs** | 60 chibi models built from upstream's cast definitions and online references (faces, ~14 hair styles, hats, outfits, accessories), full humanoid rigs with IK walk/run cycles plus Talk / Wave / Cheer. |
| **Battle** | Upstream's Gen-1 engine ported (all 165 move effects, status, stat stages, crits, multi-hit, recharge, trapping, confusion, substitute, transform, trainer AI & items, switching, catching with the shake math, EXP / level-up / move learning, evolution, prize money, ghosts + Silph Scope, Safari Zone, the old man's demo). 15 Blender-built 3D stages, pixel-exact HUD, all 165 moves animated. Battles are overlays, so story scripts continue after them. |
| **Story** | All upstream map scripts (Pallet → Cerulean Cave) as GDScript coroutines on a port of upstream's `S` scripting API: Oak, starters, rival fights, gyms, Team Rocket, Silph Co., Elite Four, trainers with line of sight, marts, Pokémon Center healing, item balls, hidden items, gifts, trades, field moves, elevators. |
| **UI** | Upstream's screens ported pixel-for-pixel on a 320×180 canvas with its own hand-drawn font (`Px` kit): title, intro, naming, text box, START menu, party, summary, bag, Pokédex, trainer card, town map (+ Fly picker), options, Bill's PC, mart. Pokémon/characters in menus are live 3D models. |
| **Audio** | Upstream's audio engine ported: the original Red music (all 52 songs + jingles) on a Game Boy–timed sequencer with its re-voiced pulse/wave/noise instruments, the procedural SFX table and per-species cries. |
| **Text** | All ~2,500 upstream dialogue lines extracted to `godot/data/text.json`. |
| **Not ported** | Upstream's online features (Social Zone lounge, link battles/trades, cloud save, share cards), Who's That Pokémon?, the character customiser, phone touch controls, slot-reel graphics (slots resolve as text), Hall of Fame / credits sequences (text only). |

## Architecture

```mermaid
flowchart TB
    subgraph Autoloads
        GameData["GameData\nspecies · moves · types · maps · cast"]
        GameState["GameState\nparty · bag · money · flags · clock · PC · save/load"]
        SceneRouter["SceneRouter\nscene swaps + battle overlays\nawait battle(enc)"]
        Story["Story\nport of upstream S API\n+ all map scripts"]
        UI["UI\nawait say / ask / choose\n(top CanvasLayer)"]
        Audio["Audio\nGB sequencer · SFX · cries"]
    end

    subgraph Scenes
        Intro["Intro\nLEVY ST. card, Oak's speech, naming"]
        Title["Title\n3D diorama + logo"]
        Overworld["Overworld\nWorldBuilder · Player · follower · NPCs\nStartMenu"]
        Battle["Battle (overlay)\nBattleEngine · BattleStage · BattleHud · BattleVfx"]
    end

    Intro --> Title --> Overworld
    Overworld -- "step / talk / sign / enter" --> Story
    Story -- "move_actor · warp_to · emote · lock_input" --> Overworld
    Story -- "await say / ask / choose" --> UI
    Story -- "await SceneRouter.battle(enc)" --> SceneRouter
    SceneRouter -- "hide + pause overworld,\nadd battle on top" --> Battle
    Battle -- "win / lose / run / caught" --> SceneRouter
    Audio -. follows active scene .-> SceneRouter
    GameData -.-> Overworld & Battle & Story
    GameState <-.-> Overworld & Battle & Story
```

### A story event across systems (Oak's Lab rival battle)

```mermaid
sequenceDiagram
    participant P as Player
    participant OW as Overworld
    participant S as Story
    participant UI as UI
    participant R as SceneRouter
    participant B as Battle
    P->>OW: steps onto row 6 with a starter
    OW->>S: on_step(cell) → true (script takes over)
    S->>OW: lock_input(true)
    S->>UI: await say("OaksLabRivalIllTakeYouOnText")
    S->>OW: await move_actor("OAKSLAB_RIVAL", path_to(...))
    S->>R: await battle({kind:"trainer", trainer_class:"RIVAL1", ...})
    R->>OW: hide + pause (node kept alive)
    R->>B: add overlay
    B-->>R: "win" / "lose"
    R->>OW: restore
    R-->>S: result
    S->>UI: await say("OaksLabRivalSmellYouLaterText")
    S->>OW: await move_actor(rival, "DDDDDD"), hide_actor
    S->>OW: lock_input(false)
```

### Battle turn

```mermaid
stateDiagram-v2
    [*] --> Intro: wild appears / trainer sends out
    Intro --> Action
    Action --> Moves: FIGHT
    Action --> Party: PKMN
    Action --> Bag: ITEM
    Action --> Run: RUN (wild)
    Moves --> Turn
    Party --> Turn: switch
    Bag --> Catch: Poké Ball
    Bag --> Turn: other item
    Catch --> Caught: shakes succeed
    Catch --> Turn: breaks free
    Turn --> Action: both still standing
    Turn --> EnemyFaint
    Turn --> PlayerFaint
    EnemyFaint --> Exp: EXP · level-up · learn move
    Exp --> Intro: trainer has more
    Exp --> Evolution: won
    PlayerFaint --> Party: healthy mon left
    PlayerFaint --> Lost: party wiped
    Evolution --> [*]
    Caught --> [*]
    Run --> [*]
    Lost --> [*]
```

`BattleMath.gd` still ports the original `calcDamage` step for step (the
`floor(floor(floor(2L/5+2)*power*atk/def)/50)` core, STAB ×1.5, type chart,
`floor(spd/2)/256` crits doubling level, the `217..255/255` random factor).

## Asset pipeline

```mermaid
flowchart LR
    UP["pokemon-claude-red\n(JS source, headless via\ntools/headless.js)"]
    subgraph Node["Node bakes (pipeline/scripts)"]
        EX["extract_*.js\npokedata · maps · mons · cast\ntext · music"]
        BM["bake_maps.js\nground textures · object atlases\nlabels · lights"]
        BS["bake_monsprites.js / bake_charsprites.js\nflat albedo layers"]
        BF["bake_font.js / bake_ui.js\npixel font · UI art"]
    end
    subgraph Blender["Headless Blender (pipeline/blender)"]
        GP["gen_pokemon.py\nSDF body groups → mesh\nsprite-projected atlas · rig · 6 clips"]
        GC["gen_characters.py\nchibi cast models"]
        GW["gen_world.py\ntrees · props"]
        GB["gen_battlebg.py\n15 stages · platforms"]
        GV["gen_vfx.py\nparticle meshes · Poké Ball"]
    end
    UP --> EX & BM & BS & BF
    EX --> DATA["godot/data/*.json"]
    BS --> GP & GC
    EX --> GP & GC
    BM --> MAPS["godot/assets/maps/"]
    GP & GC & GW & GB & GV --> GLB["godot/assets/models/**/*.glb"]
    BF --> UIA["godot/assets/ui/"]
    DATA & MAPS & GLB & UIA --> GODOT["Godot 4 project"]
```

### How an overworld map becomes 3D

```mermaid
flowchart TD
    Q["map cell = quad index"] --> C["collision tile = quads[ts][q][2]\n(pass / grass / water / door / warp)"]
    Q --> L["semantic label\n(LABELS[ts][q] + upstream per-map fixes)"]
    L --> G{"flat or solid?"}
    G -->|"grass, path, water, floor,\nflowers, ledges, curbs"| Ground["baked ground texture\n(upstream terrain painter)"]
    G -->|"roof / wall / window / door"| Bld["building: walls + gable/flat roof\nUV = oblique projection of the\nbuilding upstream paints"]
    G -->|"tree, tree2, cut tree"| Tree["Blender tree meshes\n(upstream clump layouts + ramp)"]
    G -->|"furniture, fences, signs,\nstatues, rocks"| Prop["boxes / standing cards\nfrom the object atlas"]
    Ground & Bld & Tree & Prop --> Scene["WorldBuilder → Overworld\n+ water shader, tall-grass cards,\nday/night grade & light pools"]
```

## Running it

```sh
godot --path godot --import   # first run only: import assets
godot --path godot            # play
```

Controls: arrow keys / WASD to move, Space/Enter to confirm or talk, Escape/X
to cancel, Enter (in the overworld) for the START menu.

### Tests

```sh
godot --headless --path godot --import
godot --headless --path godot -- --run-tests          # 261 checks
godot --headless --path godot -- --scene=ow_playtest  # new-game autopilot
```

The suite covers data loading, the damage formula and type chart, map
collision, the battle engine (every move's effect and animation), models and
animation clips, UI widgets driven by input events, audio (sequencer output,
JS-exact cry hashing), save/load, and the story scripts run against a fake
overworld/UI/battle host (Oak's intro and starter, rival battle, parcel and
Pokédex, marts, healing, Brock, trainer line of sight, blackout, card-key
doors, elevators). `ow_playtest` drives real input through the actual game:
Red's room → Pallet → Oak stops you → the lab → starter → rival battle →
back in the lab. CI runs both, then captures screenshots.

### Screenshots

```sh
xvfb-run godot --path godot --rendering-driver opengl3 \
  -- --screenshot=/tmp/out.png --scene=overworld --map=CeruleanCity --pc=20,18 --time=night --wait=1.5
GODOT_BIN=/path/to/godot4 bash pipeline/capture_screenshots.sh   # regenerate docs/gallery/
```

Scene keys include `title`, `intro`, `oak_speech`, `naming`, `overworld`,
`battle`, every START-menu screen, `dialogue`, `story_mart`, `model_sheet`,
`px_test`; see `godot/scripts/Main.gd` and the capture script for the flags
(`--map --pc --time --facing --follower --save=showcase`, battle `--player
--enemy --level --env --trainer --state --move --vfx_t`, …).

## Regenerating assets

See `pipeline/README.md`. Clone
[pokemon-claude-red](https://github.com/levy-street/pokemon-claude-red) and
point `UPSTREAM=` at it; every extractor, bake and Blender generator is
deterministic and re-runnable.
