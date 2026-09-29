# Characters / tools bugs fixed

Area: `pipeline/blender/char_*.py`, `gen_characters.py`, `humanoid_legacy.py`, `pipeline/scripts/*.js`, `godot/scripts/tools/*.gd`,
`util/CharacterSkin.gd`, `ui/CharacterModel.gd`, `ui/Diorama.gd`, `ui/IntroCreatures.gd`. Line numbers are approximate (post-fix).
Animation bugs were found by forward-kinematics of every generated clip (rest matrices from `char_rig.skeleton`, poses from `char_anim`)
and checking foot heights, hand-vs-head/torso penetration and foot slide; the clips are still seamless (first frame == last frame).
The node scripts (`bake_*.js`, `extract_*.js`) were re-run against `/tmp/claude-0/upstream` into a temp dir: fonts, logos, town map, text, music,
mons and cast/chars JSON are byte-identical to the committed assets, no defects found there.

| # | file:line | symptom | fix |
|---|-----------|---------|-----|
| 1 | pipeline/blender/char_anim.py:430 (`build_bow`) | Bow moved the pelvis along **X** (sideways) while the thighs tilt forward 6 deg, so both feet slid ~0.55 rows forward off the floor spot | Pelvis moves back along **+Y** (0.5 rows) so the feet stay planted |
| 2 | pipeline/blender/char_anim.py:311 (`build_cheer`) | Crouch lowered the pelvis 0.7 rows but bent the knees only 12/24 deg (needs ~30/60), so both feet sank ~0.6 rows into the floor at the bottom of every hop | Knee bend computed from the pelvis drop (`acos(1-drop/leg)`, thigh -a, shin +2a, foot compensating) |
| 3 | pipeline/blender/char_anim.py:317 (`build_cheer`) | Arms raised 150 deg: wrists and forearms pass through the (wider than the shoulders) head/hair | 130 deg (V shape), clears the head ellipsoid |
| 4 | pipeline/blender/char_anim.py:512 (`build_stretch`) | Arms raised 168 deg = straight up, hands inside the skull (v = 0.5 of the head ellipsoid) | 136 deg |
| 5 | pipeline/blender/char_anim.py:530 (`build_dance`) | `hips z += -0.25 + ...` lowered the pelvis with straight legs; the standing foot sank ~0.5 rows | Bounce only upward (`+0.32*abs(sin)`) |
| 6 | pipeline/blender/char_anim.py:537 (`build_dance`) | Lifted leg used thigh -9 / shin +16 with no foot compensation: toe pitched ~0.4 rows below the floor | Real knee bend (-16/+32) with a flat foot (-16) |
| 7 | pipeline/blender/char_anim.py:463 (`build_sleep`) | 0.2-row pelvis drop but only -6/+8 deg knee bend: feet ~0.4 rows below the floor | -15/+30 deg knees, foot -15 |
| 8 | pipeline/blender/char_anim.py:593 + gen_characters.py:102 | `build_surf` was never called by `build_all`: the documented `Surf` clip (and `CharacterSkin.LOOPING_EXTRA["Surf"]`) never existed in any generated glb | Added to `build_all` and to the manifest `animations` |
| 9 | pipeline/blender/char_anim.py:599 (`build_all`) | `build.stoop` (fishing_guru, gramps, granny, mr_fuji, agatha in character_looks.json) was stored in `Prop` but never used anywhere: old characters stood bolt upright | Constant forward hunch (spine +5, chest +4, head -6 deg per unit stoop) layered on every clip |
| 10 | godot/scripts/tools/MotionLab.gd:145 | `_record` dereferenced `_ow.follower` (null with `--follower=none`, documented flag): crash on the first frame | Null-safe follower columns |
| 11 | godot/scripts/tools/MotionLab.gd:196-205 | "Walk restarts" test hard-coded the legacy 0.8 s clip (`prev_pos < 0.6`); the generated Walk is 0.27 s so **every natural loop wrap** was counted as a mid-loop restart | Threshold uses the real length of the player's Walk clip |
| 12 | godot/scripts/tools/MotionLab.gd:24 | `--route=rrrd` (lowercase) hit `dir_of[ch]` KeyError | Route upper-cased |
| 13 | godot/scripts/ui/Diorama.gd:57 (`stand`) | `bounds(node, Transform3D(node.basis, ZERO))` applies `node.transform` again: rotation counted twice and the node's **previous position leaked into `b.position.y`**; OakSpeech calls `stand` every frame, so the model's height on screen was recomputed from its own last position (jitter / drift) | Reset `node.position` first and call `bounds(node, IDENTITY)` |
| 14 | godot/scripts/ui/IntroCreatures.gd:210 (`_knot_mesh`) | Triangle winding reversed (Godot front faces are clockwise; verified with `SurfaceTool.generate_normals`): the coloured front of the six-link knot was back-face culled and lit with inverted normals, the grey back skin showed instead | Front face winds 0-1-2, back face reversed |
| 15 | godot/scripts/util/CharacterSkin.gd:135 (`apply`) | Legacy humanoid tint always used the `shirt` colour for `mat_top`; for `body=coat` (Oak, scientists, Mr. Fuji) the torso regions are the **coat** colour (chars.js X/x) | `mat_top` uses `coat` when body is coat |
| 16 | godot/scripts/ui/CharacterModel.gd:15 (`build`) | `CharacterSkin.instantiate` never returns null (empty `Node3D` when nothing exists), so the humanoid / capsule fallbacks were dead code and menus got an invisible character | Fall through when the instance has no children |
| 17 | godot/scripts/tools/EnvSheet.gd:59 | `load(path)` result used without null check (unimportable glb) - null deref, sheet lost | Skip the file |
| 18 | godot/scripts/tools/EnvSheet.gd:39, ModelSheet.gd:21 | `--cols=0` (or garbage) made `float(n)/float(cols)` and `i % cols` divide by zero | `cols` clamped to >= 1 |
| 19 | godot/scripts/tools/EnvSheet.gd:25 | `--only=barrel.glb` became `barrel.glb.glb` (nothing rendered) | Suffix only added when missing |
| 20 | godot/scripts/tools/VfxSheet.gd:15-19 | `--moves=flamethrower` (case) / `--moves=` (empty) built a 0-row image (`Image.create` fails) and unknown ids silently animated nothing | Upper-cased, empty list -> error + quit |
| 21 | godot/scripts/tools/VfxSheet.gd:55 (`_evo_sheet`) | `--moves=evo:CHARMANDER` indexed `parts[2]` out of range | Usage error + quit |
