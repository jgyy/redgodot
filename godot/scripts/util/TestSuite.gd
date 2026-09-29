class_name TestSuite
extends RefCounted
## Minimal in-engine test suite (no external addons). Run via the normal project
## boot so autoloads (GameData/GameState/SceneRouter) are guaranteed initialized:
##   godot4 --headless --rendering-driver opengl3 --path godot -- --run-tests
## See Main.gd for the entry point. Exits process code 0 on pass, 1 on failure.

var passed := 0
var failures: Array = []

func check(cond: bool, label: String) -> void:
	if cond:
		passed += 1
	else:
		failures.append(label)

func run_all(tree: SceneTree) -> void:
	check(GameData != null, "GameData autoload present")
	check(GameData.species.size() == 151, "151 species loaded (got %d)" % GameData.species.size())
	check(GameData.moves.size() > 0, "moves loaded (%d)" % GameData.moves.size())
	check(GameData.maps.size() == 223, "223 maps loaded (got %d)" % GameData.maps.size())
	check(GameData.mon_art.has("PIKACHU"), "PIKACHU vector art present")
	check(GameData.cast.has("red"), "cast has 'red'")

	_test_type_chart()
	_test_damage_formula()
	_test_height_scaling()
	_test_map_classification(tree)
	_test_encounter_table()
	_test_party_mon()
	_test_lighting_and_clock()
	_test_dialogue_text()
	_test_ui_state()
	_test_ui_widgets(tree)
	_test_save_load()
	_test_new_game_defaults()
	AudioTests.run(self)
	_test_models_3d(tree)
	_test_new_features()
	StoryTests.run(self)
	MotionTests.run(self, tree.current_scene if tree.current_scene else tree.root)  # overworld motion continuity
	BattleTests.run(self)  # battle engine / stage / UI (scripts/battle/BattleTests.gd)

func _test_type_chart() -> void:
	check(GameData.type_multiplier("WATER", ["FIRE"]) == 2.0, "WATER is super effective vs FIRE")
	check(GameData.type_multiplier("FIRE", ["WATER"]) == 0.5, "FIRE is not very effective vs WATER")
	check(GameData.type_multiplier("NORMAL", ["GHOST"]) == 0.0, "NORMAL has no effect on GHOST")
	check(GameData.type_multiplier("NORMAL", ["NORMAL"]) == 1.0, "NORMAL vs NORMAL is neutral")

func _test_damage_formula() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	var dmg := BattleMath.calc_damage(10, 35, 15, 15, "NORMAL", ["NORMAL"], ["GRASS"], false, rng)
	check(dmg > 0, "non-zero damage for a valid attack (got %d)" % dmg)
	check(dmg < 50, "damage is sane for a low-level Tackle (got %d)" % dmg)

	var zero_power := BattleMath.calc_damage(10, 0, 15, 15, "NORMAL", [], [], false, rng)
	check(zero_power == 0, "zero-power move deals zero damage")

	# Compare crit vs non-crit with identically-seeded RNGs (so the final
	# 217-255/255 random factor draw matches) and identical types, isolating
	# the level-doubling effect the formula gives critical hits.
	var rng_a := RandomNumberGenerator.new(); rng_a.seed = 7
	var rng_b := RandomNumberGenerator.new(); rng_b.seed = 7
	var normal_dmg := BattleMath.calc_damage(10, 35, 15, 15, "NORMAL", ["NORMAL"], ["GRASS"], false, rng_a)
	var crit_dmg := BattleMath.calc_damage(10, 35, 15, 15, "NORMAL", ["NORMAL"], ["GRASS"], true, rng_b)
	check(crit_dmg >= normal_dmg, "critical hit deals at least as much damage (%d vs %d)" % [crit_dmg, normal_dmg])

	var stab_dmg := BattleMath.calc_damage(10, 35, 15, 15, "FIRE", ["FIRE"], ["NORMAL"], false, rng)
	var no_stab_dmg := BattleMath.calc_damage(10, 35, 15, 15, "FIRE", ["WATER"], ["NORMAL"], false, rng)
	check(stab_dmg >= no_stab_dmg, "same-type attack bonus increases damage")

