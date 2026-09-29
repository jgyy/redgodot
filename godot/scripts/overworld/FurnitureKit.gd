class_name FurnitureKit
extends RefCounted
## Real 3D furniture, appliances and machines for the objects upstream draws as flat sprite boxes (PCs, TVs, the
## Poke Ball healing machine, bookshelves, counters, tables, chairs, benches, vending / slot machines, stoves ...).
## Models: pipeline/blender/env_furn.py -> assets/models/world/*.glb (ramp-lit vertex colours like PropKit's props).
##
## Placement is read from the bake's label grid, one prop per cell (the cells an object covers are exactly the cells its
## sprite covers), with neighbours deciding the variant: modular sets (tables, counters, benches) pick the piece whose
## mask matches the adjacent cells, chairs face the table beside them, benches face away from the wall, the 2 x 2
## healing machine is one model, the till stands where the clerk faces.  Low objects are anchored to the front edge of
## their cell like the sprite's box was, tall ones (bookshelves, mart shelves) stand on the bottom cell of their column.
## Models are drawn as chunked MultiMeshes by PropKit (its `add` callable); WorldBuilder skips the matching sprite
## blocks (PropKit.replaces) so nothing is drawn twice.

## label -> [prop, yaw mode]   (yaw modes: "" = faces the camera, "wall" = away from a side wall)
const CELL_PROPS := {
	"pc": "pc", "pc_claude": "pc_dark", "tv": "tv_crt", "tv_woc": "tv_game", "console": "game_console", "laptop": "laptop",
	"cabinet": "cabinet_wood", "display": "display_case", "vending": "vending_machine", "slots": "slot_machine",
	"stove": "stove", "sink": "sink", "trash": "trash_can", "fossil": "fossil_case",
}
const SET_LABELS := {"table": "table_set", "desk": "desk_set"}
## every label this kit draws (WorldBuilder skips those sprite blocks when the model exists)
const LABELS := ["pc", "pc_claude", "tv", "tv_woc", "console", "laptop", "cabinet", "display", "vending", "slots", "stove", "sink", "trash", "fossil",
	"table", "desk", "counter", "chair", "bench", "bookshelf", "shelf", "machine", "heal_machine", "truck", "teleport", "mat"]
const SOLID := ["wall", "void", "wall_deco", "wall_window", "wall_surf", "bookshelf", "shelf", "cave_wall", "ship_wall"]
const DIRS := {"UP": Vector2i(0, -1), "DOWN": Vector2i(0, 1), "LEFT": Vector2i(-1, 0), "RIGHT": Vector2i(1, 0)}

static func replaced(label: String) -> bool:
	if not LABELS.has(label):
		return false
	match label:
		"table": return PropKit.mesh("table_set/m0") != null
		"desk": return PropKit.mesh("desk_set/m0") != null
		"counter": return PropKit.mesh("counter_mart_set/m0") != null
		"bench": return PropKit.mesh("bench_set/m0") != null
		"machine": return PropKit.mesh("lab_machine") != null
		"shelf": return PropKit.mesh("mart_shelf") != null
		"teleport", "mat": return false   # ground art; the 3D pads / mats are added on top
	if CELL_PROPS.has(label):
		return PropKit.mesh(String(CELL_PROPS[label])) != null
	return PropKit.mesh(label) != null

## Height (sprite units) of the top surface of a piece of furniture, for things standing on it.
static func surface_height(label: String) -> float:
	match label:
		"table": return 0.5
		"desk": return 0.55
		"counter": return 0.6
		"cabinet": return 0.7
	return 0.0

static func machine_prop(map: String, c: Vector2i = Vector2i.ZERO) -> String:
	if map == "PowerPlant" or map == "VermilionDock":
		return "generator"
	if map.begins_with("Rocket"):
		return "rocket_console"
	if map.begins_with("Silph"):
		return "server_rack" if PropKit._h(c.x, c.y, 610) < 0.35 else "server_unit"
	return "lab_machine"

