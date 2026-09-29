class_name TileKit
extends RefCounted
## The per-cell 3D decor of a baked map: upstream's trees as real 3D meshes (pipeline/blender/gen_world.py,
## one per tree kind x variant, drawn as chunked MultiMeshes), tall grass as two layered cards per cell (back
## tufts behind a character standing in it, front tufts in front of it - upstream's drawGrassFront - swaying
## and rustling with upstream's own frame timing), and flowers as animated ground cards.
## Every material here takes the same day/night grade + light pools as the baked world (apply_grade).

const TREE_SHADER := preload("res://scripts/overworld/shaders/tree.gdshader")
const TREE_OUTLINE_SHADER := preload("res://scripts/overworld/shaders/tree_outline.gdshader")
const DECOR_SHADER := preload("res://scripts/overworld/shaders/decor.gdshader")
const FX_SHADER := preload("res://scripts/overworld/shaders/fx.gdshader")
const SMOKE_SHADER := preload("res://scripts/overworld/shaders/smoke.gdshader")
const CHUNK := 8

static var _palette: Dictionary = {}
static var _tree_meshes: Dictionary = {}   # "tree0" .. "tree25" -> Mesh
static var _materials: Array = []          # ShaderMaterials that follow the day/night grade
static var _tree_mat: ShaderMaterial = null
static var _prop_mat: ShaderMaterial = null
static var _detail_tex: Texture2D = null

## Vertex-coloured prop material (trees' shader, no wind) of the current map, for Blender props (Poké Balls,
## boulders, signs, fences, plants).
static func prop_material() -> ShaderMaterial:
	return _prop_mat if _prop_mat else _tree_mat

static func detail_texture() -> Texture2D:
	if _detail_tex == null and ResourceLoader.exists("res://assets/models/tiles/env_detail.png"):
		_detail_tex = load("res://assets/models/tiles/env_detail.png")
	return _detail_tex

static func _prop_shader_material(bake: Dictionary, sway: float, outline_col: Color, outline_w: float) -> ShaderMaterial:
	var m := _register(ShaderMaterial.new(), bake)
	m.shader = TREE_SHADER
	m.set_shader_parameter("sway", sway)
	if detail_texture():
		m.set_shader_parameter("detail_tex", detail_texture())
		m.set_shader_parameter("detail_on", true)
	if outline_w > 0.0:
		var ol := _register(ShaderMaterial.new(), bake)
		ol.shader = TREE_OUTLINE_SHADER
		ol.set_shader_parameter("outline_srgb", Vector3(outline_col.r, outline_col.g, outline_col.b))
		ol.set_shader_parameter("width", outline_w)
		m.next_pass = ol
	return m

static func palette() -> Dictionary:
	if _palette.is_empty():
		var f := FileAccess.open("res://assets/maps/palette.json", FileAccess.READ)
		if f:
			var p: Variant = JSON.parse_string(f.get_as_text())
			if typeof(p) == TYPE_DICTIONARY:
				_palette = p
	return _palette

static func palette_colors(key: String) -> PackedVector3Array:
	var out := PackedVector3Array()
	for h in palette().get(key, []):
		var c := Color(String(h))
		out.append(Vector3(c.r, c.g, c.b))
	return out

static func tree_mesh(kind: int, v: int) -> Mesh:
	var key := "tree%s%d" % ["2" if kind == 1 else "", v]
	if _tree_meshes.has(key):
		return _tree_meshes[key]
	var mesh: Mesh = null
	var path := "res://assets/models/world/tree_%s.glb" % key
	if ResourceLoader.exists(path):
		var ps: PackedScene = load(path)
		if ps:
			var inst := ps.instantiate()
			var mi := _find_mesh(inst)
			if mi:
				mesh = mi.mesh
			inst.free()
	if mesh == null:
		var sm := SphereMesh.new()
		sm.radius = 0.45
		sm.height = 0.9
		mesh = sm
	_tree_meshes[key] = mesh
	return mesh

static func _find_mesh(n: Node) -> MeshInstance3D:
	if n is MeshInstance3D:
		return n
	for c in n.get_children():
		var f := _find_mesh(c)
		if f:
			return f
	return null