func _test_height_scaling() -> void:
	var h := GameData.species_height_m("PIKACHU")
	check(h > 0.1 and h < 3.0, "Pikachu height is sane (got %.2fm)" % h)

func _test_map_classification(tree: SceneTree) -> void:
	# MapLoader.load_map() only needs to be a valid Node (its GridMap child is
	# parented to it directly); it doesn't need to be inside the live tree for
	# this check, which avoids "parent busy" issues while Main is still in _ready().
	var ml := MapLoader.new()
	var ok := ml.load_map("PalletTown")
	check(ok, "PalletTown loads")
	check(ml.width == 20 and ml.height == 18, "PalletTown dimensions match source data (20x18)")
	check(not ml.warp_at(Vector2i(5, 5)).is_empty(), "PalletTown has a warp at (5,5) -> Red's house")
	# collision comes from the quad's collision tile (upstream GameMap), not the quad index
	check(ml.passable(Vector2i(5, 5)) and ml.is_door_tile(Vector2i(5, 5)), "Red's house door cell is a passable door tile")
	check(not ml.passable(Vector2i(0, 5)), "Pallet's west tree border blocks")
	check(ml.passable(Vector2i(9, 8)), "Pallet's central path is walkable")
	check(not ml.passable(Vector2i(5, 3)), "Red's house walls block")
	check(ml.is_water(Vector2i(5, 15)) and not ml.passable(Vector2i(5, 15)), "Pallet's pond is water (surf only)")
	check(ml.connection_beyond(Vector2i(9, -1)).get("conn", {}).get("map", "") == "Route1", "Pallet connects north to Route 1")
	check(ml.label_at(Vector2i(0, 5)).begins_with("tree"), "baked labels: Pallet's border is trees")
	ml.free()
	var r1 := MapLoader.new()
	r1.load_map("Route1", false)
	var grass := 0
	var ledges := 0
	for y in range(r1.height):
		for x in range(r1.width):
			if r1.is_tall_grass(Vector2i(x, y)):
				grass += 1
			if r1.is_ledge_jump(Vector2i(x, y), "down"):
				ledges += 1
	check(grass == 104, "Route 1 has its 104 tall-grass cells (got %d)" % grass)
	check(ledges > 0, "Route 1 has ledges you can hop down (got %d)" % ledges)
	r1.free()
	_test_all_maps()

## Every map loads, has a bake, a walkable cell, and every warp leads to a real map/warp.
func _test_all_maps() -> void:
	var loaded := 0
	var baked := 0
	var walkable := 0
	var bad_warps: Array = []
	for name in GameData.maps.keys():
		var ml := MapLoader.new()
		if ml.load_map(name, false):
			loaded += 1
		if FileAccess.file_exists("res://assets/maps/%s.json" % name) and ResourceLoader.exists("res://assets/maps/%s_ground.png" % name):
			baked += 1
		var any := false
		for y in range(ml.height):
			for x in range(ml.width):
				if ml.passable(Vector2i(x, y)):
					any = true
					break
			if any:
				break
		if any:
			walkable += 1
		for w in ml.map_data.get("warps", []):
			var to := String(w.get("to", ""))
			if to == "LAST_MAP":
				continue
			var dm := GameData.get_map(to)
			if dm.is_empty() or int(w.get("warp", 0)) >= (dm.get("warps", []) as Array).size():
				bad_warps.append("%s->%s#%d" % [name, to, int(w.get("warp", 0))])
		ml.free()
	var n := GameData.maps.size()
	check(loaded == n, "all %d maps load (got %d)" % [n, loaded])
	check(baked == n, "all %d maps have a 3D bake (got %d)" % [n, baked])
	check(walkable == n, "all %d maps have walkable cells (got %d)" % [n, walkable])
	check(bad_warps.size() <= 2, "warps lead to existing maps/warps (bad: %s)" % [bad_warps])

