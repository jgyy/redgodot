extends Node3D
## App entry point: registers itself with SceneRouter and boots the title screen.
## Also supports headless screenshot capture for CI / docs, e.g.:
##   godot4 --headless --rendering-driver opengl3 --path godot -- --screenshot=/tmp/out.png --scene=title --wait=1.0
##
## Recognized --scene= values: title, intro, oak_speech, naming, overworld, battle, start_menu,
## party, summary, bag, pokedex, trainer_card, town_map, options, dialogue,
## model_sheet (see scripts/tools/ModelSheet.gd for its flags).
## Extra flags (all optional): --player=SPECIES --enemy=SPECIES --level=N
## --map=MapName --pc=x,y --time=day|dusk|night --text="custom dialogue line"
## --save=showcase (reference-screenshot save: RED, 6-mon party, 126/75 dex...)

const MENU_SCENES := ["start_menu", "party", "summary", "bag", "pokedex", "trainer_card", "town_map", "options"]

func _ready() -> void:
	SceneRouter.register_root(self)
	SceneRouter.goto_title()
	if OS.get_cmdline_user_args().has("--run-tests"):
		_run_tests()
		return
	_maybe_capture_screenshot()

func _run_tests() -> void:
	await get_tree().process_frame  # let the root finish adding Main so tests can add scenes
	var suite := TestSuite.new()
	suite.run_all(get_tree())
	print("\n=== %d passed, %d failed ===" % [suite.passed, suite.failures.size()])
	for f in suite.failures:
		print("FAIL: ", f)
	get_tree().quit(1 if not suite.failures.is_empty() else 0)

func _maybe_capture_screenshot() -> void:
	var shot_path := ""
	var scene := "title"
	var wait := 1.0
	var args := {}
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--screenshot="):
			shot_path = arg.substr("--screenshot=".length())
		elif arg.begins_with("--scene="):
			scene = arg.substr("--scene=".length())
		elif arg.begins_with("--wait="):
			wait = float(arg.substr("--wait=".length()))
		elif arg.begins_with("--"):
			var kv := arg.substr(2).split("=", true, 1)
			if kv.size() == 2:
				args[kv[0]] = kv[1]
	if shot_path == "":
		return

	await _setup_scene(scene, args)

	await get_tree().create_timer(wait).timeout
	var img := get_viewport().get_texture().get_image()
	img.save_png(shot_path)
	print("[Screenshot] saved ", shot_path)
	get_tree().quit()

func _setup_scene(scene: String, args: Dictionary) -> void:
	match scene:
		"title":
			pass  # goto_title() already ran in _ready()
		"intro":
			SceneRouter.goto_intro()
			if args.has("intro_frame"):  # jump the opening to a given 60 fps frame
				var intro := get_node_or_null("Intro")
				if intro and intro.has_method("seek"):
					intro.seek(int(args["intro_frame"]), args.has("intro_hold"))
		"oak_speech":
			SceneRouter.goto_oak_speech()
		"naming":
			GameState.new_game(args.get("player", "CHARMANDER"))
			SceneRouter.goto_title()
			var n := NamingScreen.new()
			UI.layer.add_child(n)
			n.open()
		"px_test":
			var layer := CanvasLayer.new()
			layer.layer = 50
			add_child(layer)
			layer.add_child(load("res://scripts/ui/px/PxTestCard.gd").new())
		"model_sheet":
			# contact sheet of generated models (scripts/tools/ModelSheet.gd); saves itself and quits
			var out := "/tmp/model_sheet.png"
			for a in OS.get_cmdline_user_args():
				if a.begins_with("--screenshot="):
					out = a.substr("--screenshot=".length())
			var sheet: Node = load("res://scripts/tools/ModelSheet.gd").new()
			add_child(sheet)
			await sheet.run(args, out)
			await get_tree().create_timer(3600.0).timeout
		"battle":
			await _setup_battle(args)
		"dialogue":
			GameState.new_game(args.get("player", "CHARMANDER"))
			_apply_overrides(args)
			SceneRouter.goto_overworld()
			await get_tree().process_frame
			var ow_d := get_node_or_null("Overworld")
			if ow_d:
				var text: String = args.get("text", "Hello there! Welcome to the world of POKéMON!")
				ow_d.show_dialogue_for_screenshot([text])
		"story_mart":  # Story autoload: Poké Mart menus (+ --step=quantity / --step=money overlays)
			GameState.new_game(args.get("player", "CHARMANDER"))
			args["map"] = args.get("map", "ViridianMart")
			args["pc"] = args.get("pc", "2,5")
			_apply_overrides(args)
			SceneRouter.goto_overworld()
			await get_tree().process_frame
			var step: String = args.get("step", "menu")
			if step == "quantity":
				Story.money_box()
				Story.overlay().call("pick_quantity", 12, 200)
			elif step == "money":
				Story.money_box()
				Story.info_box(func() -> Array: return [Story.money_str(), Story.coin_str()])
			else:
				Story.spawn(Story.mart, [Story.pokedata.get("marts", {}).get("ViridianMartClerkText", [])], "mart")
		_:
			if MENU_SCENES.has(scene):
				GameState.new_game(args.get("player", "CHARMANDER"))
				_apply_overrides(args)
				SceneRouter.goto_overworld()
				await get_tree().process_frame
				var ow := get_node_or_null("Overworld")
				if ow:
					ow.open_menu_for_screenshot(scene)
			else:  # "overworld" and any unrecognized key fall back to plain overworld
				GameState.new_game(args.get("player", "CHARMANDER"))
				_apply_overrides(args)
				SceneRouter.goto_overworld()