static func _register(m: ShaderMaterial, bake: Dictionary) -> ShaderMaterial:
	m.set_shader_parameter("map_px", Vector2(float(bake.get("cw", 1)) * 16.0, float(bake.get("ch", 1)) * 16.0))
	m.set_shader_parameter("margin", Vector2(float(bake.get("mx", 0)), float(bake.get("my", 0))))
	m.set_shader_parameter("k_vert", WorldData.K)
	_materials.append(m)
	return m

## Builds the decor node for a bake: Trees (chunked multimeshes), TallGrass, Flowers.
static func build_decor(bake: Dictionary, mx: int, my: int) -> Node3D:
	_materials.clear()
	var root := Node3D.new()
	root.name = "Decor"
	# ---- trees
	var tree_mat := _prop_shader_material(bake, 0.022, Color(String(palette().get("leaf", ["#0c2322"])[0])), 0.035)
	tree_mat.set_shader_parameter("sway_from", 0.55)
	tree_mat.set_shader_parameter("sway_range", 1.0)
	_tree_mat = tree_mat
	_prop_mat = _prop_shader_material(bake, 0.0, Color("#1b1a2e"), 0.03)
	var groups := {}   # "chunk|kind|v" -> Array[Transform3D]
	var all_trees: Array = (bake.get("trees", []) as Array).duplicate()
	if String(bake.get("map", "")) == "ViridianForest":
		all_trees.append_array(_margin_forest(bake))
	for t in all_trees:
		var cx := int(t[0])
		var cy := int(t[1])
		var key := "%d,%d|%d|%d" % [cx / CHUNK, cy / CHUNK, int(t[2]), int(t[3])]
		if not groups.has(key):
			groups[key] = []
		var xf := Transform3D(Basis.from_scale(Vector3(1.0, WorldData.K, 1.0)), Vector3(cx - mx + 0.5 + 1.0 / 16.0, 0.0, cy - my + 1.0))
		var ph := float(cx * 16) * 0.013 + float(cy * 16) * 0.007
		groups[key].append([xf, Color((PropKit._h(cx, cy, 11) - 0.5) * 0.06, fmod(ph * 3.7, TAU), (PropKit._h(cx, cy, 12) - 0.5) * 0.6, 0.0)])
	var trees := Node3D.new()
	trees.name = "Trees"
	root.add_child(trees)
	for key in groups.keys():
		var parts: PackedStringArray = String(key).split("|")
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = tree_mesh(int(parts[1]), int(parts[2]))
		mm.use_colors = true          # (GLES3: vertex COLOR is multiplied by the instance colour, which must be white)
		mm.use_custom_data = true
		var xfs: Array = groups[key]
		mm.instance_count = xfs.size()
		for i in range(xfs.size()):
			mm.set_instance_transform(i, xfs[i][0])
			mm.set_instance_color(i, Color.WHITE)
			mm.set_instance_custom_data(i, xfs[i][1])
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = tree_mat
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		trees.add_child(mmi)
	# ---- tall grass + flowers (cards textured from upstream's own sprites)
	var deco_tex: Texture2D = load("res://assets/maps/decor_atlas.png")
	var grass: Array = bake.get("grass", [])
	if not grass.is_empty():
		var gm := _register(ShaderMaterial.new(), bake)
		gm.shader = DECOR_SHADER
		gm.set_shader_parameter("tex", deco_tex)
		gm.set_shader_parameter("mode", 0)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = _grass_card_mesh()
		mm.instance_count = grass.size()
		var index := {}
		for i in range(grass.size()):
			var g: Array = grass[i]
			var gx := int(g[0])
			var gy := int(g[1])
			mm.set_instance_transform(i, Transform3D(Basis.IDENTITY, Vector3(gx - mx, 0.0, gy - my)))
			var ph := float(gx * 16) * 0.013 + float(gy * 16) * 0.007
			mm.set_instance_custom_data(i, Color(float(g[2]), 0.0, ph, 0.0))
			index[Vector2i(gx - mx, gy - my)] = i
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "TallGrass"
		mmi.multimesh = mm
		mmi.material_override = gm
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi.set_meta("index", index)
		root.add_child(mmi)
	var flowers: Array = bake.get("flowers", [])
	var wind_mat := _prop_shader_material(bake, 0.06, Color.BLACK, 0.0)
	wind_mat.set_shader_parameter("sway_from", 0.06)
	wind_mat.set_shader_parameter("sway_range", 0.3)
	if PropKit.mesh("tuft") != null:
		for n in PropKit.build_tufts(bake, wind_mat, _prop_mat):
			root.add_child(n)
	if not flowers.is_empty() and PropKit.mesh("flower_red") != null:
		root.add_child(PropKit.build_flowers(bake, wind_mat))
	elif not flowers.is_empty():
		var fm := _register(ShaderMaterial.new(), bake)
		fm.shader = DECOR_SHADER
		fm.set_shader_parameter("tex", deco_tex)
		fm.set_shader_parameter("mode", 1)
		var mm2 := MultiMesh.new()
		mm2.transform_format = MultiMesh.TRANSFORM_3D
		mm2.use_custom_data = true
		mm2.mesh = _flower_mesh()
		mm2.instance_count = flowers.size()
		for i in range(flowers.size()):
			var fl: Array = flowers[i]
			mm2.set_instance_transform(i, Transform3D(Basis.IDENTITY, Vector3(int(fl[0]) - mx, 0.0, int(fl[1]) - my)))
			mm2.set_instance_custom_data(i, Color(float(fl[2]), 0.0, float(fl[3]), 0.0))
		var mmi2 := MultiMeshInstance3D.new()
		mmi2.name = "Flowers"
		mmi2.multimesh = mm2
		mmi2.material_override = fm
		mmi2.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mmi2)
	# ---- animated effects: brazier flames, electric barriers, teleport pads
	var fires: Array = bake.get("fires", [])
	if not fires.is_empty():
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		# card local coords: x in [-6, 6] px, standing 10 px behind the flame's base, from 9 px (bowl rim) up 17 px
		var k := WorldData.K
		var pts := [[Vector3(-6.0 / 16.0, 26.0 / 16.0 * k, 0), Vector2(0, 0)], [Vector3(6.0 / 16.0, 26.0 / 16.0 * k, 0), Vector2(1, 0)],
			[Vector3(6.0 / 16.0, 9.0 / 16.0 * k, 0), Vector2(1, 1)], [Vector3(-6.0 / 16.0, 9.0 / 16.0 * k, 0), Vector2(0, 1)]]
		for i in [0, 1, 2, 0, 2, 3]:
			st.set_normal(Vector3.BACK)
			st.set_uv(pts[i][1])
			st.add_vertex(pts[i][0])
		root.add_child(_fx_multimesh("Fires", st.commit(), 0, fires.map(func(f: Array) -> Array:
			return [Vector3(float(f[0]) / 16.0 - mx, 0.0, (float(f[1]) + 9.0) / 16.0 - my), float(f[2])])))
	var fx: Array = bake.get("fx", [])
	for kind in ["barrier", "teleport"]:
		var cells := fx.filter(func(e: Array) -> bool: return String(e[2]) == kind)
		if cells.is_empty():
			continue
		root.add_child(_fx_multimesh(kind.capitalize(), _flower_mesh(), 1 if kind == "barrier" else 2, cells.map(func(e: Array) -> Array:
			return [Vector3(int(e[0]) - mx, 0.002, int(e[1]) - my), float(int(e[0]) * 7 + int(e[1]))])))
	return root

