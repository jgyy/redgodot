# Battle presentation bug fixes

Area: `godot/scripts/battle/` (BattleScene, BattleVfx, BattleStage, EvolutionStage, PokemonActor, BattleTransition, ui/BattleHud) and `godot/assets/shaders/battle_transition.gdshader`. Ground truth: upstream `src/game/battlescene.js`, `battleflow.js`, `art/vfx.js`.

| # | file:line | symptom | fix |
|---|-----------|---------|-----|
| 1 | ui/BattleHud.gd:141-157 (`_hp_box`) | Enemy HP box corner cut was off by one column (`range(w-8, w)` vs upstream `i > w-8`) and truncated the whole row at the first cut pixel, dropping right-edge border pixels upstream keeps. | Per-pixel cut test exactly like upstream; interior run only for never-cut columns. |
| 2 | ui/BattleHud.gd:306 (`_menu_bg`) | Bag/party background stripes had the two colours swapped versus upstream `menuBg` / `Px.menu_bg` (`c1` where `((x+y+T)>>3)` is odd). | Offset stripe start by 8. |
| 3 | ui/BattleHud.gd:422 (`_draw_slot`) | Party slot bottom shade band was 3 rows starting one row too high (upstream `j > h-4` = 2 rows). | `rect(x+1, y+h-3, w-2, 2)`. |
| 4 | BattleScene.gd:1149 (`trainer_defeated`) | Gym leaders / rivals never got the leader victory jingle: `boss` was read from `b.trainer` but the engine stores it in `b.o`. | Read `b.o.get("boss")`. |
| 5 | BattleScene.gd:1296 (`evolve`) | The white flash after evolving never showed: `hud.flash_amt` was written directly and `_apply_visuals` overwrote it every tick. | Drive `flash` / `flash_color` on the scene. |
| 6 | EvolutionStage.gd:91,129 | One shared `_base_scale` (the last built actor's) was applied to both forms every frame, so the old form was drawn at the new form's size. | Per-actor `base_scale` meta. |
| 7 | EvolutionStage.gd:83 | Models were centred at y=70 px but upstream draws the 64px sprite at (128,30), centre y=62 (where the burst/flare are). | Aim the ray at (160,62). |
| 8 | BattleScene.gd:837-880 (`party_menu`) | Choosing the target of a bag item (POTION etc.) refused the mon that is out ("is already out!") and fainted mons (REVIVE: "has no energy left"); upstream `pick` allows any mon. | New `item_target` mode skipping both checks, prompt "Use on which POKéMON?". |
| 9 | BattleScene.gd:882 (`_screen_say`) | After any party-screen notice the prompt was reset to "Choose a POKéMON." even in the forced "Bring out which POKéMON?" screen. | Restore the screen's own base message. |
| 10 | BattleScene.gd:1065 (`anim`) | Hovering species (`Hover` idle) had their idle clip restarted after every move (`current_clip()` never equals "Idle"). | Also accept `idle_clip()`. |
| 11 | BattleScene.gd:293 (`_apply_actor`) | `Vector3 * Basis.inverse()` is the transposed-inverse (= the basis itself): wrong world-to-local order (latent, invisible only while anchors are unrotated). | `basis.inverse() * v`. |
| 12 | BattleScene.gd:262-277 (`_place_on_px`) | Trainer / player pics were placed relative to the anchors, which already slide with the platform, so the intro slide was applied twice (pics raced ahead of their platform). | Place from the resting `ENEMY_POS` / `PLAYER_POS` (upstream trainerX / playerPicX are absolute). |
| 13 | BattleScene.gd:51,260 | Trainer hidden for `trainer_x < 0`, so the slide-in popped in half-visible at the screen edge instead of sliding. | Separate hidden sentinel (-1000); visible when > -200. |
| 14 | BattleScene.gd:540 (`_ball_at`) | The ball was written with a bare `global_transform` after `_capture_interp`, so the next capture recorded the blended pose: ball flight lagged / smoothed itself. | Record with `vfx.interp.put`; ball dropped from `_capture_interp`. |
| 15 | BattleVfx.gd:639-640 (`_bolt_seg`) | `Basis.scaled()` is a global (row) scale: rotated non-uniform scale collapsed every lightning segment into a horizontal bar. | `bb * Basis.from_scale(...)`. |
| 16 | BattleVfx.gd:1909 (`r_string`) | Same misuse: STRING SHOT's criss-cross threads all rendered horizontal. | Local scale. |
| 17 | BattleVfx.gd:1209-1210, 1726 | Same misuse skewed BITE jaws and LICK tongue. | Local scale. |
| 18 | BattleTransition.gd:8 | Boss transition ran 48 frames; upstream holds 52 for every non-wild kind. | `"boss": 52`. |
| 19 | assets/shaders/battle_transition.gdshader:46 | Boss ball transition lacked upstream's opening white flicker (`t<10 && t%4<2`). | Added the flicker. |

Not run against a renderer; scripts were syntax-checked and the project test suite (355 checks) passes on a scratch copy.
