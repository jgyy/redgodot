extends Node
## Headless autopilot for the opening of a NEW GAME, driving the real overworld through simulated d-pad /
## A presses (Input.action_press), like upstream's tools/drive.js:
##   RED's room -> downstairs -> out the door -> north edge of Pallet (Oak stops you) -> Oak's lab ->
##   pick a starter -> walk to the exit (rival battle).
## Run: godot4 --headless --path godot -- --scene=ow_playtest [--starter=CHARMANDER] [--version=RED|BLUE|YELLOW]
## YELLOW has no starter choice: the one POKe BALL on the table is the rival's EEVEE and Oak gives PIKACHU, which then
## walks behind the player (the run checks the follower and the rival's EEVEE fight).
## Prints [playtest] lines and exits 0 when every milestone was reached, 1 otherwise.

var log_lines: Array = []
var milestones := {}
var _ow: Node = null
var _t0 := 0

func run(starter: String) -> void:
	_t0 = Time.get_ticks_msec()
	GameState.start_new_adventure()
	_note("version", GameState.version)
	SceneRouter.goto_overworld()
	await _frames(10)
	_ow = get_tree().root.find_child("Overworld", true, false)
	if _ow == null:
		_done("no overworld")
		return
	SceneRouter.battle_started.connect(func(enc: Dictionary) -> void:
		_note("battle", str(enc.get("kind", "")) + " " + str(enc.get("trainer_class", enc.get("species", "")))))
	_ow.entered_map.connect(func(m: String) -> void: _note("map", m))
	_note("start", "%s %s" % [_ow.current_map(), str(_ow.actor_cell("PLAYER"))])
	# 1. stairs down
	await _walk_to(Vector2i(7, 1))
	await _wait_map("RedsHouse1F", 240)
	# 2. out the front door (stand on the mat, push down)
	await _walk_to(Vector2i(3, 7))
	await _press_dir("down", 20)
	await _wait_map("PalletTown", 240)
	# 3. north exit: Oak stops you and leads you to his lab
	await _walk_to(Vector2i(10, 2))
	await _press_dir("up", 30)
	await _advance_until(func() -> bool: return _ow.current_map() == "OaksLab" and not _story_busy(), 3600)
	_note("lab", str(_ow.actor_cell("PLAYER")))
	# 4. pick the starter's ball on the table
	var ball := {"CHARMANDER": Vector2i(6, 3), "SQUIRTLE": Vector2i(7, 3), "BULBASAUR": Vector2i(8, 3), "PIKACHU": Vector2i(7, 3)}.get(starter, Vector2i(6, 3)) as Vector2i
	await _advance_until(func() -> bool: return not _story_busy(), 1200)
	await _walk_to(ball + Vector2i(0, 1))
	await _press_dir("up", 8)
	await _press_action("confirm", 4)
	await _advance_until(func() -> bool: return not _story_busy() and not GameState.party.is_empty(), 3600)
	_note("party", str(GameState.party.map(func(m: GameState.PartyMon) -> String: return m.species_id)))

	# 5. head for the exit: the rival challenges you on the way out
	await _advance_until(func() -> bool: return not _story_busy(), 1800)
	await _walk_to(Vector2i(5, 6))
	await _advance_until(func() -> bool: return milestones.has("battle"), 1800)
	# 6. fight it out (A picks FIGHT and the first move), then the rival leaves: back in the lab
	await _advance_until(func() -> bool: return milestones.has("battle") and not SceneRouter.in_battle() and not _story_busy(), 7200)
	if _ow.current_map() == "OaksLab" and _ow.visible:
		_note("after_battle", "%s %s party=%s" % [_ow.current_map(), str(_ow.actor_cell("PLAYER")), str(GameState.party.map(func(m: GameState.PartyMon) -> String: return "%s L%d %d/%d" % [m.species_id, m.level, m.hp, m.max_hp]))])
	if GameState.is_yellow() and _ow.current_map() == "OaksLab":
		# a couple of steps so PIKACHU shows up trailing the player, then read what the overworld reports
		await _walk_to(Vector2i(5, 8))
		await _walk_to(Vector2i(5, 9))
		await _frames(40)
		_note("follower", "%s visible=%s" % [_ow.get("_follower_species"), str(_ow.follower.visible)])
	var ok := milestones.has("lab") and not GameState.party.is_empty() and milestones.has("battle") and milestones.has("after_battle")
	if GameState.is_yellow():
		# PIKACHU is the buddy and walks behind you; the rival fought with EEVEE and picked its evolution
		ok = ok and GameState.party[0].species_id == "PIKACHU" and GameState.party[0].buddy and str(milestones.get("follower", "")).ends_with("visible=true")
		ok = ok and str(milestones.get("battle", "")).contains("RIVAL1") and ["FLAREON", "VAPOREON"].has(GameState.rival_eevee)
	elif starter != "":
		ok = ok and GameState.party[0].species_id == starter
	_done("OK" if ok else "INCOMPLETE")

