class_name Player
extends Node3D
## Grid-based overworld movement (classic one-cell-per-press Pokemon movement),
## driven against the current MapLoader for collision/warps/encounters.

## payload: {to: String, kind: "warp"|"connection", warp_index: int, dir: String, offset: Vector2i}
signal warped(payload: Dictionary)
signal encounter_triggered(species: String, level: int)

const MOVE_TIME := 0.16

var map_loader: MapLoader
var cell: Vector2i = Vector2i.ZERO
var facing: String = "down"

var _moving := false
var _rng := RandomNumberGenerator.new()
var _model: Node3D
var _anim: AnimationPlayer

func _ready() -> void:
	_rng.randomize()
	_model = _build_model()
	add_child(_model)
	_anim = _find_anim_player(_model)
	AnimUtil.fix_looping(_anim)
	_play("Idle")

func _find_anim_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var found := _find_anim_player(c)
		if found:
			return found
	return null

func _play(anim_name: String) -> void:
	if _anim and _anim.has_animation(anim_name) and _anim.current_animation != anim_name:
		_anim.play(anim_name)

func _build_model() -> Node3D:
	var path := "res://assets/models/characters/humanoid.glb"
	if ResourceLoader.exists(path):
		var scene: PackedScene = load(path)
		if scene:
			var inst: Node3D = scene.instantiate()
			CharacterSkin.apply(inst, GameData.cast.get("red", {}))
			return inst
	# Fallback capsule so the player is always visible even before/without the
	# Blender character pipeline being available.
	var body := MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.3
	capsule.height = 1.4
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.85, 0.2, 0.2)
	capsule.material = mat
	body.mesh = capsule
	body.position.y = 0.8
	return body

func place(m: MapLoader, start_cell: Vector2i) -> void:
	map_loader = m
	cell = start_cell
	global_position = map_loader.global_position + map_loader.cell_to_world(cell)

func _unhandled_input(event: InputEvent) -> void:
	if _moving or map_loader == null:
		return
	var dir := Vector2i.ZERO
	var new_facing := facing
	if event.is_action_pressed("move_up"):
		dir = Vector2i(0, -1); new_facing = "up"
	elif event.is_action_pressed("move_down"):
		dir = Vector2i(0, 1); new_facing = "down"
	elif event.is_action_pressed("move_left"):
		dir = Vector2i(-1, 0); new_facing = "left"
	elif event.is_action_pressed("move_right"):
		dir = Vector2i(1, 0); new_facing = "right"
	else:
		return

	facing = new_facing
	_model.rotation.y = {"down": PI, "up": 0.0, "left": PI / 2.0, "right": -PI / 2.0}[facing]

	var target := cell + dir
	if not map_loader.in_bounds(target):
		var conn := map_loader.connection_beyond(target)
		if not conn.is_empty():
			_cross_connection(conn)
		return
	if not map_loader.is_walkable(target):
		return
	_move_to(target)

func _move_to(target: Vector2i) -> void:
	_moving = true
	_play("Walk")
	cell = target
	var to_pos := map_loader.global_position + map_loader.cell_to_world(cell)
	var tw := create_tween()
	tw.tween_property(self, "global_position", to_pos, MOVE_TIME)
	await tw.finished
	_moving = false
	_play("Idle")

	var warp := map_loader.warp_at(cell)
	if not warp.is_empty():
		warped.emit({
			"to": String(warp.get("to", "")), "kind": "warp",
			"warp_index": int(warp.get("warp", 0)),
		})
		return

	if map_loader.is_tall_grass(cell):
		var res := EncounterSystem.roll(map_loader.map_name, false, _rng)
		if not res.is_empty():
			encounter_triggered.emit(res["species"], res["level"])

func _cross_connection(conn: Dictionary) -> void:
	var c: Dictionary = conn["conn"]
	warped.emit({
		"to": String(c.get("map", "")), "kind": "connection", "dir": String(conn.get("dir", "")),
		"offset": Vector2i(int(c.get("ox", 0)), int(c.get("oy", 0))),
	})
