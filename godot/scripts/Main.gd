extends Node3D
## App entry point: registers itself with SceneRouter and boots the title screen.
## Also supports headless screenshot capture for CI / docs, e.g.:
##   godot4 --headless --rendering-driver opengl3 --path godot -- --screenshot=/tmp/out.png --scene=title --wait=1.0
##
## Recognized --scene= values: title, intro, overworld, battle, start_menu,
## party, summary, bag, pokedex, trainer_card, town_map, options, dialogue.
## Extra flags (all optional): --player=SPECIES --enemy=SPECIES --level=N
## --map=MapName --pc=x,y --time=day|dusk|night --text="custom dialogue line"

const MENU_SCENES := ["start_menu", "party", "summary", "bag", "pokedex", "trainer_card", "town_map", "options"]

func _ready() -> void:
	SceneRouter.register_root(self)
	SceneRouter.goto_title()
	if OS.get_cmdline_user_args().has("--run-tests"):
		_run_tests()
		return
	_maybe_capture_screenshot()

func _run_tests() -> void:
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
		"battle":
			GameState.new_game(args.get("player", "SQUIRTLE"))
			SceneRouter.start_battle({
				"kind": "wild", "species": args.get("enemy", "PIDGEY"), "level": int(args.get("level", "4")),
			})
			if args.has("auto_move"):
				await get_tree().create_timer(1.3).timeout
				var battle := get_node_or_null("Battle")
				if battle and battle.has_method("auto_use_first_move"):
					battle.auto_use_first_move(int(args.get("move_index", "-1")))
		"dialogue":
			GameState.new_game(args.get("player", "CHARMANDER"))
			_apply_overrides(args)
			SceneRouter.goto_overworld()
			await get_tree().process_frame
			var ow_d := get_node_or_null("Overworld")
			if ow_d:
				var text: String = args.get("text", "Hello there! Welcome to the world of POKéMON!")
				ow_d.show_dialogue_for_screenshot([text])
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

func _apply_overrides(args: Dictionary) -> void:
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
