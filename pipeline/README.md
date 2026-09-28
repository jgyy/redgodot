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

Each Pokemon's original 2D definition is a list of primitives in a 64x64,
Y-down pixel space (`{t:'e', x,y,rx,ry}` ellipsoids, `{t:'c', x1,y1,x2,y2,r1,r2}`
tapered capsules, `{t:'p', pts:[...]}` flat polygons for fins/ears/leaves, plus
eyes/mouths/spot patterns). `gen_pokemon.py` reads that same definition and
builds genuine 3D geometry from it (spheres/capsules/extruded polygons), rigs a
generic armature from the part groups, bakes `Idle`/`Walk`/`Attack` animations,
rescales the result to the species' real Pokedex height, and exports glTF —
run once per species, for all 151, unattended.

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

**Current run (Blender 5.0.1):** all 151 species generated from their own real
per-species art data with **zero fallbacks** (1.4k–19k triangles each,
0.20m–8.79m tall — scaled from the real Pokedex height), one humanoid
character base (5.5k tris), a 14-piece tile kit, and 9 VFX meshes. Total
generation time: ~95s for the whole pipeline (151-species batch: ~86s in a
single headless invocation). Every `.glb` was verified
(`pipeline/blender/verify_glb.py`): valid glTF header, at least one mesh +
material, and the expected animation names (`Idle`/`Walk`/`Attack` for
Pokemon and characters) — two of the smallest tile/VFX meshes (`roof.glb`,
`spark.glb`, both legitimately tiny 8-triangle shapes) trip the verifier's
2KB minimum-size heuristic; that's a verifier threshold quirk, not a bad file.

Known rough edges in this pass (cosmetic, not structural):
- A handful of species have a small decorative part (spot/eye/accessory)
  sitting slightly off the body surface rather than flush against it (e.g.
  Lapras' head horn floats a little).
- Species that hover in the original 2D art (e.g. Gastly) keep that same
  hover offset in 3D rather than being grounded.
- glTF import doesn't set animation loop mode on its own; Godot's runtime code
  sets `Idle`/`Walk` to loop and leaves `Attack` one-shot (see `AnimUtil.gd`)
  rather than relying on per-file import settings.

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
