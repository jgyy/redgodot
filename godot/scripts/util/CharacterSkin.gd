class_name CharacterSkin
extends RefCounted
## Character models.
##
## * CharacterSkin.instantiate(sprite_key) -> Node3D : the best model for an upstream
##   sprite key (the `sprite` of a mapdata.json obj / a cast.json key, e.g. "red",
##   "oak", "youngster"): godot/assets/models/characters/<sprite>.glb when the Blender
##   pipeline generated one (pipeline/blender/gen_characters.py; unknown keys map to an
##   archetype through the manifest's "aliases"), otherwise the shared humanoid.glb
##   tinted from cast.json.  The result is cel-shaded (Toon.apply) and its Idle/Walk
##   clips loop.  Faces +Z (Godot MODEL_FRONT); feet at y=0.
## * CharacterSkin.apply(model, cast_entry): legacy tint of humanoid.glb's named
##   material slots (mat_skin/mat_hair/mat_top/mat_pants/mat_shoes/mat_hat).

const MODEL_DIR := "res://assets/models/characters/"

const DEFAULTS := {
	"mat_skin": "#e8c4a0", "mat_hair": "#6a5a50", "mat_top": "#b0b0b8",
	"mat_pants": "#80808a", "mat_shoes": "#606068", "mat_hat": "#909090",
}

## Clips baked by pipeline/blender/char_anim.py: Idle, Walk (one full 2-step gait per 16-frame cell, so it stays
## seamless when restarted every step), Run, Talk, Wave, Cheer -- all loop.
const LOOPING_EXTRA := ["Talk", "Wave", "Cheer", "Surf", "Nod", "Shake", "Think", "Laugh", "Point", "Sleep", "Salute",
		"Stretch", "Dance", "Sad", "Shiver"]
## The 13 gesture clips every character has on top of Idle/Walk/Run/Talk/Wave/Cheer (Bow and Surprised play once).
const GESTURES := ["Nod", "Shake", "Think", "Laugh", "Bow", "Point", "Sleep", "Surprised", "Salute", "Stretch", "Dance", "Sad", "Shiver"]

## Cel-shader settings for the realistic characters: a softer ramp than the old chibi models had, so the smooth skin and cloth
## read as forms (not as flat sprites) and the highlight band does not blow pink dresses out to white patches.
const RAMP_BIAS := 0.32
const RAMP_STRENGTH := 0.42

const SLOT_FIELD := {
	"mat_skin": "skin", "mat_hair": "hair", "mat_top": "shirt",
	"mat_pants": "pants", "mat_shoes": "shoes", "mat_hat": "hat",
}

static var _aliases: Dictionary = {}
static var _aliases_loaded := false

## Best available model for `sprite_key` (never null).
static func instantiate(sprite_key: String, toon: bool = true) -> Node3D:
	if sprite_key == "red" and GameState.look_enabled():
		var pm := PlayerModel.build(GameState.player_look(), toon)
		if pm:
			return pm
	var key := resolve_key(sprite_key)
	var model: Node3D = null
	var tinted := false
	if key != "":
		var scene: PackedScene = load(MODEL_DIR + key + ".glb")
		if scene:
			model = scene.instantiate()
	if model == null and ResourceLoader.exists(MODEL_DIR + "humanoid.glb"):
		var base: PackedScene = load(MODEL_DIR + "humanoid.glb")
		if base:
			model = base.instantiate()
			tinted = true
	if model == null:
		return Node3D.new()
	if tinted:
		apply(model, GameData.cast.get(sprite_key, {}))
	elif fit_bounds:
		_fit_bounds(model)
	if toon:
		Toon.apply(model, 1.3, 0.02)
		# keep the faces out of the darkest bands (upstream's character sprites are mostly flat skin with a darker lower edge)
		Toon.set_param(model, "ramp_bias", RAMP_BIAS)
		Toon.set_param(model, "ramp_strength", RAMP_STRENGTH)
	finish_model(model)
	return model

