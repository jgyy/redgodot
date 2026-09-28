class_name BattleStage
extends Node3D
## The 3D battle set: per-environment backdrop (Blender-generated
## assets/models/battle/bg_<env>.glb), the two elliptical platforms
## (platform_<kind>.glb), sky/fog/light presets, ambient weather particles and
## the fixed camera that frames the enemy upper-right and the player's
## Pokémon lower-left (seen from behind), like upstream's 320x132 layout
## (E_POS = (236,78), P_POS = (84,134)).
##
## Environment names and the map -> environment rule are upstream's
## (battleflow.js battleBgFor / battlebg.js THEMES).

const BG_DIR := "res://assets/models/battle/"

## Camera + anchor layout (metres). The Blender generator writes the real
## values to layout.json (it places every backdrop prop along this camera's
## rays); these are the fallbacks.
static var CAM_POS := Vector3(0.0, 1.6, 0.0)
static var CAM_PITCH := -11.5
static var CAM_FOV := 34.0
static var ENEMY_POS := Vector3(2.36, 0.14, -9.92)
static var PLAYER_POS := Vector3(-1.13, 0.14, -4.30)
static var ENEMY_PLATFORM_R := Vector2(1.93, 1.55)   # x / z radii
static var PLAYER_PLATFORM_R := Vector2(1.13, 0.74)
static var _layout_loaded := false

static func load_layout() -> void:
	if _layout_loaded:
		return
	_layout_loaded = true
	var f := FileAccess.open(BG_DIR + "layout.json", FileAccess.READ)
	if f == null:
		return
	var d: Variant = JSON.parse_string(f.get_as_text())
	if not (d is Dictionary):
		return
	var cam: Dictionary = d.get("camera", {})
	var cp: Array = cam.get("pos", [0, 1.6, 0])
	CAM_POS = Vector3(cp[0], cp[1], cp[2])
	CAM_PITCH = float(cam.get("pitch", CAM_PITCH))
	CAM_FOV = float(cam.get("fov", CAM_FOV))
	for side in ["enemy", "player"]:
		var s: Dictionary = d.get(side, {})
		if s.is_empty():
			continue
		var c: Array = s["center"]
		var pos := Vector3(c[0], c[1], c[2])
		var r := Vector2(float(s["rx"]), float(s["rz"]))
		if side == "enemy":
			ENEMY_POS = pos
			ENEMY_PLATFORM_R = r
		else:
			PLAYER_POS = pos
			PLAYER_PLATFORM_R = r

## env -> {platform kind, sky top/bottom, ambient, sun, fog}
const ENVS := {
	"grass": {"plat": "grass", "sky": ["#6cb0f0", "#d8f0ff"], "amb": "#dfe9f2", "sun": 1.25, "time": "day"},
	"forest": {"plat": "forest", "sky": ["#1c3a2e", "#2e5a3a"], "amb": "#a6c7a0", "sun": 0.8, "time": "day"},
	"cave": {"plat": "rock", "sky": ["#16121c", "#3a2e30"], "amb": "#9a8a88", "sun": 0.55, "time": "day"},
	"water": {"plat": "water", "sky": ["#58a0e8", "#d0ecff"], "amb": "#dfeaf6", "sun": 1.2, "time": "day"},
	"beach": {"plat": "sand", "enemy_plat": "water", "sky": ["#58a0e8", "#d0ecff"], "amb": "#f0ece0", "sun": 1.25, "time": "day"},
	"ice": {"plat": "ice", "sky": ["#0e2038", "#2e5e8e"], "amb": "#b8d8f0", "sun": 0.9, "time": "day", "snow": true},
	"indoor": {"plat": "floor", "sky": ["#d8d0c0", "#b8ae9c"], "amb": "#f0ece4", "sun": 0.9, "time": "day"},
	"gym": {"plat": "floor", "sky": ["#d8d0c0", "#b8ae9c"], "amb": "#f0ece4", "sun": 0.9, "time": "day"},
	"tower": {"plat": "tower", "sky": ["#1e1630", "#4a3a5a"], "amb": "#a898c0", "sun": 0.6, "time": "night"},
	"mountain": {"plat": "sand", "sky": ["#78a8e0", "#e0eef8"], "amb": "#efe6dc", "sun": 1.2, "time": "day"},
	"power": {"plat": "metal", "sky": ["#343c48", "#1c2029"], "amb": "#b0b8c8", "sun": 0.8, "time": "day"},
	"mansion": {"plat": "wood", "sky": ["#5c3236", "#3a281c"], "amb": "#d8c0a8", "sun": 0.8, "time": "day"},
	"elite": {"plat": "floor", "sky": ["#3a2a5a", "#6a4a9a"], "amb": "#e0d8f0", "sun": 0.9, "time": "day"},
	"cavewater": {"plat": "water", "sky": ["#16121c", "#3a2e30"], "amb": "#9aa8b0", "sun": 0.6, "time": "day"},
}