func _test_encounter_table() -> void:
	var table := EncounterSystem.wild_table_for_map("Route1")
	check(table.get("rate", 0) == 25, "Route1 grass encounter rate matches source data (25)")
	check(table.get("mons", []).size() == 10, "Route1 has the classic 10-slot wild table")

func _test_party_mon() -> void:
	var m := GameState.PartyMon.new("PIKACHU", 10)
	check(m.max_hp > 0, "PartyMon computes positive max HP")
	check(m.hp == m.max_hp, "new PartyMon starts at full HP")
	check(not m.moves.is_empty(), "new PartyMon has starting moves")
	check(not m.is_fainted(), "fresh PartyMon is not fainted")
	m.hp = 0
	check(m.is_fainted(), "0 HP PartyMon is fainted")

func _test_lighting_and_clock() -> void:
	check(GameState.time_period(12.0 * 60.0) == "day", "noon is day")
	check(GameState.time_period(19.0 * 60.0) == "dusk", "7 PM is dusk")
	check(GameState.time_period(23.0 * 60.0) == "night", "11 PM is night")
	check(GameState.time_period(0.0) == "night", "midnight is night")
	for period in LightingRig.periods():
		check(LightingRig.PRESETS.has(period), "LightingRig has a preset for %s" % period)
	var env := Environment.new()
	LightingRig.apply(null, env, "night")
	var night_bg := env.background_color
	LightingRig.apply(null, env, "day")
	check(env.background_color != night_bg, "day/night presets produce different sky colors")

func _test_dialogue_text() -> void:
	check(DialogueText.is_humanoid_sprite("oak"), "oak is a talkable NPC sprite")
	check(not DialogueText.is_humanoid_sprite("poke_ball"), "poke_ball is a non-humanoid prop sprite")
	check(GameText.data()["text"].size() > 2000, "text.json has upstream's text tables (%d labels)" % GameText.data()["text"].size())
	check(GameText.data()["dex"].size() == 151, "text.json has 151 Pokédex entries")
	check(GameText.dex("CHARIZARD").begins_with("CHARIZARD breathes flames"), "real Pokédex text for CHARIZARD")
	var girl := DialogueText.for_obj({"sprite": "girl", "textLabel": "PalletTownGirlText"})
	check(girl[0] == GameText.get_text("PalletTownGirlText") and girl[0].length() > 10, "NPC text comes from upstream's label table")
	check(not DialogueText.for_obj({"sprite": "totally_unknown_sprite_xyz"}).is_empty(),
		"unknown NPC sprites still get a fallback line")
	var sign_lines := DialogueText.for_sign({"textLabel": "PalletTownSignText"}, "PalletTown")
	check(sign_lines[0].findn("PALLET TOWN") >= 0, "sign text is upstream's (got: %s)" % sign_lines[0])
	check(DialogueText.for_obj({"item": "POTION", "textLabel": "PickUpItemText"})[0] == "{PLAYER} found POTION!", "item balls say what was found")
	check(DialogueText.for_obj({"sprite": "nurse", "textLabel": "ViridianPokecenterNurseText"})[0].findn("POKéMON CENTER") >= 0, "nurse falls back to the POKéMON CENTER welcome")
	var pages := Px.paginate(Px.fmt("Hello {PLAYER}!\fBye {RIVAL}.", "RED", "BLUE"))
	check(pages.size() == 2 and pages[0][0] == "Hello RED!" and pages[1][0] == "Bye BLUE.", "fmt + paginate split pages on \\f")

