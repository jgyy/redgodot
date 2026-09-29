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
blender --background --python pipeline/blender/gen_pokemon.py -- --all
blender --background --python pipeline/blender/gen_characters.py
blender --background --python pipeline/blender/gen_tiles.py
blender --background --python pipeline/blender/gen_vfx.py

# via pip-installed bpy (what generated the assets in this repo; no `blender`
# binary needed at all — `import bpy` inside plain python3 IS headless Blender)
pip install bpy   # ~375MB, official Blender Foundation package
python3 pipeline/blender/gen_pokemon.py -- --all
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

### Pokemon & character models

One command regenerates every Pokemon (151 + MISSINGNO., ~5 min with 3 workers on 4 cores):

```sh
python3 pipeline/blender/gen_pokemon.py -- --all --jobs 3
python3 pipeline/blender/gen_characters.py                       # 60 cast sprites + humanoid.glb (~2 min)
# single species while iterating (--noanim = geometry only, ~3 s per species):
python3 pipeline/blender/gen_pokemon.py -- --only PIKACHU,ONIX [--noanim]
# checks: every glb has the six clips, Idle/Walk loop seamlessly (last key == first key), no popping keys
python3 pipeline/blender/check_pokemon_anims.py
python3 pipeline/blender/verify_glb.py godot/assets/models/pokemon --anims Idle,Walk,Attack,Hurt,Faint,Special
# contact sheets vs upstream's sprites -> docs/gallery/{pokemon-151-3d,characters-3d}[-back].png
UPSTREAM=/path/to/pokemon-claude-red GODOT_BIN=/opt/godot/godot4 pipeline/scripts/model_sheets.sh
```

(MISSINGNO.'s look is upstream's `glitchSprite()` output. It is read from
`pipeline/data/missingno_{front,back}.png`, baked from upstream once, so no upstream checkout is needed; set
`UPSTREAM=/path/to/pokemon-claude-red` to re-bake it through `pipeline/scripts/bake_monsprites.js`. Everything
else reads `pipeline/extracted/*.json` and `pipeline/data/species_looks.json`.)

**Pokemon: from sprite definition to model** (`gen_pokemon.py` orchestrates; `monparts.py`, `monfield.py`,
`monsdf.py`, `monraster.py`, `monrig.py`, `monanim.py`, `species_fixes.py`, `glbtools.py`):

- *Research first.* `pipeline/data/species_looks.json` holds, for all 151 species, the researched look (from
  Bulbapedia / Pokemon Fandom / PokemonDB descriptions, sources listed per species): body plan, official
  main/secondary/accent colours, identifying features, gait, attack and special style, weight, surface (fur /
  scale / rock / skin / plant / smooth), plus optional overrides (`view`, `face`, `chains`, `roles`, `pal`,
  `flutter`). It drives the surface micro-texture, the animation archetype and the rig hints; the manifest records
  `palette_delta_e` (CIE-Lab distance between the closest of the sprite's three biggest colours and the researched
  official main colour: it flags species to eyeball, e.g. Gastly whose gas is lighter than its dark core, but the
  sprite palettes were judged faithful) and an advisory `missing_features` list; a `pal` map in
  `species_looks.json` recolours a palette that is off. `species_fixes.py` then patches the sprite's part list where the 3D result
  would be anatomically off or unappealing (a helper API: add/drop/scale/thicken/duplicate groups; e.g. Jynx's
  mane, Hitmonlee's head, the turtles' shells, Charizard's neck, Poliwag's tail, Gyarados' mouth).
- *Geometry.* The parts live in upstream's own 64x64 sprite space (Blender X = x-32, Z = 60-y, Y = depth, front
  = -Y = Godot +Z), so everything lines up with the sprite pixel-for-pixel. Every part is a signed-distance field
  (ellipsoids, tapered capsules, strokes, bevelled plates; slender plates get a round cross-section). All art groups
  share ONE grid (0.26 sprite px): groups are smooth-unioned into a single watertight surface with filleted
  joints (shoulders, necks, tail roots), while sibling limbs (left/right legs, ears, arms) use a hard minimum so
  they never web together. The surface is polygonised with surface nets (sparse numpy), snapped to the field,
  decimated (5-11k triangles), and lit with smooth normals taken from the field gradient. Depth still comes from
  paint order (`solve_depth`); belly plates, cheeks and other lens-shaped groups lying on a host group become texture
  decals instead of geometry.
- *Ambient occlusion.* AO is marched through the same field per vertex and exported as vertex colour (`COLOR_0`);
  `toon.gdshader` blends occluded areas toward its darkest cel step (`use_vertex_ao`, off by default so every other
  model is unchanged; `PokemonActor` switches it on).
- *Texture.* One anti-aliased atlas per species, `<SPECIES>_tex.webp` next to the glb (referenced by uri, so
  Godot imports it once instead of extracting a second copy): for every group a FRONT and a BACK layer (front:
  parts + `on:` spots/stripes + decals + eyes/mouths, back: `backOnly` parts, no `face` parts) rasterised
  3x3-supersampled at 5 texels per sprite px, with continuous (not pixel-snapped) glossy eyes, per-archetype fur /
  scale / rock / plant micro-detail and a subtle top-light / underside-shade gradient. Triangles are assigned to
  the group whose field they lie on (neighbour-majority filtered) and UV-mapped by planar sprite projection into
  that group's layer.
- *Rig and skinning.* One bone per art group in a parent tree (head under body, ears under head, feet under legs
  ...) plus chains where it matters: tails, necks, tentacles and serpent bodies (3-10 bones), and two-bone legs, arms,
  wings and long ears. Skin weights are blended from the group fields (a vertex near a neighbouring group's
  surface is partly skinned to it) and smoothed over the mesh, max 4 influences; chain bones share weight by
  geodesic distance along the part.
- *Animation* (`monanim.py`, baked at 30 fps from smooth closed-form motion, no coarse linear keys): `Idle` (2 s
  loop) breathes / hovers / slithers; `Walk` (16 frames = 0.533 s = one full stride, i.e. TWO overworld cells of
  0.267 s) is archetype-specific: biped alternating steps with counter-rotating shoulders, roll and foot lift,
  quadruped diagonal gait with spine pitch, serpent / fish travelling waves, wing flapping with body bob, floaters,
  squash-and-stretch hops, caterpillar inching, crab scuttle; feet are planted while the torso bobs and tails, ears,
  necks and leaves follow through with phase lag. `Attack` (anticipation, strike, follow-through; tackle / charge /
  bite / headbutt / punch / slash / tail whip / rear up / beam / slam / peck / coil / psychic), `Hurt` (recoil + damped
  spring), `Faint` (topples onto the floor, holds the last frame), `Special` (spin / roar / pulse / dance / shake /
  hop). Idle and Walk have last key == first key. `PokemonActor` cross-fades between clips (0.12 s).
- *Scale.* Model height = Pokedex height; `manifest.json` also records `px_height` (height in sprite pixels) so
  `PokemonActor.use_sprite_scale(frame_m)` sizes models exactly like upstream's battle sprites (64 px frame).
- *Size.* glb: quantised vertex colour / weights (`glbtools.py`), lossy WebP atlas: ~50 MB for all 152 models.
- *Shading* happens in Godot: `godot/assets/shaders/toon.gdshader` (upstream's 5-step hue-shifted ramp from
  gfx.js `shade()`, screen-space upper-left light, `tint`/`flash`/`fade`/`ramp_bias` uniforms, baked AO) +
  `outline.gdshader` (inverted hull), applied by `Toon.apply(node)`; both run in the Compatibility renderer.

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