## --scene=battle flags (battle agent):
##   --player=SP --player_level=N --player_maxhp=N (picks the HP DV) --player_moves=A,B
##   --player_party=SP:LV,SP:LV  --enemy=SP --level=N --enemy_hp=0..1 --dvs=a,d,s,c
##   --trainer=CLASS[:partyIndex]  --env=grass|forest|cave|water|beach|ice|...  --time=day|dusk|night
##   --state=live|idle|intro|menu|moves|message|vfx  --text="..." --waiting=1
##   --move=MOVE_ID --attacker=p|e --vfx_t=0.55 (freeze the move's animation at that fraction)
##   --autoplay=1 (live battle that plays itself)
func _setup_battle(args: Dictionary) -> void:
	GameState.new_game(args.get("player", "SQUIRTLE"))
	GameState.party.clear()
	var party_specs: Array = []
	if args.has("player_party"):
		for e in str(args["player_party"]).split(","):
			var kv: PackedStringArray = e.split(":")
			party_specs.append([kv[0], int(kv[1]) if kv.size() > 1 else 50])
	else:
		party_specs.append([args.get("player", "SQUIRTLE"), int(args.get("player_level", "5"))])
	for sp in party_specs:
		GameState.party.append(GameState.PartyMon.new(sp[0], sp[1]))
	var lead: GameState.PartyMon = GameState.party[0]
	if args.has("player_maxhp"):
		var want := int(args["player_maxhp"])
		for dv in 16:
			lead.set_dvs((dv >> 3) & 1, (dv >> 2) & 1, (dv >> 1) & 1, dv & 1)
			lead._recalc_stats()
			if lead.max_hp == want:
				break
	if args.get("player_nearlevel", "") == "1":
		lead.xp = lead.exp_to_next() - 1
	if args.has("player_moves"):
		lead.moves.clear()
		lead.pp.clear()
		for mv in str(args["player_moves"]).split(","):
			lead.add_move(mv)
	if args.has("time"):
		_apply_overrides({"time": args["time"]})
	var enc := {"kind": "wild", "species": args.get("enemy", "PIDGEY"), "level": int(args.get("level", "4")),
		"seed": 11, "dvs": {"atk": 8, "def": 8, "spd": 8, "spc": 8}}
	if args.has("trainer"):
		var tk: PackedStringArray = str(args["trainer"]).split(":")
		enc = {"kind": "trainer", "trainer_class": tk[0], "party_index": int(tk[1]) if tk.size() > 1 else 1, "seed": 11}
	if args.has("env"):
		enc["env"] = args["env"]
	for fk in ["ghost", "restless_soul", "safari", "demo", "no_catch"]:
		if args.get(fk, "") == "1":
			enc[fk] = true
	for rk in ["rot_e", "rot_p"]:
		if args.has(rk):
			enc[rk] = float(args[rk])
	if args.has("time"):
		enc["time"] = GameState.time_period()
	var state: String = args.get("state", "live")
	enc["screenshot"] = state != "live"
	enc["autoplay"] = args.get("autoplay", "") == "1"
	if args.has("auto_actions"):
		enc["auto_actions"] = Array(str(args["auto_actions"]).split(","))
	if args.has("bag"):
		for e in str(args["bag"]).split(","):
			var kv: PackedStringArray = e.split(":")
			GameState.bag[kv[0]] = int(kv[1]) if kv.size() > 1 else 1
	SceneRouter.start_battle(enc)
	var battle: Node = SceneRouter.current_battle()
	if battle == null or state == "live":
		return
	await get_tree().process_frame
	var o := {}
	for k in ["text", "move", "attacker"]:
		if args.has(k):
			o[k] = args[k]
	if args.has("enemy_hp"):
		o["enemy_hp"] = float(args["enemy_hp"])
	if args.has("vfx_t"):
		o["vfx_t"] = float(args["vfx_t"])
	o["waiting"] = args.get("waiting", "") == "1"
	await battle.pose(state, o)

func _apply_overrides(args: Dictionary) -> void:
	if args.get("save", "") == "showcase":
		GameState.build_showcase()  # the fixed save the reference screenshots use
	if args.has("map"):
		GameState.current_map = args["map"]
	if args.has("pc"):
		var parts: PackedStringArray = args["pc"].split(",")
		if parts.size() == 2:
			GameState.player_cell = Vector2i(int(parts[0]), int(parts[1]))
	if args.has("time"):
		match args["time"]:
			"day": GameState.clock_minutes = 12.0 * 60.0
			"dusk": GameState.clock_minutes = 19.0 * 60.0
			"night": GameState.clock_minutes = 23.0 * 60.0
	GameState.clock_running = false
