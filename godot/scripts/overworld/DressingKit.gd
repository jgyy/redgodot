class_name DressingKit
extends RefCounted
## Scenery that upstream's tile art has no object for, added as real 3D models (pipeline/blender/env_nature.py,
## env_town.py) so maps read as places rather than flat tile sheets:
##  - tree species: some of the baked trees are swapped for pines, oaks, birches, cherries, palms, autumn and dead trees
##    by region (TileKit asks `tree_species`), same 2 x 2 footprint and pivot
##  - shores and water: reeds along the banks, lily pads in still water, buoys and rocks at sea, driftwood and shells on sand
##  - meadows: flower patches, stones, ferns and toadstools (walkable, low: like the flower tufts already there)
##  - caves: stalagmites, crystals, ice and rock piles on the *blocked* wall cells, never on the walkable floor
##  - towns: mailboxes, lamps, benches, hydrants and bins in dead-end nooks next to buildings and on bridges' rails
## Everything tall stands only where the cells behind it (north, away from the camera) are blocked too, so a prop never
## hides a cell the player can walk on; positions come from a hash of the cell, so a map always looks the same.

const SEA_MAPS := ["Route19", "Route20", "Route21", "VermilionCity", "CinnabarIsland", "VermilionDock", "Route23"]
const NOOK_LABELS := ["grass", "path_tufts", "pavement", "path", "path_t", "flowers", "sand"]

## tree species per region: [[prop, chance], ...] applied in order to the hash of the tree's cell
const SPECIES := {
	"PalletTown": [["tree_apple", 0.09], ["tree_oak", 0.08]], "Route1": [["tree_oak", 0.12], ["tree_apple", 0.05]],
	"ViridianCity": [["tree_oak", 0.14], ["tree_apple", 0.06]], "Route2": [["tree_oak", 0.14], ["tree_birch", 0.06]],
	"ViridianForest": [["tree_pine", 0.16], ["tree_oak", 0.09], ["tree_dead", 0.02]],
	"PewterCity": [["tree_pine", 0.16], ["tree_birch", 0.08]], "Route3": [["tree_pine", 0.16], ["tree_birch", 0.09]],
	"Route4": [["tree_pine", 0.2], ["tree_dead", 0.04]], "Route24": [["tree_birch", 0.1], ["tree_oak", 0.1]],
	"Route25": [["tree_birch", 0.1], ["tree_oak", 0.1]], "CeruleanCity": [["tree_cherry", 0.14], ["tree_birch", 0.08]],
	"Route5": [["tree_oak", 0.12], ["tree_cherry", 0.05]], "Route6": [["tree_oak", 0.12], ["tree_birch", 0.06]],
	"SaffronCity": [["tree_birch", 0.1], ["tree_oak", 0.08]], "Route7": [["tree_cherry", 0.08], ["tree_oak", 0.1]],
	"CeladonCity": [["tree_cherry", 0.2], ["tree_oak", 0.06]], "Route8": [["tree_autumn", 0.16], ["tree_oak", 0.06]],
	"Route9": [["tree_autumn", 0.14], ["tree_pine", 0.08]], "Route10": [["tree_autumn", 0.1], ["tree_dead", 0.08], ["tree_pine", 0.08]],
	"LavenderTown": [["tree_dead", 0.16], ["tree_pine", 0.16]], "Route11": [["tree_oak", 0.1], ["tree_palm", 0.06]],
	"Route12": [["tree_pine", 0.1], ["tree_oak", 0.08]], "Route13": [["tree_pine", 0.1], ["tree_dead", 0.03], ["tree_oak", 0.06]],
	"Route14": [["tree_pine", 0.1], ["tree_oak", 0.08]], "Route15": [["tree_oak", 0.1], ["tree_birch", 0.06]],
	"Route16": [["tree_oak", 0.1], ["tree_birch", 0.06]], "Route17": [["tree_oak", 0.1], ["tree_dead", 0.02]],
	"Route18": [["tree_palm", 0.14], ["tree_oak", 0.08]], "FuchsiaCity": [["tree_palm", 0.22], ["tree_oak", 0.07]],
	"VermilionCity": [["tree_palm", 0.28], ["tree_oak", 0.06]], "CinnabarIsland": [["tree_palm", 0.34]],
	"Route19": [["tree_palm", 0.3]], "Route20": [["tree_palm", 0.3]], "Route21": [["tree_palm", 0.12], ["tree_oak", 0.1]],
	"Route22": [["tree_oak", 0.1], ["tree_pine", 0.06]], "Route23": [["tree_pine", 0.12], ["tree_dead", 0.03]],
	"SafariZoneCenter": [["tree_palm", 0.1], ["tree_oak", 0.12]], "SafariZoneEast": [["tree_oak", 0.14], ["tree_apple", 0.05]],
	"SafariZoneNorth": [["tree_oak", 0.14], ["tree_pine", 0.08]], "SafariZoneWest": [["tree_oak", 0.14], ["tree_palm", 0.08]],
}