const ELITE_BG := {"LoreleisRoom": "#5a90d8", "BrunosRoom": "#9a7050", "AgathasRoom": "#7a4a9a", "LancesRoom": "#b84848",
	"ChampionsRoom": "#c8a040", "HallOfFame": "#c8a040"}
const GYM_BG := {"PewterGym": "#a08868", "CeruleanGym": "#4a90d8", "VermilionGym": "#d8b030", "CeladonGym": "#58a058",
	"FuchsiaGym": "#8a58a8", "SaffronGym": "#d060a0", "CinnabarGym": "#d05030", "ViridianGym": "#8a7a50", "FightingDojo": "#b87848"}

var env := "grass"
var env_arg := ""
var camera: Camera3D
var sun: DirectionalLight3D
var world_env: WorldEnvironment
var enemy_anchor: Node3D
var player_anchor: Node3D
var enemy_platform: Node3D
var player_platform: Node3D
var backdrop: Node3D
var weather: Node3D
var _tint_override: Color = Color(0, 0, 0, 0)

## upstream battleBgFor(map, surfing): environment key for a map.
static func env_for_map(map_name: String, surfing: bool) -> String:
	if GYM_BG.has(map_name):
		return "elite:" + GYM_BG[map_name]
	if ELITE_BG.has(map_name):
		return "elite:" + ELITE_BG[map_name]
	var ts: String = str(GameData.get_map(map_name).get("ts", "overworld"))
	if surfing:
		if map_name.begins_with("Seafoam"):
			return "cavewater:ice"
		return "cavewater" if ts == "cavern" else "water"
	if map_name.begins_with("Seafoam"):
		return "ice"
	if map_name.begins_with("PowerPlant"):
		return "power"
	if map_name.begins_with("PokemonMansion"):
		return "mansion"
	if ts == "cavern" or ts == "underground":
		return "cave"
	if ts == "forest":
		return "grass" if map_name.begins_with("SafariZone") else "forest"
	if ts == "cemetery":
		return "tower"
	if ts == "gym" or ts == "dojo":
		return "gym"
	if ts == "overworld":
		var re := RegEx.create_from_string("Route(19|20|21)|Cinnabar")
		if re.search(map_name):
			return "beach"
		var re2 := RegEx.create_from_string("Route(3|4|22|23)$")
		if re2.search(map_name):
			return "mountain"
		return "grass"
	if ts == "plateau":
		return "mountain"
	return "indoor"

func build(env_name: String, time_period: String = "") -> void:
	load_layout()
	var parts := env_name.split(":")
	env = parts[0] if ENVS.has(parts[0]) else "grass"
	env_arg = parts[1] if parts.size() > 1 else ""
	var cfg: Dictionary = ENVS[env]
	_make_camera()
	_make_lights(cfg, time_period)
	_make_backdrop(cfg)
	_make_platforms(cfg)
	if cfg.get("snow", false) or (env == "cavewater" and env_arg == "ice"):
		_make_snow()