## Drives the real title screen with key presses: A opens the menu, NEW GAME, then the version list; ends once Prof. Oak's
## speech has started with that version. Run: godot4 --headless --path godot -- --scene=title_playtest --version=BLUE
func run_title(want: String) -> void:
	_t0 = Time.get_ticks_msec()
	GameState.pending_version = "RED"   # so the choice has to come from the menu
	GameState.version = "RED"
	# a plain run opens with the intro movie: skip it (any key; the first press only "turns the sound on") until the title shows
	var waited := 0
	while _title_scene() == null and waited < 3600:
		await _press_action("confirm", 2)
		await _frames(20)
		waited += 25
	_note("title", str(_title_scene() != null))
	await _frames(70)
	await _press_action("confirm", 3)
	await _frames(12)
	if GameState.has_save():
		await _press_action("move_down", 2)   # CONTINUE is first when a save exists
	await _press_action("confirm", 3)   # NEW GAME
	await _frames(12)
	_note("menu", "version list open")
	for i in GameData.VERSIONS.find(want):
		await _press_action("move_down", 2)
	await _press_action("confirm", 3)
	var n := 0
	while n < 600 and get_tree().root.find_child("Intro", true, false) == null:
		await _frames(1)
		n += 1
	var speech := get_tree().root.find_child("Intro", true, false)
	_note("oak_speech", str(speech != null))
	var ok := speech != null and GameState.version == want and GameData.active_version == want
	if ok and speech.has_method("_intro_mon"):
		ok = speech.call("_intro_mon") == ("PIKACHU" if want == "YELLOW" else "NIDORINO")
	_done("OK" if ok else "INCOMPLETE")

func _title_scene() -> Node:
	for n in get_tree().root.find_children("*", "Node3D", true, false):
		var sc: Variant = n.get_script()
		if sc != null and str((sc as Script).resource_path).ends_with("TitleScene.gd"):
			return n
	return null

func _story_busy() -> bool:
	var st := get_node_or_null("/root/Story")
	var ui := get_node_or_null("/root/UI")
	if not _ow.visible:
		return true
	return (st != null and bool(st.is_running())) or (ui != null and bool(ui.is_busy())) or bool(_ow.is_input_locked()) or bool(_ow.is_warping())

func _note(k: String, v: String) -> void:
	milestones[k] = v
	var line := "[playtest] %6.1fs %s: %s" % [(Time.get_ticks_msec() - _t0) / 1000.0, k, v]
	log_lines.append(line)
	print(line)

func _done(result: String) -> void:
	_note("result", result)
	get_tree().quit(0 if result == "OK" else 1)

## Real input events (UI text boxes read _unhandled_input), also updating Input's action state.
func _act(on: bool, a: String) -> void:
	var ev := InputEventAction.new()
	ev.action = a
	ev.pressed = on
	Input.parse_input_event(ev)

## Waits n frames at a real 60 fps: headless Godot runs uncapped, and the
## player's tap-to-turn / hold-to-walk thresholds are time-based, so counting
## raw frames would make a "hold" last only milliseconds on a fast machine.
func _frames(n: int) -> void:
	for i in n:
		var until := Time.get_ticks_usec() + 16667
		await get_tree().process_frame
		while Time.get_ticks_usec() < until:
			await get_tree().process_frame

func _press_action(a: String, hold: int = 3) -> void:
	_act(true, a)
	await _frames(hold)
	_act(false, a)
	await _frames(3)

func _press_dir(d: String, hold: int) -> void:
	var a: String = "move_" + d
	_act(true, a)
	await _frames(hold)
	_act(false, a)
	await _frames(2)

## Press A while text / scripts run, until cond() holds (or max frames).
func _advance_until(cond: Callable, max_frames: int) -> void:
	var n := 0
	while n < max_frames and not bool(cond.call()):
		if n % 300 < 5:
			var st := get_node_or_null("/root/Story")
			print("[playtest]   .. %s %s dir=%s story=%s ui=%s locked=%s" % [_ow.current_map(), str(_ow.actor_cell("PLAYER")), _ow.actor_dir("PLAYER"),
				str(st.is_running()) if st else "-", str(get_node("/root/UI").is_busy()), str(_ow.is_input_locked())])
		if _story_busy() or SceneRouter.in_battle():
			await _press_action("confirm", 2)
			n += 5
		else:
			await _frames(1)
			n += 1

func _wait_map(m: String, max_frames: int) -> void:
	await _advance_until(func() -> bool: return _ow.current_map() == m and not bool(_ow.is_warping()), max_frames)

## Walk (real input) along the overworld's BFS path to `to`, re-planning each step.
func _walk_to(to: Vector2i) -> void:
	for guard in 80:
		await _advance_until(func() -> bool: return not _story_busy(), 900)
		var cur: Vector2i = _ow.actor_cell("PLAYER")
		if cur == to:
			return
		var path: String = _ow.path_to(cur, to)
		if path == "":
			_note("stuck", "%s -> %s on %s" % [str(cur), str(to), _ow.current_map()])
			return
		var d: String = {"U": "up", "D": "down", "L": "left", "R": "right"}[path[0]]
		if _ow.actor_dir("PLAYER") != d:
			await _press_dir(d, 2)
			await _frames(8)
		_act(true, "move_" + d)
		var t := 0
		while _ow.actor_cell("PLAYER") == cur and t < 40:
			await _frames(1)
			t += 1
		_act(false, "move_" + d)
		await _frames(18)
