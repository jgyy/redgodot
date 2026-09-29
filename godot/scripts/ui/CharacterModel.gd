class_name CharacterModel
extends RefCounted
## Builds the 3D model for a cast.json character (menus, title, intro).
## Prefers a dedicated res://assets/models/characters/<key>.glb when the
## character pipeline provides one, else the shared humanoid.glb recoloured
## through CharacterSkin, else a capsule placeholder.

const DIR := "res://assets/models/characters/"

static func build(cast_key: String) -> Node3D:
	# the character pipeline's cel-shaded model (with humanoid fallback)
	var best := CharacterSkin.instantiate(cast_key)
	# instantiate() never returns null: with no model at all it hands back an empty Node3D, which would skip the
	# fallbacks below and leave the menu/intro with an invisible character
	if best and best.get_child_count() > 0:
		return best
	if best:
		best.free()
	var entry: Dictionary = GameData.cast.get(cast_key, {})
	for path in [DIR + cast_key + ".glb", DIR + "humanoid.glb"]:
		if ResourceLoader.exists(path):
			var scene: PackedScene = load(path)
			if scene:
				var inst: Node3D = scene.instantiate()
				if path.ends_with("humanoid.glb"):
					CharacterSkin.apply(inst, entry)
				return inst
	var body := MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.3
	capsule.height = 1.4
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(entry.get("shirt", "#d64a3a"))
	capsule.material = mat
	body.mesh = capsule
	body.position.y = 0.7
	var root := Node3D.new()
	root.add_child(body)
	return root

static func find_anim(node: Node) -> AnimationPlayer:
	if node == null:
		return null
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var found := find_anim(c)
		if found:
			return found
	return null
