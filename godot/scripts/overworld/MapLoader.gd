class_name MapLoader
extends Node3D
## One map of the overworld: collision exactly like upstream's GameMap (src/game/map.js) plus its 3D build.
##
## Collision: each cell holds a *quad index* into mapdata.quads[tileset file]; the quad's bottom-left 8x8 tile
## (quads[ts][q][2]) is the collision tile, checked against the tileset's pass list, grass tile, water tiles,
## door/warp tiles, the ledge table and the tile-pair (elevation) table.
##
## Visuals: built from the map's bake (res://assets/maps/<Map>.*, see pipeline/scripts/bake_maps.js) by
## WorldBuilder (ground + extruded buildings/walls/furniture) and TileKit (3D trees, tall grass, flowers).
## World space: 1 unit per cell, map cell (x, y) spans [x, x+1] x [y, y+1] on the XZ plane (+z = south).

const CELL_SIZE := WorldData.CELL

var map_name: String = ""
var map_data: Dictionary = {}
var tileset: Dictionary = {}
var tileset_name := ""
var ts_file := ""
var width: int = 0
var height: int = 0
var outdoor := false
var interior := false
var bake: Dictionary = {}

var _coll: PackedInt32Array = PackedInt32Array()
var _pass := {}
var _doors := {}
var _warps_tiles := {}
var _counters := {}
var _grass_tile := -1
var _has_water := false
var _pairs: Array = []
var _warp_at := {}       # Vector2i -> warp index
var _sign_at := {}       # Vector2i -> sign dict
var pass_override := {}  # Vector2i -> bool (scripts: cut trees, boulders...)

var actors: Array = []   # OwActor NPCs currently on this map
var world_mat: ShaderMaterial
var obj_mat: ShaderMaterial
var grass_node: Node3D

func load_map(name: String, with_bake: bool = true) -> bool:
	WorldData.ensure()
	map_name = name
	map_data = GameData.get_map(name)
	if map_data.is_empty():
		push_error("[MapLoader] unknown map: %s" % name)
		return false
	tileset_name = String(map_data.get("tsc", ""))
	ts_file = String(map_data.get("ts", ""))
	tileset = GameData.get_tileset(tileset_name)
	width = int(map_data.get("w", 0))
	height = int(map_data.get("h", 0))
	outdoor = ts_file == "overworld" or ts_file == "plateau"
	interior = not ["overworld", "plateau", "forest", "ship_port"].has(ts_file)

	var q: Array = WorldData.quads.get(ts_file, [])
	var cells: Array = map_data.get("cells", [])
	_coll.resize(cells.size())
	for i in range(cells.size()):
		var qi := int(cells[i])
		_coll[i] = int(q[qi][2]) if qi < q.size() else -1
	_pass.clear()
	for t in tileset.get("pass", []):
		_pass[int(t)] = true
	_doors.clear()
	for t in tileset.get("doors", []):
		_doors[int(t)] = true
	_warps_tiles.clear()
	for t in tileset.get("warps", []):
		_warps_tiles[int(t)] = true
	_counters.clear()
	for t in tileset.get("counters", []):
		_counters[int(t)] = true
	_grass_tile = int(tileset.get("grass", -1))
	_has_water = bool(tileset.get("water", false))
	_pairs.clear()
	var tsu := tileset_name.to_upper()
	for p in WorldData.pair_land:
		if String(p[0]).to_upper().replace("_", "") == tsu:
			_pairs.append([int(p[1]), int(p[2])])

	_warp_at.clear()
	var ws: Array = map_data.get("warps", [])
	for i in range(ws.size()):
		var w: Dictionary = ws[i]
		var c := Vector2i(int(w.get("x", 0)), int(w.get("y", 0)))
		if not _warp_at.has(c):
			_warp_at[c] = i
	_sign_at.clear()
	for s in map_data.get("signs", []):
		_sign_at[Vector2i(int(s.get("x", 0)), int(s.get("y", 0)))] = s
	pass_override.clear()

	bake = WorldBuilder.load_bake(name) if with_bake else {}
	if is_inside_tree() and with_bake:
		_build_visuals()
	return true

