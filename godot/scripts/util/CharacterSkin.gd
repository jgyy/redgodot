class_name CharacterSkin
extends RefCounted
## Applies a cast.json character's colors to the shared humanoid.glb base mesh's
## named material slots (mat_skin/mat_hair/mat_top/mat_pants/mat_shoes/mat_hat -
## see godot/assets/models/characters/manifest.json), without mutating the
## shared imported material resource (each instance gets its own override).

const DEFAULTS := {
	"mat_skin": "#e8c4a0", "mat_hair": "#6a5a50", "mat_top": "#b0b0b8",
	"mat_pants": "#80808a", "mat_shoes": "#606068", "mat_hat": "#909090",
}

const SLOT_FIELD := {
	"mat_skin": "skin", "mat_hair": "hair", "mat_top": "shirt",
	"mat_pants": "pants", "mat_shoes": "shoes", "mat_hat": "hat",
}

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

## The one place that decides which 3D model an overworld character sprite key (cast.json key, e.g. "red",
## "oak", "youngster") uses: a dedicated res://assets/models/characters/<sprite>.glb when the character
## pipeline has generated one, else the shared tinted humanoid.glb. Returns null if neither exists.
static func instantiate_character(sprite: String) -> Node3D:
	var own := "res://assets/models/characters/%s.glb" % sprite
	if sprite != "" and ResourceLoader.exists(own):
		var ps: PackedScene = load(own)
		if ps:
			return ps.instantiate()
	var base := "res://assets/models/characters/humanoid.glb"
	if ResourceLoader.exists(base):
		var scene: PackedScene = load(base)
		if scene:
			var inst: Node3D = scene.instantiate()
			apply(inst, GameData.cast.get(sprite, {}))
			return inst
	return null
