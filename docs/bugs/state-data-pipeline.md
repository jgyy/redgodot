# Bugs fixed: GameState, data, pipeline, shaders

Data audit: `godot/data/pokedata.json`, `mons.json`, `cast.json`, `chars.json`, `mapdata.json`, `text.json`, `music.json` were diffed against
upstream (`/tmp/claude-0/upstream/src/data`, re-running the extract scripts) and are byte/structure identical; `pipeline/extracted/*` are identical
copies. No data entries needed fixing. `bake_font.js` / `bake_ui.js` re-runs reproduce the committed assets exactly.

| # | file:line | symptom | fix |
|---|-----------|---------|-----|
| 1 | godot/scripts/autoload/GameState.gd `exp_for_level` | Level 1 needed 1 exp (`1^3`) instead of upstream's 0 (`if (n <= 1) return 0`), so a fresh L1 mon was 1 exp above its floor and `exp_this()` disagreed with upstream | return 0 for `n <= 1` |
| 2 | GameState.gd `exp_for_level` (MEDIUM_SLOW/FAST/SLOW) | Float math (`1.2 * n^3`, `4.0*n^3/5.0`) can land just under an integer and floor one exp too low vs upstream's `Math.floor(6*n^3/5)` | pure integer arithmetic (`6 * n3 / 5 - 15n^2 + 100n - 140`, etc.) |
| 3 | GameState.gd `PartyMon.from_dict` | Saved `hp` was not clamped: a save with hp > max_hp (or edited/legacy) loaded an over-full or negative HP (upstream `Mon.from`: `min(o.hp, maxhp)`) | `clampi(hp, 0, max_hp)` |
| 4 | GameState.gd `PartyMon.from_dict` | A move missing from the saved `pp` dict had no PP entry (later `pp[m]` misses / 0 PP), PP above `pp_max` was accepted, and `moves` aliased the parsed dict's array | rebuild `pp` per move: default to `pp_max`, clamp to `0..pp_max`; `moves.duplicate()` |
| 5 | GameState.gd `reset_story_state` | `lucky_slot` and `vermilion_trash` (both in `STORY_KEYS`) were not reset, so NEW GAME inherited the previous run's slot-machine / trash-can puzzle state | reset both |
| 6 | GameState.gd `load_save` | Story keys absent from a save kept the previous session's values (stale flags/daycare/hall of fame after loading an older save) | call `reset_story_state()` before `story_from_dict()` |
| 7 | GameState.gd `load_save` | JSON numbers load as floats, so `bag` counts became `3.0` (text showed "x3.0", `%d`/int-keyed logic and equality with ints misbehaved) | coerce every bag count to `int` |
| 8 | GameState.gd `load_save` | Legacy saves with `options.text_speed = "NORMAL"` went through `int("NORMAL") == 0` and came back as the SLOWEST speed (clamped to 1) | map SLOW/NORMAL/FAST to 1/2/3, clamp 1..3 |
| 9 | GameState.gd `load_save` / `start_new_adventure` | The SOUND option was persisted in `options` but never applied on load/new game: `sound_on`, legacy `text_speed` and the Audio mute were left at the previous state, so a save with sound OFF played music | new `apply_options()` syncs `sound_on`, `text_speed` and `/root/Audio.set_muted()`; called from both |
| 10 | GameState.gd `start_new_adventure` | NEW GAME kept the previous run's `player_name`, `rival_name`, `last_heal_map/cell` (blackout destination) and `clock_minutes` (upstream `newState()`: RED / BLUE / lastHeal null / fresh clock) | reset to PalletTown defaults, RED, BLUE, 9:00 |
| 11 | GameState.gd `add_to_party` | With a full party the new mon was created, marked caught, then silently dropped (upstream `receiveMon` sends it to the current box) | append to the current PC box when it has < 20 mons |
| 12 | GameState.gd `load_save` | `FileAccess.open` returning null (unreadable file) crashed on `f.get_as_text()`; a save whose JSON root is not an object crashed on `var d: Dictionary = parsed` | null-check the file, require `parsed is Dictionary` |
| 13 | GameState.gd `load_save` | `player_cell` / `last_heal_cell` with fewer than 2 entries crashed on `pc[1]` (index out of range) | fall back to the defaults when the array is short |
| 14 | GameState.gd `load_save` | `clock_minutes` outside 0..1440 (edited/legacy save) broke `time_period()` (always "night") and the lighting cycle until the next wrap | `fposmod(..., 1440.0)` |
| 15 | GameState.gd `box()` | Any index >= 12 silently created extra PC boxes (a stray `current_box` grew unlimited boxes; Bill's PC has 12) | clamp index to 0..11 |
| 16 | godot/assets/shaders/transition.gdshader (mode 6) | The radial "clock" wipe used `atan(d.x, -d.y)/TAU + 0.5`, which starts at 6 o'clock (angle 0 is at the bottom) instead of 12 o'clock | `fract(atan(d.x, -d.y)/TAU)` so it sweeps clockwise from the top |
| 17 | pipeline/blender/gen_vfx.py `s_needle` | Both cones were rotated the wrong way: the tips met at the origin (bow-tie, fat ends outward) instead of a spike whose tip leads at +X with a short tail behind | swap the two Y rotations (+90 deg / -90 deg) |
| 18 | pipeline/blender/env_buildings.py `porch` | The front gable triangle spanned only `-w/2 .. w/2` while the roof slopes overhang to `+-(w/2+ov)`, leaving open gaps at both ends of the gable | triangle spans `+-(w/2+ov)` (and the dead `ov * 0` term is gone) |
| 19 | pipeline/blender/gen_world.py `hash2` | The tree-canopy jitter used exact 32-bit integer multiplies, which differ from upstream's double-precision `hash2` (59 of 60 sample points mismatch), so generated tree meshes did not use upstream's noise | import `upstream_px.hash2` (verified 0/60 mismatches vs node) |
| 20 | pipeline/scripts/stitch_rows.py | `sorted()` ordered row files lexicographically (`row10` before `row2`), stacking rows in the wrong order | natural-sort key |
| 21 | pipeline/scripts/compose_model_sheet.py | Without `--ids`/`--manifest`, `ids` stayed `None` and the script died with `TypeError: object of type 'NoneType' has no len()` | explicit usage error via `sys.exit` |
