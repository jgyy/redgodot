class_name WorldBuilder
extends RefCounted
## Turns one baked map (pipeline/scripts/bake_maps.js -> res://assets/maps/<Map>.json + pngs) into 3D:
##  - the ground plane (upstream's ground painter output, water animated in the shader)
##  - every baked object extruded into real geometry whose UVs are the *oblique projection* of its 2D art:
##    a point (x, z) on the map at height h (in 2D-art pixels) samples the 2D pixel (x, z - h). From the game
##    camera each building / wall / table therefore reads exactly like the 2D game's pixel art, while it is a
##    real box with a roof, sides and depth that occludes the characters walking behind it.
## Map pixel space: 16 px per cell, pixel (0,0) = map cell (-mx, -my). World: 1 unit per cell, map cell (0,0)
## at the origin, +z = south, heights scaled by WorldData.K.

const SHADER := preload("res://scripts/overworld/shaders/world.gdshader")

var bake: Dictionary
var mx := 0
var my := 0
var atlas_size := Vector2(4, 4)
var _st: SurfaceTool
var _cur: Dictionary   # the block being emitted (sx, sy, ax, ay)

static func load_bake(map_name: String) -> Dictionary:
	var path := "res://assets/maps/%s.json" % map_name
	if not FileAccess.file_exists(path):
		return {}
	var f := FileAccess.open(path, FileAccess.READ)
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}

func _init(b: Dictionary) -> void:
	bake = b
	mx = int(b.get("mx", 0))
	my = int(b.get("my", 0))
	var a: Array = b.get("atlas", [4, 4])
	atlas_size = Vector2(float(a[0]), float(a[1]))

func px_to_world(px: float, pz: float, hpx: float) -> Vector3:
	return Vector3(px / 16.0 - mx, hpx / 16.0 * WorldData.K, pz / 16.0 - my)

## Material shared by the ground and the objects of one map.
func make_material(tex: Texture2D, is_ground: bool) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = SHADER
	m.set_shader_parameter("albedo_tex", tex)
	m.set_shader_parameter("map_px", Vector2(float(bake.get("cw", 1)) * 16.0, float(bake.get("ch", 1)) * 16.0))
	m.set_shader_parameter("margin", Vector2(mx, my))
	m.set_shader_parameter("k_vert", WorldData.K)
	m.set_shader_parameter("is_ground", is_ground)
	return m

func build_ground(mat: ShaderMaterial) -> MeshInstance3D:
	var cw := float(bake.get("cw", 1))
	var ch := float(bake.get("ch", 1))
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# interiors: the baked void border is clamped outward so the room floats in upstream's black void to the
	# screen edges
	var ext := 40.0 if String(bake.get("kind", "")) == "interior" else 0.0
	var u0 := -ext / cw
	var v0 := -ext / ch
	var u1 := 1.0 + ext / cw
	var v1 := 1.0 + ext / ch
	var p0 := Vector3(-mx - ext, 0, -my - ext)
	var p1 := Vector3(cw - mx + ext, 0, -my - ext)
	var p2 := Vector3(cw - mx + ext, 0, ch - my + ext)
	var p3 := Vector3(-mx - ext, 0, ch - my + ext)
	st.set_normal(Vector3.UP)
	for v in [[p0, Vector2(u0, v0)], [p1, Vector2(u1, v0)], [p2, Vector2(u1, v1)], [p0, Vector2(u0, v0)], [p2, Vector2(u1, v1)], [p3, Vector2(u0, v1)]]:
		st.set_uv(v[1])
		st.add_vertex(v[0])
	var mi := MeshInstance3D.new()
	mi.name = "Ground"
	mi.mesh = st.commit()
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

## All baked blocks of the map merged into one mesh (one draw call).
func build_objects(mat: ShaderMaterial) -> MeshInstance3D:
	_st = SurfaceTool.new()
	_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n := 0
	for b in bake.get("blocks", []):
		_cur = b
		match String(b.get("t", "")):
			"card": _emit_card(b); n += 1
			"box": _emit_box_sprite(b); n += 1
			"walls":
				for bx in b.get("boxes", []):
					_emit_box(float(bx[0]), float(bx[1]), float(bx[2]), float(bx[3]), float(bx[4]))
				n += 1
			"cellboxes":
				for c in b.get("cells", []):
					_emit_cellbox(b, float(c[0]), float(c[1]))
				n += 1
			"terrace": _emit_terrace(b); n += 1
			"house": _emit_house(b); n += 1
	var mi := MeshInstance3D.new()
	mi.name = "Objects"
	if n > 0:
		mi.mesh = _st.commit()
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

