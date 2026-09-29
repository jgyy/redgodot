class_name PropKit
extends RefCounted
## Real 3D props for the objects upstream draws as flat sprite cards / extruded sprites: signs, picket fences,
## potted plants, crates, barrels, gravestones, guardian statues, cuttable trees, braziers and flower tufts
## (pipeline/blender/env_props.py -> assets/models/world/*.glb: ramp-lit vertex colours + detail overlay + ink
## outline, drawn as chunked MultiMeshes with per-instance tint / lean / wind phase).
## They are placed from the bake's label grid (cells), blocks (cards) and fire list, so WorldBuilder skips the
## matching baked blocks (REPLACED) and script-set cell labels (label_override) still win.

const CHUNK := 8
## baked block labels that a 3D prop replaces (WorldBuilder skips them)
const REPLACED := ["sign", "plant", "fence", "crate", "barrel", "grave", "cut_tree", "statue", "gym_statue", "brazier", "bed"]
## label cells -> one prop per cell: label -> [prop, foot z offset inside the cell, yaw jitter]
const CELL_PROPS := {
	"sign": ["sign", 0.82, 0.10], "plant": ["plant", 0.86, 0.6], "crate": ["crate", 0.6, 0.16], "barrel": ["barrel", 0.66, 0.5],
}
## card blocks -> prop
const BLOCK_PROPS := {"cut_tree": "bush", "statue": "statue", "gym_statue": "statue"}
## sprite boxes (art extruded by WorldBuilder) that a prop replaces, fitted to the box footprint: label -> [prop, model width, model length]
const BOX_PROPS := {"bed": ["bed", 0.96, 1.9]}
const FLOWER_MESHES := ["flower_red", "flower_yellow", "flower_white", "flower_pink"]

static var _meshes: Dictionary = {}

static func mesh(prop: String) -> Mesh:
	if _meshes.has(prop):
		return _meshes[prop]
	var m: Mesh = null
	var path := "res://assets/models/world/%s.glb" % prop
	if ResourceLoader.exists(path):
		var ps: PackedScene = load(path)
		if ps:
			var inst := ps.instantiate()
			var mi := TileKit._find_mesh(inst)
			if mi:
				m = mi.mesh
			inst.free()
	_meshes[prop] = m
	return m

static func _h(x: int, y: int, s: int) -> float:
	var h: int = (x * 374761393 + y * 668265263 + s * 2147483647) & 0xffffffff
	h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
	h = h ^ (h >> 16)
	return float(h & 0xffffff) / 16777216.0

