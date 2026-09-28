extends Node3D
## App entry point: registers itself with SceneRouter and boots the title screen.
## Also supports headless screenshot capture for CI / docs, e.g.:
##   godot4 --headless --rendering-driver opengl3 --path godot -- --screenshot=/tmp/out.png --scene=title --wait=1.0

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
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--screenshot="):
			shot_path = arg.substr("--screenshot=".length())
		elif arg.begins_with("--scene="):
			scene = arg.substr("--scene=".length())
		elif arg.begins_with("--wait="):
			wait = float(arg.substr("--wait=".length()))
	if shot_path == "":
		return

	match scene:
		"overworld":
			GameState.new_game("CHARMANDER")
			SceneRouter.goto_overworld()
		"battle":
			GameState.new_game("SQUIRTLE")
			SceneRouter.start_battle({"kind": "wild", "species": "PIDGEY", "level": 4})
		_:
			pass

	await get_tree().create_timer(wait).timeout
	var img := get_viewport().get_texture().get_image()
	img.save_png(shot_path)
	print("[Screenshot] saved ", shot_path)
	get_tree().quit()
