# Bug-fix log

A review of every subsystem found and fixed **88 bugs**. Each was checked against the code (and against the upstream JS game where the rule comes from it) before being fixed; the per-area source tables live in `docs/bugs/`.

* **Battle engine (BattleEngine / BattleMath / BattleSide)**: 20
* **Overworld (scene, maps, encounters, fx, util)**: 19
* **UI, menus, audio, scene routing**: 25
* **Game state, data, pipeline, shaders**: 21
* **Found while testing**: 3

## Battle engine (BattleEngine / BattleMath / BattleSide) (20)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 1 | BattleEngine.gd:742 | Crit chance used the mon's full *stat* Speed instead of the species' *base* Speed (upstream `A.sp.spd`), so high-level / fast mons crit far too often (cap 255 hit almost always). | Roll crit from `GameData.get_species(...).spd` (copied species when transformed) via new `atr_species()`. |
| 2 | BattleEngine.gd:1491, 1509 | SAFARI_BALL was treated like a POKE_BALL in the catch formula (rand 0-255, /255) instead of upstream's Ultra-style 0-150 / 150, making Safari catches much harder. | Removed SAFARI_BALL from the POKE_BALL branches of `catch_roll`. |
| 3 | BattleEngine.gd:207 | In the failed-RUN branch, a result set by the enemy's move (TELEPORT/WHIRLWIND/ROAR -> `fled`) was only honoured if `check_faints()` returned true, so the battle carried on after the foe "ran away". | Return `_finish(result)` right after that `do_move`. |
| 4 | BattleEngine.gd:218, 240 | Battles ending through `result` set by a move / Safari action (`return result`) skipped `_finish()`/`_cleanup()`, so MIMIC'd move slots were never restored. | Return `_finish(result)` on both paths. |
| 5 | BattleNullUI.gd:29 | Scripted UI picked the first move with PP even if DISABLED; the engine rejects it and re-asks forever (infinite loop in headless sims/tests). | Skip disabled moves via `b.is_disabled()`. |
| 6 | BattleEngine.gd:504 | After a trapping move (WRAP/BIND/...) ended, the stale `trapping{started}` dict made every later move count as "continuing", so no PP was ever deducted. | "Continuing" trapping now requires `turns > 0`. |
| 7 | BattleEngine.gd:306 | The same stale trapping dict beat `rage` in `player_action`'s locked-move pick, so a RAGE-locked mon kept re-selecting WRAP. | Only use the trapping move while `turns > 0`. |
| 8 | BattleEngine.gd:325 | A negative `slot` from a UI indexed the move list from the end (GDScript negative index) instead of being rejected. | Reject `slot < 0`. |
| 9 | BattleEngine.gd:611 | SELFDESTRUCT/EXPLOSION on an immune target ("It doesn't affect...") left the user alive; in Gen 1 the user always faints. | KO the user in the immunity early-return. |
| 10 | BattleEngine.gd:431 | `last_dmg_dealt` was never cleared, so COUNTER hit back with damage from earlier turns after the foe missed / used a status move / flinched. | Reset `last_dmg_dealt` at the start of every `do_move`. |
| 11 | BattleEngine.gd:1067 | MIMIC with an out-of-range menu index (or a foe with no moves) indexed past the array end -> runtime error. | Bounds-check the pick / empty option list. |
| 12 | BattleEngine.gd:488, 495 | Full paralysis / confusion self-hit while FLY/DIG-charging cleared `invuln` but never un-hid the sprite, leaving the mon invisible. | Call `ui.hide_side(side, false)` before `_break_lock`. |
| 13 | BattleEngine.gd:1652 | `BattleScene.trainer_defeated` reads `b.trainer["boss"]`, but `trainer_opts` only put `boss` at the top level, so leader/rival wins never got the leader victory theme. | Also store `boss` inside the `trainer` dict. |
| 14 | BattleEngine.gd:196 | FLINCH set on a foe that had already moved stayed set (and `moved` was never reset), so the foe flinched on the *next* turn. | Reset `moved`/`flinch` for both sides at the start of each turn. |
| 15 | BattleEngine.gd:1560, 1567 | Enemy FULL RESTORE / FULL HEAL cured status but left the TOXIC counter (and, for FULL RESTORE, confusion), so later poison/LEECH SEED damage was still multiplied. | Reset `toxic` (and `confused`) in `enemy_use_item`. |
| 16 | BattleEngine.gd:132 | Effective stats were only floored at 1; Gen 1 caps stage/badge-modified stats at 999. | `clampi(val, 1, 999)`. |
| 17 | BattleMath.gd:25 | `calc_damage` divided by `def` with no guard (DEF 0 -> inf/NaN -> garbage int). | `def = maxi(1, def)`. |
| 18 | BattleEngine.gd:1093 | TRANSFORM into an already-transformed mon copied the target's real species/stats instead of its transformed ones. | Use `atr_species()` / `_raw_stat()` which honour the target's `transformed` state. |
| 19 | BattleEngine.gd:466 | The final trapped turn (`_TRAPPED` after the trapper's counter hit 0) silently skipped the victim's action with no message. | Show "X can't move!" on that path. |
| 20 | BattleEngine.gd:328 | A sleeping/frozen player mon makes the scene auto-pick slot 0; if that move had 0 PP or was DISABLED the engine said "No PP left"/"disabled" and re-asked forever (soft-lock). | Skip the PP/disabled validation while SLP/FRZ (the move never executes). |
## Overworld (scene, maps, encounters, fx, util) (19)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 21 | overworld/EncounterSystem.gd:18 | Encounter roll drew 0..254 (`randi_range(0,254)` / `% 255`) but upstream is `rnd(256) >= rate`; every route's encounter rate was inflated by 256/255 and a rate of 255 could never fail. | Roll over 256 values: `randi_range(0, 255)` / `randi() % 256`. |
| 22 | overworld/OverworldScene.gd:534 + overworld/MapLoader.gd:121 | Caves, Pokémon Tower and other tilesets with no tall-grass tile never produced wild encounters (only `is_tall_grass` or surfing rolled). Upstream: `noGrassTile` means any dry cell uses the grass table. | Added `MapLoader.has_no_grass_tile()` and roll on every non-water cell in such tilesets. |
| 23 | overworld/OverworldScene.gd:527-540 | REPEL never worked: `GameState.repel` was set by the item but nothing decremented it or filtered encounters. | Per step: decrement, show "REPEL's effect wore off." and end the step at 0; while active, drop encounters whose level is below the first non-fainted party member (upstream `encounters.check`). |
| 24 | overworld/OverworldScene.gd:240 | `_spinning` (and `_pending_conn` / `_pending_land`) survived a map change; warping off a spinner tile made the player keep sliding on the next map's first step. | Reset all three in `_load_map`. |
| 25 | overworld/OverworldScene.gd:280-288 | Night light pools / lit-window glow were only built when a map was first loaded at night; entering a map by day and letting dusk arrive never rebuilt them (`rebuild` false, textures null). | Track `_light_maps_for`; rebuild when `la > 0` and the maps for this map are not built (reset on `_load_map`). |
| 26 | overworld/OverworldScene.gd:985-997 | `emote_on` used `await tw2.finished` and `l.queue_free()` after the actor may have been freed by a map change: Story scripts awaiting `emote` hung forever (tween on freed node never finishes) and `queue_free()` hit a freed instance. | Tween on the bubble node, wait with timers, guard with `is_instance_valid(l)`. |
| 27 | overworld/MapLoader.gd:96 | `label_override` (script-set cell looks) was not cleared by `load_map`, so a reused loader kept stale labels. | `label_override.clear()` next to `pass_override.clear()`. |
| 28 | overworld/MapLoader.gd:271 | `_cell_fx` `queue_free`d the old `CellFx_x_y` node then added a new node with the same name in the same frame; Godot renamed the new one (`@CellFx...`) so later lookups missed it and stale barrier/teleport fx leaked. | `remove_child(old)` before `queue_free()`. |
| 29 | overworld/OverworldScene.gd:272 | OPTION > DAY/NIGHT off was ignored by the world grade / light pools / clouds (only fireflies looked at it); upstream `timeOfDay()` returns `{night:0,dusk:0}`. | Force `td = {night:0, dusk:0}` when the option is off. |
| 30 | overworld/OverworldScene.gd:324-326 | Fireflies only appeared on Route*/Forest/Safari/Town maps and used a coarse "night" period; upstream shows them in every 'outdoor', 'safari' and 'forest' env (cities included) when `timeOfDay().night > 0.5`. | Use `ambient_env()` and `LightingRig.time_of_day(...).night > 0.5`. |
| 31 | overworld/OverworldScene.gd:495 | `_arrived_dir` was never cleared by a finished step (upstream `onPlayerStep` sets `arrived = false`), so after the door step-out the "bounce" rule kept suppressing push-warps. | Clear it at the top of `_on_player_step`. |
| 32 | overworld/OverworldScene.gd:684 | Idle NPCs with `dir == NONE` also randomly turned object actors (boulders, Poké Balls, fossils...); upstream only turns non-object sprites. | Add `not act.is_object`. |
| 33 | util/GameText.gd:44 | `text_for()` returned "" for labels whose upstream text is empty (e.g. MtMoonPokecenterClipboardText), giving a blank text box; upstream `G.textFor` falls back to '...' (empty string is falsy). | Return "..." when the resolved text is empty. |
| 34 | overworld/OverworldScene.gd:742 | OPTION > FOLLOWER OFF had no effect (only a debug meta flag was read). | `_lead_species()` also checks `GameState.options["follower"]`. |
| 35 | overworld/OverworldScene.gd:807 | The walking partner stayed visible while surfing or cycling; upstream sends it back into its ball. | Hide the follower when `ride != "walk"`. |
| 36 | overworld/OverworldScene.gd:1137-1157 | `flash_white` / `poison_flash` / `heal_machine` glow each spawned a tween on the same `color:a`, fighting each other and leaving the flash rect partly tinted. | One shared `_flash_tw`, killed and replaced by the next flash; `flash_white` waits on a timer (a killed tween never emits `finished`). |
| 37 | overworld/OverworldScene.gd:307 | `_process` overwrote `player.stop_hint` every frame, so scripted multi-step walks (`move_actor` chaining `start_move(..., more=true)`) decelerated and stopped at every cell. | Only drive `stop_hint` from the d-pad when the player is not `scripted`. |
| 38 | overworld/OverworldScene.gd:645 | Talking to an NPC with a fixed facing (`dir` UP/DOWN/LEFT/RIGHT, not WALK) never turned it toward the player; upstream `talkTo` turns every non-object actor. | `if not a.is_object: a.face(OPP[player.facing])`. |
| 39 | overworld/OverworldScene.gd:802 | The follower model was only set up on map load: receiving the first Pokémon (Oak's lab), changing the lead, or re-enabling the option left no/the wrong partner until the next map change (upstream `tick()` refreshes the species every frame). | `_update_follower_visibility` calls `_place_follower()` when the lead species differs from the shown one. |
## UI, menus, audio, scene routing (25)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 40 | ui/PartyMenu.gd:~168 (`_field_move` SOFTBOILED) | SOFTBOILED could target itself, a full-HP mon or a fainted mon (which it silently revived); upstream says "It won't have any effect." | Validate target (`tgt == m`, `hp >= max_hp`, `hp <= 0`) before spending HP |
| 41 | ui/PartyMenu.gd:~35-44,88,101,181 | Forced party screens (`forced`) showed "Choose a POKéMON." instead of upstream's "Bring out which POKéMON?" | Added `_default_msg()`, used for open and every message reset |
| 42 | ui/PartyMenu.gd:~76,83,92 | No cursor/select sfx in the party screen (upstream plays `cursor`/`select`) | `UI.sfx` calls added |
| 43 | ui/PxMenu.gd:~340 | `PxMenu.pick` with an empty list did `% 0` (crash) on any key press and could never be closed | Empty list: confirm/cancel finishes with -1, other input ignored |
| 44 | ui/SummaryScreen.gd:~194-204 | Move cursor `msel` kept its value when switching to another party member, leaving it out of range (no highlight, `m.moves[msel]` past end on next MOVES visit) | Reset `msel = 0` when the shown mon changes; clamp on down with 0 moves |
| 45 | ui/SummaryScreen.gd:~238 | "TO NEXT" at level 100 showed `exp_for_level(101) - exp` instead of 0 | Use `PartyMon.exp_to_next()` (0 at L100) |
| 46 | ui/BagMenu.gd:~408 (RARE_CANDY) | Level went up without raising `xp`, so EXP/TO NEXT and later battle EXP were wrong | `xp = max(xp, exp_this())` |
| 47 | ui/BagMenu.gd:~408 (RARE_CANDY) | Current HP recomputed by fraction (not Gen-1 "gain the max-HP difference") and level-up moves never learned | `recalc_keep_hp()` and `add_move()` for `moves_at_level(level)` |
| 48 | ui/BagMenu.gd:~345,368 | After tossing/using the last items the list shrank but `scroll` stayed past the end (blank rows, `▲` shown with nothing above) | Clamp `scroll`/`sel` to the new list size |
| 49 | ui/BagMenu.gd:~313-327 | No cursor/select sfx in the bag | `UI.sfx("cursor")` / `("select")` |
| 50 | ui/PCMenu.gd:~155 (`quantity`) | The ×NN picker read `is_action_just_pressed("confirm")` in the same frame as the A press that chose the item, so it instantly confirmed ×1 (withdraw/deposit quantity could never be picked) | Wait one extra frame before polling |
| 51 | ui/PCMenu.gd:~138 | Withdrawing items ignored the bag limits (99/stack, 20 slots) and could exceed 99 | Use `Story.bag_add`, "You can't carry any more items." on failure |
| 52 | ui/PCMenu.gd:~19-28,44 | PC menu always listed BILL's PC and PROF.OAK's PC; upstream shows "SOMEONE's PC" until BILL is met and OAK's PC only with the POKéDEX | Conditional on `EVENT_MET_BILL` / `EVENT_GOT_POKEDEX` |
| 53 | ui/PCMenu.gd:~17,24,44,110 | Missing `pc_on` / `pc_off` / `pc_access` sfx of pc.js | Added |
| 54 | ui/StartMenu.gd:~442 | POKéDEX row always present; upstream only after `EVENT_GOT_POKEDEX` (new-game player could open an empty dex) | Conditional row (showcase save sets the flag in `GameState.build_showcase`) |
| 55 | ui/StartMenu.gd:~438,447 | The `menu` sfx replayed every time a sub-screen returned to the start menu (upstream plays it once) | `_returning` flag |
| 56 | ui/StartMenu.gd:~476 | SAVE reported "saved the game!" even when `GameState.save()` failed | Check the return value |
| 57 | TitleScene.gd:~227 | CONTINUE ignored `load_save()` failure and started the overworld with empty/stale state | On failure show a message and stay on the title menu |
| 58 | autoload/SceneRouter.gd:~37-47,77-83,127-137 | A queued-for-free scene keeps its node name for a frame, so the replacement ("Overworld" after whiteout, a second "Battle") was auto-renamed `@Overworld@2`; Audio's name-based scene follow then never matched | Rename the outgoing node before `queue_free()` |
| 59 | autoload/SceneRouter.gd:~116-121 | Starting a battle while one is active re-ran `_suspend_active()` on the already-hidden scene, saving `PROCESS_MODE_DISABLED` as its "original" mode so the overworld stayed frozen afterwards | Free old battle, skip re-suspending |
| 60 | autoload/Audio.gd:~232 | Battles are overlays (`SceneRouter._active` stays the hidden Overworld), so the wild/trainer/gym-leader battle theme was never selected and the map song was never restored after a battle | `_follow_scene` looks at `SceneRouter._battle` first |
| 61 | autoload/Audio.gd:~236 | The Intro scene auto-started "oak_intro" (Routes2) over the silent opening card; upstream is silent until IntroBattle | `Intro` follows no song |
| 62 | autoload/Audio.gd:~210 | While a jingle ducked the music (gain ~0) the song sequencer was not rendered at all, so music froze and resumed mid-phrase after item/heal jingles instead of continuing (audio.js duck()) | Keep rendering the ducked song |
| 63 | autoload/Audio.gd:~236 | Surfing/cycling music was replaced by the map song on the next map change (audio.js mapMusic overrides) | Follow key includes ride state; `Surfing`/`BikeRiding` override |
| 64 | autoload/GameState.gd:376 | (supporting fix for #15) showcase save now owns the POKéDEX flag so the START-menu test/reference screenshots stay correct | one line |
## Game state, data, pipeline, shaders (21)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 65 | godot/scripts/autoload/GameState.gd `exp_for_level` | Level 1 needed 1 exp (`1^3`) instead of upstream's 0 (`if (n <= 1) return 0`), so a fresh L1 mon was 1 exp above its floor and `exp_this()` disagreed with upstream | return 0 for `n <= 1` |
| 66 | GameState.gd `exp_for_level` (MEDIUM_SLOW/FAST/SLOW) | Float math (`1.2 * n^3`, `4.0*n^3/5.0`) can land just under an integer and floor one exp too low vs upstream's `Math.floor(6*n^3/5)` | pure integer arithmetic (`6 * n3 / 5 - 15n^2 + 100n - 140`, etc.) |
| 67 | GameState.gd `PartyMon.from_dict` | Saved `hp` was not clamped: a save with hp > max_hp (or edited/legacy) loaded an over-full or negative HP (upstream `Mon.from`: `min(o.hp, maxhp)`) | `clampi(hp, 0, max_hp)` |
| 68 | GameState.gd `PartyMon.from_dict` | A move missing from the saved `pp` dict had no PP entry (later `pp[m]` misses / 0 PP), PP above `pp_max` was accepted, and `moves` aliased the parsed dict's array | rebuild `pp` per move: default to `pp_max`, clamp to `0..pp_max`; `moves.duplicate()` |
| 69 | GameState.gd `reset_story_state` | `lucky_slot` and `vermilion_trash` (both in `STORY_KEYS`) were not reset, so NEW GAME inherited the previous run's slot-machine / trash-can puzzle state | reset both |
| 70 | GameState.gd `load_save` | Story keys absent from a save kept the previous session's values (stale flags/daycare/hall of fame after loading an older save) | call `reset_story_state()` before `story_from_dict()` |
| 71 | GameState.gd `load_save` | JSON numbers load as floats, so `bag` counts became `3.0` (text showed "x3.0", `%d`/int-keyed logic and equality with ints misbehaved) | coerce every bag count to `int` |
| 72 | GameState.gd `load_save` | Legacy saves with `options.text_speed = "NORMAL"` went through `int("NORMAL") == 0` and came back as the SLOWEST speed (clamped to 1) | map SLOW/NORMAL/FAST to 1/2/3, clamp 1..3 |
| 73 | GameState.gd `load_save` / `start_new_adventure` | The SOUND option was persisted in `options` but never applied on load/new game: `sound_on`, legacy `text_speed` and the Audio mute were left at the previous state, so a save with sound OFF played music | new `apply_options()` syncs `sound_on`, `text_speed` and `/root/Audio.set_muted()`; called from both |
| 74 | GameState.gd `start_new_adventure` | NEW GAME kept the previous run's `player_name`, `rival_name`, `last_heal_map/cell` (blackout destination) and `clock_minutes` (upstream `newState()`: RED / BLUE / lastHeal null / fresh clock) | reset to PalletTown defaults, RED, BLUE, 9:00 |
| 75 | GameState.gd `add_to_party` | With a full party the new mon was created, marked caught, then silently dropped (upstream `receiveMon` sends it to the current box) | append to the current PC box when it has < 20 mons |
| 76 | GameState.gd `load_save` | `FileAccess.open` returning null (unreadable file) crashed on `f.get_as_text()`; a save whose JSON root is not an object crashed on `var d: Dictionary = parsed` | null-check the file, require `parsed is Dictionary` |
| 77 | GameState.gd `load_save` | `player_cell` / `last_heal_cell` with fewer than 2 entries crashed on `pc[1]` (index out of range) | fall back to the defaults when the array is short |
| 78 | GameState.gd `load_save` | `clock_minutes` outside 0..1440 (edited/legacy save) broke `time_period()` (always "night") and the lighting cycle until the next wrap | `fposmod(..., 1440.0)` |
| 79 | GameState.gd `box()` | Any index >= 12 silently created extra PC boxes (a stray `current_box` grew unlimited boxes; Bill's PC has 12) | clamp index to 0..11 |
| 80 | godot/assets/shaders/transition.gdshader (mode 6) | The radial "clock" wipe used `atan(d.x, -d.y)/TAU + 0.5`, which starts at 6 o'clock (angle 0 is at the bottom) instead of 12 o'clock | `fract(atan(d.x, -d.y)/TAU)` so it sweeps clockwise from the top |
| 81 | pipeline/blender/gen_vfx.py `s_needle` | Both cones were rotated the wrong way: the tips met at the origin (bow-tie, fat ends outward) instead of a spike whose tip leads at +X with a short tail behind | swap the two Y rotations (+90 deg / -90 deg) |
| 82 | pipeline/blender/env_buildings.py `porch` | The front gable triangle spanned only `-w/2 .. w/2` while the roof slopes overhang to `+-(w/2+ov)`, leaving open gaps at both ends of the gable | triangle spans `+-(w/2+ov)` (and the dead `ov * 0` term is gone) |
| 83 | pipeline/blender/gen_world.py `hash2` | The tree-canopy jitter used exact 32-bit integer multiplies, which differ from upstream's double-precision `hash2` (59 of 60 sample points mismatch), so generated tree meshes did not use upstream's noise | import `upstream_px.hash2` (verified 0/60 mismatches vs node) |
| 84 | pipeline/scripts/stitch_rows.py | `sorted()` ordered row files lexicographically (`row10` before `row2`), stacking rows in the wrong order | natural-sort key |
| 85 | pipeline/scripts/compose_model_sheet.py | Without `--ids`/`--manifest`, `ids` stayed `None` and the script died with `TypeError: object of type 'NoneType' has no len()` | explicit usage error via `sys.exit` |
## Found while testing (3)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 86 | godot/scripts/fx/TickInterp.gd:55 | An effect node that had not popped in yet (zero-scale basis) made `Transform3D.interpolate_with` print "Basis must be normalized" errors every frame during battles. | `_blend()` snaps to the nearer end when either basis is degenerate. |
| 87 | godot/scripts/tools/ModelSheet.gd:49 | `--anim=<clip> --anim_t=<t>` contact sheets always showed the Idle pose: the paused player was still cross-fading from Idle (default blend 0.12 s, never advancing), so no clip could be inspected. | Zero the blend time after `AnimUtil.fix_looping` and hold the pose with `speed_scale = 0` instead of `pause()`. |
| 88 | godot/scripts/overworld/SpinnerTest.gd:12 | `var ok := <Variant expr>` is a GDScript parse error, which makes Godot idle forever instead of failing. | Explicit `bool` type. |