## Shared tail of instantiate(): looping clips and short cross-fades.
static func finish_model(model: Node3D) -> void:
	var ap := AnimUtil.find_player(model)
	AnimUtil.fix_looping(ap)
	if ap:
		# short cross-fades so Idle <-> Walk <-> Run never pop (Walk restarts seamlessly: one cycle == one cell)
		ap.playback_default_blend_time = 0.07
		# the character pipeline's extra looping clips (AnimUtil only knows Idle/Walk/Run)
		for clip in LOOPING_EXTRA:
			if ap.has_animation(clip):
				ap.get_animation(clip).loop_mode = Animation.LOOP_LINEAR

## Callers that size a model by its bounding box (OwActor._fit_height) would shrink every character with
## tall spiky hair, a chef's toque or a mohawk and enlarge children to adult height.  The generated meshes
## therefore report a body-based AABB: at least REF_TOP_M tall (a standard adult incl. ordinary hair / hat), at
## most MAX_TOP_M; anything taller is still drawn (extra_cull_margin keeps it from being culled).
const REF_TOP_M := 1.53
const MAX_TOP_M := 1.66
static var fit_bounds := true

static func _fit_bounds(model: Node) -> void:
	for item in _find_mesh_instances(model):
		var inst: MeshInstance3D = item
		var mesh := inst.mesh as ArrayMesh
		if mesh == null:
			continue
		if not mesh.has_meta("true_top"):
			mesh.set_meta("true_top", mesh.get_aabb().end.y)
			var a: AABB = mesh.get_aabb()
			var top := clampf(a.end.y, REF_TOP_M, MAX_TOP_M)
			mesh.custom_aabb = AABB(a.position, Vector3(a.size.x, top - a.position.y, a.size.z))
		inst.extra_cull_margin = maxf(0.0, float(mesh.get_meta("true_top")) - (mesh.custom_aabb.end.y))

## The generated model file key for a sprite key ("" if none): exact file first, then
## the manifest's alias table (sprite keys that share an archetype model).
static func resolve_key(sprite_key: String) -> String:
	if sprite_key == "":
		return ""
	if ResourceLoader.exists(MODEL_DIR + sprite_key + ".glb"):
		return sprite_key
	if not _aliases_loaded:
		_aliases_loaded = true
		var f := FileAccess.open(MODEL_DIR + "manifest.json", FileAccess.READ)
		if f:
			var data: Variant = JSON.parse_string(f.get_as_text())
			if data is Dictionary:
				_aliases = (data as Dictionary).get("aliases", {})
	var a: String = _aliases.get(sprite_key, "")
	if a != "" and ResourceLoader.exists(MODEL_DIR + a + ".glb"):
		return a
	return ""

## `cast_entry` is one value from GameData.cast (e.g. GameData.cast["red"]).
static func apply(model: Node3D, cast_entry: Dictionary) -> void:
	for item in _find_mesh_instances(model):
		var mesh_inst: MeshInstance3D = item
		var mesh: Mesh = mesh_inst.mesh
		if mesh == null:
			continue
		for i in range(mesh.get_surface_count()):
			var mat: Material = mesh.surface_get_material(i)
			var slot: String = (mat.resource_name if mat else "")
			if not DEFAULTS.has(slot):
				continue
			var field: String = SLOT_FIELD[slot]
			# body=coat characters (Oak, scientists): the torso region codes are X/x = the coat colour, not the shirt
			if slot == "mat_top" and cast_entry.get("body", "") == "coat" and cast_entry.has("coat"):
				field = "coat"
			var hex: String = cast_entry.get(field, DEFAULTS[slot])
			var new_mat: StandardMaterial3D = (mat.duplicate() if mat is StandardMaterial3D else StandardMaterial3D.new())
			new_mat.albedo_color = Color(hex)
			mesh_inst.set_surface_override_material(i, new_mat)

static func _find_mesh_instances(node: Node) -> Array:
	var out: Array = []
	if node is MeshInstance3D:
		out.append(node)
	for c in node.get_children():
		out.append_array(_find_mesh_instances(c))
	return out

## The one place that decides which 3D model an overworld character sprite key (cast.json key, e.g. "red",
## "oak", "youngster") uses: a dedicated res://assets/models/characters/<sprite>.glb when the character
## pipeline has generated one, else the shared tinted humanoid.glb. Returns null if neither exists.
static func instantiate_character(sprite: String) -> Node3D:
	return instantiate(sprite)