func _test_ui_state() -> void:
	var saved := GameState.options.duplicate()
	GameState.options = GameState.DEFAULT_OPTIONS.duplicate()
	OptionsMenu.toggle(0)
	check(GameState.options["text_speed"] == 3 and GameState.text_speed_chars() == 3, "TEXT SPEED cycles MID -> FAST")
	OptionsMenu.toggle(0)
	check(GameState.options["text_speed"] == 1, "TEXT SPEED wraps FAST -> SLOW")
	OptionsMenu.toggle(2)
	check(GameState.options["battle_style"] == "set", "BATTLE STYLE toggles to SET")
	GameState.options = saved
	check(GameState.exp_for_level("MEDIUM_SLOW", 52) == 133229, "medium-slow EXP at Lv52 matches upstream (133229)")
	GameState.build_showcase()
	check(GameState.party.size() == 6 and GameState.party[0].species_id == "CHARIZARD" and GameState.party[0].max_hp == 158, "showcase party")
	check(GameState.seen_species.size() == 126 and GameState.caught_species.size() == 75, "showcase dex 126 seen / 75 own")
	check(GameState.money == 48210 and GameState.bag.size() == 7, "showcase money and bag")
	var info := TownMap.info()
	check(info.get("where", {}).has("PalletTown") and info.get("towns", []).size() == 11, "town map bake has every town")
	check(BagMenu.item_name("POKE_BALL") == "POKé BALL", "item names come from pokedata")
	check(UI.text("PalletTownSignText") == GameText.fmt(GameText.get_text("PalletTownSignText")), "UI.text() resolves upstream labels")
	check(UI.text("NoSuchLabelAnywhere") == "...", "UI.text() falls back to '...' like G.textFor")
	GameText.vars["wStringBuffer"] = "POTION"
	check(GameText.fmt("{PLAYER} got {wStringBuffer} !") == GameState.player_name + " got POTION!", "fmt substitutes textVars and trims space before punctuation")

static func _act(action: String) -> InputEventAction:
	var e := InputEventAction.new()
	e.action = action
	e.pressed = true
	return e

func _test_ui_widgets(tree: SceneTree) -> void:
	# Main is still in _ready(): parent test nodes under it (the root is busy)
	var root: Node = tree.current_scene if tree.current_scene else tree.root
	var box := DialogueBox.new()
	root.add_child(box)
	var fin := [false]
	box.finished.connect(func(): fin[0] = true)
	box.show_lines(["Page one.\fPage two {PLAYER}."])
	check(box.visible and box._pages.size() == 2, "DialogueBox paginates on \\f")
	box._unhandled_input(_act("confirm"))
	check(box._page == 0, "DialogueBox waits for the typewriter before paging")
	box.reveal_all()
	box._unhandled_input(_act("confirm"))
	check(box._page == 1 and box._pages[1][0] == "Page two %s." % GameState.player_name, "DialogueBox pages and formats {PLAYER}")
	box.reveal_all()
	box._unhandled_input(_act("confirm"))
	check(fin[0] and not box.visible, "DialogueBox closes and emits finished after the last page")
	box.queue_free()

	var m := PxMenu.new()
	m.setup(["YES", "NO"], {"x": 262, "y": 84, "w": 52})
	root.add_child(m)
	var res := [-9]
	m.done.connect(func(r): res[0] = r)
	check(m.rows == 2 and m.h == 42, "PxMenu sizes rows like ui.js Menu")
	m._unhandled_input(_act("move_down"))
	m._unhandled_input(_act("confirm"))
	check(res[0] == 1, "PxMenu returns the chosen index")
	m.queue_free()
	var m2 := PxMenu.new()
	m2.setup(["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"], {})
	check(m2.rows == 7 and m2.y == Px.BOX.position.y - m2.h - 2 and m2.x == 320 - m2.w - 6, "PxMenu default placement/scrolling matches ui.js")
	m2.free()

	var ns := NamingScreen.new()
	root.add_child(ns)
	ns.open()
	var named := [""]
	ns.named.connect(func(n): named[0] = n)
	ns._input_event(_act("confirm"))       # 'A'
	ns._input_event(_act("move_right"))
	ns._input_event(_act("confirm"))       # 'B'
	ns._input_event(_act("menu"))          # START = done
	check(named[0] == "AB", "NamingScreen types from the letter grid (got %s)" % named[0])
	ns.queue_free()

	GameState.build_showcase()
	var host := Node.new()
	root.add_child(host)
	var sm := StartMenu.new()
	host.add_child(sm)
	sm.open()
	check(sm._items == ["POKéDEX", "POKéMON", "ITEM", "RED", "SHARE", "SAVE", "OPTION", "EXIT"], "START menu rows match upstream")
	sm._input_event(_act("move_down"))
	sm._input_event(_act("confirm"))
	check(sm.party_menu.visible and not sm.visible, "START > POKéMON opens the party screen")
	sm.party_menu._input_event(_act("cancel"))
	check(sm.visible and not sm.party_menu.visible, "leaving the party screen returns to the START menu")
	host.queue_free()

