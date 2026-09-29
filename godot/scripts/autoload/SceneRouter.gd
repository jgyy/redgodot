extends Node
## Central scene-transition hub. The Main scene keeps a single child under
## %ActiveScene and this autoload swaps it out, so battle <-> overworld <-> menus
## don't need to know about each other directly.
##
## Battles are OVERLAYS (cross-area contract): the current scene (usually the
## Overworld) stays alive but hidden with processing disabled while the Battle
## scene runs on top, then it is restored exactly as it was, so story scripts
## awaiting a battle keep running afterwards:
##     var result: String = await SceneRouter.battle(enc)   # "win"|"lose"|"run"|"caught"
## enc: {kind:"wild", species, level}
##    | {kind:"trainer", trainer_class, party_index (1-based, upstream S.battle(cls, idx)),
##       name, win_text (alias on_win_text), lose_text, no_blackout, party:[PartyMon...] (optional)}
## Optional keys: env (battle backdrop, default from the current map), no_run, no_catch.

signal battle_started(encounter: Dictionary)
signal battle_ended(result: String)
## Fired with the full outcome dictionary {result, money, caught_species, ...}.
signal battle_finished(outcome: Dictionary)

const OVERWORLD := "res://scenes/Overworld.tscn"
const BATTLE := "res://scenes/Battle.tscn"
const TITLE := "res://scenes/Title.tscn"
const INTRO := "res://scenes/Intro.tscn"

var _root: Node = null
var _active: Node = null
var _battle: Node = null
var _suspended: Dictionary = {}   # state of the hidden scene under a battle overlay
var _return_state: Dictionary = {}
var last_result: String = ""
var last_outcome: Dictionary = {}

func register_root(root: Node) -> void:
	_root = root

func _swap(scene: PackedScene) -> Node:
	if _battle:
		_battle.queue_free()
		_battle = null
		_suspended = {}
	if _active:
		_active.queue_free()
		_active = null
	_active = scene.instantiate()
	_root.add_child(_active)
	return _active

## Upstream boot order: the opening (intro.js) plays first, then the title.
## Main.gd calls goto_title() at startup; the very first call of a normal run
## (not tests / screenshot capture) is redirected to the intro, which ends by
## calling goto_title() itself.
var _booted := false

func _plain_run() -> bool:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--screenshot") or a == "--run-tests":
			return false
	return true

func goto_intro() -> void:
	_booted = true
	_swap(load(INTRO))

func goto_title() -> void:
	if not _booted and _plain_run():
		goto_intro()
		return
	_booted = true
	_swap(load(TITLE))

## NEW GAME: Professor Oak's speech (title.js newGameIntro), which names the
## player and rival and ends in RED's room.
func goto_oak_speech() -> void:
	_swap_node(OakSpeech.new())

func _swap_node(node: Node) -> Node:
	if _active:
		_active.queue_free()
		_active = null
	_active = node
	_root.add_child(_active)
	return _active

func goto_overworld() -> void:
	_swap(load(OVERWORLD))

func in_battle() -> bool:
	return _battle != null and is_instance_valid(_battle)

func current_battle() -> Node:
	return _battle if in_battle() else null

## Awaitable battle: returns "win" | "lose" | "run" | "caught" (a wild mon that
## used TELEPORT/ROAR returns "run" too). Whiteout on "lose" is the caller's
## job (see whiteout()).
func battle(enc: Dictionary) -> String:
	_open_battle(enc)
	var r: String = await battle_ended
	return r

## Fire-and-forget battle (random encounters). A "lose" without
## enc.no_blackout whites out to the last POKéMON CENTER.
func start_battle(encounter: Dictionary) -> void:
	_open_battle(encounter)
	var r: String = await battle_ended
	if r == "lose" and not encounter.get("no_blackout", false):
		whiteout()

func _open_battle(enc: Dictionary) -> void:
	if _root and not enc.has("_snapshot"):
		var snap := BattleTransition.snapshot(_root.get_viewport())
		if snap:
			enc["_snapshot"] = snap
	_return_state = {"map": GameState.current_map, "cell": GameState.player_cell, "facing": GameState.player_facing}
	if in_battle():
		_battle.queue_free()
	_suspend_active()
	_battle = load(BATTLE).instantiate()
	_root.add_child(_battle)
	battle_started.emit(enc)
	if _battle.has_method("setup"):
		_battle.setup(enc)

## Called by the Battle scene when it is completely done (after evolutions).
## `result` may be a String or the outcome Dictionary {result: ...}.
func end_battle(result: Variant) -> void:
	var outcome: Dictionary = result if result is Dictionary else {"result": str(result)}
	var r: String = str(outcome.get("result", ""))
	if r == "fled":
		r = "run"
	outcome["result"] = r
	last_result = r
	last_outcome = outcome
	if _battle and is_instance_valid(_battle):
		_battle.queue_free()
	_battle = null
	var had_scene := _resume_active()
	if not had_scene:
		goto_overworld()
	battle_finished.emit(outcome)
	battle_ended.emit(r)

## upstream blackout(): money halved, party healed, back at the last POKéMON CENTER.
func whiteout() -> void:
	GameState.money = int(floor(GameState.money / 2.0))
	GameState.heal_party()
	GameState.current_map = GameState.last_heal_map
	GameState.player_cell = GameState.last_heal_cell
	GameState.player_facing = "down"
	goto_overworld()

# ------------------------------------------------------------------ overlay plumbing
func _suspend_active() -> void:
	_suspended = {}
	if _active == null or not is_instance_valid(_active):
		return
	var st := {"node": _active, "process_mode": _active.process_mode, "cameras": [], "layers": [], "controls": []}
	if _active is Node3D:
		st["visible"] = (_active as Node3D).visible
		(_active as Node3D).visible = false
	_collect(_active, st)
	_active.process_mode = Node.PROCESS_MODE_DISABLED
	_suspended = st

func _collect(n: Node, st: Dictionary) -> void:
	for c in n.get_children():
		if c is Camera3D and (c as Camera3D).current:
			st["cameras"].append(c)
			(c as Camera3D).current = false
		elif c is CanvasLayer and (c as CanvasLayer).visible:
			st["layers"].append(c)
			(c as CanvasLayer).visible = false
		elif c is Control and (c as Control).visible and not (n is Control):
			st["controls"].append(c)
			(c as Control).visible = false
		elif c is WorldEnvironment:
			st.get_or_add("envs", []).append([c, (c as WorldEnvironment).environment])
			(c as WorldEnvironment).environment = null
		elif c is DirectionalLight3D and (c as DirectionalLight3D).visible:
			st.get_or_add("lights", []).append(c)
			(c as DirectionalLight3D).visible = false
		_collect(c, st)

func _resume_active() -> bool:
	if _suspended.is_empty():
		return false
	var node: Node = _suspended["node"]
	if node == null or not is_instance_valid(node):
		_suspended = {}
		return false
	node.process_mode = _suspended["process_mode"]
	if node is Node3D:
		(node as Node3D).visible = _suspended.get("visible", true)
	for c in _suspended["cameras"]:
		if is_instance_valid(c):
			(c as Camera3D).current = true
	for l in _suspended["layers"]:
		if is_instance_valid(l):
			(l as CanvasLayer).visible = true
	for k in _suspended["controls"]:
		if is_instance_valid(k):
			(k as Control).visible = true
	for pair in _suspended.get("envs", []):
		if is_instance_valid(pair[0]):
			(pair[0] as WorldEnvironment).environment = pair[1]
	for li in _suspended.get("lights", []):
		if is_instance_valid(li):
			(li as DirectionalLight3D).visible = true
	_suspended = {}
	return true
