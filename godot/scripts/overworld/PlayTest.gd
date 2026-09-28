extends Node
## Headless autopilot for the opening of a NEW GAME, driving the real overworld through simulated d-pad /
## A presses (Input.action_press), like upstream's tools/drive.js:
##   RED's room -> downstairs -> out the door -> north edge of Pallet (Oak stops you) -> Oak's lab ->
##   pick a starter -> walk to the exit (rival battle).
## Run: godot4 --headless --path godot -- --scene=ow_playtest [--starter=CHARMANDER]
## Prints [playtest] lines and exits 0 when every milestone was reached, 1 otherwise.

var log_lines: Array = []
var milestones := {}
var _ow: Node = null
var _t0 := 0

func run(starter: String) -> void:
	_t0 = Time.get_ticks_msec()
	GameState.start_new_adventure()
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
	var ball := {"CHARMANDER": Vector2i(6, 3), "SQUIRTLE": Vector2i(7, 3), "BULBASAUR": Vector2i(8, 3)}.get(starter, Vector2i(6, 3)) as Vector2i
	await _advance_until(func() -> bool: return not _story_busy(), 1200)
	await _walk_to(ball + Vector2i(0, 1))
	await _press_dir("up", 8)
	await _press_action("confirm", 4)
	await _advance_until(func() -> bool: return not _story_busy() and not GameState.party.is_empty(), 3600)
	_note("party", str(GameState.party.map(func(m: GameState.PartyMon) -> String: return m.species_id)))
	# 5. head for the exit: the rival challenges you
	await _walk_to(Vector2i(5, 6))
	await _press_dir("down", 60)
	await _advance_until(func() -> bool: return milestones.has("battle"), 1800)
	var ok := milestones.has("lab") and not GameState.party.is_empty() and milestones.has("battle")
	_done("OK" if ok else "INCOMPLETE")

func _story_busy() -> bool:
	var st := get_node_or_null("/root/Story")
	var ui := get_node_or_null("/root/UI")
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

func _frames(n: int) -> void:
	for i in n:
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
		if _story_busy():
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
