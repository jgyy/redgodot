class_name Debris
extends Node3D
## Small rigid-body-style chunks for immersion: leaves, rock chips, twigs and sparks that are thrown out with a real
## velocity, fall under gravity, tumble, bounce off the ground (restitution + friction), settle and fade.  One shared
## pool of MeshInstance3D so bursts stay cheap.  Used for cut trees, pushed boulders, ledge landings, tall grass and
## battle impacts; `ground_y` is the world height chunks collide with.

const GRAVITY := 9.0
const MAX_CHUNKS := 96

const LEAF := Color(0.42, 0.72, 0.28)
const LEAF_DARK := Color(0.26, 0.5, 0.2)
const ROCK := Color(0.62, 0.58, 0.52)
const TWIG := Color(0.45, 0.32, 0.2)
const SPARK := Color(1.0, 0.85, 0.4)

var ground_y := 0.0
var _live: Array = []
var _pool: Array = []
var _rng := RandomNumberGenerator.new()
var _box := BoxMesh.new()
var _leaf := QuadMesh.new()

func _init() -> void:
	_rng.randomize()
	_box.size = Vector3.ONE
	_leaf.size = Vector2(1.0, 1.4)

func active_count() -> int:
	return _live.size()

func clear() -> void:
	for c in _live:
		_release(c)
	_live.clear()

func _rand(a: float, b: float) -> float:
	return _rng.randf_range(a, b)

func _take() -> MeshInstance3D:
	if not _pool.is_empty():
		return _pool.pop_back()
	var m := MeshInstance3D.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.material_override = mat
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(m)
	return m

func _release(c: Dictionary) -> void:
	var n: MeshInstance3D = c["node"]
	if is_instance_valid(n):
		n.visible = false
		_pool.append(n)

## One chunk. o: pos, vel, size(Vector3), col, kind("box"|"leaf"), bounce (restitution), life, spin (rad/s Vector3),
## grav_scale, drag.
func spawn(o: Dictionary) -> void:
	if _live.size() >= MAX_CHUNKS:
		return
	var n := _take()
	var kind: String = o.get("kind", "box")
	n.mesh = _leaf if kind == "leaf" else _box
	(n.material_override as StandardMaterial3D).albedo_color = o.get("col", ROCK)
	n.scale = o.get("size", Vector3.ONE * 0.06)
	n.position = o["pos"]
	n.rotation = Vector3(_rand(0, TAU), _rand(0, TAU), _rand(0, TAU))
	n.visible = true
	var c := {"node": n, "vel": o.get("vel", Vector3.ZERO), "spin": o.get("spin", Vector3(_rand(-9, 9), _rand(-9, 9), _rand(-9, 9))),
		"bounce": o.get("bounce", 0.45), "life": o.get("life", 1.4), "age": 0.0, "gs": o.get("grav_scale", 1.0),
		"drag": o.get("drag", 0.4), "rest": false, "base": o.get("col", ROCK), "half": maxf(0.01, (o.get("size", Vector3.ONE * 0.06) as Vector3).y * 0.5)}
	_live.append(c)

func _scatter(pos: Vector3, count: int, speed: float, up: float) -> Array:
	var out: Array = []
	for i in count:
		var a := _rand(0.0, TAU)
		var s := _rand(0.35, 1.0) * speed
		out.append(Vector3(cos(a) * s, _rand(0.6, 1.0) * up, sin(a) * s * 0.7))
	return out

## Leaves + twigs burst out of a cut tree / rustled bush.
func leaves(pos: Vector3, count: int = 14, strength: float = 1.0) -> void:
	for v in _scatter(pos, count, 1.6 * strength, 3.0 * strength):
		spawn({"kind": "leaf", "pos": pos + Vector3(_rand(-0.15, 0.15), _rand(0.0, 0.3), _rand(-0.1, 0.1)), "vel": v,
			"size": Vector3(_rand(0.07, 0.11), _rand(0.07, 0.11), 0.01), "col": LEAF.lerp(LEAF_DARK, _rng.randf()),
			"bounce": 0.15, "drag": 1.8, "grav_scale": 0.35, "life": _rand(1.2, 1.9)})
	for v in _scatter(pos, count / 4, 1.2 * strength, 2.2 * strength):
		spawn({"pos": pos + Vector3(0, 0.15, 0), "vel": v, "size": Vector3(0.02, 0.02, _rand(0.08, 0.14)), "col": TWIG,
			"bounce": 0.35, "life": _rand(1.0, 1.5)})

## Rock chips kicked off a pushed boulder or a landing.
func chips(pos: Vector3, count: int = 8, strength: float = 1.0, col: Color = ROCK) -> void:
	for v in _scatter(pos, count, 1.4 * strength, 2.4 * strength):
		var s := _rand(0.03, 0.07)
		spawn({"pos": pos + Vector3(0, 0.05, 0), "vel": v, "size": Vector3(s, s * _rand(0.6, 1.0), s), "col": col.lerp(Color.BLACK, _rand(0.0, 0.3)),
			"bounce": 0.5, "life": _rand(1.0, 1.6)})

## Glowing sparks that arc up and fall back (battle hits, level-up).
func sparks(pos: Vector3, count: int = 10, strength: float = 1.0, col: Color = SPARK) -> void:
	for v in _scatter(pos, count, 2.0 * strength, 3.4 * strength):
		spawn({"pos": pos, "vel": v, "size": Vector3(0.025, 0.025, 0.06), "col": col, "bounce": 0.3, "life": _rand(0.5, 0.9), "drag": 0.2})

func _process(dt: float) -> void:
	dt = minf(dt, 0.05)
	var i := _live.size() - 1
	while i >= 0:
		var c: Dictionary = _live[i]
		var n: MeshInstance3D = c["node"]
		c["age"] += dt
		var v: Vector3 = c["vel"]
		if not c["rest"]:
			v.y -= GRAVITY * float(c["gs"]) * dt
			v *= maxf(0.0, 1.0 - float(c["drag"]) * dt)
			n.position += v * dt
			n.rotation += (c["spin"] as Vector3) * dt
			var floor_y: float = ground_y + float(c["half"])
			if n.position.y <= floor_y:
				n.position.y = floor_y
				if absf(v.y) > 0.45:
					v.y = -v.y * float(c["bounce"])
					v.x *= 0.7
					v.z *= 0.7
					c["spin"] = (c["spin"] as Vector3) * 0.6
				else:
					v = Vector3.ZERO
					c["rest"] = true
			c["vel"] = v
		var life: float = c["life"]
		var a := clampf((life - float(c["age"])) / 0.35, 0.0, 1.0)
		var col: Color = c["base"]
		(n.material_override as StandardMaterial3D).albedo_color = Color(col, a)
		if c["age"] >= life:
			_release(c)
			_live.remove_at(i)
		i -= 1
