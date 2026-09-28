class_name TileKit
extends RefCounted
## Builds (once) the shared MeshLibrary used by every GridMap-based overworld map.
## Tries to load Blender-generated glb tiles from res://assets/models/tiles/; falls back
## to simple primitive meshes so the game is fully playable even before/without those assets.

enum Cat { FLOOR, BLOCKING, TALLGRASS, WATER, DOOR, COUNTER, LEDGE }

const TILE_FILES := {
	Cat.FLOOR: "res://assets/models/tiles/floor_path.glb",
	Cat.BLOCKING: "res://assets/models/tiles/tree.glb",
	Cat.TALLGRASS: "res://assets/models/tiles/tallgrass.glb",
	Cat.WATER: "res://assets/models/tiles/water.glb",
	Cat.DOOR: "res://assets/models/tiles/door.glb",
	Cat.COUNTER: "res://assets/models/tiles/counter.glb",
	Cat.LEDGE: "res://assets/models/tiles/ledge.glb",
}

const FALLBACK_COLOR := {
	Cat.FLOOR: Color(0.55, 0.42, 0.28),
	Cat.BLOCKING: Color(0.18, 0.42, 0.2),
	Cat.TALLGRASS: Color(0.28, 0.62, 0.26),
	Cat.WATER: Color(0.22, 0.4, 0.85),
	Cat.DOOR: Color(0.5, 0.32, 0.18),
	Cat.COUNTER: Color(0.6, 0.45, 0.28),
	Cat.LEDGE: Color(0.45, 0.4, 0.35),
}

const WALKABLE := [Cat.FLOOR, Cat.TALLGRASS, Cat.DOOR, Cat.COUNTER, Cat.LEDGE]

static var _library: MeshLibrary = null

static func get_library() -> MeshLibrary:
	if _library == null:
		_library = _build_library()
	return _library

static func is_walkable(cat: int) -> bool:
	return WALKABLE.has(cat)

static func _build_library() -> MeshLibrary:
	var lib := MeshLibrary.new()
	for cat in TILE_FILES.keys():
		var mesh := _load_mesh_or_fallback(cat)
		var id := int(cat)
		lib.create_item(id)
		lib.set_item_name(id, Cat.keys()[cat])
		lib.set_item_mesh(id, mesh)
	return lib

static func _load_mesh_or_fallback(cat: int) -> Mesh:
	var path: String = TILE_FILES[cat]
	if ResourceLoader.exists(path):
		var scene: PackedScene = load(path)
		if scene:
			var inst := scene.instantiate()
			var mesh_inst := _find_mesh_instance(inst)
			if mesh_inst and mesh_inst.mesh:
				var m: Mesh = mesh_inst.mesh
				inst.queue_free()
				return m
			inst.queue_free()
	return _fallback_mesh(cat)

static func _find_mesh_instance(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D:
		return node
	for c in node.get_children():
		var found := _find_mesh_instance(c)
		if found:
			return found
	return null

static func _fallback_mesh(cat: int) -> Mesh:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = FALLBACK_COLOR[cat]
	var mesh: Mesh
	match cat:
		Cat.BLOCKING:
			var box := BoxMesh.new()
			box.size = Vector3(0.8, 1.6, 0.8)
			mesh = box
		Cat.TALLGRASS:
			var box := BoxMesh.new()
			box.size = Vector3(0.9, 0.4, 0.9)
			mesh = box
		Cat.LEDGE:
			var box := BoxMesh.new()
			box.size = Vector3(1.0, 0.4, 1.0)
			mesh = box
		_:
			var plane := BoxMesh.new()
			plane.size = Vector3(1.0, 0.1, 1.0)
			mesh = plane
	(mesh as PrimitiveMesh).material = mat
	return mesh