## `overrides`: Vector2i (map cell) -> label set by scripts. Returns the Props node (or an empty one).
static func build(bake: Dictionary, overrides: Dictionary, mat: ShaderMaterial) -> Node3D:
	var root := Node3D.new()
	root.name = "Props"
	var cw := int(bake.get("cw", 0))
	var ch := int(bake.get("ch", 0))
	var mx := int(bake.get("mx", 0))
	var my := int(bake.get("my", 0))
	var legend: Array = bake.get("legend", [])
	var labels: Array = bake.get("labels", [])
	if legend.is_empty() or labels.size() < cw * ch:
		return root
	var groups := {}   # "chunk|prop" -> Array[[Transform3D, Color]]
	var add := func(prop: String, pos: Vector3, yaw: float, c: Vector2i, extra_scale: float = 1.0) -> void:
		var key := "%d,%d|%s" % [floori(float(c.x) / CHUNK), floori(float(c.y) / CHUNK), prop]
		if not groups.has(key):
			groups[key] = []
		var b := Basis.from_scale(Vector3(extra_scale, WorldData.K * extra_scale, extra_scale)) * Basis(Vector3.UP, yaw)
		var dev := (_h(c.x, c.y, 5) - 0.5) * 0.10
		groups[key].append([Transform3D(b, pos), Color(dev, _h(c.x, c.y, 6) * TAU, _h(c.x, c.y, 7) - 0.5, 0.0)])
	# ---- label cells
	var fence_at := {}
	var grave_at := []
	for i in range(cw * ch):
		var lab: String = String(legend[int(labels[i])])
		if not (CELL_PROPS.has(lab) or lab == "fence" or lab == "grave"):
			continue
		var c := Vector2i(i % cw - mx, i / cw - my)
		if overrides.has(c) and String(overrides[c]) != lab:
			continue
		if lab == "fence":
			fence_at[c] = true
		elif lab == "grave":
			grave_at.append(c)
		else:
			var cp: Array = CELL_PROPS[lab]
			var sc := 1.0 + (_h(c.x, c.y, 3) - 0.5) * 0.08
			add.call(cp[0], Vector3(c.x + 0.5, 0.0, c.y + float(cp[1])), (_h(c.x, c.y, 2) - 0.5) * float(cp[2]) * 2.0, c, sc)
	for c in grave_at:
		var v := "grave_a" if _h(c.x, c.y, 4) < 0.55 else "grave_b"
		add.call(v, Vector3(c.x + 0.5, 0.0, c.y + 0.72), (_h(c.x, c.y, 2) - 0.5) * 0.12, c)
	for k in fence_at.keys():
		var c: Vector2i = k
		var l: bool = fence_at.has(c + Vector2i(-1, 0))
		var r: bool = fence_at.has(c + Vector2i(1, 0))
		var u: bool = fence_at.has(c + Vector2i(0, -1))
		var d: bool = fence_at.has(c + Vector2i(0, 1))
		var horiz := l or r or (not u and not d)
		var vert := u or d
		if horiz:
			add.call("fence_x", Vector3(c.x + 0.5, 0.0, c.y + 0.9), 0.0, c)
			if not l or (c.x % 3 == 0):
				add.call("fence_post", Vector3(c.x + 0.02, 0.0, c.y + 0.9), 0.0, c)
			if not r:
				add.call("fence_post", Vector3(c.x + 0.98, 0.0, c.y + 0.9), 0.0, c)
		if vert:
			add.call("fence_z", Vector3(c.x + 0.5, 0.0, c.y + 0.5), 0.0, c)
			if not u:
				add.call("fence_post", Vector3(c.x + 0.5, 0.0, c.y + 0.06), 0.0, c)
			if not d:
				add.call("fence_post", Vector3(c.x + 0.5, 0.0, c.y + 0.94), 0.0, c)
			elif c.y % 3 == 0 and not (horiz and (l or r)):
				add.call("fence_post", Vector3(c.x + 0.5, 0.0, c.y + 0.5), 0.0, c)
		if horiz and vert:
			add.call("fence_post", Vector3(c.x + 0.5, 0.0, c.y + 0.9), 0.0, c)
	# ---- card blocks (cut trees, statues)
	for b in bake.get("blocks", []):
		var lab: String = String(b.get("lbl", ""))
		if not BLOCK_PROPS.has(lab):
			continue
		var fx: float = float(b.sx) + float(b.w) * 0.5
		var fz: float = float(b.get("z", float(b.sy) + float(b.h) - 1.0)) + 1.0
		var cell := Vector2i(floori(fx / 16.0) - mx, floori((fz - 1.0) / 16.0) - my)
		if overrides.has(cell) and String(overrides[cell]) != lab:
			continue
		add.call(BLOCK_PROPS[lab], Vector3(fx / 16.0 - mx, 0.0, fz / 16.0 - my - 0.14), (_h(cell.x, cell.y, 2) - 0.5) * 0.1, cell)
	# ---- extruded sprite boxes (beds), scaled to the box's ground footprint
	for b in bake.get("blocks", []):
		var lab2: String = String(b.get("lbl", ""))
		if not BOX_PROPS.has(lab2) or String(b.get("t", "")) != "box":
			continue
		var bp: Array = BOX_PROPS[lab2]
		var z0 := float(b.sy) + float(b.get("hgt", 0))
		var z1 := float(b.sy) + float(b.h)
		var cxp := (float(b.sx) + float(b.w) * 0.5) / 16.0 - mx
		var czp := (z0 + z1) * 0.5 / 16.0 - my
		var cell3 := Vector2i(floori((float(b.sx) + float(b.w) * 0.5) / 16.0) - mx, floori((z1 - 1.0) / 16.0) - my)
		if overrides.has(cell3) and String(overrides[cell3]) != lab2:
			continue
		var sxw: float = float(b.w) / 16.0 / float(bp[1])
		var szl: float = (z1 - z0) / 16.0 / float(bp[2])
		var key3 := "%d,%d|%s" % [floori(float(cell3.x) / CHUNK), floori(float(cell3.y) / CHUNK), bp[0]]
		if not groups.has(key3):
			groups[key3] = []
		groups[key3].append([Transform3D(Basis.from_scale(Vector3(sxw, WorldData.K, szl)), Vector3(cxp, 0.0, czp)), Color(0, 0, 0, 0)])
	# ---- braziers (their flames are the bake's fire list)
	for f in bake.get("fires", []):
		var cell2 := Vector2i(floori(float(f[0]) / 16.0) - mx, floori((float(f[1]) + 8.0) / 16.0) - my)
		add.call("brazier", Vector3(float(f[0]) / 16.0 - mx, 0.0, (float(f[1]) + 9.0) / 16.0 - my), 0.0, cell2)
	_flush(root, groups, mat)
	return root

