class_name OwActor
extends Node3D
## One overworld character in 3D: the player, an NPC from a map's `objs`, or the walking partner Pokémon.
## Grid-locked like upstream's Actor (src/game/overworld.js): one cell per step, 16 frames per cell at walking
## speed, 2-cell hops over ledges, facing in four directions.

signal step_finished(actor: OwActor)

const FRAME := 1.0 / 60.0
const FOOT_Z := 0.8          # where in its cell (0..1, north->south) a character's feet stand: the 2D sprites
                             # stand on the bottom of their cell
const DIRS := {"down": Vector2i(0, 1), "up": Vector2i(0, -1), "left": Vector2i(-1, 0), "right": Vector2i(1, 0)}
const YAW := {"down": 0.0, "up": PI, "left": -PI / 2.0, "right": PI / 2.0}   # models face +Z (Blender -Y)
const CHAR_PX := 20.0        # height of a character sprite in the 2D game (px)
const LEAN_DEG := -22.0   # negative: top away from the camera, so the face turns up toward it

var cell := Vector2i.ZERO
var facing := "down"
var moving := false
var sprite := ""
var obj: Dictionary = {}     # the map object this actor was spawned from (NPCs)
var home := Vector2i.ZERO
var idle_t := 0.0
var scripted := false        # a script is driving it: no idle wandering
var is_mon := false
var is_object := false

var _model: Node3D
var _lean: Node3D
var _anim: AnimationPlayer
var _shadow: MeshInstance3D
var _move_from := Vector3.ZERO
var _move_to := Vector3.ZERO
var _move_t := 0.0
var _move_dur := 0.2667
var _jump := false
var _bob_phase := 0.0

static func cell_pos(c: Vector2i) -> Vector3:
	return Vector3(c.x + 0.5, 0.0, c.y + FOOT_Z)

const OBJECT_SPRITES := ["poke_ball", "boulder", "pokedex", "clipboard", "paper", "fossil", "old_amber"]
const CREATURE_DEFAULT := {"bird": "PIDGEY", "fairy": "CLEFAIRY", "seel": "SEEL", "snorlax": "SNORLAX", "monster": "NIDORAN_M"}

## upstream objsprites.js speciesFromLabel: the longest species name found in a text label
static func species_from_label(label: String) -> String:
	var up := label.to_upper()
	var best := ""
	for sp in GameData.species.keys():
		var k := String(sp).replace("_", "")
		if up.contains(k) and k.length() > best.replace("_", "").length():
			best = sp
	return best

## sprite: cast key for people, or "mon:SPECIES" for a Pokémon (follower). `o` is the map object (NPCs): its
## cast entry decides between a person, a Pokémon (creature objects, like upstream's objSprites) or an item
## (a 3D Poké Ball / boulder, or a small standing sprite).
func setup(sprite_key: String, px_height: float = CHAR_PX, o: Dictionary = {}) -> void:
	sprite = sprite_key
	for c in get_children():
		c.queue_free()
	_anim = null
	var def: Dictionary = GameData.cast.get(sprite_key, {})
	if def.has("creature"):
		var sp := String(o.get("species", GameData.species_override.get(String(o.get("id", "")), "")))
		if sp == "":
			sp = species_from_label(String(o.get("textLabel", "")))
		if sp == "":
			sp = String(CREATURE_DEFAULT.get(String(def.creature), "PIKACHU"))
		sprite_key = "mon:" + sp
		px_height = 26.0 if (def.creature == "snorlax" or sp == "SNORLAX") else 18.0
	if def.has("object"):
		_setup_object(sprite_key)
		return
	if sprite_key.begins_with("mon:"):
		is_mon = true
		_model = _load_mon(sprite_key.substr(4), px_height)
	else:
		_model = CharacterSkin.instantiate_character(sprite_key)
		if _model == null:
			_model = _fallback()
		_fit_height(_model, px_height)
	# characters lean back toward the camera a little, so the steep game camera sees their faces the way
	# the 2D sprites show them
	_lean = Node3D.new()
	_lean.name = "Lean"
	_lean.rotation.x = deg_to_rad(LEAN_DEG)
	add_child(_lean)
	_lean.add_child(_model)
	_anim = _find_anim(_model)
	AnimUtil.fix_looping(_anim)
	_play("Idle")
	_shadow = _make_shadow(0.36 if not is_mon else 0.3)
	add_child(_shadow)
	face(facing)

## Items on the map: 3D Poké Ball / boulder (pipeline/blender/gen_world.py), other objects as a standing
## sprite card of upstream's object art.
func _setup_object(key: String) -> void:
	is_object = true
	var mesh_path: String = {"poke_ball": "res://assets/models/world/pokeball.glb", "boulder": "res://assets/models/world/boulder.glb"}.get(key, "")
	_model = Node3D.new()
	_model.name = "Object"
	add_child(_model)
	if mesh_path != "" and ResourceLoader.exists(mesh_path):
		var ps: PackedScene = load(mesh_path)
		var inst := ps.instantiate()
		var mi := TileKit._find_mesh(inst)
		if mi:
			var m := MeshInstance3D.new()
			m.mesh = mi.mesh
			m.material_override = TileKit.prop_material()
			m.scale = Vector3(1.0, WorldData.K, 1.0)
			m.position = Vector3(0.0, 0.0, 0.8 - FOOT_Z)
			_model.add_child(m)
		inst.free()
	else:
		var idx := OBJECT_SPRITES.find(key)
		var q := QuadMesh.new()
		q.size = Vector2(1.0, WorldData.K)
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_texture = load("res://assets/maps/objects_atlas.png")
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		mat.uv1_scale = Vector3(1.0 / OBJECT_SPRITES.size(), 1.0, 1.0)
		mat.uv1_offset = Vector3(float(maxi(idx, 0)) / OBJECT_SPRITES.size(), 0.0, 0.0)
		q.material = mat
		var m2 := MeshInstance3D.new()
		m2.mesh = q
		m2.position = Vector3(0.0, WorldData.K * 0.5, 1.0 - FOOT_Z)
		_model.add_child(m2)
	face(facing)