## `ctx`: {map: String, objs: Array}; `add`: Callable(prop, pos, yaw, cell, scale) from PropKit.build.
static func place(bake: Dictionary, overrides: Dictionary, ctx: Dictionary, add: Callable) -> void:
	var cw := int(bake.get("cw", 0))
	var ch := int(bake.get("ch", 0))
	var mx := int(bake.get("mx", 0))
	var my := int(bake.get("my", 0))
	var legend: Array = bake.get("legend", [])
	var labels: Array = bake.get("labels", [])
	if legend.is_empty() or labels.size() < cw * ch:
		return
	var map: String = String(ctx.get("map", bake.get("map", "")))
	var lab := {}      # every cell of the padded grid -> label (overrides applied)
	var mine := []     # cells whose label this kit draws
	for i in range(cw * ch):
		var c := Vector2i(i % cw - mx, i / cw - my)
		var l: String = String(legend[int(labels[i])])
		if overrides.has(c):
			l = String(overrides[c])
		lab[c] = l
		if LABELS.has(l):
			mine.append(c)
	if mine.is_empty():
		return
	var K := WorldData.K
	var heal_done := {}
	for c in mine:
		var l: String = lab[c]
		var centre := Vector3(c.x + 0.5, 0.0, c.y + 0.5)
		match l:
			"heal_machine":
				if heal_done.has(c):
					continue
				var grp := _flood(lab, c, "heal_machine")
				for g in grp:
					heal_done[g] = true
				var bb := _bbox(grp)
				if bb.size == Vector2i(2, 2) and grp.size() == 4 and PropKit.mesh("heal_machine") != null:
					# one machine against the wall, its front on the group's lower edge
					var zf: float = float(bb.position.y + 2) - 0.06
					add.call("heal_machine", Vector3(bb.position.x + 1.0, 0.0, zf - _front("heal_machine")), 0.0, c, 1.0)
				else:
					for g in grp:
						_front_anchor(add, "heal_cabinet", g, 0.0)
			"table", "desk":
				var pc := String(SET_LABELS[l])
				add.call("%s/m%d" % [pc, _mask(lab, c, [l])], centre, 0.0, c, 1.0)
				_table_item(map, c, l, ctx, add)
			"counter":
				var set_name := "counter_center_set" if map.contains("Pokecenter") else "counter_mart_set"
				add.call("%s/m%d" % [set_name, _mask(lab, c, ["counter"])], centre, 0.0, c, 1.0)
			"bench":
				var yaw := 0.0
				var left_solid: bool = SOLID.has(String(lab.get(c + Vector2i(-1, 0), "void")))
				var right_solid: bool = SOLID.has(String(lab.get(c + Vector2i(1, 0), "void")))
				if left_solid and not right_solid:
					yaw = PI * 0.5
				elif right_solid and not left_solid:
					yaw = -PI * 0.5
				# neighbours along the bench's own axis (local +X after the yaw is world -Z for +90, +Z for -90, -X for 180)
				var along := Vector2i(1, 0)
				if is_equal_approx(yaw, PI * 0.5):
					along = Vector2i(0, -1)
				elif is_equal_approx(yaw, -PI * 0.5):
					along = Vector2i(0, 1)
				var m := 0
				if String(lab.get(c - along, "")) == "bench":
					m |= 1
				if String(lab.get(c + along, "")) == "bench":
					m |= 2
				add.call("bench_set/m%d" % m, centre, yaw, c, 1.0)
			"chair":
				var yaw2 := 0.0
				for d in [Vector2i(0, -1), Vector2i(-1, 0), Vector2i(1, 0), Vector2i(0, 1)]:
					var nl: String = String(lab.get(c + d, ""))
					if nl == "table" or nl == "desk" or nl == "counter":
						yaw2 = {Vector2i(0, -1): PI, Vector2i(-1, 0): -PI * 0.5, Vector2i(1, 0): PI * 0.5, Vector2i(0, 1): 0.0}[d]
						break
				add.call("chair", centre, yaw2, c, 1.0)
			"bookshelf", "shelf":
				# stands on the bottom cell of its column; two rows of label = full height, one row = the low case
				if String(lab.get(c + Vector2i(0, 1), "")) == l:
					continue
				var tall: bool = String(lab.get(c + Vector2i(0, -1), "")) == l
				var pr := "bookshelf" if tall else "bookshelf_low"
				if l == "shelf":
					pr = "mart_shelf"
				_front_anchor(add, pr, c, 0.0)
			"machine":
				_front_anchor(add, machine_prop(map, c), c, 0.0)
			"truck":
				pass
			"teleport":
				add.call("teleporter_pad", Vector3(c.x + 0.5, 0.0, c.y + 0.5), 0.0, c, 1.0)
			"mat":
				# door mats only (one or two cells); a big field of 'mat' cells is a carpet, which stays ground art
				if _flood(lab, c, "mat").size() <= 2:
					add.call("doormat", Vector3(c.x + 0.5, 0.0, c.y + 0.5), 0.0, c, 1.0)
			_:
				if CELL_PROPS.has(l):
					_front_anchor(add, String(CELL_PROPS[l]), c, 0.0)
	# ---- the till stands on the counter cell in front of each clerk
	for o in ctx.get("objs", []):
		var spr := String(o.get("sprite", ""))
		if spr != "clerk":
			continue
		var oc := Vector2i(int(o.get("x", 0)), int(o.get("y", 0)))
		var dn := String(o.get("dir", "DOWN"))
		if not DIRS.has(dn):
			continue
		var tc: Vector2i = oc + DIRS[dn]
		if String(lab.get(tc, "")) != "counter" or PropKit.mesh("cash_register") == null:
			continue
		var yawr: float = {"DOWN": 0.0, "UP": PI, "RIGHT": PI * 0.5, "LEFT": -PI * 0.5}[dn]
		add.call("cash_register", Vector3(tc.x + 0.5, 0.6 * K, tc.y + 0.5), yawr, tc, 1.0)

