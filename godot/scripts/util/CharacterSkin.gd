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

const SLOT_FIELD := {
	"mat_skin": "skin", "mat_hair": "hair", "mat_top": "shirt",
	"mat_pants": "pants", "mat_shoes": "shoes", "mat_hat": "hat",
}

static var _aliases: Dictionary = {}
static var _aliases_loaded := false

## Best available model for `sprite_key` (never null).
static func instantiate(sprite_key: String, toon: bool = true) -> Node3D:
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
	if toon:
		Toon.apply(model, 1.3, 0.02)
	AnimUtil.fix_looping(AnimUtil.find_player(model))
	return model

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