## Hand-placed set pieces per map: [prop, x, y, yaw, scale, need, clear]  (cell coords, may lie outside the playable area;
## `need` = "water" (the cell and its neighbours must be water) or "any"; `clear` = radius in cells of baked trees removed).
const LANDMARKS := {
	"CinnabarIsland": [["lighthouse", 3.5, 15.5, 0.0, 0.75, "water", 0], ["sailboat", -7.5, 12.5, 0.5, 1.0, "water", 0], ["rowboat", 22.5, 9.5, 0.3, 1.0, "water", 0],
		["buoy", -2.5, 12.5, 0.0, 1.0, "water", 0], ["buoy", 23.5, 3.5, 0.0, 1.0, "water", 0], ["anchor", 3.5, 15.5, 0.6, 0.9, "water", 0]],
	"VermilionCity": [["sailboat", -6.5, 16.5, 0.4, 1.0, "water", 0], ["rowboat", 13.5, 26.5, 1.1, 1.0, "water", 0], ["sailboat", 20.5, 33.5, -0.3, 1.0, "water", 0],
		["buoy", 6.5, 30.5, 0.0, 1.0, "water", 0], ["buoy", 40.5, 20.5, 0.0, 1.0, "water", 0]],
	"VermilionDock": [["buoy", 6.5, 8.5, 0.0, 1.0, "water", 0], ["rowboat", 20.5, 8.5, 0.2, 1.0, "water", 0]],
	"Route19": [["sailboat", 4.5, 18.5, 0.2, 1.0, "water", 0]], "Route20": [["sailboat", 8.5, 8.5, -0.4, 1.0, "water", 0]],
	"PalletTown": [["windmill", -5.0, 10.0, 0.0, 1.0, "any", 3], ["hay_bale", -2.0, 12.0, 0.4, 1.0, "any", 0], ["scarecrow", -3.0, 13.5, 0.0, 1.0, "any", 1]],
	"Route1": [["scarecrow", -3.0, 20.0, 0.3, 1.0, "any", 1]],
	"CeladonCity": [["market_stall", 12.0, 22.7, 0.0, 1.0, "any", 0], ["market_stall", 30.0, 22.7, 0.0, 1.0, "any", 0], ["water_tower", -3.0, 3.0, 0.0, 1.0, "any", 2], ["billboard", 52.5, 14.5, 0.0, 1.0, "any", 2]],
	"Route10": [["power_pylon", -3.0, 10.0, 0.0, 1.0, "any", 2], ["power_pylon", -3.0, 24.0, 0.0, 1.0, "any", 2], ["power_pylon", 23.0, 17.0, 0.0, 1.0, "any", 2]],
	"LavenderTown": [["telephone_pole", -2.0, 5.5, 0.0, 1.0, "any", 1], ["telephone_pole", -2.0, 12.5, 0.0, 1.0, "any", 1]],
}
## Doors that get a walk-through frame in front of them: map -> [[door x, door y, prop]]
const WARP_ARCHES := {
	"FuchsiaCity": [[18.5, 4.5, "safari_gate"]], "IndigoPlateau": [[10.0, 6.5, "stone_arch"]],
	"Route23": [[4.5, 32.5, "stone_arch"], [14.5, 32.5, "stone_arch"]],
}