## Small things on a table top: plates and flowers at home, papers in offices and labs, pots and boards in the galley.
## Never on a cell with a person / item object on it (the starter Poke Balls, a trainer).
static func _table_item(map: String, c: Vector2i, l: String, ctx: Dictionary, add: Callable) -> void:
	for o in ctx.get("objs", []):
		if Vector2i(int(o.get("x", 0)), int(o.get("y", 0))) == c:
			return
	var r := PropKit._h(c.x, c.y, 600)
	var list: Array
	var p := 0.3
	if map.contains("Kitchen"):
		list = ["cutting_board", "stew_pot", "fruit_bowl", "tableware"]
		p = 0.38
	elif map.begins_with("Silph") or map.contains("Lab") or map.contains("Museum") or map.contains("Captain") or map.contains("Hideout") or l == "desk":
		list = ["paper_pile", "book_stack", "paper_pile"]
	else:
		list = ["tableware", "flower_vase", "fruit_bowl", "book_stack"]
	if r > p:
		return
	var prop: String = list[int(PropKit._h(c.x, c.y, 601) * list.size()) % list.size()]
	if PropKit.mesh(prop) == null:
		return
	var top := surface_height(l) * WorldData.K
	add.call(prop, Vector3(c.x + 0.3 + PropKit._h(c.x, c.y, 602) * 0.4, top, c.y + 0.3 + PropKit._h(c.x, c.y, 603) * 0.4), PropKit._h(c.x, c.y, 604) * TAU, c, 1.5)

## Front edge (Godot +Z extent) of a prop's mesh.
static func _front(prop: String) -> float:
	var m := PropKit.mesh(prop)
	if m == null:
		return 0.0
	var bb := m.get_aabb()
	return bb.position.z + bb.size.z

## Prop centred on the cell's x, its front on the cell's lower edge (how the sprite's box sat in the cell).
static func _front_anchor(add: Callable, prop: String, c: Vector2i, yaw: float) -> void:
	add.call(prop, Vector3(c.x + 0.5, 0.0, float(c.y + 1) - 0.05 - _front(prop)), yaw, c, 1.0)

## bit 0 = same label to the left, 1 = right, 2 = behind (up), 3 = in front (down)
static func _mask(lab: Dictionary, c: Vector2i, same: Array) -> int:
	var m := 0
	if same.has(String(lab.get(c + Vector2i(-1, 0), ""))):
		m |= 1
	if same.has(String(lab.get(c + Vector2i(1, 0), ""))):
		m |= 2
	if same.has(String(lab.get(c + Vector2i(0, -1), ""))):
		m |= 4
	if same.has(String(lab.get(c + Vector2i(0, 1), ""))):
		m |= 8
	return m

static func _flood(lab: Dictionary, start: Vector2i, l: String) -> Array:
	var seen := {start: true}
	var stack := [start]
	var out := []
	while not stack.is_empty():
		var c: Vector2i = stack.pop_back()
		out.append(c)
		for d in DIRS.values():
			var n: Vector2i = c + d
			if not seen.has(n) and String(lab.get(n, "")) == l:
				seen[n] = true
				stack.append(n)
	return out

static func _bbox(cells: Array) -> Rect2i:
	var x0 := 1 << 20
	var y0 := 1 << 20
	var x1 := -(1 << 20)
	var y1 := -(1 << 20)
	for c in cells:
		x0 = mini(x0, c.x)
		y0 = mini(y0, c.y)
		x1 = maxi(x1, c.x)
		y1 = maxi(y1, c.y)
	return Rect2i(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