func _load_mon(species: String, px_height: float) -> Node3D:
	var path := "res://assets/models/pokemon/%s.glb" % species
	var m: Node3D = null
	if ResourceLoader.exists(path):
		var ps: PackedScene = load(path)
		if ps:
			m = ps.instantiate()
	if m == null:
		m = _fallback()
	_fit_height(m, px_height)
	return m

## Scale a model so its bounding box is `px` pixels of 2D art tall (the game camera's vertical scale).
func _fit_height(m: Node3D, px: float) -> void:
	var aabb := _model_aabb(m)
	var h := aabb.size.y
	if h <= 0.001:
		return
	# the model leans back by LEAN_DEG, so its projected height grows: size it so that on screen it is `px`
	# pixels of 2D art tall (a ground cell of 16 px shows as sin(pitch) cells)
	var pitch := deg_to_rad(WorldData.CAM_PITCH_DEG)
	var target := px / 16.0 * WorldData.CELL * sin(pitch) / cos(pitch - absf(deg_to_rad(LEAN_DEG)))
	var s := target / h
	var holder := m
	holder.scale = Vector3(s, s, s)
	holder.position.y = -aabb.position.y * s

static func _model_aabb(n: Node) -> AABB:
	var out := AABB()
	var first := true
	for mi in _meshes(n):
		var m: MeshInstance3D = mi
		if m.mesh == null:
			continue
		var a: AABB = _rel_xform(m, n) * m.mesh.get_aabb()
		if first:
			out = a
			first = false
		else:
			out = out.merge(a)
	return out

static func _rel_xform(node: Node3D, root: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	var cur: Node = node
	while cur != null and cur != root:
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t

static func _meshes(n: Node) -> Array:
	var out: Array = []
	if n is MeshInstance3D:
		out.append(n)
	for c in n.get_children():
		out.append_array(_meshes(c))
	return out

func _fallback() -> Node3D:
	var root := Node3D.new()
	var body := MeshInstance3D.new()
	var cap := CapsuleMesh.new()
	cap.radius = 0.3
	cap.height = 1.4
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(GameData.cast.get(sprite, {}).get("shirt", "#c8a0d8"))
	cap.material = mat
	body.mesh = cap
	body.position.y = 0.7
	root.add_child(body)
	return root

func _make_shadow(r: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(r * 2.0, r * 0.9)
	q.orientation = PlaneMesh.FACE_Y
	var mat := ShaderMaterial.new()
	mat.shader = preload("res://scripts/overworld/shaders/blob_shadow.gdshader")
	q.material = mat
	mi.mesh = q
	mi.position = Vector3(0.05, 0.01, 0.0)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

static func _find_anim(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var f := _find_anim(c)
		if f:
			return f
	return null

func _play(n: String) -> void:
	if _anim and _anim.has_animation(n) and _anim.current_animation != n:
		_anim.play(n)

func place(c: Vector2i, dir: String = "") -> void:
	cell = c
	moving = false
	position = cell_pos(c)
	if dir != "":
		face(dir)
	_play("Idle")

func face(dir: String) -> void:
	if not YAW.has(dir):
		return
	facing = dir
	if _model and not is_object:
		_model.rotation.y = YAW[dir]

func facing_cell() -> Vector2i:
	return cell + DIRS.get(facing, Vector2i.ZERO)

## Start a one-cell step (or a two-cell ledge hop). speed: 1 walk, 2 run, 3 bike (upstream px per frame).
func start_move(dir: String, speed: float = 1.0, jump: bool = false) -> void:
	face(dir)
	var dist := 2 if jump else 1
	var target: Vector2i = cell + DIRS[dir] * dist
	_move_from = position
	_move_to = cell_pos(target)
	cell = target
	_move_t = 0.0
	_move_dur = (16.0 * dist) / maxf(speed, 0.5) * FRAME
	_jump = jump
	moving = true
	_play("Walk")

func _process(dt: float) -> void:
	if moving:
		_move_t += dt
		var k := clampf(_move_t / _move_dur, 0.0, 1.0)
		position = _move_from.lerp(_move_to, k)
		if _jump:
			position.y = sin(k * PI) * WorldData.px_h(10.0)
		if k >= 1.0:
			moving = false
			_jump = false
			position = _move_to
			_play("Idle")
			step_finished.emit(self)
	if is_mon and _model:
		# two bobs per tile while walking, a slow breath standing still (follower.js)
		_bob_phase += dt
		var bob := 0.0
		if moving:
			bob = 1.0 if int(_move_t / (4.0 * FRAME)) % 2 == 1 else 0.0
		else:
			bob = 1.0 if fmod(_bob_phase, 0.8) > 0.4 else 0.0
		_model.position.y = _model.position.y - _model.get_meta("bob", 0.0) + WorldData.px_h(bob)
		_model.set_meta("bob", WorldData.px_h(bob))
