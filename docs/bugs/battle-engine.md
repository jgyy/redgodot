# Battle engine bug fixes

Area: `godot/scripts/battle/BattleEngine.gd`, `BattleMath.gd`, `BattleNullUI.gd` (ground truth: upstream `src/game/battle.js`, Gen-1 rules).

| # | file:line | symptom | fix |
|---|-----------|---------|-----|
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