func _make_camera() -> void:
	camera = Camera3D.new()
	camera.fov = CAM_FOV
	camera.near = 0.1
	camera.far = 400.0
	add_child(camera)
	camera.position = CAM_POS
	camera.rotation_degrees = Vector3(CAM_PITCH, 0, 0)
	camera.current = true

func _make_lights(cfg: Dictionary, time_period: String) -> void:
	world_env = WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	var sky: Array = cfg["sky"]
	e.background_color = Color(sky[1])
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(cfg["amb"])
	e.ambient_light_energy = 0.32
	e.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	world_env.environment = e
	add_child(world_env)
	sun = DirectionalLight3D.new()
	sun.light_energy = float(cfg["sun"]) * 0.34
	sun.rotation_degrees = Vector3(-52, -35, 0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 30.0
	add_child(sun)
	var tp := time_period if time_period != "" else str(cfg.get("time", "day"))
	if tp == "night" and env in ["grass", "water", "beach", "mountain", "forest"]:
		# upstream darkens outdoor backdrops at night (ref 073 gengar)
		_tint_override = Color("#aab2d4")
		sun.light_color = Color("#b8c0e8")
		sun.light_energy *= 0.8
		e.ambient_light_color = Color("#a8b0d8")
	elif tp == "dusk" and env in ["grass", "water", "beach", "mountain"]:
		_tint_override = Color("#f0b890")
		sun.light_color = Color("#ffc8a0")

func _load_glb(file: String) -> Node3D:
	var path := BG_DIR + file
	if not ResourceLoader.exists(path):
		return null
	var ps: PackedScene = load(path)
	return ps.instantiate() if ps else null

func _make_backdrop(cfg: Dictionary) -> void:
	backdrop = _load_glb("bg_%s.glb" % (env + ("_ice" if env == "cavewater" and env_arg == "ice" else "")))
	if backdrop == null:
		backdrop = _fallback_backdrop(cfg)
	add_child(backdrop)
	var tint := _tint_override
	if env == "elite" and env_arg != "":
		tint = Color(env_arg) * Color(1.6, 1.6, 1.6)
		tint.a = 1.0
	_prep_materials(backdrop, tint)

## Sky/backdrop materials named "*sky*"/"*cloud*"/"*far*" render unshaded so the
## gradient + painted cloud colors match upstream's flat backdrops.
## Prepares imported backdrop materials: pixel-art sampling, no specular,
## names containing "sky"/"cloud"/"unlit" render unshaded (upstream's flat
## backdrop colours), and an optional multiplicative tint (night / elite rooms).
func _prep_materials(n: Node, tint: Color = Color(1, 1, 1, 0)) -> void:
	if n is MeshInstance3D:
		var mi: MeshInstance3D = n
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for i in mi.mesh.get_surface_count():
			var m: Material = mi.get_surface_override_material(i)
			if m == null:
				m = mi.mesh.surface_get_material(i)
			if not (m is BaseMaterial3D):
				continue
			var d: BaseMaterial3D = m.duplicate()
			d.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
			d.metallic_specular = 0.0
			d.roughness = 1.0
			var nm := m.resource_name
			if nm.contains("sky") or nm.contains("cloud") or nm.contains("unlit"):
				d.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
				d.disable_receive_shadows = true
			if tint.a > 0:
				d.albedo_color = d.albedo_color * tint
			mi.set_surface_override_material(i, d)
	for c in n.get_children():
		_prep_materials(c, tint)

func _tint_meshes(n: Node, tint: Color) -> void:
	if n is MeshInstance3D:
		var mi: MeshInstance3D = n
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for i in mi.mesh.get_surface_count():
			var m: Material = mi.get_surface_override_material(i)
			if m == null:
				m = mi.mesh.surface_get_material(i)
			if m is BaseMaterial3D:
				var d: BaseMaterial3D = m.duplicate()
				d.albedo_color = d.albedo_color * tint
				mi.set_surface_override_material(i, d)
	for c in n.get_children():
		_tint_meshes(c, tint)

func _make_platforms(cfg: Dictionary) -> void:
	var kind: String = cfg["plat"]
	var ekind: String = cfg.get("enemy_plat", kind)
	enemy_platform = _platform(ekind, ENEMY_PLATFORM_R)
	enemy_platform.position = Vector3(ENEMY_POS.x, ENEMY_POS.y - 0.14, ENEMY_POS.z)
	add_child(enemy_platform)
	player_platform = _platform(kind, PLAYER_PLATFORM_R)
	player_platform.position = Vector3(PLAYER_POS.x, PLAYER_POS.y - 0.14, PLAYER_POS.z)
	add_child(player_platform)
	enemy_anchor = Node3D.new()
	enemy_anchor.name = "EnemyAnchor"
	enemy_anchor.position = ENEMY_POS
	add_child(enemy_anchor)
	player_anchor = Node3D.new()
	player_anchor.name = "PlayerAnchor"
	player_anchor.position = PLAYER_POS
	add_child(player_anchor)

func _platform(kind: String, r: Vector2) -> Node3D:
	var n := _load_glb("platform_%s.glb" % kind)
	if n == null:
		var mi := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = 1.0
		cyl.bottom_radius = 1.0
		cyl.height = 0.15
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color("#62b452")
		cyl.material = mat
		mi.mesh = cyl
		mi.position.y = -0.075
		n = Node3D.new()
		n.add_child(mi)
	_prep_materials(n, _tint_override)
	var holder := Node3D.new()
	holder.add_child(n)
	n.scale = Vector3(r.x, 1.0, r.y)
	return holder

func _fallback_backdrop(cfg: Dictionary) -> Node3D:
	var root := Node3D.new()
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(200, 200)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color("#7cc05a")
	pm.material = gm
	ground.mesh = pm
	root.add_child(ground)
	var sky: Array = cfg["sky"]
	world_env.environment.background_color = Color(sky[0])
	return root

## Ambient snowfall (ice caves, ref 074 / 085): CPU particles work in the
## Compatibility renderer. Deterministic seed so screenshots are stable.
func _make_snow() -> void:
	var p := CPUParticles3D.new()
	p.amount = 260
	p.lifetime = 6.0
	p.preprocess = 6.0
	p.use_fixed_seed = true
	p.seed = 1234
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	p.emission_box_extents = Vector3(14, 0.5, 9)
	p.position = Vector3(0.5, 7.5, -3.0)
	p.direction = Vector3(-0.5, -1, 0.2)
	p.spread = 12.0
	p.gravity = Vector3(0, -0.4, 0)
	p.initial_velocity_min = 0.9
	p.initial_velocity_max = 1.6
	var q := QuadMesh.new()
	q.size = Vector2(0.07, 0.07)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(1, 1, 1)
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	q.material = m
	p.mesh = q
	add_child(p)
	weather = p

# ------------------------------------------------------------------ 2D <-> 3D mapping
## Upstream draws effects in 320x132 battle-screen pixels. This maps such a
## pixel onto a 3D point on the slanted plane that contains both battlers'
## centres (and the world up axis), so ported effect paths land between the
## real 3D Pokémon at the right depth.
func px_to_world(px: Vector2, e_center: Vector3, p_center: Vector3) -> Vector3:
	var vp := Vector2(px.x * 3.0, px.y * 3.0)
	var from := camera.project_ray_origin(vp)
	var dir := camera.project_ray_normal(vp)
	var axis := (e_center - p_center)
	var n := axis.cross(Vector3.UP).normalized()
	if n.dot(dir) > 0:
		n = -n
	var denom := n.dot(dir)
	if absf(denom) < 1e-4:
		return p_center
	var t := n.dot(p_center - from) / denom
	return from + dir * t

func world_to_px(p: Vector3) -> Vector2:
	var v := camera.unproject_position(p)
	return v / 3.0
