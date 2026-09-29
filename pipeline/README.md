# Asset & data pipeline

This directory turns the original [pokemon-claude-red](https://github.com/levy-street/pokemon-claude-red)
JS source (a from-scratch, zero-image-files Pokemon Red remake — every sprite is
procedural pixel art) into the data and 3D assets the Godot 4 project consumes.

```
pokemon-claude-red (JS)                pipeline/                          godot/
─────────────────────────              ──────────────────────             ──────────────────
src/data/pokedata.json  ───extract───▶  extracted/pokedata.json  ───copy──▶ data/pokedata.json
src/data/maps.js        ───extract───▶  extracted/mapdata.json   ───copy──▶ data/mapdata.json
src/data/mons/*.js      ───extract───▶  extracted/mons.json      ───┬────▶ data/mons.json
src/data/cast.js        ───extract───▶  extracted/cast.json      ───┤      data/cast.json
src/art/chars.js        ───extract───▶  extracted/chars.json     ───┘      data/chars.json
                                              │
                                              ▼
                                    blender/gen_*.py (headless)
                                              │
                                              ▼
                                    godot/assets/models/**/*.glb
```

## 1. Data extraction (`pipeline/scripts/*.js`, run with Node)

`pokedata.js` and `maps.js` in the original source are already pure JSON blobs
assigned to a global (`G.DATA = {...}`, `G.MAPDATA = {...}`) — extraction is just
stripping the JS wrapper. The per-Pokemon vector art (`src/data/mons/*.js`) and
the character/cast definitions (`src/art/chars.js`, `src/data/cast.js`) are real
JS (helper functions build polygon point lists), so those are extracted by
stubbing the `G` global and evaluating the files with Node — no fragile parsing.

```sh
node pipeline/scripts/extract_mons.js /path/to/pokemon-claude-red pipeline/extracted/mons.json
node pipeline/scripts/extract_cast_chars.js /path/to/pokemon-claude-red pipeline/extracted
```

The result: **151/151 species** (full stats, movesets, learnsets, evolutions),
**165 moves**, the full **type chart**, **223 maps** (the entire Kanto region,
tile-accurate), **73 named cast members**, all sourced directly from the
original game's real data tables — nothing here is invented.

### 1b. Game versions: RED / BLUE / YELLOW (`pipeline/scripts/extract_versions.py`, Python 3, needs network)

The upstream remake is Red only. `godot/data/versions.json` holds everything that differs in the other two cartridges,
extracted from the real disassemblies ([pret/pokered](https://github.com/pret/pokered) for RED and BLUE,
[pret/pokeyellow](https://github.com/pret/pokeyellow)) so it is reproducible:

```sh
python3 pipeline/scripts/extract_versions.py [--cache /tmp/pret-cache]   # writes godot/data/versions.json
cp godot/data/versions.json pipeline/extracted/versions.json
python3 pipeline/scripts/content_audit.py                                 # the numbers behind docs/CONTENT_AUDIT.md
```

| Key | Content | Source file(s) |
| --- | --- | --- |
| `wild` | grass/water tables per map, RED / BLUE / YELLOW (`IF DEF(_RED)` blocks resolved) | `data/wild/grass_water.asm`, `data/wild/maps/*.asm` |
| `goodRod`, `superRod` | fishing groups | `data/wild/good_rod.asm`, `super_rod.asm` |
| `trades` | the ten in-game trades | `data/events/trades.asm` |
| `prizes` | Game Corner prize windows (species, coins, level) | `data/events/prizes.asm`, `prize_mon_levels.asm` |
| `marts` (YELLOW) | stock of the marts that differ | `data/items/marts.asm` |
| `parties`, `specialMoves`, `jessieJames` (YELLOW) | every trainer team, custom movesets, the four Jessie & James teams | `data/trainers/parties.asm`, `special_moves.asm` |
| `species` (YELLOW) | base stats / start moves / learnset / evolution changes (34 POKeMON) | `data/pokemon/base_stats/*.asm`, `evos_moves.asm` |
| `objects` (YELLOW) | per map: trainer/item/position patches, added and removed NPCs (matched by `TEXT_*` constant) | `data/maps/objects/*.asm` |
| `text` (YELLOW) | dialogue that differs from RED (326 labels) | `text/*.asm` |

`GameData.apply_version()` swaps all of this over the RED base data at runtime (`GameState.set_version`), and
`VersionTests.gd` checks the results against the values the disassemblies document. RED's tables parsed from pokered are
asserted equal to the upstream Red data, so the extractor itself is verified on every run.

## 2. 3D generation (`pipeline/blender/*.py`, run with headless Blender)

Pokemon and trainer models are built from upstream's own art definitions — see
**Pokemon & character models** below for how, and for the one-command regeneration.

**Blender version:** generated with **Blender 5.0.1**, via the official
[`bpy` PyPI package](https://pypi.org/project/bpy/) (Blender Foundation's
headless-only Python module — no GUI ever, so it's a fully legitimate
"headless Blender", just distributed as a wheel instead of the standalone
executable). This sandbox's network policy blocks `blender.org` and its
mirrors outright (`pypi.org` is unrestricted), so the standalone installer —
where a newer point release such as 5.2 might live — isn't reachable from
here; 5.0.1 is the newest Blender actually obtainable in this environment. If
your environment can reach `blender.org`, the exact same scripts run
identically via the standalone binary:

```sh
# via the standalone executable (any environment that can reach blender.org)
blender --background --python pipeline/blender/gen_rigged_pokemon.py -- --all --jobs 1
blender --background --python pipeline/blender/gen_characters.py
blender --background --python pipeline/blender/gen_tiles.py
blender --background --python pipeline/blender/gen_vfx.py

# via pip-installed bpy (what generated the assets in this repo; no `blender`
# binary needed at all — `import bpy` inside plain python3 IS headless Blender)
pip install bpy   # ~375MB, official Blender Foundation package
python3 pipeline/blender/gen_rigged_pokemon.py -- --all --jobs 4
python3 pipeline/blender/gen_objprops.py          # ground items + emote bubbles
python3 pipeline/blender/gen_characters.py
python3 pipeline/blender/gen_tiles.py
python3 pipeline/blender/gen_vfx.py
```

Porting `common.py` from Blender 4.0 to 5.0's Python API required two real
fixes (Blender 4.4+ replaced the old single-layer `Action.fcurves`/`id_root`
API with slotted/layered actions, and 4.2+'s EEVEE Next dropped
`Material.shadow_method`) — see the git history for `pipeline/blender/common.py`
if you're porting further forward yourself.

Outputs land in `godot/assets/models/{pokemon,characters,tiles,vfx}/`, each with
a `manifest.json` describing what was generated. Godot's runtime code
(`TileKit.gd`, `PokemonActor.gd`, `Player.gd`) loads these by convention and
gracefully falls back to a simple colored primitive for anything the pipeline
hasn't generated yet, so the game is always playable even for parts of the
pipeline still in progress.


### Character creator parts and NPC gestures

```sh
python3 pipeline/blender/gen_characters.py            # 60 NPCs, 19 clips each (~3 min)
python3 pipeline/blender/gen_player_parts.py --jobs 4 # 36 head + 7 body parts for the creator (~30 s)
```

`char_anim.py` bakes 13 gesture clips (`Nod Shake Think Laugh Bow Point Sleep Surprised Salute Stretch Dance Sad Shiver`) on
top of `Idle Walk Run Talk Wave Cheer`. `gen_player_parts.py` splits the character build into a head part (head, face,
hair, hat + skeleton + clips) and a body part (outfit, shoes, bag), and ships each part's atlas as RGBA where alpha encodes
the colour role (found by rebuilding once per role with that role recoloured and diffing the painted atlases), so
`godot/scripts/util/PlayerModel.gd` can recolour skin, hair, hat, clothes, shoes, bag and eyes at runtime.

### Pokemon models (public GLBs, rigged + animated here)

The Pokémon meshes and textures are the openly published
[`Pokemon-3D-api/assets`](https://github.com/Pokemon-3D-api/assets) models (MIT; `models/opt/regular/<dex>.glb`,
originally Sketchfab uploads). They are Draco-compressed, mostly unrigged and posed inconsistently, so
`gen_rigged_pokemon.py` turns them into game-ready assets with headless Blender:

```sh
git clone --depth 1 https://github.com/Pokemon-3D-api/assets.git pipeline/_assets     # or set SRC_ASSETS=<clone>
python3 pipeline/blender/gen_rigged_pokemon.py -- --all --jobs 4                      # 151 + MISSINGNO., ~1.5 min on 4 cores
python3 pipeline/blender/gen_rigged_pokemon.py -- --only PIKACHU,CHARIZARD           # while iterating
python3 pipeline/blender/verify_glb.py godot/assets/models/pokemon --require-skin --anims Idle,Walk,Run,Attack,Special,Hurt,Faint,Victory,Sleep,Roar,Dodge,Spin,Hop,Charge,Taunt,Spawn,Hover,Talk
# contact sheets -> docs/gallery/{pokemon-151-3d,characters-3d}[-back].png
UPSTREAM=/path/to/pokemon-claude-red GODOT_BIN=/opt/godot/godot4 pipeline/scripts/model_sheets.sh
```

Steps per species (all in `gen_rigged_pokemon.py`):

1. **Import + clean** - Blender decodes Draco; the rest pose is baked into fresh meshes, helper spheres, bone shapes and
   inverted-hull "outline" shells are dropped (the cel shader draws its own outline), tiled UVs are folded into 0..1.
2. **Normalise** - feet on the ground, centred, facing +Z (glTF/Godot), scaled to the Pokedex height, decimated to at most
   14k triangles, textures capped at 512 px. `pipeline/data/pokemon_model_overrides.json` fixes the odd model (Pikachu's axes,
   Rapidash's flame masks, T-posed arms that get lowered).
3. **Rig** - 17 bones fitted to each mesh's own proportions (upright vs horizontal body plan, head slab, tail cluster,
   feet/hands found from the vertex cloud): Root, Hips, Spine, Chest, Neck, Head, Tail1-3 and four 2-bone limbs. Smooth
   inverse-distance skin weights, 4 influences per vertex.
4. **Animate** - 18 clips baked at 30 fps, expressed as world-axis rotations/translations per bone so they work on every
   skeleton: `Idle Walk Run Attack Special Hurt Faint Victory Sleep Roar Dodge Spin Hop Charge Taunt Spawn Hover Talk`.
   `Idle Walk Run Sleep Charge Taunt Hover Talk` loop seamlessly (last key == first key).
5. **Export** - glb (JPEG textures, extracted by Godot's importer next to the glb like the character atlases) and an updated
   `manifest.json` (`height_m`, `px_height` used to size battlers like upstream's 64 px sprites, tris, bones).

MISSINGNO. has no public model: `pipeline/data/MISSINGNO_source.glb` (the glitch slab built earlier from upstream's
`glitchSprite()` output) goes through the same rig + animation step.


**Characters** (`gen_characters.py`): every humanoid `cast.json` entry (head style
cap/spiky/short/long/bald/hat/beanie/bun/pony, body normal/coat/dress/shorts/swim,
palette, backpack/glasses/beard/emblem) becomes a chibi figure — big round head like the
16x24 sprite, SDF hair shells with the face carved out, caps/brims/hats, sleeves, hands,
skirts/coats — with materials named by palette role (`mat_skin`, `mat_hair`, `mat_hat`,
`mat_top`, `mat_pants`, ...), bones hips/spine/head/arm_L/arm_R/leg_L/leg_R, clips
`Idle`/`Walk`/`Run`, 1.5 m tall, as `characters/<sprite>.glb`. `CharacterSkin.instantiate(key)`
returns the right model (manifest `aliases`, then the tinted legacy `humanoid.glb`).
Creature/object sprites (`monster`, `bird`, `poke_ball`, ...) are not built here.

Known limits: sprite art that is really a side view is still a fairly thin relief (species_fixes.py adds depth where
it matters most); a few face details can peek out at the silhouette from behind (e.g. Diglett's nose); eyes are
texture decals (crisp, glossy, anti-aliased) rather than modelled eyeballs; the Walk clip is authored for two
overworld cells, so the overworld should not restart it every cell (let it run, or seek to the cell's phase).

## Regenerating

Everything here is deterministic and re-runnable: re-clone the source repo,
re-run the extraction scripts, re-run the Blender scripts, and the Godot
project picks up the new `.glb` files on its next asset import
(`godot4 --headless --path godot --import`). No original assets are stored in
this repository — only the generation pipeline and the generated output.

## UI suite: text tables and 2D UI art (title / intro / menus)

Both scripts load the upstream game headlessly (`UPSTREAM=/path/to/pokemon-claude-red`)
and are deterministic; outputs are committed.

- `node pipeline/scripts/extract_text.js` → `godot/data/text.json`: every upstream text
  table (general.js, maps_a.js, maps_b.js, dex.js, aliases.js) keyed exactly like upstream
  (`text` = G.TEXT labels, `dex` = G.DEX_TEXT, `aliases`, `files` = labels per source file).
  Read it via `GameText` / `UI.text()`.
- `node pipeline/scripts/bake_ui.js` → `godot/assets/ui/`: `title_logo_big/red.png`
  (logo.js), `levy_mark/word.png` (intro card), `townmap.png` + `townmap.json`
  (townmap.js build(): Kanto minimap from every outdoor map's terrain + map centres/names).

Reference captures for 001/002/092–100 use `--save=showcase`, `--title_t=100` and
`--scene=intro --intro_frame=505 --intro_hold=1` (see `capture_screenshots.sh`).

## Battle: 3D stages and move effects (battle agent)

```sh
python3 pipeline/blender/gen_battlebg.py            # 15 environments + 11 platforms + layout.json (~6 s)
python3 pipeline/blender/gen_battlebg.py -- ice     # one environment
python3 pipeline/blender/gen_vfx.py                 # 22 particle meshes + poke_ball.glb
/opt/godot/godot4 --headless --path godot --import  # pick up the new glbs
```

* `upstream_px.py` ports upstream's pixel primitives exactly (gfx.js `hash2`/`bayer`/`shade`,
  palette.js `NoiseTex`, and battlebg.js's `vgrad`/`clouds`/`hills`/`treeLine`/`ground`/`platform`);
  its hash and noise output match the JS bit-for-bit.
* `gen_battlebg.py` fixes the battle camera (`CAM`, written to
  `godot/assets/models/battle/layout.json`, which `BattleStage.gd` reads) and places every
  prop along the camera ray through the pixel where upstream paints it in its 320x132 battle
  framebuffer: 3D clouds, hill ridges, toon-shaded tree lines, stalactites, icicles, boulders,
  pipes, pillars, light shafts. Sky / walls / ground / sea are 3D planes whose UVs are the camera
  projection of upstream's own painting, so they read exactly like the 2D game from the battle
  camera while still receiving the Pokémon's shadows. Platforms are real elliptical discs with
  upstream's platform art on top. Environments: grass, forest, cave, ice, water, beach, indoor,
  gym, tower, mountain, power, mansion, elite (tinted per room), cavewater, cavewater_ice.
* `gen_vfx.py` builds a mesh for each of upstream `drawShape`'s particle shapes (flame, spark,
  star, ring, bubble, leaf, snow, rock, note, z, coin, seed, needle, bone, egg, shard, heart) plus
  impact, claw, fist, drop and the poke ball. `godot/scripts/battle/BattleVfx.gd` runs upstream's
  vfx.js particle simulation and every per-move recipe in its pixel space and draws the result as
  these meshes on the 3D plane through both battlers; beams, bolts, shock rings and the SURF wave
  are real 3D geometry.

Battle reference captures: `pipeline/capture_screenshots.sh` "Battle" section
(`--scene=battle --state=vfx --move=... --vfx_t=...`, see `Main.gd _setup_battle()`).

## Overworld: maps baked from upstream, rebuilt in 3D (overworld agent)

```sh
UPSTREAM=/path/to/pokemon-claude-red node pipeline/scripts/bake_maps.js   # all maps (~30 s), or list map names
python3 pipeline/blender/gen_world.py                                    # 3D trees / Poké Ball / boulder
godot4 --headless --path godot --import                                  # import the new textures
godot4 --path godot -- --scene=ow_playtest                               # new-game autopilot (Pallet -> rival battle)
```

`bake_maps.js` runs upstream's own renderer code (map.js labels + connections + border, maprender.js,
terrain.js, buildings.js, buildingstyles.js, interior.js) for every map and splits the result:

- `godot/assets/maps/<Map>_ground.png` — the flat layer: `paintGround` (grass/path/sand/pavement/rock/water),
  ledges, cliffs, bridges, curbs, stairs, ships, interior floors / carpets / mats / ladders, elevation edges and
  the soft shadows every object casts. Outdoor maps carry a 14 x 10 cell margin (neighbour maps via `labelAt`,
  then the border pattern) so the 3D camera never sees the void; interiors a 2-cell black void.
- `godot/assets/maps/<Map>_atlas.png` + `<Map>.json` `blocks` — every object that becomes geometry, painted *in
  isolation* by the same painter (paint once on the ground for its shadow, once on a transparent layer for its
  pixels, restore the ground under it): whole buildings (`house`: roof top / wall top / wall bottom / chimney /
  flat roof), interior wall runs (`walls`), furniture (`box` with the front-face height, `cellboxes`), and thin
  sprites (`card`: signs, fences, cut trees, statues, plants...).
- `<Map>.json` also: the margin-inclusive label grid, `trees` (kind + upstream variant), `grass`, `flowers`,
  `lights` (windows / Center & Mart signs / fires, for the night light pools), `fires`, `fx` (barriers, teleports).
- `<Map>_water.png` (water mask, shore distance, deep patch) + `noise_water.png` / `noise_big.png`: the world
  shader re-evaluates upstream's `waterColor()` every 4 frames and its drifting cloud shadows.
- `decor_atlas.png` (tall grass v0-3 x 2 frames, flowers x 2 frames), `objects_atlas.png`, `palette.json`,
  and `pipeline/blender/world_defs.json` (tree clump layouts / tuft offsets evaluated with upstream's hash).

Variant hashes use upstream's own surface coordinates (margin 11 x 7), so trees, flowers, grass tufts, roofs
and statues pick exactly the variants the 2D game shows.

In Godot (`godot/scripts/overworld/`): `WorldBuilder` extrudes each block into boxes / gable or flat roofs /
cards whose UVs are the *oblique projection* of the 2D art (a point at (x, z) and height h samples the pixel
(x, z - h)), with heights scaled by K = tan(camera pitch 60°): from the game camera every building reads
exactly like its 2D sprite, but it is real geometry that occludes characters, catches the night lights and
shows perspective. `TileKit` draws the Blender trees (chunked MultiMeshes + inverted-hull outline), layered
tall-grass cards (upstream's sway / rustle timing), animated flowers, brazier flames, barriers and teleport
pads. All world shaders do their colour maths in sRGB like the 2D game (grade, light pools, cloud shadows).

### Environment models and buildings (`env_*.py`)

`pipeline/blender/env_textures.py` (procedural painted tiles, `pipeline/data/env_tex/`), `env_kit.py` (the bmesh
`Prop` builder: ramp-lit vertex colours, detail ids in vertex alpha, ink outlines), `env_props.py` / `env_tiles.py`
(fences, signs, crates, statues, trees, flowers ...), `env_bg.py` / `env_bgprops.py` (battle backdrops) and
`env_buildings.py` (building parts) are driven by `gen_world.py` / `gen_tiles.py` / `gen_battlebg.py`.

Buildings are real volumes assembled at load time by `godot/scripts/overworld/BuildingBuilder.gd` for every
`house` block (types house / big / center / gym / mart); `WorldBuilder._emit_house` falls back to the older
sprite-extruded building whenever a block cannot be sampled (set `BLD_LEGACY=1` to force that path for
before/after comparisons). The baked atlas supplies only the colours and layout: roof, wall, trim and door colours
are the modes of the building's own sprite pixels; windows, doors and signs are found from the label grid and the
sprite's glass pixels.

- GDScript geometry: plinth, corner posts and a frieze on the walls, a hip roof with a real overhang, fascia,
  modelled shingle rows (lip + riser), hip caps and ridge cap, the Center's Poké Ball emblem re-drawn as a disc
  on the slope, flat roofs with parapet, coping and cornice, sign boards (the sprite's lettering as a texture) with
  side pins. Solid faces carry a procedural material id in vertex alpha (`0.04 * id`, decoded in `world.gdshader`
  `bld_pattern`: 1/2 shingle rows, 3 clapboard, 4 brick, 5 ashlar, 6 concrete panels, 7 plaster) laid on the 2D
  art's pixel grid, plus baked AO in the vertex colours.
- Blender parts (`assets/models/world/bld_*.glb`, generated by `gen_world.py`): `window`, `window_big`
  (frame, mullions, sill, lintel, recessed gradient glass with reflection), `shutter`, `door` (frame, steps,
  hinges, bell), `glassdoor`, `awning`, `porch`, `pillar`, `lamp`, `dormer`, `chimney`, `acunit`. Tintable
  slots are vertex alpha ids 11-15 (wall / roof / trim / door / shutter) on a grey ramp; `BuildingBuilder._part`
  recolours them per building and bakes the instance into the building's single mesh. Fixed-colour parts
  (glass, steel, lamp glow) use alpha 1.

### Furniture, nature, town and building-module models (`env_furn.py`, `env_nature.py`, `env_town.py`, `env_mods.py`)

153 more props built on the same `Prop` kit (bevelled boxes with 1-2 segment rounds, lathes, swept tubes, faceted
blobs; ramp-lit vertex colours, baked ground AO). Self-lit ramps (screens, LEDs, lamp glass) use vertex alpha 15/16
so `tree.gdshader` keeps them bright at night. `env_ext.py` registers the extra ramps (plastics, cloth, crystals,
ice, lava ...); `env_registry.py` lists the four sets for `gen_world.py`, which writes
`assets/models/world/<name>.glb` plus the manifest (`GEN_SET=furniture,nature,town,building` or
`GEN_ONLY=pc,heal_machine` regenerate a subset; without them everything is rebuilt). `gen_tiles.py` also writes
textured copies of the hero props into `assets/models/tiles/`.

- `env_furn.py` - PC, laptop, CRT TVs, Poke Ball healing machine (2 x 2 cells), bookshelves, mart shelves, racks,
  vending / slot machines, stove, sink, fridge, seating, lab machines, generator, table-top items ... and five
  modular *sets* (`table_set`, `desk_set`, `counter_center_set`, `counter_mart_set`, `bench_set`): one glb holding a
  mesh per neighbour mask (`m0..m15`), so a run of table cells gets end / middle / corner pieces.
- `env_nature.py` - tree species (pine, slim pine, oak, birch, dead, cherry, palm, autumn, apple), bushes, ferns,
  reeds, lily pads, flower patches, rocks, stalagmites, crystals, ice, lava rock, logs, stumps, driftwood ...
- `env_town.py` - mailbox, lamp, benches, fountain, hydrant, market stall, flag, windmill, gates and arches, bridge /
  dock parts, boats, lighthouse, pylon, water tower, truck, container, incense burner ...
- `env_mods.py` - roof aerials / vanes / masts / hatches / tanks and one roof ornament per gym type.

Godot side: `FurnitureKit.gd` (label cells -> furniture, neighbour-aware), `DressingKit.gd` (tree species, shores,
meadows, caves, nooks, bridge rails, roofs, hand-placed landmarks), both drawing through `PropKit`'s chunked
MultiMeshes; `EnvTests.gd` covers them (and builds the props of all 223 maps in the unit tests).
`python3 pipeline/blender/verify_glb.py godot/assets/models/world --min-kb 1 --max-kb 300 --max-tris 4000 --meshes
table_set=16,desk_set=16,counter_center_set=16,counter_mart_set=16,bench_set=4` checks the files;
`--scene=model_sheet --kind=props|kit --dir=world|tiles --view=game|close` renders the contact sheets
(`docs/gallery/props-sheet.png`).