# ---------------------------------------------------------------- primitives
func _uv(px: float, pz: float, hpx: float) -> Vector2:
	var sx := float(_cur.get("sx", 0)) - float(_cur.get("ax", 0))
	var sy := float(_cur.get("sy", 0)) - float(_cur.get("ay", 0))
	return Vector2((px - sx) / atlas_size.x, (pz - hpx - sy) / atlas_size.y)

## One quad; corners are map-px points [x, z, h]. uv_fix: optional column to sample for faces seen edge-on.
func _quad(pts: Array, normal: Vector3, uv_col: float = -1.0) -> void:
	normal = _true_normal(pts, normal)
	var tri := [0, 1, 2, 0, 2, 3]
	for i in tri:
		var p: Array = pts[i]
		_st.set_normal(normal)
		var uvx: float = float(p[0]) if uv_col < 0.0 else uv_col
		_st.set_uv(_uv(uvx, float(p[1]), float(p[2])))
		_st.add_vertex(px_to_world(float(p[0]), float(p[1]), float(p[2])))

func _tri(pts: Array, normal: Vector3, uv_col: float = -1.0) -> void:
	normal = _true_normal(pts, normal)
	for p in pts:
		_st.set_normal(normal)
		var uvx: float = float(p[0]) if uv_col < 0.0 else uv_col
		_st.set_uv(_uv(uvx, float(p[1]), float(p[2])))
		_st.add_vertex(px_to_world(float(p[0]), float(p[1]), float(p[2])))

## Geometric normal of a (planar) polygon, oriented to agree with `hint`.
func _true_normal(pts: Array, hint: Vector3) -> Vector3:
	var a := px_to_world(float(pts[0][0]), float(pts[0][1]), float(pts[0][2]))
	var b := px_to_world(float(pts[1][0]), float(pts[1][1]), float(pts[1][2]))
	var c := px_to_world(float(pts[2][0]), float(pts[2][1]), float(pts[2][2]))
	var n := (b - a).cross(c - a)
	if n.length_squared() < 1e-10:
		return hint
	n = n.normalized()
	return -n if n.dot(hint) < 0.0 else n

## Extruded box over the 2D rect [x0,x1] x [y0,y1] (map px) with a front face `h` px tall: the top face shows
## the upper part of the art, the front face the bottom `h` rows.
func _emit_box(x0: float, y0: float, x1: float, y1: float, h: float) -> void:
	h = clampf(h, 0.0, y1 - y0)
	var zb := y0 + h   # back edge of the footprint
	var zf := y1       # front edge
	if zf - zb > 0.01:
		_quad([[x0, zb, h], [x1, zb, h], [x1, zf, h], [x0, zf, h]], Vector3.UP)
	if h > 0.01:
		_quad([[x0, zf, h], [x1, zf, h], [x1, zf, 0.0], [x0, zf, 0.0]], Vector3.BACK)
		if zf - zb > 0.01:
			_quad([[x0, zb, h], [x0, zf, h], [x0, zf, 0.0], [x0, zb, 0.0]], Vector3.LEFT, x0 + 0.5)
			_quad([[x1, zf, h], [x1, zb, h], [x1, zb, 0.0], [x1, zf, 0.0]], Vector3.RIGHT, x1 - 0.5)

func _emit_box_sprite(b: Dictionary) -> void:
	var x0 := float(b.sx)
	var y0 := float(b.sy)
	_emit_box(x0, y0, x0 + float(b.w), y0 + float(b.h), float(b.get("hgt", 8)))

func _emit_cellbox(b: Dictionary, cx: float, cy: float) -> void:
	var x0 := maxf(cx, float(b.sx))
	var y0 := maxf(cy - 8.0, float(b.sy))
	var x1 := minf(cx + 16.0, float(b.sx) + float(b.w))
	var y1 := minf(cy + 16.0, float(b.sy) + float(b.h))
	if x1 <= x0 or y1 <= y0:
		return
	_emit_box(x0, y0, x1, y1, minf(float(b.get("hgt", 6)), y1 - y0))

## A thin standing sprite (sign, fence, statue, plant...): a vertical plane at depth z showing the whole sprite.
func _emit_card(b: Dictionary) -> void:
	var x0 := float(b.sx)
	var x1 := x0 + float(b.w)
	var zc := float(b.get("z", float(b.sy) + float(b.h) - 1.0)) + 1.0
	var top := zc - float(b.sy)
	_quad([[x0, zc, top], [x1, zc, top], [x1, zc, 0.0], [x0, zc, 0.0]], Vector3.BACK)