## Landmarks of a map whose baked trees must make room (TileKit skips trees within `clear` cells): [[x, y, clear]]
static func tree_clearings(map: String) -> Array:
	var out := []
	for l in LANDMARKS.get(map, []):
		if int(l[6]) > 0:
			out.append([float(l[1]), float(l[2]), float(l[6])])
	return out

static func _h(x: int, y: int, s: int) -> float:
	return PropKit._h(x, y, s)

static func tree_species(map: String, cx: int, cy: int) -> String:
	var rules: Array = SPECIES.get(map, [["tree_oak", 0.06]])
	var r := _h(cx, cy, 401)
	var acc := 0.0
	for e in rules:
		acc += float(e[1])
		if r < acc and PropKit.mesh(String(e[0])) != null:
			if e[0] == "tree_pine" and _h(cx, cy, 402) < 0.4:
				return "tree_pine_slim"
			return String(e[0])
	return ""

static func _noise(x: float, y: float, s: int) -> float:
	var x0 := floori(x)
	var y0 := floori(y)
	var fx := x - x0
	var fy := y - y0
	fx = fx * fx * (3.0 - 2.0 * fx)
	fy = fy * fy * (3.0 - 2.0 * fy)
	var a := _h(x0, y0, s)
	var b := _h(x0 + 1, y0, s)
	var c := _h(x0, y0 + 1, s)
	var d := _h(x0 + 1, y0 + 1, s)
	return lerpf(lerpf(a, b, fx), lerpf(c, d, fx), fy)