## Grass tufts on plain grass / path-edge cells and stones along ledge feet (visual sprinkles, windy material).
static func build_tufts(bake: Dictionary, mat: ShaderMaterial, stones_mat: ShaderMaterial) -> Array:
	var cw := int(bake.get("cw", 0))
	var ch := int(bake.get("ch", 0))
	var mx := int(bake.get("mx", 0))
	var my := int(bake.get("my", 0))
	var legend: Array = bake.get("legend", [])
	var labels: Array = bake.get("labels", [])
	var w := int(bake.get("w", 0))
	var h := int(bake.get("h", 0))
	if String(bake.get("kind", "")) == "interior" or legend.is_empty() or labels.size() < cw * ch:
		return []
	var prob := {}
	for i in range(legend.size()):
		match String(legend[i]):
			"grass": prob[i] = 0.16
			"path_tufts": prob[i] = 0.42
			"flowers": prob[i] = 0.0
			"ledge_d", "ledge_l", "ledge_r": prob[i] = -1.0
	var tufts := {}
	var stones := {}
	for i in range(cw * ch):
		var li := int(labels[i])
		if not prob.has(li):
			continue
		var x := i % cw
		var y := i / cw
		# only near the playable area (the far margin is never seen closely)
		if x < mx - 8 or x >= mx + w + 8 or y < my - 8 or y >= my + h + 8:
			continue
		var c := Vector2i(x - mx, y - my)
		var p: float = prob[li]
		var key_chunk := "%d,%d" % [floori(float(c.x) / CHUNK), floori(float(c.y) / CHUNK)]
		if p < 0.0:
			for k in range(2):
				var jx := 0.2 + _h(x, y, 90 + k) * 0.6
				var b := Basis.from_scale(Vector3.ONE * (0.8 + _h(x, y, 92 + k) * 0.7)) * Basis(Vector3.UP, _h(x, y, 94 + k) * TAU)
				b = Basis.from_scale(Vector3(1.0, WorldData.K, 1.0)) * b
				var key := "%s|pebbles" % key_chunk
				if not stones.has(key):
					stones[key] = []
				if _h(x, y, 96 + k) < 0.5:
					stones[key].append([Transform3D(b, Vector3(c.x + jx, 0.0, c.y + 0.9)), Color(0, 0, 0, 0)])
			var kt := "%s|tuft" % key_chunk
			if not tufts.has(kt):
				tufts[kt] = []
			if _h(x, y, 98) < 0.5:
				tufts[kt].append([Transform3D(Basis.from_scale(Vector3(1.0, WorldData.K, 1.0)), Vector3(c.x + 0.2 + _h(x, y, 99) * 0.6, 0.0, c.y + 0.12)), Color(0, _h(x, y, 100) * TAU, 0, 0)])
			continue
		if _h(x, y, 60) < p:
			var kt2 := "%s|tuft" % key_chunk
			if not tufts.has(kt2):
				tufts[kt2] = []
			var sc := 0.8 + _h(x, y, 61) * 0.7
			var bb := Basis.from_scale(Vector3(sc, WorldData.K * sc, sc)) * Basis(Vector3.UP, _h(x, y, 62) * TAU)
			tufts[kt2].append([Transform3D(bb, Vector3(c.x + 0.15 + _h(x, y, 63) * 0.7, 0.0, c.y + 0.2 + _h(x, y, 64) * 0.7)), Color((_h(x, y, 65) - 0.5) * 0.1, _h(x, y, 66) * TAU, _h(x, y, 67) - 0.5, 0.0)])
	var t := Node3D.new()
	t.name = "GrassTufts"
	_flush(t, tufts, mat)
	var s := Node3D.new()
	s.name = "LedgeStones"
	_flush(s, stones, stones_mat)
	return [t, s]

