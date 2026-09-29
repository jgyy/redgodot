class_name EnvTests
extends RefCounted
## Unit tests for the environment prop system (FurnitureKit / DressingKit / PropKit) - see TestSuite.run_all.

const NEW_SETS := ["furniture", "nature", "town", "building"]

static func run(t: TestSuite) -> void:
	_test_assets(t)
	_test_furniture(t)
	_test_dressing(t)
	_test_real_maps(t)

static func _load_manifest() -> Dictionary:
	var f := FileAccess.open("res://assets/models/world/manifest.json", FileAccess.READ)
	if f == null:
		return {}
	var d: Variant = JSON.parse_string(f.get_as_text())
	return d if typeof(d) == TYPE_DICTIONARY else {}

static func _test_assets(t: TestSuite) -> void:
	var man := _load_manifest()
	var fresh := 0
	var big := []
	for k in man.keys():
		var e: Dictionary = man[k]
		if NEW_SETS.has(String(e.get("set", ""))):
			fresh += 1
			if int(e.get("bytes", 0)) > 300 * 1024:
				big.append(k)
	t.check(fresh >= 100, "world manifest lists >= 100 new environment glbs (got %d)" % fresh)
	t.check(big.is_empty(), "every new glb is under 300KB (%s)" % [big])
	var missing := []
	for k in man.keys():
		if not ResourceLoader.exists("res://assets/models/world/%s.glb" % k):
			missing.append(k)
	t.check(missing.is_empty(), "every manifest glb exists (missing %s)" % [missing])
	# modular sets: the 16 neighbour masks each resolve to a mesh
	for set_name in ["table_set", "desk_set", "counter_center_set", "counter_mart_set"]:
		var ok := true
		for m in range(16):
			if PropKit.mesh("%s/m%d" % [set_name, m]) == null:
				ok = false
		t.check(ok, "%s has meshes m0..m15" % set_name)
	t.check(PropKit.mesh("bench_set/m3") != null, "bench_set has m3")
	# the hero props are fitted to their cell: footprint <= 1 cell wide, sane height
	for p in ["pc", "tv_crt", "bookshelf", "vending_machine", "chair", "stove", "fridge"]:
		var m := PropKit.mesh(p)
		t.check(m != null, "%s loads" % p)
		if m:
			var bb := m.get_aabb()
			t.check(bb.size.x <= 1.06 and bb.size.z <= 1.06 and bb.size.y > 0.3 and bb.size.y < 1.6, "%s fits its cell (%s)" % [p, bb.size])
	var heal := PropKit.mesh("heal_machine")
	t.check(heal != null and heal.get_aabb().size.x > 1.6 and heal.get_aabb().size.x <= 2.1, "heal_machine spans 2 cells")
	# every model has the vertex-colour attribute the prop shader multiplies (Godot forgets it on a first primitive)
	var pcm := PropKit.mesh("pc")
	var arr := pcm.surface_get_arrays(0)
	t.check((arr[Mesh.ARRAY_COLOR] as PackedColorArray).size() == (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size(), "pc keeps vertex colours")

## records what a placement pass would draw
class Rec:
	var items: Array = []
	func add(prop: String, pos: Vector3, yaw: float, cell: Vector2i, scale: float = 1.0) -> void:
		items.append([prop, pos, yaw, cell, scale])
	func names() -> Array:
		var out := []
		for i in items:
			out.append(i[0])
		return out
	func find(prop: String) -> Array:
		for i in items:
			if i[0] == prop:
				return i
		return []

static func _bake(legend: Array, rows: Array, mx: int = 0, my: int = 0, extra: Dictionary = {}) -> Dictionary:
	var ch := rows.size()
	var cw: int = String(rows[0]).length()
	var labels := []
	for r in rows:
		for c in String(r):
			labels.append(int(c))
	var b := {"cw": cw, "ch": ch, "mx": mx, "my": my, "w": cw - 2 * mx, "h": ch - 2 * my, "legend": legend, "labels": labels, "kind": "interior", "map": "TestRoom"}
	b.merge(extra)
	return b

static func _test_furniture(t: TestSuite) -> void:
	# floor(0) pc(1) table(2) chair(3) counter(4) heal_machine(5) wall(6)
	var legend := ["floor", "pc", "table", "chair", "counter", "heal_machine", "wall"]
	var rows := ["6666666",
		"0550000",
		"0550120",
		"0000330",
		"0004440",
		"0000000"]
	var bake := _bake(legend, rows)
	var rec := Rec.new()
	FurnitureKit.place(bake, {}, {"map": "ViridianMart", "objs": [{"sprite": "clerk", "x": 6, "y": 4, "dir": "LEFT"}]}, Callable(rec, "add"))
	var names := rec.names()
	t.check(names.has("heal_machine"), "a 2 x 2 group of heal_machine cells becomes one healing machine")
	t.check(not names.has("heal_cabinet"), "no stray heal cabinets for a full 2 x 2 group")
	t.check(names.has("pc"), "a pc cell places the PC model")
	t.check(names.has("table_set/m2") or names.has("table_set/m0"), "a lone table cell picks a mask piece (%s)" % [names])
	var chair := []
	for i in rec.items:
		if i[0] == "chair" and i[3] == Vector2i(5, 3):
			chair = i
	t.check(not chair.is_empty(), "chairs are placed")
	if not chair.is_empty():
		t.check(is_equal_approx(float(chair[2]), PI), "a chair below a table turns its back to the camera (yaw %f)" % float(chair[2]))
	# counters: the three-cell run has an end piece each side and a middle piece
	var counter_pieces := []
	for n in names:
		if String(n).begins_with("counter_mart_set/"):
			counter_pieces.append(n)
	t.check(counter_pieces.size() == 3 and counter_pieces.has("counter_mart_set/m2") and counter_pieces.has("counter_mart_set/m3") and counter_pieces.has("counter_mart_set/m1"),
		"a 3-cell counter run uses end / middle / end pieces (%s)" % [counter_pieces])
	t.check(names.has("cash_register"), "the clerk's counter gets a cash register")
	# script-changed cells win over the baked label
	var rec2 := Rec.new()
	FurnitureKit.place(bake, {Vector2i(1, 1): "floor"}, {"map": "X"}, Callable(rec2, "add"))
	t.check(rec2.names().count("heal_machine") == 0 and rec2.names().count("heal_cabinet") == 3, "a label override breaks up the healing machine group")
	# replaced() only claims a sprite block when the model exists
	t.check(FurnitureKit.replaced("pc") and FurnitureKit.replaced("bookshelf") and not FurnitureKit.replaced("grass"), "FurnitureKit.replaced follows the model list")
	t.check(PropKit.replaces("pc") and PropKit.replaces("sign") and not PropKit.replaces("wall"), "PropKit.replaces covers furniture and the older props")

static func _test_dressing(t: TestSuite) -> void:
	var sp := DressingKit.tree_species("CinnabarIsland", 3, 4)
	t.check(sp == DressingKit.tree_species("CinnabarIsland", 3, 4), "tree species are deterministic per cell")
	var palms := 0
	var total := 400
	for i in range(total):
		if DressingKit.tree_species("CinnabarIsland", i % 20, i / 20) == "tree_palm":
			palms += 1
	t.check(palms > total * 0.2 and palms < total * 0.5, "Cinnabar's trees are about a third palms (%d / %d)" % [palms, total])
	var pines := 0
	for i in range(total):
		var s := DressingKit.tree_species("ViridianForest", i % 20, i / 20)
		if s == "tree_pine":
			pines += 1
		if s != "" and i < 40:
			t.check(PropKit.mesh(s) != null, "species %s has a mesh" % s)
	t.check(pines > total * 0.08 and pines < total * 0.3, "Viridian Forest gets pines (%d / %d)" % [pines, total])
	# a synthetic outdoor map: reeds on the bank, nothing on walkable cells that is tall
	var legend := ["grass", "water", "sand", "cave_high"]
	var rows := ["0000000000", "0011111100", "0011111100", "0011111100", "0000000000"]
	var bake := _bake(legend, rows, 0, 0, {"kind": "outdoor", "map": "TestPond"})
	var rec := Rec.new()
	var ctx := {"map": "TestPond", "passable": func(c: Vector2i) -> bool: return (c.x < 2 or c.x > 7 or c.y == 0 or c.y == 4), "objs": [], "warps": [], "signs": []}
	var n := DressingKit.place(bake, {}, ctx, Callable(rec, "add"))
	t.check(n == rec.items.size(), "place() reports what it placed")
	for i in rec.items:
		var c: Vector2i = i[3]
		var bad := ["tree_oak", "lighthouse", "windmill"].has(i[0])
		t.check(not bad, "no landmark props from the generic rules")
	# hand-placed landmarks need water when they say so
	var rec2 := Rec.new()
	DressingKit.place(_bake(["grass"], ["0000000", "0000000", "0000000"], 0, 0, {"kind": "outdoor", "map": "CinnabarIsland"}), {}, {"map": "CinnabarIsland", "passable": func(c: Vector2i) -> bool: return true}, Callable(rec2, "add"))
	t.check(not rec2.names().has("lighthouse"), "a lighthouse is not placed on grass")
	t.check(DressingKit.tree_clearings("PalletTown").size() >= 1, "Pallet Town's windmill clears trees")

static func _test_real_maps(t: TestSuite) -> void:
	# the real Pokemon Center bake: PCs, machines, counters, benches and plants all resolve to models
	var bake := WorldBuilder.load_bake("ViridianPokecenter")
	t.check(not bake.is_empty(), "ViridianPokecenter bake loads")
	if bake.is_empty():
		return
	var rec := Rec.new()
	FurnitureKit.place(bake, {}, {"map": "ViridianPokecenter", "objs": []}, Callable(rec, "add"))
	var names := rec.names()
	t.check(names.count("heal_machine") == 2, "the Pokemon Center has two healing machines (got %d)" % names.count("heal_machine"))
	t.check(names.has("pc"), "the Pokemon Center has its PC")
	var bench_pieces := 0
	for n in names:
		if String(n).begins_with("bench_set/"):
			bench_pieces += 1
	t.check(bench_pieces == 2, "two bench cells on the left wall (%d)" % bench_pieces)
	var b := rec.find("bench_set/m0")
	var b1 := rec.find("bench_set/m1")
	var b2 := rec.find("bench_set/m2")
	var any_bench := b if not b.is_empty() else (b1 if not b1.is_empty() else b2)
	t.check(not any_bench.is_empty() and is_equal_approx(float(any_bench[2]), PI * 0.5), "the wall benches face into the room")
	var counters := 0
	for n in names:
		if String(n).begins_with("counter_center_set/"):
			counters += 1
	t.check(counters >= 10, "the Pokemon Center counter uses the white/pink pieces (%d)" % counters)
