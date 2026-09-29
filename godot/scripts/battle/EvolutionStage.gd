class_name EvolutionStage
extends Node3D
## The 3D evolution sequence (upstream battleflow.js EvoScene): a dark blue
## backdrop of expanding rings, the Pokémon on a light pedestal alternating
## between its old and new model as a glowing silhouette, sparkles rising
## from the floor, then a white flash and the new form.

const RING_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled;
uniform float t = 0.0;
void fragment() {
	vec2 p = (UV - vec2(0.5, 0.39)) * vec2(320.0, 180.0);
	float r = length(p);
	float k = mod(floor(r / 10.0 - t / 6.0), 2.0);
	ALBEDO = k > 0.5 ? vec3(0.157, 0.188, 0.376) : vec3(0.110, 0.133, 0.282);
}
"""

var scene: Node
var stage: BattleStage
var _from: PokemonActor
var _to: PokemonActor
var _bg: MeshInstance3D
var _bg_mat: ShaderMaterial
var _tint: ShaderMaterial
var _t := 0
var _hidden: Array = []

func build(the_scene: Node, from_sp: String, to_sp: String) -> void:
	scene = the_scene
	stage = scene.stage
	for c in stage.get_children():
		if c is Node3D and c != stage.camera and not (c is DirectionalLight3D) and (c as Node3D).visible:
			_hidden.append(c)
			(c as Node3D).visible = false
	var cam := stage.camera
	var depth := 30.0
	_bg = MeshInstance3D.new()
	var q := QuadMesh.new()
	var h := 2.0 * depth * tan(deg_to_rad(cam.fov) / 2.0)
	q.size = Vector2(h * 16.0 / 9.0 * 1.05, h * 1.05)
	_bg.mesh = q
	_bg_mat = ShaderMaterial.new()
	var sh := Shader.new()
	sh.code = RING_SHADER
	_bg_mat.shader = sh
	_bg.material_override = _bg_mat
	add_child(_bg)
	_bg.global_transform = Transform3D(cam.global_transform.basis, cam.global_position - cam.global_transform.basis.z * depth)
	_tint = ShaderMaterial.new()
	_tint.shader = load("res://scripts/battle/actor_tint.gdshader")
	_tint.set_shader_parameter("tint", Color.WHITE.lerp(Color("#c8e0ff"), 0.2))
	_from = _actor(from_sp)
	_to = _actor(to_sp)
	show_form(false, false)

func _actor(sp: String) -> PokemonActor:
	var a := PokemonActor.new()
	add_child(a)
	a.setup(sp)
	var cam := stage.camera
	var d := 9.0
	var dir := cam.project_ray_normal(Vector2(160, 70) * 3.0)
	var pos := cam.global_position + dir * (d / dir.dot(-cam.global_transform.basis.z))
	var w := d * 2.0 * tan(deg_to_rad(cam.fov) / 2.0) / 180.0
	var ab: AABB = scene._aabb_of(a)
	var sc := 58.0 * w / maxf(0.05, maxf(ab.size.y, maxf(ab.size.x, ab.size.z) * 0.9))
	a.scale = Vector3.ONE * sc
	a.global_position = pos - Vector3(0, (ab.position.y + ab.size.y / 2.0) * sc, 0)
	a.rotation_degrees.y = -15.0
	for mi in scene._mesh_instances(a):
		(mi as GeometryInstance3D).material_overlay = _tint
	return a

func show_form(new_form: bool, silhouette: bool) -> void:
	_from.visible = not new_form
	_to.visible = new_form
	_tint.set_shader_parameter("amt", 0.85 if silhouette else 0.0)

func spark_up() -> void:
	var v: BattleVfx = scene.vfx
	v.particle({"x": 160.0 + (v.rng.randf() - 0.5) * 120.0, "y": 170.0, "vy": -1.0 - v.rng.randf() * 2.0, "life": 60,
		"shape": "dot", "size": 1.5, "cols": [Color("#e8f0ff")], "glow": 0.3})

func burst() -> void:
	var v: BattleVfx = scene.vfx
	for i in 60:
		var a := v.rng.randf() * TAU
		v.particle({"x": 160.0, "y": 62.0, "vx": cos(a) * 3.0, "vy": sin(a) * 3.0, "life": 40, "shape": "star", "size": 2.0,
			"cols": [Color("#fff8c0")], "delay": i / 4})

func _process(_dt: float) -> void:
	_t += 1
	_bg_mat.set_shader_parameter("t", float(_t))

func _exit_tree() -> void:
	for c in _hidden:
		if is_instance_valid(c):
			(c as Node3D).visible = true