func _test_save_load() -> void:
	var saved_party := GameState.party
	var saved_map := GameState.current_map
	GameState.new_game("BULBASAUR")
	GameState.current_map = "Route1"
	GameState.player_cell = Vector2i(3, 4)
	GameState.options["text_speed"] = 3
	GameState.money = 1234
	GameState.box(0).append(GameState.PartyMon.new("PIDGEY", 7))
	GameState.pc_items = {"POTION": 2}
	var ok := GameState.save()
	check(ok, "GameState.save() succeeds")
	GameState.current_map = "PewterCity"
	var loaded := GameState.load_save()
	check(loaded, "GameState.load_save() succeeds")
	check(GameState.current_map == "Route1", "load_save() restores current_map")
	check(GameState.player_cell == Vector2i(3, 4), "load_save() restores player_cell")
	check(not GameState.party.is_empty() and GameState.party[0].species_id == "BULBASAUR",
		"load_save() restores the party")
	check(GameState.options["text_speed"] == 3 and GameState.money == 1234, "load_save() restores options and money")
	check(GameState.box(0).size() == 1 and GameState.box(0)[0].species_id == "PIDGEY", "load_save() restores PC boxes")
	check(GameState.pc_items.get("POTION", 0) == 2, "load_save() restores PC items")
	GameState.pc_boxes = []
	GameState.pc_items = {}
	GameState.options = GameState.DEFAULT_OPTIONS.duplicate()
	GameState.party = saved_party
	GameState.current_map = saved_map

func _test_new_game_defaults() -> void:
	GameState.new_game("SQUIRTLE")
	check(GameState.bag.get("POKE_BALL", 0) > 0, "new_game() starts with POKE_BALLs")
	check(GameState.bag.has("TOWN_MAP"), "new_game() starts with a TOWN MAP")
	check(GameState.seen_species.has("SQUIRTLE"), "picking a starter marks it seen")
	check(GameState.caught_species.has("SQUIRTLE"), "picking a starter marks it caught")