## `add`: PropKit's Callable(prop, pos, yaw, cell, scale).  Returns the number of props placed (for tests / stats).
static func place(bake: Dictionary, overrides: Dictionary, ctx: Dictionary, add: Callable) -> int:
	var cw := int(bake.get("cw", 0))
	var ch := int(bake.get("ch", 0))
	var mx := int(bake.get("mx", 0))
	var my := int(bake.get("my", 0))
	var w := int(bake.get("w", 0))
	var h := int(bake.get("h", 0))
	var legend: Array = bake.get("legend", [])
	var labels: Array = bake.get("labels", [])
	if legend.is_empty() or labels.size() < cw * ch or not ctx.has("passable"):
		return 0
	var map := String(ctx.get("map", bake.get("map", "")))
	var kind := String(bake.get("kind", ""))
	var is_cave := legend.has("cave_floor") or legend.has("cave_wall")
	var is_ice := map.begins_with("Seafoam")
	var pass_fn: Callable = ctx["passable"]
	var lab := {}
	for i in range(cw * ch):
		var c := Vector2i(i % cw - mx, i / cw - my)
		var l: String = String(legend[int(labels[i])])
		lab[c] = String(overrides[c]) if overrides.has(c) else l
	var pass_cache := {}
	var can_walk := func(c: Vector2i) -> bool:
		if not pass_cache.has(c):
			pass_cache[c] = (c.x >= 0 and c.y >= 0 and c.x < w and c.y < h) and bool(pass_fn.call(c))
		return pass_cache[c]
	var busy := {}    # warps / people / signs
	for wp in ctx.get("warps", []):
		busy[Vector2i(int(wp.get("x", 0)), int(wp.get("y", 0)))] = true
	for o in ctx.get("objs", []):
		busy[Vector2i(int(o.get("x", 0)), int(o.get("y", 0)))] = true
	for sg in ctx.get("signs", []):
		busy[Vector2i(int(sg.get("x", 0)), int(sg.get("y", 0)))] = true
	var north_blocked := func(c: Vector2i, rows: int) -> bool:
		for k in range(1, rows + 1):
			if bool(can_walk.call(c + Vector2i(0, -k))):
				return false
		return true
	var sea := SEA_MAPS.has(map)
	var placed := 0
	var lo := Vector2i(-6, -6)
	var hi := Vector2i(w + 6, h + 6)
	for y in range(lo.y, hi.y):
		for x in range(lo.x, hi.x):
			var c := Vector2i(x, y)
			if not lab.has(c) or busy.has(c):
				continue
			var l: String = String(lab[c])
			var r := _h(x, y, 500)
			var jx := 0.2 + _h(x, y, 501) * 0.6
			var jz := 0.35 + _h(x, y, 502) * 0.5
			var yaw := _h(x, y, 503) * TAU
			var sc := 0.85 + _h(x, y, 504) * 0.3
			var inb := x >= 0 and y >= 0 and x < w and y < h
			var pos := Vector3(x + jx, 0.0, y + jz)
			if is_cave:
				if l == "cave_high" or l == "cave_wall":
					if bool(can_walk.call(c)) or not bool(north_blocked.call(c, 2)):
						continue
					if not inb:
						continue
					if is_ice:
						if r < 0.05:
							placed += _one(add, "ice_spike", pos, yaw, c, sc * 0.8)
						elif r < 0.09:
							placed += _one(add, "ice_block", pos, yaw, c, sc * 0.8)
					elif r < 0.06:
						placed += _one(add, "stalagmite_a" if r < 0.03 else "stalagmite_b", pos, yaw, c, sc * 0.72)
					elif r < 0.07:
						placed += _one(add, "boulder_large", pos, yaw, c, sc * 0.8)
					elif r < 0.075:
						placed += _one(add, "rock_pile" if r < 0.0725 else "cairn", pos, yaw, c, sc)
					elif r < 0.09 and (map.begins_with("MtMoon") or map.begins_with("CeruleanCave") or map.begins_with("VictoryRoad")):
						var cry := "crystal_blue" if map.begins_with("MtMoon") else ("crystal_purple" if map.begins_with("CeruleanCave") else "crystal_green")
						placed += _one(add, cry, pos, yaw, c, sc * 0.75)
				elif l == "water" and inb and r < 0.09 and not bool(can_walk.call(c)):
					var shore := false
					for d in [Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0)]:
						if String(lab.get(c + d, "water")) != "water":
							shore = true
					if shore:
						placed += _one(add, "coral" if r < 0.045 else "seaweed", Vector3(x + jx, 0.0, y + jz), yaw, c, sc)
				elif l == "cave_floor" and bool(can_walk.call(c)) and inb and r < 0.014:
					placed += _one(add, "rock_small_a" if r < 0.007 else "rock_small_b", pos, yaw, c, sc)
				continue
			if kind == "interior":
				continue
			match l:
				"water":
					var land_n := 0
					var dirs := [Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0)]
					for d in dirs:
						var nl: String = String(lab.get(c + d, "water"))
						if nl != "water" and nl != "void" and nl != "bridge":
							land_n += 1
					if land_n > 0 and not sea and r < 0.2:
						placed += _one(add, "tall_reeds", Vector3(x + jx, 0.0, y + jz), yaw, c, sc)
					elif land_n == 0 and not sea and _noise(x * 0.42, y * 0.42, 510) > 0.68 and r < 0.35:
						placed += _one(add, "lily_pads", Vector3(x + jx, 0.006, y + jz), yaw, c, sc)
					elif land_n == 0 and r > 0.986 and inb:
						placed += _one(add, "buoy" if sea and r > 0.994 else ("rock_mossy" if r > 0.99 else "rock_small_a"), Vector3(x + 0.5, 0.0, y + 0.55), yaw, c, sc)
				"sand":
					if r < 0.022 and bool(can_walk.call(c)):
						var sand_prop := "driftwood" if r < 0.011 else "seashell"
						if map == "CinnabarIsland" and r < 0.011:
							sand_prop = "lava_rock"
						elif map.begins_with("Safari") and r < 0.011:
							sand_prop = "cactus"
						placed += _one(add, sand_prop, pos, yaw, c, sc)
				"grass", "flowers":
					if not inb or not bool(can_walk.call(c)):
						continue
					if l == "grass" and r < 0.02:
						placed += _one(add, ["flower_patch_a", "flower_patch_b", "flower_patch_c"][int(_h(x, y, 505) * 3.0) % 3], pos, yaw, c, sc)
					elif l == "grass" and r < 0.03:
						placed += _one(add, "rock_small_b", pos, yaw, c, sc)
					elif map == "ViridianForest" or map.begins_with("Safari"):
						if r < 0.045:
							placed += _one(add, "mushrooms" if r < 0.036 else "fern", pos, yaw, c, sc)
	if kind == "interior" and not is_cave:
		placed += _interior(map, lab, can_walk, busy, w, h, add)
	placed += _landmarks(map, lab, add)
	if map.ends_with("City") or map.ends_with("Town"):
		placed += _pond_fountain(lab, w, h, add)
	placed += _nooks(lab, can_walk, busy, ctx, w, h, add)
	placed += _bridges(lab, w, h, add)
	placed += _buildings(bake, add)
	return placed