## Viridian Forest is a 'field' map drawn on void; in 3D the camera sees past its edge, so the bake's margin is grown
## into more forest (visual only): a hashed grid of trees in every margin cell that is not already a tree.
static func _margin_forest(bake: Dictionary) -> Array:
	var out: Array = []
	var cw := int(bake.get("cw", 0))
	var ch := int(bake.get("ch", 0))
	var mx := int(bake.get("mx", 0))
	var my := int(bake.get("my", 0))
	var w := int(bake.get("w", 0))
	var h := int(bake.get("h", 0))
	var taken := {}
	for t in bake.get("trees", []):
		taken[Vector2i(int(t[0]), int(t[1]))] = true
	for y in range(ch):
		for x in range(cw):
			var inside := x >= mx and x < mx + w and y >= my and y < my + h
			if inside or taken.has(Vector2i(x, y)):
				continue
			if PropKit._h(x, y, 71) < 0.86:
				out.append([x, y, 0, int(PropKit._h(x, y, 72) * 6.0) % 6])
	return out

## Smoke puffs rising from the chimneys (world points = chimney tops from WorldBuilder.smoke_points).
static func build_smoke(bake: Dictionary, points: Array) -> Node3D:
	if points.is_empty():
		return null
	var mat := _register(ShaderMaterial.new(), bake)
	mat.shader = SMOKE_SHADER
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	var q := QuadMesh.new()
	q.size = Vector2(1, 1)
	mm.mesh = q
	var per := 5
	mm.instance_count = points.size() * per
	for i in range(points.size()):
		for j in range(per):
			var idx := i * per + j
			mm.set_instance_transform(idx, Transform3D(Basis.IDENTITY, points[i]))
			mm.set_instance_custom_data(idx, Color(float(j) / float(per) + float(i) * 0.137, 0, 0, 0))
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "Smoke"
	mmi.multimesh = mm
	mmi.material_override = mat
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mmi.custom_aabb = AABB(Vector3(-200, -20, -200), Vector3(400, 80, 400))
	return mmi

