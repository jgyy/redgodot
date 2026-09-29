class_name Fireflies
extends Node3D
## Night-time fireflies (upstream art/ambient.js): a small swarm of warm pulsing lights drifts around `center` on
## slow Lissajous paths and fades in/out with the time of day.  Purely visual; toggled by `set_active`.

const COUNT := 22
const AREA := Vector2(9.0, 5.0)

var center := Vector3.ZERO
var _flies: Array = []
var _fade := 0.0
var _want := false
var _t := 0.0

func _init() -> void:
	var mesh := QuadMesh.new()
	mesh.size = Vector2(0.42, 0.42)
	var rng := RandomNumberGenerator.new()
	rng.seed = 4242
	for i in COUNT:
		var mi := MeshInstance3D.new()
		mi.mesh = mesh
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		mat.albedo_texture = _glow()
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.visible = false
		add_child(mi)
		_flies.append({"node": mi, "mat": mat, "ph": rng.randf() * TAU, "fx": rng.randf_range(0.15, 0.4), "fz": rng.randf_range(0.12, 0.33),
			"ox": rng.randf_range(-AREA.x, AREA.x), "oz": rng.randf_range(-AREA.y, AREA.y), "h": rng.randf_range(0.25, 1.2),
			"pulse": rng.randf_range(0.8, 1.9)})

static func _glow() -> GradientTexture2D:
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.95, 0.55, 1.0))
	g.set_color(1, Color(1.0, 0.8, 0.2, 0.0))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = 32
	t.height = 32
	return t

func set_active(on: bool) -> void:
	_want = on

func is_visible_now() -> bool:
	return _fade > 0.01

func _process(dt: float) -> void:
	_t += dt
	_fade = move_toward(_fade, 1.0 if _want else 0.0, dt * 0.5)
	for f in _flies:
		var n: MeshInstance3D = f["node"]
		n.visible = _fade > 0.01
		if not n.visible:
			continue
		var t: float = _t
		n.global_position = center + Vector3(f["ox"] + sin(t * f["fx"] + f["ph"]) * 2.2, f["h"] + sin(t * 0.9 + f["ph"]) * 0.12,
			f["oz"] + cos(t * f["fz"] + f["ph"] * 1.7) * 1.8)
		var pulse := 0.5 + 0.5 * sin(t * f["pulse"] * 2.0 + f["ph"])
		(f["mat"] as StandardMaterial3D).albedo_color = Color(1, 1, 1, _fade * (0.35 + 0.65 * pulse))