const WALLS := ["wall", "void", "wall_deco", "wall_window", "bookshelf", "shelf", "ship_wall", "cave_wall"]

## Rooms of houses, labs and the school: standing lamps, armchairs, wardrobes, fridges, globes ... in the corners
## (a walkable cell with a wall behind it and a wall beside it is a dead end, so nothing is blocked), clocks and pictures
## on the back wall, the school blackboard.
static func _interior(map: String, lab: Dictionary, can_walk: Callable, busy: Dictionary, w: int, h: int, add: Callable) -> int:
	var theme := ""
	if map.contains("SchoolHouse"):
		theme = "school"
	elif map.begins_with("PokemonTower"):
		theme = "tower"
	elif map.contains("Lab") or map.contains("Museum"):
		theme = "lab"
	elif map.contains("House") or map.contains("Daycare") or map.contains("FanClub") or map.contains("Dojo"):
		theme = "home"
	if theme == "":
		return 0
	var corner_props: Array = {"home": ["floor_lamp", "armchair", "wardrobe", "fridge", "stool", "globe"], "lab": ["microscope", "globe", "floor_lamp", "lab_machine"],
		"school": ["school_desk", "stool", "globe"], "tower": ["candle_stand", "incense_burner"]}[theme]
	var n := 0
	var board_done := false
	for y in range(h):
		for x in range(w):
			var c := Vector2i(x, y)
			var l := String(lab.get(c, ""))
			if busy.has(c) or not bool(can_walk.call(c)):
				continue
			var r := _h(x, y, 560)
			var north := String(lab.get(c + Vector2i(0, -1), ""))
			# ---- wall dressing on the back wall
			if theme == "tower" and north == "wall" and l.begins_with("floor") and r < 0.07:
				n += _one(add, "wall_lantern", Vector3(x + 0.5, 0.55 * WorldData.K, y - 0.02), 0.0, c, 1.0)
				continue
			if theme != "tower" and north == "wall" and l.begins_with("floor") and not busy.has(c + Vector2i(0, -1)):
				if theme == "school" and not board_done and String(lab.get(c + Vector2i(1, -1), "")) == "wall" and bool(can_walk.call(c + Vector2i(1, 0))) and r < 0.5:
					board_done = true
					n += _one(add, "blackboard", Vector3(x + 1.0, 0.4 * WorldData.K, y - 0.02), 0.0, c, 1.0)
					continue
				if r < 0.16:
					var wall_props := ["wall_clock", "poster_view", "poster_map", "painting", "poster_ball"]
					if theme == "home":
						wall_props = ["wall_clock", "poster_view", "painting", "kitchen_rack", "poster_map"]
					elif theme == "lab":
						wall_props = ["wall_clock", "poster_map", "poster_ball", "poster_view"]
					n += _one(add, wall_props[int(_h(x, y, 561) * wall_props.size()) % wall_props.size()], Vector3(x + 0.5, 0.5 * WorldData.K, y - 0.02), 0.0, c, 1.0)
					continue
			# ---- corner furniture
			if not l.begins_with("floor") or not WALLS.has(north):
				continue
			var w_solid := WALLS.has(String(lab.get(c + Vector2i(-1, 0), "")))
			var e_solid := WALLS.has(String(lab.get(c + Vector2i(1, 0), "")))
			if not (w_solid or e_solid) or r > 0.5:
				continue
			var near_door := false
			for d in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1), Vector2i(1, 1), Vector2i(-1, 1)]:
				var nl := String(lab.get(c + d, ""))
				if busy.has(c + d) or nl == "door" or nl.begins_with("stairs") or nl == "mat":
					near_door = true
			if near_door:
				continue
			var prop: String = corner_props[int(_h(x, y, 562) * corner_props.size()) % corner_props.size()]
			var ox := 0.5
			if theme == "home" and _h(x, y, 563) < 0.3:
				# a two-cell sofa needs the next cell along the wall to be free floor as well
				var ec := c + Vector2i(1, 0)
				if String(lab.get(ec, "")).begins_with("floor") and bool(can_walk.call(ec)) and not busy.has(ec) and WALLS.has(String(lab.get(ec + Vector2i(0, -1), ""))):
					prop = "sofa"
					ox = 1.0
			var m := PropKit.mesh(prop)
			if m == null:
				continue
			var bb := m.get_aabb()
			n += _one(add, prop, Vector3(x + ox, 0.0, float(y + 1) - 0.05 - (bb.position.z + bb.size.z)), 0.0, c, 1.0)
	return n