# ---------------------------------------------------------------- collision (upstream GameMap)
func in_bounds(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < width and cell.y < height

func tile(cell: Vector2i) -> int:
	return _coll[cell.y * width + cell.x] if in_bounds(cell) else -1

func passable(cell: Vector2i) -> bool:
	if not in_bounds(cell):
		return false
	if pass_override.has(cell):
		return bool(pass_override[cell])
	return _pass.has(tile(cell))

func is_tall_grass(cell: Vector2i) -> bool:
	return in_bounds(cell) and _grass_tile >= 0 and tile(cell) == _grass_tile and not pass_override.has(cell)

func is_water(cell: Vector2i) -> bool:
	if not in_bounds(cell) or not _has_water:
		return false
	var t := tile(cell)
	return t == 0x14 or t == 0x32 or t == 0x48

func is_door_tile(cell: Vector2i) -> bool:
	return _doors.has(tile(cell))

func is_warp_tile(cell: Vector2i) -> bool:
	return _warps_tiles.has(tile(cell))

func is_counter(cell: Vector2i) -> bool:
	return _counters.has(tile(cell))

func pair_blocked(a: Vector2i, b: Vector2i) -> bool:
	var ta := tile(a)
	var tb := tile(b)
	for p in _pairs:
		if (ta == p[0] and tb == p[1]) or (ta == p[1] and tb == p[0]):
			return true
	return false

## Upstream's ledge table (Overworld tileset only): stepping `dir` from a stand tile onto a ledge tile hops.
func is_ledge_jump(from: Vector2i, dir: String) -> bool:
	if tileset_name != "Overworld":
		return false
	var nxt: Vector2i = from + OwActor.DIRS[dir]
	var cur := tile(from)
	var nt := tile(nxt)
	for l in WorldData.ledges:
		if String(l[0]) == dir and int(l[1]) == cur and int(l[2]) == nt:
			return true
	return false

## Legacy helper (tests/other callers): walkable = passable and not occupied by an NPC.
func is_walkable(cell: Vector2i) -> bool:
	return passable(cell) and npc_at(cell).is_empty()

func warp_index_at(cell: Vector2i) -> int:
	return int(_warp_at.get(cell, -1))

func warp_at(cell: Vector2i) -> Dictionary:
	var i := warp_index_at(cell)
	if i < 0:
		return {}
	return map_data.get("warps", [])[i]

func sign_at(cell: Vector2i) -> Dictionary:
	return _sign_at.get(cell, {})

func label_at(cell: Vector2i) -> String:
	if label_override.has(cell):
		return String(label_override[cell])
	if bake.is_empty():
		return ""
	var x := cell.x + int(bake.get("mx", 0))
	var y := cell.y + int(bake.get("my", 0))
	var cw := int(bake.get("cw", 0))
	var ch := int(bake.get("ch", 0))
	if x < 0 or y < 0 or x >= cw or y >= ch:
		return ""
	var legend: Array = bake.get("legend", [])
	var labels: Array = bake.get("labels", [])
	return String(legend[int(labels[y * cw + x])])

func connection_dir(cell: Vector2i) -> String:
	if cell.y < 0:
		return "north"
	if cell.y >= height:
		return "south"
	if cell.x < 0:
		return "west"
	if cell.x >= width:
		return "east"
	return ""

func connection_beyond(cell: Vector2i) -> Dictionary:
	var conns: Dictionary = map_data.get("conns", {})
	var d := connection_dir(cell)
	if d != "" and conns.has(d):
		return {"dir": d, "conn": conns[d]}
	return {}

func arrival_cell(warp_index: int) -> Vector2i:
	var warps: Array = map_data.get("warps", [])
	if warp_index >= 0 and warp_index < warps.size():
		var w: Dictionary = warps[warp_index]
		return Vector2i(int(w.get("x", 0)), int(w.get("y", 0)))
	if not warps.is_empty():
		var w0: Dictionary = warps[0]
		return Vector2i(int(w0.get("x", 0)), int(w0.get("y", 0)))
	return Vector2i(width / 2, height / 2)

func cell_to_world(cell: Vector2i) -> Vector3:
	return OwActor.cell_pos(cell)

# ---------------------------------------------------------------- NPCs
func npc_at(cell: Vector2i) -> Dictionary:
	var a := actor_at(cell)
	if a:
		return a.obj
	if actors.is_empty():
		# not in the scene tree (tests): answer from the static placements
		for o in map_data.get("objs", []):
			if int(o.get("x", -99)) == cell.x and int(o.get("y", -99)) == cell.y and _obj_shown(o):
				return o
	return {}

func actor_at(cell: Vector2i, except: OwActor = null) -> OwActor:
	for a in actors:
		var act: OwActor = a
		if act == except or not act.visible:
			continue
		if act.cell == cell:
			return act
	return null

func _obj_shown(o: Dictionary) -> bool:
	var story := get_node_or_null("/root/Story") if is_inside_tree() else null
	if story and story.has_method("is_shown"):
		return bool(story.is_shown(String(o.get("id", "")), map_name))
	return bool(o.get("shown", true))

var label_override := {}   # Vector2i -> label (scripts)

func set_cell_override(cell: Vector2i, label: String, passable: bool) -> void:
	pass_override[cell] = passable
	if label != "":
		label_override[cell] = label
		_rebuild_objects()
		_cell_fx(cell, label)

func clear_cell_override(cell: Vector2i) -> void:
	pass_override.erase(cell)
	if label_override.has(cell):
		label_override.erase(cell)
		_rebuild_objects()
		_cell_fx(cell, "")

## Animated effects for script-set labels (electric barriers, teleport pads).
func _cell_fx(cell: Vector2i, label: String) -> void:
	if not is_inside_tree():
		return
	var n := "CellFx_%d_%d" % [cell.x, cell.y]
	var old := get_node_or_null(n)
	if old:
		old.queue_free()
	if label == "barrier" or label == "teleport":
		var fx := TileKit._fx_multimesh(n, TileKit._flower_mesh(), 1 if label == "barrier" else 2,
			[[Vector3(cell.x, 0.002, cell.y), float(cell.x * 7 + cell.y)]])
		fx.name = n
		add_child(fx)

func _rebuild_objects() -> void:
	if bake.is_empty() or obj_mat == null or not is_inside_tree():
		return
	var old := get_node_or_null("Objects")
	if old:
		old.free()
	var wb := WorldBuilder.new(bake)
	var hide: Array = []
	for c in label_override.keys():
		hide.append(c)
	var node := wb.build_objects(obj_mat, hide)
	add_child(node)

func spawn_actor(o: Dictionary) -> OwActor:
	var a := OwActor.new()
	a.name = "NPC_%s" % String(o.get("id", str(actors.size())))
	var npcs := get_node_or_null("NPCs")
	if npcs == null:
		npcs = Node3D.new()
		npcs.name = "NPCs"
		add_child(npcs)
	npcs.add_child(a)
	a.obj = o
	var spr := String(GameData.sprite_override.get(String(o.get("id", "")), o.get("sprite", "youngster")))
	a.setup(spr, OwActor.CHAR_PX, o)
	var dir := "down"
	var od := String(o.get("dir", "NONE"))
	if ["UP", "DOWN", "LEFT", "RIGHT"].has(od):
		dir = od.to_lower()
	a.place(Vector2i(int(o.get("x", 0)), int(o.get("y", 0))), dir)
	a.home = a.cell
	a.idle_t = randf_range(0.0, 2.0)
	actors.append(a)
	return a

func remove_actor(a: OwActor) -> void:
	actors.erase(a)
	if is_instance_valid(a):
		a.queue_free()

func _spawn_npcs() -> void:
	for o in map_data.get("objs", []):
		if _obj_shown(o):
			spawn_actor(o)

# ---------------------------------------------------------------- visuals
func _build_visuals() -> void:
	for c in get_children():
		c.queue_free()
	actors.clear()
	if bake.is_empty():
		push_warning("[MapLoader] no bake for %s (run pipeline/scripts/bake_maps.js)" % map_name)
		_spawn_npcs()
		return
	var wb := WorldBuilder.new(bake)
	var ground_tex: Texture2D = load("res://assets/maps/%s_ground.png" % map_name)
	var atlas_tex: Texture2D = load("res://assets/maps/%s_atlas.png" % map_name)
	world_mat = wb.make_material(ground_tex, true)
	if bool(bake.get("water", false)):
		world_mat.set_shader_parameter("has_water", true)
		world_mat.set_shader_parameter("water_tex", load("res://assets/maps/%s_water.png" % map_name))
		world_mat.set_shader_parameter("noise_tex", load("res://assets/maps/noise_water.png"))
		world_mat.set_shader_parameter("world_px0", Vector2(float(bake.get("wx0", 0)), float(bake.get("wy0", 0))))
		world_mat.set_shader_parameter("water_pal", TileKit.palette_colors("water"))
	obj_mat = wb.make_material(atlas_tex, false)
	add_child(wb.build_ground(world_mat))
	add_child(wb.build_objects(obj_mat))
	var mx := int(bake.get("mx", 0))
	var my := int(bake.get("my", 0))
	var deco := TileKit.build_decor(bake, mx, my)
	add_child(deco)
	grass_node = deco.get_node_or_null("TallGrass")
	_spawn_npcs()

## ambient.js cloud shadows on/off for every world material of this map.
func set_clouds(on: bool) -> void:
	var big: Texture2D = load("res://assets/maps/noise_big.png") if on else null
	var mats: Array = [world_mat, obj_mat]
	mats.append_array(TileKit._materials)
	for m in mats:
		if m == null:
			continue
		var mat: ShaderMaterial = m
		mat.set_shader_parameter("clouds", on)
		if big:
			mat.set_shader_parameter("big_tex", big)

## Shader-level day/night: upstream's multiplicative grade + light pools (see LightingRig).
func apply_grade(grade: Color, light_amt: float, light_tex: Texture2D, glow_tex: Texture2D) -> void:
	for m in [world_mat, obj_mat]:
		if m == null:
			continue
		var mat: ShaderMaterial = m
		mat.set_shader_parameter("grade", Vector3(grade.r, grade.g, grade.b))
		mat.set_shader_parameter("light_amt", light_amt)
		if light_tex:
			mat.set_shader_parameter("light_tex", light_tex)
		if glow_tex:
			mat.set_shader_parameter("glow_tex", glow_tex)
	TileKit.apply_grade(grade, light_amt, light_tex, glow_tex)
