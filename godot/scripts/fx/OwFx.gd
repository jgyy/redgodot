class_name OwFx
extends Node3D
## Lightweight, time-based overworld effects: footstep dust, ledge-landing puffs, water rings and splashes while
## surfing, grass blades, sparkles. Each effect is a handful of camera-facing procedural sprites
## (fx/ow_sprite.gdshader) simulated with the frame delta, so they look the same at any frame rate.
## One OwFx node lives under the overworld scene; actors call the spawn helpers with world positions.

const SHADER := preload("res://scripts/fx/ow_sprite.gdshader")

enum Kind { PUFF, RING, BLADE, SPARKLE, DROP }

const DUST := Color(0.86, 0.80, 0.68, 0.55)
const SAND := Color(0.90, 0.82, 0.60, 0.6)
const WATER := Color(0.85, 0.94, 1.0, 0.75)
const GRASS := Color(0.36, 0.66, 0.26, 1.0)

var grade := Vector3.ONE
var _live: Array = []      # dictionaries: {node, mat, vel, life, age, s0, s1, a0, ...}
var _pool: Array = []
var _quad: QuadMesh
var _ground_quad: QuadMesh
var _rng := RandomNumberGenerator.new()

func _init() -> void:
	name = "OwFx"
	_rng.seed = 4242
	_quad = QuadMesh.new()
	_quad.size = Vector2.ONE
	_ground_quad = QuadMesh.new()
	_ground_quad.size = Vector2.ONE
	_ground_quad.orientation = PlaneMesh.FACE_Y

func set_grade(g: Color) -> void:
	grade = Vector3(g.r, g.g, g.b)
	for e in _live:
		((e as Dictionary)["mat"] as ShaderMaterial).set_shader_parameter("grade", grade)

## Rigid chunks (leaves / rock chips) that accompany the billboard particles; set by the scene.
var debris: Debris

func active_count() -> int:
	return _live.size()

func clear() -> void:
	for e in _live.duplicate():
		_release(e)
	_live.clear()

# ------------------------------------------------------------------ spawn helpers
func _rand(a: float, b: float) -> float:
	return a + _rng.randf() * (b - a)

## A generic sprite. o: kind, pos, vel, grav, drag (per second, 0..1 velocity kept), life, s0, s1 (size), a0 (start
## alpha), fade (alpha curve exponent), col, spin, spin_v, delay.
func spawn(o: Dictionary) -> void:
	var e: Dictionary = {"kind": Kind.PUFF, "pos": Vector3.ZERO, "vel": Vector3.ZERO, "grav": 0.0, "drag": 1.0, "life": 0.4,
		"age": 0.0, "s0": 0.2, "s1": 0.4, "a0": 0.6, "fade": 1.5, "col": DUST, "spin": 0.0, "spin_v": 0.0, "delay": 0.0,
		"pop": 0.0}
	e.merge(o, true)
	var node := _take(int(e["kind"]))
	var mat: ShaderMaterial = node.material_override
	mat.set_shader_parameter("kind", int(e["kind"]))
	mat.set_shader_parameter("color", e["col"])
	mat.set_shader_parameter("grade", grade)
	mat.set_shader_parameter("seed", _rng.randf())
	mat.set_shader_parameter("alpha", 0.0)
	e["node"] = node
	e["mat"] = mat
	node.position = e["pos"]
	node.visible = float(e["delay"]) <= 0.0
	_live.append(e)

func _take(kind: int) -> MeshInstance3D:
	var node: MeshInstance3D
	if not _pool.is_empty():
		node = _pool.pop_back()
	else:
		node = MeshInstance3D.new()
		var mat := ShaderMaterial.new()
		mat.shader = SHADER
		node.material_override = mat
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(node)
	node.mesh = _ground_quad if kind == Kind.RING else _quad
	return node

func _release(e: Dictionary) -> void:
	var node: MeshInstance3D = e["node"]
	if is_instance_valid(node):
		node.visible = false
		_pool.append(node)

## Small brown-beige dust puffs kicked up at a character's feet (walking off-road, running, biking).
func dust(pos: Vector3, count: int = 2, strength: float = 1.0, col: Color = DUST) -> void:
	for i in count:
		var ang := _rand(0.0, TAU)
		var sp := _rand(0.15, 0.45) * strength
		spawn({"kind": Kind.PUFF, "pos": pos + Vector3(_rand(-0.08, 0.08), 0.05, _rand(-0.05, 0.05)),
			"vel": Vector3(cos(ang) * sp, _rand(0.15, 0.4) * strength, sin(ang) * sp * 0.6), "drag": 0.05, "grav": -0.25,
			"life": _rand(0.32, 0.5), "s0": _rand(0.10, 0.16) * strength, "s1": _rand(0.28, 0.4) * strength,
			"a0": col.a, "fade": 1.6, "col": col, "spin": _rand(0.0, TAU)})

## Landing after a ledge hop: a ring of dust puffs pushed outward plus a flat shock ring.
func land(pos: Vector3, col: Color = DUST) -> void:
	if debris:
		debris.ground_y = pos.y
		debris.chips(pos, 5, 0.6, col.darkened(0.25))
	for i in 7:
		var ang := float(i) / 7.0 * TAU + _rand(-0.2, 0.2)
		spawn({"kind": Kind.PUFF, "pos": pos + Vector3(cos(ang) * 0.12, 0.06, sin(ang) * 0.08),
			"vel": Vector3(cos(ang) * 0.9, 0.35, sin(ang) * 0.55), "drag": 0.02, "grav": -0.6,
			"life": _rand(0.35, 0.5), "s0": 0.14, "s1": _rand(0.34, 0.5), "a0": col.a + 0.1, "fade": 1.4, "col": col,
			"spin": _rand(0.0, TAU)})
	spawn({"kind": Kind.RING, "pos": pos + Vector3(0, 0.03, 0), "life": 0.28, "s0": 0.25, "s1": 1.15, "a0": 0.35,
		"fade": 1.2, "col": Color(1, 1, 1, 1)})