## A fountain in the middle of a town pond (a small inland water body of 3 x 3 cells or more).
static func _pond_fountain(lab: Dictionary, w: int, h: int, add: Callable) -> int:
	var seen := {}
	for y in range(2, h - 2):
		for x in range(2, w - 2):
			var c := Vector2i(x, y)
			if seen.has(c) or String(lab.get(c, "")) != "water":
				continue
			var comp := FurnitureKit._flood(lab, c, "water")
			for q in comp:
				seen[q] = true
			var bb := FurnitureKit._bbox(comp)
			if comp.size() < 9 or comp.size() > 40 or bb.position.x < 1 or bb.position.y < 1 or bb.end.x > w - 1 or bb.end.y > h - 1 or bb.size.x < 3 or bb.size.y < 3:
				continue
			return _one(add, "fountain", Vector3(bb.position.x + bb.size.x * 0.5, 0.02, bb.position.y + bb.size.y * 0.5), 0.0, c, 1.0)
	return 0

static func _landmarks(map: String, lab: Dictionary, add: Callable) -> int:
	var n := 0
	for l in LANDMARKS.get(map, []):
		var c := Vector2i(floori(float(l[1])), floori(float(l[2])))
		if String(l[5]) == "water":
			var ok := true
			for dy in range(-1, 2):
				for dx in range(-1, 2):
					if String(lab.get(c + Vector2i(dx, dy), "")) != "water":
						ok = false
			if not ok:
				continue
		n += _one(add, String(l[0]), Vector3(float(l[1]), 0.0, float(l[2])), float(l[3]), c, float(l[4]))
	for a in WARP_ARCHES.get(map, []):
		n += _one(add, String(a[2]), Vector3(float(a[0]), 0.0, float(a[1])), 0.0, Vector2i(floori(float(a[0])), floori(float(a[1]))), 1.0)
	return n

