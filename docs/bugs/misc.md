# Found while testing

| # | file:line | symptom | fix |
|---|-----------|---------|-----|
| 1 | godot/scripts/fx/TickInterp.gd:55 | An effect node that had not popped in yet (zero-scale basis) made `Transform3D.interpolate_with` print "Basis must be normalized" errors every frame during battles. | `_blend()` snaps to the nearer end when either basis is degenerate. |
| 2 | godot/scripts/tools/ModelSheet.gd:49 | `--anim=<clip> --anim_t=<t>` contact sheets always showed the Idle pose: the paused player was still cross-fading from Idle (default blend 0.12 s, never advancing), so no clip could be inspected. | Zero the blend time after `AnimUtil.fix_looping` and hold the pose with `speed_scale = 0` instead of `pause()`. |
| 3 | godot/scripts/overworld/SpinnerTest.gd:12 | `var ok := <Variant expr>` is a GDScript parse error, which makes Godot idle forever instead of failing. | Explicit `bool` type. |
| 4 | godot/scripts/ui/PartyMenu.gd:151 | FLY, SURF, CUT, STRENGTH, FLASH, DIG and TELEPORT from the party menu only said "There's no place to use X here." (`Story.use_field_move` was never called), so FLASH/Rock Tunnel, FLY and menu-SURF were unreachable. | The party menu closes and runs `Story.use_field_move`; if the move can't be used it reopens. |
| 5 | godot/scripts/ui/BagMenu.gd:130 | BICYCLE, rods, ESCAPE ROPE, REPEL, POKé FLUTE, ITEMFINDER and COIN CASE answered "OAK: This isn't the time to use that!" (`Story.use_field_item` was never called). | The bag closes and runs `Story.use_field_item`; on failure it reopens. |