## Expanding ring on the water surface (surf wake, splash).
func ripple(pos: Vector3, r1: float = 0.9, life: float = 0.9, a0: float = 0.6) -> void:
	spawn({"kind": Kind.RING, "pos": pos + Vector3(0, 0.02, 0), "life": life, "s0": r1 * 0.25, "s1": r1 * 2.0,
		"a0": a0, "fade": 1.2, "col": WATER})

## Droplets thrown up where something enters or leaves water.
func splash(pos: Vector3, count: int = 6, strength: float = 1.0) -> void:
	for i in count:
		var ang := _rand(0.0, TAU)
		spawn({"kind": Kind.DROP, "pos": pos + Vector3(0, 0.05, 0),
			"vel": Vector3(cos(ang) * _rand(0.2, 0.7) * strength, _rand(1.4, 2.4) * strength, sin(ang) * _rand(0.1, 0.4) * strength),
			"grav": 7.0, "life": _rand(0.35, 0.55), "s0": _rand(0.05, 0.09), "s1": 0.04, "a0": 0.9, "fade": 1.0, "col": WATER})
	ripple(pos, 0.7 * strength, 0.7, 0.55)

## Blades of grass flung out of a tall-grass cell as something walks through it.
func grass(pos: Vector3, count: int = 5, col: Color = GRASS) -> void:
	if debris and count >= 3:
		debris.ground_y = pos.y
		debris.leaves(pos + Vector3(0, 0.15, 0), 2, 0.5)
	for i in count:
		var ang := _rand(0.0, TAU)
		var c := col.lerp(Color(0.62, 0.84, 0.36), _rng.randf() * 0.6)
		spawn({"kind": Kind.BLADE, "pos": pos + Vector3(_rand(-0.25, 0.25), 0.08, _rand(-0.1, 0.1)),
			"vel": Vector3(cos(ang) * _rand(0.3, 0.8), _rand(0.9, 1.6), sin(ang) * _rand(0.1, 0.4)), "grav": 4.0, "drag": 0.3,
			"life": _rand(0.35, 0.6), "s0": _rand(0.16, 0.24), "s1": 0.1, "a0": 1.0, "fade": 2.5, "col": c,
			"spin": _rand(0.0, TAU), "spin_v": _rand(-9.0, 9.0)})

## Gold four-point twinkles (item pickups, healing machine, etc.).
func sparkle(pos: Vector3, count: int = 4, col: Color = Color(1.0, 0.95, 0.6, 1.0)) -> void:
	for i in count:
		spawn({"kind": Kind.SPARKLE, "pos": pos + Vector3(_rand(-0.35, 0.35), _rand(0.0, 0.8), _rand(-0.2, 0.2)),
			"vel": Vector3(0, _rand(0.2, 0.6), 0), "life": _rand(0.4, 0.7), "s0": 0.04, "s1": _rand(0.22, 0.34), "a0": 1.0,
			"fade": 1.0, "pop": 0.35, "col": col, "delay": _rand(0.0, 0.25), "spin_v": _rand(-2.0, 2.0)})

# ------------------------------------------------------------------ simulation
func _process(dt: float) -> void:
	if _live.is_empty():
		return
	var i := _live.size() - 1
	while i >= 0:
		var e: Dictionary = _live[i]
		if not _tick(e, dt):
			_release(e)
			_live.remove_at(i)
		i -= 1

func _tick(e: Dictionary, dt: float) -> bool:
	var node: MeshInstance3D = e["node"]
	if not is_instance_valid(node):
		return false
	if float(e["delay"]) > 0.0:
		e["delay"] = float(e["delay"]) - dt
		if float(e["delay"]) > 0.0:
			return true
		node.visible = true
	e["age"] = float(e["age"]) + dt
	var t := float(e["age"]) / float(e["life"])
	if t >= 1.0:
		return false
	var vel: Vector3 = e["vel"]
	vel.y -= float(e["grav"]) * dt
	vel *= pow(float(e["drag"]), dt)   # per-second retention, so drag is frame-rate independent
	e["vel"] = vel
	var pos: Vector3 = e["pos"] + vel * dt
	e["pos"] = pos
	node.position = pos
	var s0 := float(e["s0"])
	var s1 := float(e["s1"])
	# ease-out growth: fast expansion that settles
	var sz := lerpf(s0, s1, 1.0 - pow(1.0 - t, 2.0))
	var pop := float(e["pop"])
	if pop > 0.0:
		# sparkles twinkle: grow to full size, then shrink away
		var k := clampf(t / pop, 0.0, 1.0)
		sz = s1 * (sin(k * PI * 0.5) if t < pop else 1.0 - (t - pop) / (1.0 - pop))
	node.scale = Vector3(sz, sz, sz)
	var mat: ShaderMaterial = e["mat"]
	mat.set_shader_parameter("alpha", float(e["a0"]) * pow(1.0 - t, float(e["fade"])) * clampf(t * 12.0, 0.0, 1.0))
	if float(e["spin_v"]) != 0.0:
		e["spin"] = float(e["spin"]) + float(e["spin_v"]) * dt
	mat.set_shader_parameter("spin", float(e["spin"]))
	return true