## Dead-end nooks of a town (a walkable cell with three blocked sides, so nobody has to pass through it): mailboxes,
## lamps, bins, hydrants, benches and hay bales face the open side.
static func _nooks(lab: Dictionary, can_walk: Callable, busy: Dictionary, ctx: Dictionary, w: int, h: int, add: Callable) -> int:
	var map := String(ctx.get("map", ""))
	var pick: Array
	var strict := true      # true: only real dead ends (one open side); false: corners (two open sides) as well
	if map.ends_with("City") or map.ends_with("Town") or map.ends_with("Island"):
		pick = ["mailbox", "lamp_post", "bin_street", "fire_hydrant", "park_bench", "mailbox", "lamp_post", "flag_pole", "street_sign", "town_sign"]
		if map == "VermilionCity":
			pick = pick + ["cargo_crates", "anchor", "life_ring"]
		if map == "PewterCity" or map == "ViridianCity" or map == "PalletTown":
			pick = pick + ["bush_flowering", "sunflower"]
	elif map.begins_with("Route") or map == "ViridianForest" or map.begins_with("Safari"):
		pick = ["bush_round", "bush_berry", "bush_flowering", "stump", "log_fallen", "sunflower", "grass_clump", "log_pile", "hay_bale", "telephone_pole"]
		if map in ["Route16", "Route17", "Route18"]:
			pick = pick + ["barricade", "traffic_cone", "billboard"]
		strict = false
	elif map == "VermilionDock":
		pick = ["cargo_crates", "container", "anchor", "life_ring", "pier_post", "barricade"]
		strict = false
	else:
		return 0
	var n := 0
	for y in range(h):
		for x in range(w):
			var c := Vector2i(x, y)
			if busy.has(c) or not NOOK_LABELS.has(String(lab.get(c, ""))) or not bool(can_walk.call(c)):
				continue
			var open: Array = []
			for d in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1)]:
				if bool(can_walk.call(c + d)) or busy.has(c + d) and String(lab.get(c + d, "")) == "door":
					open.append(d)
			if open.is_empty() or open.size() > (1 if strict else 2) or _h(x, y, 520) > (0.7 if strict else 0.32):
				continue
			var d0: Vector2i = open[0]
			var yaw: float = {Vector2i(0, 1): 0.0, Vector2i(0, -1): PI, Vector2i(1, 0): PI * 0.5, Vector2i(-1, 0): -PI * 0.5}[d0]
			var prop: String = pick[int(_h(x, y, 521) * pick.size()) % pick.size()]
			if ["bush_round", "bush_berry", "bush_flowering", "stump", "log_fallen", "sunflower", "grass_clump", "log_pile"].has(prop):
				yaw = _h(x, y, 523) * TAU
			# tuck it against the blocked back wall of the nook
			var pos := Vector3(x + 0.5 - float(d0.x) * 0.16, 0.0, y + 0.5 - float(d0.y) * 0.16)
			n += _one(add, prop, pos, yaw, c, 1.0)
	return n

## Wooden railings along both sides of every bridge cell (on the water beside it), posts where a bridge ends.
static func _bridges(lab: Dictionary, w: int, h: int, add: Callable) -> int:
	var n := 0
	for y in range(-1, h + 1):
		for x in range(-1, w + 1):
			var c := Vector2i(x, y)
			if String(lab.get(c, "")) != "bridge":
				continue
			var up := String(lab.get(c + Vector2i(0, -1), ""))
			var dn := String(lab.get(c + Vector2i(0, 1), ""))
			var lf := String(lab.get(c + Vector2i(-1, 0), ""))
			var rt := String(lab.get(c + Vector2i(1, 0), ""))
			var horiz := up == "water" and dn == "water" or (lf == "bridge" or rt == "bridge") and up != "bridge" and dn != "bridge"
			if horiz:
				n += _one(add, "rail_x", Vector3(x + 0.5, 0.0, y + 0.06), 0.0, c, 1.0)
				n += _one(add, "rail_x", Vector3(x + 0.5, 0.0, y + 0.94), 0.0, c, 1.0)
				if lf != "bridge":
					n += _one(add, "rail_post", Vector3(x + 0.04, 0.0, y + 0.06), 0.0, c, 1.0) + _one(add, "rail_post", Vector3(x + 0.04, 0.0, y + 0.94), 0.0, c, 1.0)
				if rt != "bridge":
					n += _one(add, "rail_post", Vector3(x + 0.96, 0.0, y + 0.06), 0.0, c, 1.0) + _one(add, "rail_post", Vector3(x + 0.96, 0.0, y + 0.94), 0.0, c, 1.0)
			elif lf == "water" and rt == "water" or (up == "bridge" or dn == "bridge"):
				n += _one(add, "rail_z", Vector3(x + 0.06, 0.0, y + 0.5), 0.0, c, 1.0)
				n += _one(add, "rail_z", Vector3(x + 0.94, 0.0, y + 0.5), 0.0, c, 1.0)
				if up != "bridge":
					n += _one(add, "rail_post", Vector3(x + 0.06, 0.0, y + 0.04), 0.0, c, 1.0) + _one(add, "rail_post", Vector3(x + 0.94, 0.0, y + 0.04), 0.0, c, 1.0)
				if dn != "bridge":
					n += _one(add, "rail_post", Vector3(x + 0.06, 0.0, y + 0.96), 0.0, c, 1.0) + _one(add, "rail_post", Vector3(x + 0.94, 0.0, y + 0.96), 0.0, c, 1.0)
	return n

