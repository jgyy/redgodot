# UI / audio bugs fixed

All paths under `godot/scripts/`. Line numbers are approximate (post-fix).

| # | file:line | symptom | fix |
|---|-----------|---------|-----|
| 1 | ui/PartyMenu.gd:~168 (`_field_move` SOFTBOILED) | SOFTBOILED could target itself, a full-HP mon or a fainted mon (which it silently revived); upstream says "It won't have any effect." | Validate target (`tgt == m`, `hp >= max_hp`, `hp <= 0`) before spending HP |
| 2 | ui/PartyMenu.gd:~35-44,88,101,181 | Forced party screens (`forced`) showed "Choose a POKéMON." instead of upstream's "Bring out which POKéMON?" | Added `_default_msg()`, used for open and every message reset |
| 3 | ui/PartyMenu.gd:~76,83,92 | No cursor/select sfx in the party screen (upstream plays `cursor`/`select`) | `UI.sfx` calls added |
| 4 | ui/PxMenu.gd:~340 | `PxMenu.pick` with an empty list did `% 0` (crash) on any key press and could never be closed | Empty list: confirm/cancel finishes with -1, other input ignored |
| 5 | ui/SummaryScreen.gd:~194-204 | Move cursor `msel` kept its value when switching to another party member, leaving it out of range (no highlight, `m.moves[msel]` past end on next MOVES visit) | Reset `msel = 0` when the shown mon changes; clamp on down with 0 moves |
| 6 | ui/SummaryScreen.gd:~238 | "TO NEXT" at level 100 showed `exp_for_level(101) - exp` instead of 0 | Use `PartyMon.exp_to_next()` (0 at L100) |
| 7 | ui/BagMenu.gd:~408 (RARE_CANDY) | Level went up without raising `xp`, so EXP/TO NEXT and later battle EXP were wrong | `xp = max(xp, exp_this())` |
| 8 | ui/BagMenu.gd:~408 (RARE_CANDY) | Current HP recomputed by fraction (not Gen-1 "gain the max-HP difference") and level-up moves never learned | `recalc_keep_hp()` and `add_move()` for `moves_at_level(level)` |
| 9 | ui/BagMenu.gd:~345,368 | After tossing/using the last items the list shrank but `scroll` stayed past the end (blank rows, `▲` shown with nothing above) | Clamp `scroll`/`sel` to the new list size |
| 10 | ui/BagMenu.gd:~313-327 | No cursor/select sfx in the bag | `UI.sfx("cursor")` / `("select")` |
| 11 | ui/PCMenu.gd:~155 (`quantity`) | The ×NN picker read `is_action_just_pressed("confirm")` in the same frame as the A press that chose the item, so it instantly confirmed ×1 (withdraw/deposit quantity could never be picked) | Wait one extra frame before polling |
| 12 | ui/PCMenu.gd:~138 | Withdrawing items ignored the bag limits (99/stack, 20 slots) and could exceed 99 | Use `Story.bag_add`, "You can't carry any more items." on failure |
| 13 | ui/PCMenu.gd:~19-28,44 | PC menu always listed BILL's PC and PROF.OAK's PC; upstream shows "SOMEONE's PC" until BILL is met and OAK's PC only with the POKéDEX | Conditional on `EVENT_MET_BILL` / `EVENT_GOT_POKEDEX` |
| 14 | ui/PCMenu.gd:~17,24,44,110 | Missing `pc_on` / `pc_off` / `pc_access` sfx of pc.js | Added |
| 15 | ui/StartMenu.gd:~442 | POKéDEX row always present; upstream only after `EVENT_GOT_POKEDEX` (new-game player could open an empty dex) | Conditional row (showcase save sets the flag in `GameState.build_showcase`) |
| 16 | ui/StartMenu.gd:~438,447 | The `menu` sfx replayed every time a sub-screen returned to the start menu (upstream plays it once) | `_returning` flag |
| 17 | ui/StartMenu.gd:~476 | SAVE reported "saved the game!" even when `GameState.save()` failed | Check the return value |
| 18 | TitleScene.gd:~227 | CONTINUE ignored `load_save()` failure and started the overworld with empty/stale state | On failure show a message and stay on the title menu |
| 19 | autoload/SceneRouter.gd:~37-47,77-83,127-137 | A queued-for-free scene keeps its node name for a frame, so the replacement ("Overworld" after whiteout, a second "Battle") was auto-renamed `@Overworld@2`; Audio's name-based scene follow then never matched | Rename the outgoing node before `queue_free()` |
| 20 | autoload/SceneRouter.gd:~116-121 | Starting a battle while one is active re-ran `_suspend_active()` on the already-hidden scene, saving `PROCESS_MODE_DISABLED` as its "original" mode so the overworld stayed frozen afterwards | Free old battle, skip re-suspending |
| 21 | autoload/Audio.gd:~232 | Battles are overlays (`SceneRouter._active` stays the hidden Overworld), so the wild/trainer/gym-leader battle theme was never selected and the map song was never restored after a battle | `_follow_scene` looks at `SceneRouter._battle` first |
| 22 | autoload/Audio.gd:~236 | The Intro scene auto-started "oak_intro" (Routes2) over the silent opening card; upstream is silent until IntroBattle | `Intro` follows no song |
| 23 | autoload/Audio.gd:~210 | While a jingle ducked the music (gain ~0) the song sequencer was not rendered at all, so music froze and resumed mid-phrase after item/heal jingles instead of continuing (audio.js duck()) | Keep rendering the ducked song |
| 24 | autoload/Audio.gd:~236 | Surfing/cycling music was replaced by the map song on the next map change (audio.js mapMusic overrides) | Follow key includes ride state; `Surfing`/`BikeRiding` override |
| 25 | autoload/GameState.gd:376 | (supporting fix for #15) showcase save now owns the POKéDEX flag so the START-menu test/reference screenshots stay correct | one line |
