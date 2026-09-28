class_name MapLoader
extends Node3D
## Builds a real, playable 3D representation of one map from the original game's
## authentic tile-grid data (godot/data/mapdata.json, 223 maps / full Kanto).
## Tile ids are classified generically per-tileset (walkable / blocking / tall-grass /
## door / counter / water) using the same pass/grass/doors/warps lists the original
## engine used for collision, rather than per-tile bespoke art.

const CELL_SIZE := 2.0  # meters per map cell

var map_name: String = ""
var map_data: Dictionary = {}
var tileset: Dictionary = {}
var width: int = 0
var height: int = 0

var _grid: GridMap
var _category_at := {}   # Vector2i -> TileKit.Cat
var _warp_at := {}       # Vector2i -> warp dict {x,y,to,warp}
var _sign_at := {}       # Vector2i -> sign dict
var _npc_at := {}        # Vector2i -> obj dict (NPC/prop from mapdata.json's `objs`)

func load_map(name: String) -> bool:
	map_name = name
	map_data = GameData.get_map(name)
	if map_data.is_empty():
		push_error("[MapLoader] unknown map: %s" % name)
		return false
	tileset = GameData.get_tileset(map_data.get("tsc", ""))
	width = map_data.get("w", 0)
	height = map_data.get("h", 0)

	if _grid:
		_grid.queue_free()
	_grid = GridMap.new()
	_grid.cell_size = Vector3(CELL_SIZE, CELL_SIZE, CELL_SIZE)
	_grid.mesh_library = TileKit.get_library()
	add_child(_grid)

	_category_at.clear()
	_warp_at.clear()
	_sign_at.clear()

	var pass_ids := {}
	for pid in tileset.get("pass", []):
		pass_ids[int(pid)] = true
	var grass_id := int(tileset.get("grass", -1))
	var door_ids := {}
	for did in tileset.get("doors", []):
		door_ids[int(did)] = true
	var counter_ids := {}
	for cid in tileset.get("counters", []):
		counter_ids[int(cid)] = true

	var cells: Array = map_data.get("cells", [])
	for y in range(height):
		for x in range(width):
			var idx := y * width + x
			if idx >= cells.size():
				continue
			var v := int(cells[idx])
			var cat := _classify(v, pass_ids, grass_id, door_ids, counter_ids)
			_category_at[Vector2i(x, y)] = cat
			_grid.set_cell_item(Vector3i(x, 0, y), int(cat))

	for w in map_data.get("warps", []):
		_warp_at[Vector2i(int(w.get("x", 0)), int(w.get("y", 0)))] = w
	for s in map_data.get("signs", []):
		_sign_at[Vector2i(int(s.get("x", 0)), int(s.get("y", 0)))] = s

	_spawn_npcs()
	return true

## Populates NPCs/props from the map's `objs` list (real placements from the
## source data) as static humanoid-or-prop markers the player can talk to.
## No movement AI (even "WALK" objs stay put) — future work. Building the
## visual subtree is skipped when not inside the SceneTree (e.g. TestSuite's
## off-tree MapLoader.load_map() calls) so `npc_at()` still works for tests
## without touching the renderer before nodes have entered the tree.
func _spawn_npcs() -> void:
	_npc_at.clear()
	for o in map_data.get("objs", []):
		var cell := Vector2i(int(o.get("x", 0)), int(o.get("y", 0)))
		if in_bounds(cell) and not _npc_at.has(cell):
			_npc_at[cell] = o
	if not is_inside_tree():
		return
	var npcs := Node3D.new()
	npcs.name = "NPCs"
	add_child(npcs)
	for cell in _npc_at.keys():
		var model := _build_npc_model(_npc_at[cell])
		model.position = cell_to_world(cell)
		npcs.add_child(model)

func _build_npc_model(obj: Dictionary) -> Node3D:
	var sprite: String = obj.get("sprite", "")
	if DialogueText.is_humanoid_sprite(sprite):
		var path := "res://assets/models/characters/humanoid.glb"
		if ResourceLoader.exists(path):
			var scene: PackedScene = load(path)
			if scene:
				var inst: Node3D = scene.instantiate()
				CharacterSkin.apply(inst, GameData.cast.get(sprite, {}))
				return inst
	var body := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = 0.25
	sphere.height = 0.5
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(GameData.cast.get(sprite, {}).get("shirt", "#c8a0d8"))
	sphere.material = mat
	body.mesh = sphere
	body.position.y = 0.25
	return body

func npc_at(cell: Vector2i) -> Dictionary:
	return _npc_at.get(cell, {})

func _classify(v: int, pass_ids: Dictionary, grass_id: int, door_ids: Dictionary, counter_ids: Dictionary) -> int:
	if v == grass_id:
		return TileKit.Cat.TALLGRASS
	if door_ids.has(v):
		return TileKit.Cat.DOOR
	if counter_ids.has(v):
		return TileKit.Cat.COUNTER
	if pass_ids.has(v):
		return TileKit.Cat.FLOOR
	# Non-passable tiles are ambiguous in this data (tree/wall/water/mountain all
	# just mean "not in the pass list") - default to a generic blocking prop.
	# Distinguishing tree vs. wall vs. water visually per-tile-id is future work
	# (would need the original tileset PNGs, which this from-scratch remake has none of).
	return TileKit.Cat.BLOCKING

func cell_to_world(cell: Vector2i) -> Vector3:
	return Vector3(cell.x * CELL_SIZE, 0.0, cell.y * CELL_SIZE)

func in_bounds(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < width and cell.y < height

func is_walkable(cell: Vector2i) -> bool:
	if not in_bounds(cell):
		return false
	if _npc_at.has(cell):
		return false
	return TileKit.is_walkable(_category_at.get(cell, TileKit.Cat.BLOCKING))

func is_tall_grass(cell: Vector2i) -> bool:
	return _category_at.get(cell, -1) == TileKit.Cat.TALLGRASS

func warp_at(cell: Vector2i) -> Dictionary:
	return _warp_at.get(cell, {})

func sign_at(cell: Vector2i) -> Dictionary:
	return _sign_at.get(cell, {})

func connection_beyond(cell: Vector2i) -> Dictionary:
	var conns: Dictionary = map_data.get("conns", {})
	if cell.y < 0 and conns.has("north"):
		return {"dir": "north", "conn": conns["north"]}
	if cell.y >= height and conns.has("south"):
		return {"dir": "south", "conn": conns["south"]}
	if cell.x < 0 and conns.has("west"):
		return {"dir": "west", "conn": conns["west"]}
	if cell.x >= width and conns.has("east"):
		return {"dir": "east", "conn": conns["east"]}
	return {}

## Resolves the arrival cell on this map for warp index `warp_index` (as used by the
## classic bidirectional warp encoding: the destination map's warps[warp_index]).
func arrival_cell(warp_index: int) -> Vector2i:
	var warps: Array = map_data.get("warps", [])
	if warp_index >= 0 and warp_index < warps.size():
		var w = warps[warp_index]
		return Vector2i(int(w.get("x", 0)), int(w.get("y", 0)))
	return Vector2i(width / 2, height / 2)