const GYM_TOP := {"PewterCity": "gym_top_rock", "CeruleanCity": "gym_top_water", "VermilionCity": "gym_top_electric", "CeladonCity": "gym_top_grass",
	"FuchsiaCity": "gym_top_poison", "SaffronCity": "gym_top_psychic", "CinnabarIsland": "gym_top_fire", "ViridianCity": "gym_top_ground"}

## Roof dressing from the building blocks' geometry (the same numbers BuildingBuilder uses): TV aerials and vanes on
## pitched house roofs, the gym-type ornament on each town's gym, hatches / tanks / masts on the flat office roofs.
static func _buildings(bake: Dictionary, add: Callable) -> int:
	var mx := int(bake.get("mx", 0))
	var my := int(bake.get("my", 0))
	var map := String(bake.get("map", ""))
	var K := WorldData.K
	var n := 0
	var bi := 0
	for b in bake.get("blocks", []):
		bi += 1
		if String(b.get("t", "")) != "house":
			continue
		var btype := String(b.get("type", "house"))
		var x0 := float(b.x0) - 1.0
		var x1 := float(b.x1) + 1.0
		var zf := float(b.wallBottom) + 1.0
		var wall_top := float(b.wallTop)
		var roof_top := float(b.roofTop) - 1.0
		var hw := zf - wall_top
		var rh := wall_top - roof_top
		var flat := bool(b.get("flat", false))
		var W := x1 - x0
		var depth := rh if flat else rh * 0.7
		var zr := zf - depth * 0.5
		var hr := zr - roof_top
		var bseed := int(x0) * 7 + int(zf)
		var cell := Vector2i(floori((x0 + x1) * 0.5 / 16.0) - mx, floori(zf / 16.0) - my)
		if btype == "house" and not flat and W >= 48.0:
			var ch_x := float(b.chimney[0]) if b.has("chimney") else -999.0
			var ax := x0 + W * (0.66 if _h(bseed, 1, 530) < 0.5 else 0.34)
			if absf(ax - ch_x) < 18.0:
				ax = x0 + W * 0.5
			var pos := Vector3(ax / 16.0 - mx, hr / 16.0 * K, zr / 16.0 - my)
			n += _one(add, "tv_antenna" if _h(bseed, 2, 531) < 0.5 else "weather_vane", pos, 0.0, cell, 0.9)
		elif btype == "gym" and GYM_TOP.has(map):
			var gtop := (hr if not flat else hw) / 16.0 * K
			n += _one(add, String(GYM_TOP[map]), Vector3((x0 + x1) * 0.5 / 16.0 - mx, gtop, (zr if not flat else zf - depth * 0.5) / 16.0 - my), 0.0, cell, 1.1)
		elif btype == "big" and flat and W >= 40.0:
			var zc := (zf - depth * 0.5) / 16.0 - my
			var top := (hw + 1.5) / 16.0 * K
			if rh > 44.0:      # a tall office block: mast on one corner, hatch and tank on the other
				n += _one(add, "radio_mast", Vector3((x1 - 10.0) / 16.0 - mx, top, zc), 0.0, cell, 1.0)
				n += _one(add, "roof_hatch", Vector3((x0 + 12.0) / 16.0 - mx, top, zc - 0.1), 0.0, cell, 0.8)
			elif _h(bseed, 3, 532) < 0.55:
				var roof_prop: String = ["roof_tank", "roof_hatch", "satellite_dish"][int(_h(bseed, 4, 533) * 3.0) % 3]
				n += _one(add, roof_prop, Vector3((x0 + W * (0.22 + 0.5 * _h(bseed, 5, 534))) / 16.0 - mx, top, zc), 0.0, cell, 0.9)
	return n

static func _one(add: Callable, prop: String, pos: Vector3, yaw: float, c: Vector2i, sc: float) -> int:
	if PropKit.mesh(prop) == null:
		return 0
	add.call(prop, pos, yaw, c, sc)
	return 1