func _emit_terrace(b: Dictionary) -> void:
	var cells := {}
	for c in b.get("cells", []):
		cells[Vector2i(int(c[0]), int(c[1]))] = true
	var cols := {}
	for k in cells.keys():
		var v: Vector2i = k
		if not cols.has(v.x):
			cols[v.x] = []
		cols[v.x].append(v.y)
	for x in cols.keys():
		var ys: Array = cols[x]
		ys.sort()
		var a: int = ys[0]
		var prev: int = ys[0]
		for i in range(1, ys.size() + 1):
			if i < ys.size() and int(ys[i]) == prev + 1:
				prev = ys[i]
				continue
			var run := (prev - a + 1) * 16.0
			_emit_box(float(x) * 16.0, float(a) * 16.0, float(x) * 16.0 + 16.0, float(prev + 1) * 16.0, minf(10.0, run))
			if i < ys.size():
				a = ys[i]
				prev = ys[i]

## A whole building: walls box + pitched (gable) or flat roof, chimney as a small standing card.
func _emit_house(b: Dictionary) -> void:
	var x0 := float(b.x0) - 1.0
	var x1 := float(b.x1) + 1.0
	var rx0 := float(b.x0) - 2.0
	var rx1 := float(b.x1) + 2.0
	var roof_top := float(b.roofTop) - 1.0
	var wall_top := float(b.wallTop)
	var zf := float(b.wallBottom) + 1.0
	var hw := zf - wall_top               # wall height (px of art)
	var rh := wall_top - roof_top         # roof rows on screen
	if bool(b.get("flat", false)):
		var zb := roof_top + hw
		# front + sides
		_quad([[x0, zf, hw], [x1, zf, hw], [x1, zf, 0.0], [x0, zf, 0.0]], Vector3.BACK)
		_quad([[x0, zb, hw], [x0, zf, hw], [x0, zf, 0.0], [x0, zb, 0.0]], Vector3.LEFT, x0 + 1.5)
		_quad([[x1, zf, hw], [x1, zb, hw], [x1, zb, 0.0], [x1, zf, 0.0]], Vector3.RIGHT, x1 - 1.5)
		# flat roof (overhangs the walls by a pixel each side)
		_quad([[rx0, zb, hw], [rx1, zb, hw], [rx1, zf, hw], [rx0, zf, hw]], Vector3.UP)
		return
	var d := rh * 0.7                      # building depth behind the front wall (px)
	var e := 3.0                           # eave overhang toward the camera
	var zr := zf - d * 0.5                 # ridge
	var hr := zr - roof_top                # ridge height so that it projects onto the roof's top row
	var zb2 := zf - d
	# walls
	_quad([[x0, zf, hw], [x1, zf, hw], [x1, zf, 0.0], [x0, zf, 0.0]], Vector3.BACK)
	_quad([[x0, zb2, hw], [x0, zf, hw], [x0, zf, 0.0], [x0, zb2, 0.0]], Vector3.LEFT, x0 + 1.5)
	_quad([[x1, zf, hw], [x1, zb2, hw], [x1, zb2, 0.0], [x1, zf, 0.0]], Vector3.RIGHT, x1 - 1.5)
	# gable ends
	_tri([[x0, zf, hw], [x0, zr, hr], [x0, zb2, hw]], Vector3.LEFT, x0 + 2.5)
	_tri([[x1, zb2, hw], [x1, zr, hr], [x1, zf, hw]], Vector3.RIGHT, x1 - 2.5)
	# front slope: from the eave (projects onto wall_top) up to the ridge (projects onto roof_top)
	var slope_n := Vector3(0, 1, 1)
	_quad([[rx0, zr, hr], [rx1, zr, hr], [rx1, zf + e, hw + e], [rx0, zf + e, hw + e]], slope_n)
	# back slope (mostly hidden behind the front one)
	_quad([[rx1, zr, hr], [rx0, zr, hr], [rx0, zb2 - e, hw + e], [rx1, zb2 - e, hw + e]], Vector3(0, 1, -1))
	# chimney: a standing card rooted on the front slope
	if b.has("chimney"):
		var c: Array = b.chimney
		var cx := float(c[0])
		var cy := float(c[1])
		var v_base := cy + 9.0
		# point on the front slope whose projection is v_base: z - h(z) = v_base with h linear eave->ridge
		var za := zf + e
		var ha := hw + e
		var t := clampf(((za - ha) - v_base) / ((za - ha) - (zr - hr)), 0.0, 1.0)
		var zc := lerpf(za, zr, t)
		var hc := lerpf(ha, hr, t)
		var top := hc + 10.0
		_quad([[cx - 1.0, zc, top], [cx + 7.0, zc, top], [cx + 7.0, zc, hc], [cx - 1.0, zc, hc]], Vector3.BACK)