## Generated Pokemon / character models: every species has a glb with all clips, the cel
## shader applies, sprite-frame sizing works, and characters resolve to their own model.
## Debris physics, follower moods, transitions and the Who's That Pokémon quiz.
func _test_new_features() -> void:
	var d := Debris.new()
	d.ground_y = 1.0
	d.spawn({"pos": Vector3(0, 3.0, 0), "vel": Vector3(0.5, 2.0, 0), "size": Vector3.ONE * 0.05, "life": 3.0, "bounce": 0.5})
	var min_y := 99.0
	var bounced := false
	var last_vy := 0.0
	for i in 400:
		d._process(1.0 / 60.0)
		if d.active_count() == 0:
			break
		var c: Dictionary = d._live[0]
		min_y = minf(min_y, (c["node"] as Node3D).position.y)
		if float(c["vel"].y) > last_vy + 1.0 and last_vy < 0.0:
			bounced = true
		last_vy = float(c["vel"].y)
	check(min_y >= 1.0 - 0.001, "debris never falls through the ground (min y %f)" % min_y)
	check(bounced, "debris bounces off the ground")
	check(d.active_count() == 0, "debris fades out and is released")
	d.free()
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	var m := GameState.PartyMon.new("PIKACHU", 30)
	m.status = "PSN"
	check("poison" in str(OverworldScene.follower_mood(m, "Route1", false, rng)[0]), "poisoned follower says so")
	m.status = ""
	m.hp = 1
	check("exhausted" in str(OverworldScene.follower_mood(m, "Route1", false, rng)[0]), "weak follower looks exhausted")
	m.hp = m.max_hp
	var mood: Array = OverworldScene.follower_mood(m, "PalletTown", false, rng)
	check(mood.size() == 2 and ["heart", "!", "?", "..."].has(mood[1]), "follower mood has a text and an emote")
	check(BattleTransition.FRAMES.size() == 3 and BattleTransition.KINDS.has("boss"), "wild / trainer / boss transitions exist")
	check(OverworldScene.style_for_map("MtMoonB1F", false) == 4 and OverworldScene.style_for_map("PewterMart", true) == 1 and OverworldScene.style_for_map("Route1", false) == 0, "warp transition styles by destination")
	var w := WtpScreen.new()
	var ch := w.choices_for("SNORLAX")
	check(ch.size() == 4 and ch.has("SNORLAX"), "quiz offers four species including the answer")
	var uniq := {}
	for c2 in ch:
		uniq[c2] = true
	check(uniq.size() == 4, "quiz choices are distinct")
	w.free()

func _test_models_3d(_tree: SceneTree) -> void:
	var missing: Array = []
	for sid in GameData.species.keys():
		if not ResourceLoader.exists("res://assets/models/pokemon/%s.glb" % sid):
			missing.append(sid)
	check(missing.is_empty(), "every species has a glb (missing %s)" % [missing])
	var actor := PokemonActor.new()  # not added to the tree (root is busy during boot)
	actor.setup("PIKACHU")
	check(PokemonActor.CLIPS.size() >= 10, "at least 10 Pokemon clips are defined")
	for clip in PokemonActor.CLIPS:
		check(actor.has_anim(clip), "PIKACHU has clip %s" % clip)
	check(actor.model.find_child("Skeleton3D", true, false) != null, "PIKACHU is rigged (Skeleton3D)")
	actor.sleeping = true
	check(actor.idle_clip() == "Sleep", "sleeping mons rest in the Sleep clip")
	actor.sleeping = false
	var bird := PokemonActor.new()
	bird.setup("PIDGEY")
	check(bird.idle_clip() == "Hover", "fliers idle in Hover")
	bird.free()
	var mi: MeshInstance3D = Toon._mesh_instances(actor)[0]
	var mat := mi.get_surface_override_material(0) as ShaderMaterial
	check(mat != null and mat.shader == Toon.TOON_SHADER and mat.next_pass != null, "PIKACHU uses toon + outline")
	check(float(PokemonActor.species_info("PIKACHU").get("px_height", 0.0)) > 20.0, "manifest has px_height")
	var s := actor.use_sprite_scale(1.6)
	check(s > 0.5 and s < 10.0, "sprite-frame scale sane (%f)" % s)
	actor.free()
	check(ResourceLoader.exists("res://assets/models/pokemon/MISSINGNO.glb"), "MISSINGNO model present")
	check(CharacterSkin.resolve_key("red") == "red", "red has its own character model")
	var red := CharacterSkin.instantiate("red")
	var ap := AnimUtil.find_player(red)
	check(ap != null and ap.has_animation("Walk"), "red model has Walk")
	red.free()
	var fallback := CharacterSkin.instantiate("no_such_sprite")
	check(fallback != null, "unknown sprite falls back to humanoid")
	fallback.free()