## Flower tufts on the bake's flower cells (windy: own material).
static func build_flowers(bake: Dictionary, mat: ShaderMaterial) -> Node3D:
	var root := Node3D.new()
	root.name = "Flowers3D"
	var mx := int(bake.get("mx", 0))
	var my := int(bake.get("my", 0))
	var groups := {}
	for fl in bake.get("flowers", []):
		var cx := int(fl[0])
		var cy := int(fl[1])
		var col := clampi(int(fl[2]), 0, 3)
		var key := "%d,%d|%s" % [floori(float(cx - mx) / CHUNK), floori(float(cy - my) / CHUNK), FLOWER_MESHES[col]]
		if not groups.has(key):
			groups[key] = []
		var spots := [Vector2(0.2, 0.25), Vector2(0.62, 0.2), Vector2(0.86, 0.45), Vector2(0.28, 0.66), Vector2(0.68, 0.78), Vector2(0.48, 0.5)]
		for s in range(spots.size()):
			var jx := (_h(cx, cy, 20 + s) - 0.5) * 0.14
			var jz := (_h(cx, cy, 30 + s) - 0.5) * 0.14
			var sc := 1.05 + _h(cx, cy, 40 + s) * 0.45
			var b := Basis.from_scale(Vector3(sc, WorldData.K * sc, sc)) * Basis(Vector3.UP, _h(cx, cy, 50 + s) * TAU)
			var p := Vector3(cx - mx + spots[s].x + jx, 0.0, cy - my + spots[s].y + jz)
			groups[key].append([Transform3D(b, p), Color(0.0, float(fl[3]) * 0.7 + s * 1.9, 0.0, 0.0)])
	_flush(root, groups, mat)
	return root

static func _flush(root: Node3D, groups: Dictionary, mat: ShaderMaterial) -> void:
	for key in groups.keys():
		var parts: PackedStringArray = String(key).split("|")
		var m := mesh(parts[1])
		if m == null:
			continue
		var items: Array = groups[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		mm.mesh = m
		mm.instance_count = items.size()
		for i in range(items.size()):
			mm.set_instance_transform(i, items[i][0])
			mm.set_instance_color(i, Color.WHITE)
			mm.set_instance_custom_data(i, items[i][1])
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "%s_%s" % [parts[1], parts[0].replace(",", "_")]
		mmi.multimesh = mm
		mmi.material_override = mat
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mmi)
