# Bug-fix log

A review of every subsystem found and fixed **171 bugs**. Each was checked against the code (and against the upstream JS game where the rule comes from it) before being fixed; the per-area source tables live in `docs/bugs/`.

* **Battle engine (BattleEngine / BattleMath / BattleSide)**: 20
* **Battle presentation (scene, VFX, HUD, actors, shaders)**: 19
* **Overworld (scene, maps, encounters, fx, util)**: 19
* **Story scripts (Story.gd and story/*)**: 20
* **UI, menus, audio, scene routing**: 25
* **Game state, data, pipeline, shaders**: 21
* **Character pipeline, tools**: 21
* **This branch's new features**: 21
* **Found while testing**: 5

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
## Battle presentation (scene, VFX, HUD, actors, shaders) (19)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 21 | ui/BattleHud.gd:141-157 (`_hp_box`) | Enemy HP box corner cut was off by one column (`range(w-8, w)` vs upstream `i > w-8`) and truncated the whole row at the first cut pixel, dropping right-edge border pixels upstream keeps. | Per-pixel cut test exactly like upstream; interior run only for never-cut columns. |
| 22 | ui/BattleHud.gd:306 (`_menu_bg`) | Bag/party background stripes had the two colours swapped versus upstream `menuBg` / `Px.menu_bg` (`c1` where `((x+y+T)>>3)` is odd). | Offset stripe start by 8. |
| 23 | ui/BattleHud.gd:422 (`_draw_slot`) | Party slot bottom shade band was 3 rows starting one row too high (upstream `j > h-4` = 2 rows). | `rect(x+1, y+h-3, w-2, 2)`. |
| 24 | BattleScene.gd:1149 (`trainer_defeated`) | Gym leaders / rivals never got the leader victory jingle: `boss` was read from `b.trainer` but the engine stores it in `b.o`. | Read `b.o.get("boss")`. |
| 25 | BattleScene.gd:1296 (`evolve`) | The white flash after evolving never showed: `hud.flash_amt` was written directly and `_apply_visuals` overwrote it every tick. | Drive `flash` / `flash_color` on the scene. |
| 26 | EvolutionStage.gd:91,129 | One shared `_base_scale` (the last built actor's) was applied to both forms every frame, so the old form was drawn at the new form's size. | Per-actor `base_scale` meta. |
| 27 | EvolutionStage.gd:83 | Models were centred at y=70 px but upstream draws the 64px sprite at (128,30), centre y=62 (where the burst/flare are). | Aim the ray at (160,62). |
| 28 | BattleScene.gd:837-880 (`party_menu`) | Choosing the target of a bag item (POTION etc.) refused the mon that is out ("is already out!") and fainted mons (REVIVE: "has no energy left"); upstream `pick` allows any mon. | New `item_target` mode skipping both checks, prompt "Use on which POKéMON?". |
| 29 | BattleScene.gd:882 (`_screen_say`) | After any party-screen notice the prompt was reset to "Choose a POKéMON." even in the forced "Bring out which POKéMON?" screen. | Restore the screen's own base message. |
| 30 | BattleScene.gd:1065 (`anim`) | Hovering species (`Hover` idle) had their idle clip restarted after every move (`current_clip()` never equals "Idle"). | Also accept `idle_clip()`. |
| 31 | BattleScene.gd:293 (`_apply_actor`) | `Vector3 * Basis.inverse()` is the transposed-inverse (= the basis itself): wrong world-to-local order (latent, invisible only while anchors are unrotated). | `basis.inverse() * v`. |
| 32 | BattleScene.gd:262-277 (`_place_on_px`) | Trainer / player pics were placed relative to the anchors, which already slide with the platform, so the intro slide was applied twice (pics raced ahead of their platform). | Place from the resting `ENEMY_POS` / `PLAYER_POS` (upstream trainerX / playerPicX are absolute). |
| 33 | BattleScene.gd:51,260 | Trainer hidden for `trainer_x < 0`, so the slide-in popped in half-visible at the screen edge instead of sliding. | Separate hidden sentinel (-1000); visible when > -200. |
| 34 | BattleScene.gd:540 (`_ball_at`) | The ball was written with a bare `global_transform` after `_capture_interp`, so the next capture recorded the blended pose: ball flight lagged / smoothed itself. | Record with `vfx.interp.put`; ball dropped from `_capture_interp`. |
| 35 | BattleVfx.gd:639-640 (`_bolt_seg`) | `Basis.scaled()` is a global (row) scale: rotated non-uniform scale collapsed every lightning segment into a horizontal bar. | `bb * Basis.from_scale(...)`. |
| 36 | BattleVfx.gd:1909 (`r_string`) | Same misuse: STRING SHOT's criss-cross threads all rendered horizontal. | Local scale. |
| 37 | BattleVfx.gd:1209-1210, 1726 | Same misuse skewed BITE jaws and LICK tongue. | Local scale. |
| 38 | BattleTransition.gd:8 | Boss transition ran 48 frames; upstream holds 52 for every non-wild kind. | `"boss": 52`. |
| 39 | assets/shaders/battle_transition.gdshader:46 | Boss ball transition lacked upstream's opening white flicker (`t<10 && t%4<2`). | Added the flicker. |
## Overworld (scene, maps, encounters, fx, util) (19)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 40 | overworld/EncounterSystem.gd:18 | Encounter roll drew 0..254 (`randi_range(0,254)` / `% 255`) but upstream is `rnd(256) >= rate`; every route's encounter rate was inflated by 256/255 and a rate of 255 could never fail. | Roll over 256 values: `randi_range(0, 255)` / `randi() % 256`. |
| 41 | overworld/OverworldScene.gd:534 + overworld/MapLoader.gd:121 | Caves, Pokémon Tower and other tilesets with no tall-grass tile never produced wild encounters (only `is_tall_grass` or surfing rolled). Upstream: `noGrassTile` means any dry cell uses the grass table. | Added `MapLoader.has_no_grass_tile()` and roll on every non-water cell in such tilesets. |
| 42 | overworld/OverworldScene.gd:527-540 | REPEL never worked: `GameState.repel` was set by the item but nothing decremented it or filtered encounters. | Per step: decrement, show "REPEL's effect wore off." and end the step at 0; while active, drop encounters whose level is below the first non-fainted party member (upstream `encounters.check`). |
| 43 | overworld/OverworldScene.gd:240 | `_spinning` (and `_pending_conn` / `_pending_land`) survived a map change; warping off a spinner tile made the player keep sliding on the next map's first step. | Reset all three in `_load_map`. |
| 44 | overworld/OverworldScene.gd:280-288 | Night light pools / lit-window glow were only built when a map was first loaded at night; entering a map by day and letting dusk arrive never rebuilt them (`rebuild` false, textures null). | Track `_light_maps_for`; rebuild when `la > 0` and the maps for this map are not built (reset on `_load_map`). |
| 45 | overworld/OverworldScene.gd:985-997 | `emote_on` used `await tw2.finished` and `l.queue_free()` after the actor may have been freed by a map change: Story scripts awaiting `emote` hung forever (tween on freed node never finishes) and `queue_free()` hit a freed instance. | Tween on the bubble node, wait with timers, guard with `is_instance_valid(l)`. |
| 46 | overworld/MapLoader.gd:96 | `label_override` (script-set cell looks) was not cleared by `load_map`, so a reused loader kept stale labels. | `label_override.clear()` next to `pass_override.clear()`. |
| 47 | overworld/MapLoader.gd:271 | `_cell_fx` `queue_free`d the old `CellFx_x_y` node then added a new node with the same name in the same frame; Godot renamed the new one (`@CellFx...`) so later lookups missed it and stale barrier/teleport fx leaked. | `remove_child(old)` before `queue_free()`. |
| 48 | overworld/OverworldScene.gd:272 | OPTION > DAY/NIGHT off was ignored by the world grade / light pools / clouds (only fireflies looked at it); upstream `timeOfDay()` returns `{night:0,dusk:0}`. | Force `td = {night:0, dusk:0}` when the option is off. |
| 49 | overworld/OverworldScene.gd:324-326 | Fireflies only appeared on Route*/Forest/Safari/Town maps and used a coarse "night" period; upstream shows them in every 'outdoor', 'safari' and 'forest' env (cities included) when `timeOfDay().night > 0.5`. | Use `ambient_env()` and `LightingRig.time_of_day(...).night > 0.5`. |
| 50 | overworld/OverworldScene.gd:495 | `_arrived_dir` was never cleared by a finished step (upstream `onPlayerStep` sets `arrived = false`), so after the door step-out the "bounce" rule kept suppressing push-warps. | Clear it at the top of `_on_player_step`. |
| 51 | overworld/OverworldScene.gd:684 | Idle NPCs with `dir == NONE` also randomly turned object actors (boulders, Poké Balls, fossils...); upstream only turns non-object sprites. | Add `not act.is_object`. |
| 52 | util/GameText.gd:44 | `text_for()` returned "" for labels whose upstream text is empty (e.g. MtMoonPokecenterClipboardText), giving a blank text box; upstream `G.textFor` falls back to '...' (empty string is falsy). | Return "..." when the resolved text is empty. |
| 53 | overworld/OverworldScene.gd:742 | OPTION > FOLLOWER OFF had no effect (only a debug meta flag was read). | `_lead_species()` also checks `GameState.options["follower"]`. |
| 54 | overworld/OverworldScene.gd:807 | The walking partner stayed visible while surfing or cycling; upstream sends it back into its ball. | Hide the follower when `ride != "walk"`. |
| 55 | overworld/OverworldScene.gd:1137-1157 | `flash_white` / `poison_flash` / `heal_machine` glow each spawned a tween on the same `color:a`, fighting each other and leaving the flash rect partly tinted. | One shared `_flash_tw`, killed and replaced by the next flash; `flash_white` waits on a timer (a killed tween never emits `finished`). |
| 56 | overworld/OverworldScene.gd:307 | `_process` overwrote `player.stop_hint` every frame, so scripted multi-step walks (`move_actor` chaining `start_move(..., more=true)`) decelerated and stopped at every cell. | Only drive `stop_hint` from the d-pad when the player is not `scripted`. |
| 57 | overworld/OverworldScene.gd:645 | Talking to an NPC with a fixed facing (`dir` UP/DOWN/LEFT/RIGHT, not WALK) never turned it toward the player; upstream `talkTo` turns every non-object actor. | `if not a.is_object: a.face(OPP[player.facing])`. |
| 58 | overworld/OverworldScene.gd:802 | The follower model was only set up on map load: receiving the first Pokémon (Oak's lab), changing the lead, or re-enabling the option left no/the wrong partner until the next map change (upstream `tick()` refreshes the species every frame). | `_update_follower_visibility` calls `_place_follower()` when the lead species differs from the shown one. |
## Story scripts (Story.gd and story/*) (20)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 59 | autoload/Story.gd:649 (`mon_name`) | Text for a Pokémon without a nickname printed the species id (`MR_MIME`, `NIDORAN_M`, `FARFETCHD`): "... traded X for ...", "X was transferred to BILL's PC", "X used STRENGTH", Name Rater text, etc. (`PartyMon.nickname` defaults to the id; upstream `Mon.name` falls back to the species display name.) | Use `PartyMon.display_name()`. |
| 60 | autoload/Story.gd:733 (`heal_all`) | Every script heal (Mom, Silph 9F nurse, Tower 5F purified zone, blackout, Pokécenter nurse) restored PP from the move's *base* PP, undoing PP UPs, and never cleared the sleep counter. | Call `PartyMon.heal_full()` (HP, status, sleep, PP up to `pp_max`) and emit `party_changed`. |
| 61 | autoload/Story.gd:786 (`new_mon`) | Starter, Eevee, Lapras, Hitmonlee/chan, revived fossils, Magikarp and in-game-trade Pokémon were created with all-zero DVs and no OT (upstream `new G.Mon` rolls random DVs and uses the player as OT), so every story Pokémon had worse stats than upstream. | `PartyMon.new(sp, lv, {"random": true})` and `ot = player_name`. |
| 62 | autoload/Story.gd:881 (`in_game_trade`) and story/Early.gd:261 (`trade`) | The traded-in Pokémon got `set_meta("ot", "TRAINER")`, but `BattleEngine` (traded 1.5x EXP bonus) and the save file read the `ot` property, so traded Pokémon never got the bonus and lost the OT on load. | `nm.set("ot", "TRAINER")`. |
| 63 | autoload/Story.gd:883 (`in_game_trade`) | The party slot was replaced without `party_changed`, so the follower / party UIs kept showing the Pokémon that was traded away. | Emit `GameState.party_changed`. |
| 64 | autoload/Story.gd:853 (`party_screen` fallback) | The "Trade which POKéMON?" / daycare / Name Rater list showed raw ids (`MR_MIME  Lv20`). | `display_name()`. |
| 65 | autoload/Story.gd:1363 (`nurse_heal`) | Healing only set `last_heal_town`, but random-encounter defeats go through `SceneRouter.whiteout()` which reads `last_heal_map/cell`: after healing in Viridian a wild-battle loss still returned the player to Pallet Town (trainer losses used the right town). | Keep `last_heal_map` / `last_heal_cell` in sync with the blackout point. |
| 66 | autoload/Story.gd:834 (`name_entry`) | `UI` has no `name_entry`, so the fallback returned the default name: answering YES to "Do you want to give a nickname?" (starter, gifts, Name Rater) never opened the naming screen. | Fallback opens `NamingScreen.ask_name` on the UI layer. |
| 67 | autoload/Story.gd:1524 (`set_cells`) | A `null` label ("original look") only overrode passability; `MapLoader.label_override` kept the earlier `barrier` / `door` label, so opened Mansion switch gates, Cinnabar quiz gates, Elite Four doors and the S.S. Anne gangway stayed drawn as blocked (barrier fx, hidden object) although walkable. | Clear the cell override first, then set the passability. |
| 68 | story/Early.gd:453 (`_jigglypuff`) | The JIGGLYPUFF text (`say(..., no_wait)`) stays on screen as a sticky box until the next UI call; upstream pops its StaticBox when the song ends, so the text hung around forever. | New `Story.drop_sticky()` called when the song ends. |
| 69 | story/Mid.gd:362 (`_name_rater`) | Traded Pokémon were detected with `has_meta("ot")`, which nothing else set (and is lost on save): a traded Pokémon could be renamed. | Compare the real `ot` property (empty = own). |
| 70 | story/Extra.gd:21 (`_gentleman`) | Retrieving a Pokémon from the Day Care rebuilt it with `PartyMon.new(...)`, resetting its DVs, stat EXP, OT and PP UPs (stats fell to the all-zero-DV values). Its name text used the species id. | Level up in place (`recalc_keep_hp()`, full HP as upstream `recalc(true)`), names through `display_name()`. |
| 71 | story/Late.gd:1113 (`hall_of_fame`) | The recorded Hall of Fame team used `nickname`, i.e. species ids (`MR_MIME`) for un-nicknamed Pokémon. | `display_name()`. |
| 72 | story/Late.gd:1137 (`hall_of_fame`) | After the credits `last_heal_town` was reset to Pallet Town but the legacy `last_heal_map/cell` (used by `SceneRouter.whiteout()`) kept the pre-League town. | Reset both pairs. |
| 73 | autoload/Story.gd:1894 (`try_push_boulder`) | `strength` was only set by `use_field_move("STRENGTH")`, which nothing calls (the party menu has no STRENGTH entry), so boulders (Seafoam, Victory Road, Rock Tunnel area) could never be pushed. | Pushing against a boulder with the RAINBOWBADGE and a STRENGTH Pokémon activates STRENGTH ("X used STRENGTH." / "X can move boulders."), then pushes. |
| 74 | autoload/Story.gd:128-145 (`_on_battle_started/_ended`) | Random encounters go `OverworldScene -> SceneRouter.start_battle`, never through `Story.wild_battle`, so Safari Zone battles were never flagged `safari` (normal battle menu, no BAIT/ROCK/BALLs) and running out of SAFARI BALLs never ended the game. | Tag wild encounters in the Safari as `safari` on `SceneRouter.battle_started` and run `safari_game_over` on `battle_ended` (skipped for battles started by `wild_battle`, which already does it). |
| 75 | autoload/Story.gd:1759-1790 (`field_interact`, `_bookshelf_label`) | upstream `G.fieldInteract` texts for tile-based "signs" (bookshelves, wall town map, shop / Pokécenter shelves, elevator panel in lobbies, Indigo Plateau statues, ship books) were not ported: facing them did nothing. | Ported the `bookshelves` table (tileset name + quad tile) with upstream's fallback texts. |
| 76 | autoload/Story.gd:675 (`dex_page`) | `UI` has no `dex_page`, so the POKéDEX page shown by the dojo Poké Balls (before "Do you want this?"), Bill's PC list, fossil / zoo signs and the S.S. Anne gentleman never appeared. | Fallback shows the page with `PokedexMenu` (`page_species`) and waits for A/B. |
| 77 | story/Late.gd:391 (`_articuno_binoculars`) | The ARTICUNO picture (DisplayMonFrontSpriteInBox) vanished by itself after 90 frames; upstream waits for A/B. | `wait_button` with a 10 minute cap instead of 90 frames. |
| 78 | autoload/Story.gd:1066 (`_sync_runtime_state`) | Runtime-only story state (`cell_overrides` such as cut trees, elevator redirects, Mt. Moon rocket `sight_off`, surf/bike/strength/flash, `busy`) was never cleared, so a NEW GAME / CONTINUE in the same session (e.g. back at the title after the Hall of Fame) inherited it (trees already cut, opened doors, ...). | When `GameState.flags` is replaced by a fresh dictionary, clear that state on the next `on_enter`. |
## UI, menus, audio, scene routing (25)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 79 | ui/PartyMenu.gd:~168 (`_field_move` SOFTBOILED) | SOFTBOILED could target itself, a full-HP mon or a fainted mon (which it silently revived); upstream says "It won't have any effect." | Validate target (`tgt == m`, `hp >= max_hp`, `hp <= 0`) before spending HP |
| 80 | ui/PartyMenu.gd:~35-44,88,101,181 | Forced party screens (`forced`) showed "Choose a POKéMON." instead of upstream's "Bring out which POKéMON?" | Added `_default_msg()`, used for open and every message reset |
| 81 | ui/PartyMenu.gd:~76,83,92 | No cursor/select sfx in the party screen (upstream plays `cursor`/`select`) | `UI.sfx` calls added |
| 82 | ui/PxMenu.gd:~340 | `PxMenu.pick` with an empty list did `% 0` (crash) on any key press and could never be closed | Empty list: confirm/cancel finishes with -1, other input ignored |
| 83 | ui/SummaryScreen.gd:~194-204 | Move cursor `msel` kept its value when switching to another party member, leaving it out of range (no highlight, `m.moves[msel]` past end on next MOVES visit) | Reset `msel = 0` when the shown mon changes; clamp on down with 0 moves |
| 84 | ui/SummaryScreen.gd:~238 | "TO NEXT" at level 100 showed `exp_for_level(101) - exp` instead of 0 | Use `PartyMon.exp_to_next()` (0 at L100) |
| 85 | ui/BagMenu.gd:~408 (RARE_CANDY) | Level went up without raising `xp`, so EXP/TO NEXT and later battle EXP were wrong | `xp = max(xp, exp_this())` |
| 86 | ui/BagMenu.gd:~408 (RARE_CANDY) | Current HP recomputed by fraction (not Gen-1 "gain the max-HP difference") and level-up moves never learned | `recalc_keep_hp()` and `add_move()` for `moves_at_level(level)` |
| 87 | ui/BagMenu.gd:~345,368 | After tossing/using the last items the list shrank but `scroll` stayed past the end (blank rows, `▲` shown with nothing above) | Clamp `scroll`/`sel` to the new list size |
| 88 | ui/BagMenu.gd:~313-327 | No cursor/select sfx in the bag | `UI.sfx("cursor")` / `("select")` |
| 89 | ui/PCMenu.gd:~155 (`quantity`) | The ×NN picker read `is_action_just_pressed("confirm")` in the same frame as the A press that chose the item, so it instantly confirmed ×1 (withdraw/deposit quantity could never be picked) | Wait one extra frame before polling |
| 90 | ui/PCMenu.gd:~138 | Withdrawing items ignored the bag limits (99/stack, 20 slots) and could exceed 99 | Use `Story.bag_add`, "You can't carry any more items." on failure |
| 91 | ui/PCMenu.gd:~19-28,44 | PC menu always listed BILL's PC and PROF.OAK's PC; upstream shows "SOMEONE's PC" until BILL is met and OAK's PC only with the POKéDEX | Conditional on `EVENT_MET_BILL` / `EVENT_GOT_POKEDEX` |
| 92 | ui/PCMenu.gd:~17,24,44,110 | Missing `pc_on` / `pc_off` / `pc_access` sfx of pc.js | Added |
| 93 | ui/StartMenu.gd:~442 | POKéDEX row always present; upstream only after `EVENT_GOT_POKEDEX` (new-game player could open an empty dex) | Conditional row (showcase save sets the flag in `GameState.build_showcase`) |
| 94 | ui/StartMenu.gd:~438,447 | The `menu` sfx replayed every time a sub-screen returned to the start menu (upstream plays it once) | `_returning` flag |
| 95 | ui/StartMenu.gd:~476 | SAVE reported "saved the game!" even when `GameState.save()` failed | Check the return value |
| 96 | TitleScene.gd:~227 | CONTINUE ignored `load_save()` failure and started the overworld with empty/stale state | On failure show a message and stay on the title menu |
| 97 | autoload/SceneRouter.gd:~37-47,77-83,127-137 | A queued-for-free scene keeps its node name for a frame, so the replacement ("Overworld" after whiteout, a second "Battle") was auto-renamed `@Overworld@2`; Audio's name-based scene follow then never matched | Rename the outgoing node before `queue_free()` |
| 98 | autoload/SceneRouter.gd:~116-121 | Starting a battle while one is active re-ran `_suspend_active()` on the already-hidden scene, saving `PROCESS_MODE_DISABLED` as its "original" mode so the overworld stayed frozen afterwards | Free old battle, skip re-suspending |
| 99 | autoload/Audio.gd:~232 | Battles are overlays (`SceneRouter._active` stays the hidden Overworld), so the wild/trainer/gym-leader battle theme was never selected and the map song was never restored after a battle | `_follow_scene` looks at `SceneRouter._battle` first |
| 100 | autoload/Audio.gd:~236 | The Intro scene auto-started "oak_intro" (Routes2) over the silent opening card; upstream is silent until IntroBattle | `Intro` follows no song |
| 101 | autoload/Audio.gd:~210 | While a jingle ducked the music (gain ~0) the song sequencer was not rendered at all, so music froze and resumed mid-phrase after item/heal jingles instead of continuing (audio.js duck()) | Keep rendering the ducked song |
| 102 | autoload/Audio.gd:~236 | Surfing/cycling music was replaced by the map song on the next map change (audio.js mapMusic overrides) | Follow key includes ride state; `Surfing`/`BikeRiding` override |
| 103 | autoload/GameState.gd:376 | (supporting fix for #15) showcase save now owns the POKéDEX flag so the START-menu test/reference screenshots stay correct | one line |
## Game state, data, pipeline, shaders (21)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 104 | godot/scripts/autoload/GameState.gd `exp_for_level` | Level 1 needed 1 exp (`1^3`) instead of upstream's 0 (`if (n <= 1) return 0`), so a fresh L1 mon was 1 exp above its floor and `exp_this()` disagreed with upstream | return 0 for `n <= 1` |
| 105 | GameState.gd `exp_for_level` (MEDIUM_SLOW/FAST/SLOW) | Float math (`1.2 * n^3`, `4.0*n^3/5.0`) can land just under an integer and floor one exp too low vs upstream's `Math.floor(6*n^3/5)` | pure integer arithmetic (`6 * n3 / 5 - 15n^2 + 100n - 140`, etc.) |
| 106 | GameState.gd `PartyMon.from_dict` | Saved `hp` was not clamped: a save with hp > max_hp (or edited/legacy) loaded an over-full or negative HP (upstream `Mon.from`: `min(o.hp, maxhp)`) | `clampi(hp, 0, max_hp)` |
| 107 | GameState.gd `PartyMon.from_dict` | A move missing from the saved `pp` dict had no PP entry (later `pp[m]` misses / 0 PP), PP above `pp_max` was accepted, and `moves` aliased the parsed dict's array | rebuild `pp` per move: default to `pp_max`, clamp to `0..pp_max`; `moves.duplicate()` |
| 108 | GameState.gd `reset_story_state` | `lucky_slot` and `vermilion_trash` (both in `STORY_KEYS`) were not reset, so NEW GAME inherited the previous run's slot-machine / trash-can puzzle state | reset both |
| 109 | GameState.gd `load_save` | Story keys absent from a save kept the previous session's values (stale flags/daycare/hall of fame after loading an older save) | call `reset_story_state()` before `story_from_dict()` |
| 110 | GameState.gd `load_save` | JSON numbers load as floats, so `bag` counts became `3.0` (text showed "x3.0", `%d`/int-keyed logic and equality with ints misbehaved) | coerce every bag count to `int` |
| 111 | GameState.gd `load_save` | Legacy saves with `options.text_speed = "NORMAL"` went through `int("NORMAL") == 0` and came back as the SLOWEST speed (clamped to 1) | map SLOW/NORMAL/FAST to 1/2/3, clamp 1..3 |
| 112 | GameState.gd `load_save` / `start_new_adventure` | The SOUND option was persisted in `options` but never applied on load/new game: `sound_on`, legacy `text_speed` and the Audio mute were left at the previous state, so a save with sound OFF played music | new `apply_options()` syncs `sound_on`, `text_speed` and `/root/Audio.set_muted()`; called from both |
| 113 | GameState.gd `start_new_adventure` | NEW GAME kept the previous run's `player_name`, `rival_name`, `last_heal_map/cell` (blackout destination) and `clock_minutes` (upstream `newState()`: RED / BLUE / lastHeal null / fresh clock) | reset to PalletTown defaults, RED, BLUE, 9:00 |
| 114 | GameState.gd `add_to_party` | With a full party the new mon was created, marked caught, then silently dropped (upstream `receiveMon` sends it to the current box) | append to the current PC box when it has < 20 mons |
| 115 | GameState.gd `load_save` | `FileAccess.open` returning null (unreadable file) crashed on `f.get_as_text()`; a save whose JSON root is not an object crashed on `var d: Dictionary = parsed` | null-check the file, require `parsed is Dictionary` |
| 116 | GameState.gd `load_save` | `player_cell` / `last_heal_cell` with fewer than 2 entries crashed on `pc[1]` (index out of range) | fall back to the defaults when the array is short |
| 117 | GameState.gd `load_save` | `clock_minutes` outside 0..1440 (edited/legacy save) broke `time_period()` (always "night") and the lighting cycle until the next wrap | `fposmod(..., 1440.0)` |
| 118 | GameState.gd `box()` | Any index >= 12 silently created extra PC boxes (a stray `current_box` grew unlimited boxes; Bill's PC has 12) | clamp index to 0..11 |
| 119 | godot/assets/shaders/transition.gdshader (mode 6) | The radial "clock" wipe used `atan(d.x, -d.y)/TAU + 0.5`, which starts at 6 o'clock (angle 0 is at the bottom) instead of 12 o'clock | `fract(atan(d.x, -d.y)/TAU)` so it sweeps clockwise from the top |
| 120 | pipeline/blender/gen_vfx.py `s_needle` | Both cones were rotated the wrong way: the tips met at the origin (bow-tie, fat ends outward) instead of a spike whose tip leads at +X with a short tail behind | swap the two Y rotations (+90 deg / -90 deg) |
| 121 | pipeline/blender/env_buildings.py `porch` | The front gable triangle spanned only `-w/2 .. w/2` while the roof slopes overhang to `+-(w/2+ov)`, leaving open gaps at both ends of the gable | triangle spans `+-(w/2+ov)` (and the dead `ov * 0` term is gone) |
| 122 | pipeline/blender/gen_world.py `hash2` | The tree-canopy jitter used exact 32-bit integer multiplies, which differ from upstream's double-precision `hash2` (59 of 60 sample points mismatch), so generated tree meshes did not use upstream's noise | import `upstream_px.hash2` (verified 0/60 mismatches vs node) |
| 123 | pipeline/scripts/stitch_rows.py | `sorted()` ordered row files lexicographically (`row10` before `row2`), stacking rows in the wrong order | natural-sort key |
| 124 | pipeline/scripts/compose_model_sheet.py | Without `--ids`/`--manifest`, `ids` stayed `None` and the script died with `TypeError: object of type 'NoneType' has no len()` | explicit usage error via `sys.exit` |
## Character pipeline, tools (21)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 125 | pipeline/blender/char_anim.py:430 (`build_bow`) | Bow moved the pelvis along **X** (sideways) while the thighs tilt forward 6 deg, so both feet slid ~0.55 rows forward off the floor spot | Pelvis moves back along **+Y** (0.5 rows) so the feet stay planted |
| 126 | pipeline/blender/char_anim.py:311 (`build_cheer`) | Crouch lowered the pelvis 0.7 rows but bent the knees only 12/24 deg (needs ~30/60), so both feet sank ~0.6 rows into the floor at the bottom of every hop | Knee bend computed from the pelvis drop (`acos(1-drop/leg)`, thigh -a, shin +2a, foot compensating) |
| 127 | pipeline/blender/char_anim.py:317 (`build_cheer`) | Arms raised 150 deg: wrists and forearms pass through the (wider than the shoulders) head/hair | 130 deg (V shape), clears the head ellipsoid |
| 128 | pipeline/blender/char_anim.py:512 (`build_stretch`) | Arms raised 168 deg = straight up, hands inside the skull (v = 0.5 of the head ellipsoid) | 136 deg |
| 129 | pipeline/blender/char_anim.py:530 (`build_dance`) | `hips z += -0.25 + ...` lowered the pelvis with straight legs; the standing foot sank ~0.5 rows | Bounce only upward (`+0.32*abs(sin)`) |
| 130 | pipeline/blender/char_anim.py:537 (`build_dance`) | Lifted leg used thigh -9 / shin +16 with no foot compensation: toe pitched ~0.4 rows below the floor | Real knee bend (-16/+32) with a flat foot (-16) |
| 131 | pipeline/blender/char_anim.py:463 (`build_sleep`) | 0.2-row pelvis drop but only -6/+8 deg knee bend: feet ~0.4 rows below the floor | -15/+30 deg knees, foot -15 |
| 132 | pipeline/blender/char_anim.py:593 + gen_characters.py:102 | `build_surf` was never called by `build_all`: the documented `Surf` clip (and `CharacterSkin.LOOPING_EXTRA["Surf"]`) never existed in any generated glb | Added to `build_all` and to the manifest `animations` |
| 133 | pipeline/blender/char_anim.py:599 (`build_all`) | `build.stoop` (fishing_guru, gramps, granny, mr_fuji, agatha in character_looks.json) was stored in `Prop` but never used anywhere: old characters stood bolt upright | Constant forward hunch (spine +5, chest +4, head -6 deg per unit stoop) layered on every clip |
| 134 | godot/scripts/tools/MotionLab.gd:145 | `_record` dereferenced `_ow.follower` (null with `--follower=none`, documented flag): crash on the first frame | Null-safe follower columns |
| 135 | godot/scripts/tools/MotionLab.gd:196-205 | "Walk restarts" test hard-coded the legacy 0.8 s clip (`prev_pos < 0.6`); the generated Walk is 0.27 s so **every natural loop wrap** was counted as a mid-loop restart | Threshold uses the real length of the player's Walk clip |
| 136 | godot/scripts/tools/MotionLab.gd:24 | `--route=rrrd` (lowercase) hit `dir_of[ch]` KeyError | Route upper-cased |
| 137 | godot/scripts/ui/Diorama.gd:57 (`stand`) | `bounds(node, Transform3D(node.basis, ZERO))` applies `node.transform` again: rotation counted twice and the node's **previous position leaked into `b.position.y`**; OakSpeech calls `stand` every frame, so the model's height on screen was recomputed from its own last position (jitter / drift) | Reset `node.position` first and call `bounds(node, IDENTITY)` |
| 138 | godot/scripts/ui/IntroCreatures.gd:210 (`_knot_mesh`) | Triangle winding reversed (Godot front faces are clockwise; verified with `SurfaceTool.generate_normals`): the coloured front of the six-link knot was back-face culled and lit with inverted normals, the grey back skin showed instead | Front face winds 0-1-2, back face reversed |
| 139 | godot/scripts/util/CharacterSkin.gd:135 (`apply`) | Legacy humanoid tint always used the `shirt` colour for `mat_top`; for `body=coat` (Oak, scientists, Mr. Fuji) the torso regions are the **coat** colour (chars.js X/x) | `mat_top` uses `coat` when body is coat |
| 140 | godot/scripts/ui/CharacterModel.gd:15 (`build`) | `CharacterSkin.instantiate` never returns null (empty `Node3D` when nothing exists), so the humanoid / capsule fallbacks were dead code and menus got an invisible character | Fall through when the instance has no children |
| 141 | godot/scripts/tools/EnvSheet.gd:59 | `load(path)` result used without null check (unimportable glb) - null deref, sheet lost | Skip the file |
| 142 | godot/scripts/tools/EnvSheet.gd:39, ModelSheet.gd:21 | `--cols=0` (or garbage) made `float(n)/float(cols)` and `i % cols` divide by zero | `cols` clamped to >= 1 |
| 143 | godot/scripts/tools/EnvSheet.gd:25 | `--only=barrel.glb` became `barrel.glb.glb` (nothing rendered) | Suffix only added when missing |
| 144 | godot/scripts/tools/VfxSheet.gd:15-19 | `--moves=flamethrower` (case) / `--moves=` (empty) built a 0-row image (`Image.create` fails) and unknown ids silently animated nothing | Upper-cased, empty list -> error + quit |
| 145 | godot/scripts/tools/VfxSheet.gd:55 (`_evo_sheet`) | `--moves=evo:CHARMANDER` indexed `parts[2]` out of range | Usage error + quit |
## This branch's new features (21)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 146 | godot/scripts/ui/CharacterCreator.gd:_arrow | The left/right selector arrows are swapped: the "left" arrow points right and vice versa. | Swapped the column mapping (`cx := x + (i if dir < 0 else 2 - i)`) so dir -1 has its tip on the left. |
| 147 | godot/scripts/ui/CharacterCreator.gd:step_value | A colour that is not in the palette (old save, hand-edited look) has `find()` = -1, so LEFT jumps to the second-to-last swatch and the step is off by one. | An out-of-palette colour now lands on the first swatch (right) or the last (left). |
| 148 | godot/scripts/ui/CharacterCreator.gd:_rebuild | Every change rebuilds the preview model, which restarts in Idle while the label still names the old clip (e.g. "DANCE") for up to 3 s. | `_rebuild()` re-plays `PREVIEW_CLIPS[_clip_i]` on the new model. |
| 149 | godot/scripts/util/PlayerLook.gd:from_dict | A save with a malformed colour such as `"#zz"` passes the `begins_with("#")` test; `Color("#zz")` then errors or turns black in PlayerModel. | Colours are accepted only if `Color.html_is_valid`; otherwise the default is kept. |
| 150 | godot/scripts/fx/Debris.gd:_process | A chunk spawned below `ground_y` and moving up hits the floor branch, and its velocity is flipped downward, so it sinks and rests inside the ground. | A rising chunk is only clamped to the floor, and bounce/rest is applied only to falling chunks. |
| 151 | godot/scripts/fx/Debris.gd:_process/_take | A chunk node freed externally (scene teardown) makes `_process` touch a freed instance, and a freed pooled node is handed out again by `_take`. | `_process` drops chunks whose node is invalid; `_take` skips invalid pooled nodes. |
| 152 | godot/scripts/overworld/OwActor.gd:_update_gait | A gesture started within `IDLE_GRACE` of a step ending (emote reactions, talk) is overridden by the lingering walk clip and never shows. | The grace-window "walking" state is ignored while `_gesture != ""`. |
| 153 | godot/scripts/overworld/OwActor.gd:setup | Re-skinning an actor (`setup`) leaves `_gesture`/`gesture_wait` from the old model, so `is_gesturing()` stays true with no clip playing (a "Sleep" gesture lasts 1e6 s). | `setup` clears `_gesture`, `_gesture_left`, `gesture_wait`. |
| 154 | godot/scripts/overworld/OwActor.gd:place | `place()` (warp / map load) resets the clip to Idle but keeps `_gesture`, so the actor counts as gesturing and skips Idle handling until the timer expires. | `place()` clears `_gesture`. |
| 155 | godot/scripts/overworld/OverworldScene.gd:_emote_node | The Label3D fallback prints the raw kind ("heart", "...") because the glyph mapping was dropped in the refactor. | Restored the `{"heart": "♥", "...": "…"}` mapping in the fallback label. |
| 156 | godot/scripts/overworld/OverworldScene.gd:_try_interact | Talking to the follower calls `play_once("Talk")`, but Talk is a looping clip, so the queued Idle never plays and the Pokémon talks forever. | A 1.6 s timer hands the actor back to `Idle` if it is still in Talk. |
| 157 | godot/scripts/overworld/OverworldScene.gd:_process | `_player_idle` keeps counting while a menu or dialogue is open, so the player fidgets (Dance/Stretch) the instant the UI closes. | The UI-open / locked branch resets `_player_idle`. |
| 158 | godot/scripts/overworld/OverworldScene.gd:heal_machine | `heal_machine` is called once per ball, and each call restarts the nurse's Bow clip so she twitches. | Bow is only started when the nurse is not already gesturing. |
| 159 | godot/scripts/ui/OakSpeech.gd:_rebuild_player_model | The old model is only `queue_free`d, so `Diorama.play_anim(holder)` finds the old (about to die) AnimationPlayer and the new model stays in T-pose. | The old children are removed from the tree before `queue_free`. |
| 160 | godot/scripts/battle/BattleScene.gd:ball_throw | After the bounce loop the ball's x jumps from `tx + rolled*(1-exp(-0.12i))*2` to `tx + rolled*2`, and the spin angle snaps (`rolled*i*0.05`) at every bounce and again at the shakes. | Track `bx` and set `tx = bx` after the loop; the spin is accumulated and reused during the shakes. |
| 161 | godot/scripts/util/PlayerModel.gd:build | The player model skips `CharacterSkin._fit_bounds`, so tall hair / beanies change the bounding box and `OwActor._fit_height` shrinks the player relative to NPCs. | `build()` applies `_fit_bounds` when `CharacterSkin.fit_bounds` is set. |
| 162 | godot/scripts/util/PlayerModel.gd:_texture | With `toon = false` there are no ShaderMaterial overrides, so the recoloured atlas is never applied and the model is untextured. | Plain materials get a `StandardMaterial3D` override copy carrying the recoloured atlas. |
| 163 | godot/assets/shaders/battle_transition.gdshader:56 | `smoothstep(0.55R, 0.35R, x)` has reversed edges (undefined in GLSL), so the boss-ball highlight can vanish or invert on some drivers. | Rewritten as `1.0 - smoothstep(0.35R, 0.55R, x)`. |
| 164 | pipeline/capture_screenshots.sh:~183 | `NPC_CAST` contains `lass`, which is not a cast.json key, so that gesture column renders the untinted humanoid. | Replaced with the valid key `girl`. |
| 165 | pipeline/scripts/stitch_rows.py:14 | Called with no rows (e.g. an unmatched glob after a failed shot) it dies with `max() arg is an empty sequence` and no usage hint. | Explicit usage check and `sys.exit` before processing. |
| 166 | pipeline/blender/gen_player_parts.py:main | `any(p.wait() for p in procs)` stops at the first failing worker, leaving the other Blender jobs unwaited/orphaned while the parent exits 1. | All workers are waited on (`codes = [p.wait() ...]`) before checking failure. |
## Found while testing (5)

| # | Where | Symptom | Fix |
|---|---|---|---|
| 167 | godot/scripts/fx/TickInterp.gd:55 | An effect node that had not popped in yet (zero-scale basis) made `Transform3D.interpolate_with` print "Basis must be normalized" errors every frame during battles. | `_blend()` snaps to the nearer end when either basis is degenerate. |
| 168 | godot/scripts/tools/ModelSheet.gd:49 | `--anim=<clip> --anim_t=<t>` contact sheets always showed the Idle pose: the paused player was still cross-fading from Idle (default blend 0.12 s, never advancing), so no clip could be inspected. | Zero the blend time after `AnimUtil.fix_looping` and hold the pose with `speed_scale = 0` instead of `pause()`. |
| 169 | godot/scripts/overworld/SpinnerTest.gd:12 | `var ok := <Variant expr>` is a GDScript parse error, which makes Godot idle forever instead of failing. | Explicit `bool` type. |
| 170 | godot/scripts/ui/PartyMenu.gd:151 | FLY, SURF, CUT, STRENGTH, FLASH, DIG and TELEPORT from the party menu only said "There's no place to use X here." (`Story.use_field_move` was never called), so FLASH/Rock Tunnel, FLY and menu-SURF were unreachable. | The party menu closes and runs `Story.use_field_move`; if the move can't be used it reopens. |
| 171 | godot/scripts/ui/BagMenu.gd:130 | BICYCLE, rods, ESCAPE ROPE, REPEL, POKé FLUTE, ITEMFINDER and COIN CASE answered "OAK: This isn't the time to use that!" (`Story.use_field_item` was never called). | The bag closes and runs `Story.use_field_item`; on failure it reopens. |