static func _fx_multimesh(node_name: String, mesh: Mesh, mode: int, items: Array) -> MultiMeshInstance3D:
	var mat := ShaderMaterial.new()
	mat.shader = FX_SHADER
	mat.set_shader_parameter("mode", mode)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = items.size()
	for i in range(items.size()):
		var it: Array = items[i]
		mm.set_instance_transform(i, Transform3D(Basis.IDENTITY, it[0]))
		mm.set_instance_custom_data(i, Color(float(it[1]), 0, 0, 0))
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	mmi.material_override = mat
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mmi

## Two cards per tall-grass cell (local coords: the cell spans [0,1] x [0,1]): the back tufts stand behind a
## character in the cell (depth 10/16, sprite rows 0..10), the front tufts in front of it (depth 1, rows 6..16).
static func _grass_card_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var k := WorldData.K
	for card in [[10.0, 0.0, 10.0], [16.0, 6.0, 16.0]]:
		var zc: float = card[0] / 16.0
		var r0: float = card[1]
		var r1: float = card[2]
		var htop: float = (float(card[0]) - r0) / 16.0 * k
		var hbot: float = (float(card[0]) - r1) / 16.0 * k
		var pts := [[Vector3(0, htop, zc), Vector2(0, r0 / 16.0)], [Vector3(1, htop, zc), Vector2(1, r0 / 16.0)],
			[Vector3(1, hbot, zc), Vector2(1, r1 / 16.0)], [Vector3(0, hbot, zc), Vector2(0, r1 / 16.0)]]
		for i in [0, 1, 2, 0, 2, 3]:
			st.set_normal(Vector3.BACK)
			st.set_uv(pts[i][1])
			st.add_vertex(pts[i][0])
	return st.commit()

static func _flower_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var pts := [[Vector3(0, 0.004, 0), Vector2(0, 0)], [Vector3(1, 0.004, 0), Vector2(1, 0)],
		[Vector3(1, 0.004, 1), Vector2(1, 1)], [Vector3(0, 0.004, 1), Vector2(0, 1)]]
	for i in [0, 1, 2, 0, 2, 3]:
		st.set_normal(Vector3.UP)
		st.set_uv(pts[i][1])
		st.add_vertex(pts[i][0])
	return st.commit()

## Rustle the tall grass at `cell` (map coords) for 12 frames, like upstream mapRender.rustle.
static func rustle(grass_node: Node3D, cell: Vector2i) -> void:
	if grass_node == null or not grass_node is MultiMeshInstance3D:
		return
	var index: Dictionary = grass_node.get_meta("index", {})
	if not index.has(cell):
		return
	var mm: MultiMesh = (grass_node as MultiMeshInstance3D).multimesh
	var i: int = index[cell]
	var c := mm.get_instance_custom_data(i)
	c.g = 1.0
	mm.set_instance_custom_data(i, c)
	var tree := grass_node.get_tree()
	if tree:
		await tree.create_timer(12.0 / 60.0).timeout
		if is_instance_valid(grass_node):
			c.g = 0.0
			mm.set_instance_custom_data(i, c)

static func apply_grade(grade: Color, light_amt: float, light_tex: Texture2D = null, glow_tex: Texture2D = null) -> void:
	for m in _materials:
		var mat: ShaderMaterial = m
		mat.set_shader_parameter("grade", Vector3(grade.r, grade.g, grade.b))
		mat.set_shader_parameter("light_amt", light_amt)
		if light_tex:
			mat.set_shader_parameter("light_tex", light_tex)
