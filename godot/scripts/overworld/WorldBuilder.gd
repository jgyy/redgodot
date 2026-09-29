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
var smoke_points: Array = []   # world position of every chimney top (TileKit.build_smoke)
var atlas_img: Image = null   # the atlas pixels (to pick trim colours that belong to each building)
const NEUTRAL := 0.8   # textured faces multiply the atlas by COLOR.rgb / NEUTRAL (world.gdshader): 0.8 = unchanged

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
func build_objects(mat: ShaderMaterial, hide_cells: Array = []) -> MeshInstance3D:
	_st = SurfaceTool.new()
	_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	smoke_points.clear()
	var n := 0
	for b in bake.get("blocks", []):
		_cur = b
		if PropKit.replaces(String(b.get("lbl", ""))):
			continue   # drawn as a real 3D prop (PropKit)
		if not hide_cells.is_empty() and _covers_hidden(b, hide_cells):
			continue
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

## A small object block (card / box / furniture) standing on a cell a script changed: it's gone.
func _covers_hidden(b: Dictionary, cells: Array) -> bool:
	var t := String(b.get("t", ""))
	if t == "house" or t == "walls" or t == "terrace":
		return false
	var bx0 := float(b.sx)
	var bx1 := bx0 + float(b.w)
	var by1 := float(b.sy) + float(b.h)
	for c in cells:
		var cell: Vector2i = c
		var px := float(cell.x + mx) * 16.0
		var py := float(cell.y + my) * 16.0
		# the object's foot (bottom rows) lies in the cell
		if bx0 < px + 16.0 and bx1 > px and by1 > py and by1 <= py + 17.0:
			return true
	return false

# ---------------------------------------------------------------- primitives
func _uv(px: float, pz: float, hpx: float) -> Vector2:
	var sx := float(_cur.get("sx", 0)) - float(_cur.get("ax", 0))
	var sy := float(_cur.get("sy", 0)) - float(_cur.get("ay", 0))
	return Vector2((px - sx) / atlas_size.x, (pz - hpx - sy) / atlas_size.y)

## One quad; corners are map-px points [x, z, h]. uv_col: optional column to sample for faces seen edge-on.
## shades: optional per-corner brightness (1 = the art as painted) for baked ambient occlusion.
func _quad(pts: Array, normal: Vector3, uv_col: float = -1.0, shades: Array = []) -> void:
	normal = _true_normal(pts, normal)
	var tri := [0, 1, 2, 0, 2, 3]
	for i in tri:
		var p: Array = pts[i]
		var sh: float = float(shades[i]) if shades.size() > i else 1.0
		_st.set_color(Color(NEUTRAL * sh, NEUTRAL * sh, NEUTRAL * sh, 1.0))
		_st.set_normal(normal)
		var uvx: float = float(p[0]) if uv_col < 0.0 else uv_col
		_st.set_uv(_uv(uvx, float(p[1]), float(p[2])))
		_st.add_vertex(px_to_world(float(p[0]), float(p[1]), float(p[2])))

func _tri(pts: Array, normal: Vector3, uv_col: float = -1.0, shades: Array = []) -> void:
	normal = _true_normal(pts, normal)
	for i in range(3):
		var p: Array = pts[i]
		var sh: float = float(shades[i]) if shades.size() > i else 1.0
		_st.set_color(Color(NEUTRAL * sh, NEUTRAL * sh, NEUTRAL * sh, 1.0))
		_st.set_normal(normal)
		var uvx: float = float(p[0]) if uv_col < 0.0 else uv_col
		_st.set_uv(_uv(uvx, float(p[1]), float(p[2])))
		_st.add_vertex(px_to_world(float(p[0]), float(p[1]), float(p[2])))

## Flat-coloured trim quad (fascia, ridge cap, sills, steps ...): vertex alpha < 1 tells the shader to use the vertex
## colour instead of the atlas. `shade` scales the colour (baked light).
func _solid(pts: Array, normal: Vector3, col: Color, shade: float = 1.0, alpha: float = 0.5) -> void:
	normal = _true_normal(pts, normal)
	var c := Color(col.r * shade, col.g * shade, col.b * shade, alpha)
	for i in ([0, 1, 2, 0, 2, 3] if pts.size() == 4 else [0, 1, 2]):
		var p: Array = pts[i]
		_st.set_color(c)
		_st.set_normal(normal)
		_st.set_uv(Vector2.ZERO)
		_st.add_vertex(px_to_world(float(p[0]), float(p[1]), float(p[2])))

## Trim quad with one colour per corner (baked AO gradients); alpha 0.04 * id selects a procedural material.
func _solid_v(pts: Array, normal: Vector3, cols: Array, alpha: float = 0.5) -> void:
	normal = _true_normal(pts, normal)
	for i in ([0, 1, 2, 0, 2, 3] if pts.size() == 4 else [0, 1, 2]):
		var p: Array = pts[i]
		var cc: Color = cols[i]
		_st.set_color(Color(cc.r, cc.g, cc.b, alpha))
		_st.set_normal(normal)
		_st.set_uv(Vector2.ZERO)
		_st.add_vertex(px_to_world(float(p[0]), float(p[1]), float(p[2])))

## A solid trim box between map-px corners lo=(x,z,h) and hi (h up), five visible faces.
func _solid_box(x0: float, z0: float, h0: float, x1: float, z1: float, h1: float, col: Color) -> void:
	_solid([[x0, z0, h1], [x1, z0, h1], [x1, z1, h1], [x0, z1, h1]], Vector3.UP, col, 1.1)               # top
	_solid([[x0, z1, h1], [x1, z1, h1], [x1, z1, h0], [x0, z1, h0]], Vector3.BACK, col, 0.86)            # front (toward the camera)
	_solid([[x0, z0, h1], [x0, z1, h1], [x0, z1, h0], [x0, z0, h0]], Vector3.LEFT, col, 0.98)
	_solid([[x1, z1, h1], [x1, z0, h1], [x1, z0, h0], [x1, z1, h0]], Vector3.RIGHT, col, 0.7)

## Ambient-occlusion grid over a vertical or sloped quad: corners tl, tr, br, bl ([x, z, h]) bilinearly subdivided
## nx x ny; shade_fn(u, v) -> brightness, u along tl->tr, v down tl->bl.
func _grid_quad(tl: Array, tr: Array, br: Array, bl: Array, normal: Vector3, nx: int, ny: int, shade_fn: Callable, uv_col: float = -1.0, uv_u: Array = [], uv_v: Array = []) -> void:
	var us: Array = uv_u if not uv_u.is_empty() else _lin(nx)
	var vs: Array = uv_v if not uv_v.is_empty() else _lin(ny)
	for j in range(vs.size() - 1):
		for i in range(us.size() - 1):
			var pts: Array = []
			var sh: Array = []
			for c in [[us[i], vs[j]], [us[i + 1], vs[j]], [us[i + 1], vs[j + 1]], [us[i], vs[j + 1]]]:
				var u: float = c[0]
				var v: float = c[1]
				var top := _lerp3(tl, tr, u)
				var bot := _lerp3(bl, br, u)
				pts.append(_lerp3(top, bot, v))
				sh.append(float(shade_fn.call(u, v)))
			_quad(pts, normal, uv_col, sh)

func _lin(n: int) -> Array:
	var a: Array = []
	for i in range(n + 1):
		a.append(float(i) / float(n))
	return a

func _lerp3(a: Array, b: Array, t: float) -> Array:
	return [lerpf(float(a[0]), float(b[0]), t), lerpf(float(a[1]), float(b[1]), t), lerpf(float(a[2]), float(b[2]), t)]

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

## Colour of the atlas pixel under map-px point (x, z) of the block being emitted (or `fallback`).
func _atlas_col(x: float, z: float, fallback: Color) -> Color:
	if atlas_img == null:
		return fallback
	var ax := int(x) - int(_cur.get("sx", 0)) + int(_cur.get("ax", 0))
	var ay := int(z) - int(_cur.get("sy", 0)) + int(_cur.get("ay", 0))
	if ax < 0 or ay < 0 or ax >= atlas_img.get_width() or ay >= atlas_img.get_height():
		return fallback
	var c := atlas_img.get_pixel(ax, ay)
	return c if c.a > 0.5 else fallback

static func _shade_col(c: Color, k: float) -> Color:
	return Color(clampf(c.r * k, 0.0, 1.0), clampf(c.g * k, 0.0, 1.0), clampf(c.b * k, 0.0, 1.0), 1.0)

## Extruded box over the 2D rect [x0,x1] x [y0,y1] (map px) with a front face `h` px tall: the top face shows
## the upper part of the art, the front face the bottom `h` rows. The top-front edge is bevelled (a 45 degree
## chamfer that reads as a lit rim), like the top-right/left edges when the box has real depth.
func _emit_box(x0: float, y0: float, x1: float, y1: float, h: float) -> void:
	h = clampf(h, 0.0, y1 - y0)
	var zb := y0 + h   # back edge of the footprint
	var zf := y1       # front edge
	var c := minf(1.6, h * 0.25)
	var deep := zf - zb > 0.01
	var rim := 1.08
	if deep:
		var ztop := zf - (c if h > 3.0 else 0.0)
		if ztop - zb > 0.01:
			_quad([[x0, zb, h], [x1, zb, h], [x1, ztop, h], [x0, ztop, h]], Vector3.UP)
		if h > 3.0:
			# chamfer
			_quad([[x0, ztop, h], [x1, ztop, h], [x1, zf, h - c], [x0, zf, h - c]], Vector3(0, 1, 1), -1.0, [rim, rim, 1.0, 1.0])
	if h > 0.01:
		var hf := h - (c if (deep and h > 3.0) else 0.0)
		_quad([[x0, zf, hf], [x1, zf, hf], [x1, zf, 0.0], [x0, zf, 0.0]], Vector3.BACK)
		if deep:
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

## Baked ambient occlusion of a wall face: darker under the eaves, in the corners and at the foot.
func _wall_shade(u: float, v: float, w_px: float, h_px: float) -> float:
	var s := 1.0
	s *= lerpf(0.70, 1.0, smoothstep(0.0, 1.0, clampf(v * h_px / 5.0, 0.0, 1.0)))
	var edge := minf(u * w_px, (1.0 - u) * w_px)
	s *= lerpf(0.88, 1.0, smoothstep(0.0, 1.0, clampf(edge / 3.0, 0.0, 1.0)))
	return s

func _breaks(len_px: float, marks: Array) -> Array:
	var out: Array = [0.0]
	for m in marks:
		var f: float = float(m) / len_px
		if f > 0.02 and f < 0.98:
			out.append(f)
	out.append(1.0)
	return out

## A whole building: walls (with baked AO), pitched (gable) or flat roof with real eave fascia, ridge cap and
## parapet, a 3D chimney, window sills and door steps.
func _emit_house(b: Dictionary) -> void:
	if BuildingBuilder.supported(b, self):
		BuildingBuilder.new(self, b).emit()
		return
	var x0 := float(b.x0) - 1.0
	var x1 := float(b.x1) + 1.0
	var rx0 := float(b.x0) - 2.0
	var rx1 := float(b.x1) + 2.0
	var roof_top := float(b.roofTop) - 1.0
	var wall_top := float(b.wallTop)
	var zf := float(b.wallBottom) + 1.0
	var hw := zf - wall_top               # wall height (px of art)
	var rh := wall_top - roof_top         # roof rows on screen
	var flat := bool(b.get("flat", false))
	var W := x1 - x0
	var roof_col := _atlas_col((x0 + x1) * 0.5, roof_top + rh * 0.45, Color("#a03828"))
	var front_v := _breaks(hw, [4.0, 9.0])
	var front_u := _breaks(W, [3.0, W - 3.0])
	var front_shade := func(u: float, v: float) -> float: return _wall_shade(u, v, W, hw)
	if flat:
		var zb := roof_top + hw
		var D := zf - zb
		var side_u := _breaks(D, [3.0, D - 3.0])
		_grid_quad([x0, zf, hw], [x1, zf, hw], [x1, zf, 0.0], [x0, zf, 0.0], Vector3.BACK, 1, 1, front_shade, -1.0, front_u, front_v)
		_grid_quad([x0, zb, hw], [x0, zf, hw], [x0, zf, 0.0], [x0, zb, 0.0], Vector3.LEFT, 1, 1,
			func(u: float, v: float) -> float: return _wall_shade(u, v, D, hw) * 0.96, x0 + 1.5, side_u, front_v)
		_grid_quad([x1, zf, hw], [x1, zb, hw], [x1, zb, 0.0], [x1, zf, 0.0], Vector3.RIGHT, 1, 1,
			func(u: float, v: float) -> float: return _wall_shade(u, v, D, hw), x1 - 1.5, side_u, front_v)
		# flat roof (overhangs the walls by a pixel each side)
		_quad([[rx0, zb, hw], [rx1, zb, hw], [rx1, zf, hw], [rx0, zf, hw]], Vector3.UP)
		# parapet: a raised rim around the roof, in the roof edge's own colour
		var rim_col := _shade_col(_atlas_col(rx0 + 4.0, roof_top + 3.0, roof_col), 1.12)
		var t := 1.2
		var ph := 1.5
		_solid_box(rx0, zf - t, hw, rx1, zf + 0.6, hw + ph, rim_col)      # front lip
		_solid_box(rx0, zb, hw, rx0 + t, zf - t, hw + ph, rim_col)         # left
		_solid_box(rx1 - t, zb, hw, rx1, zf - t, hw + ph, rim_col)         # right
		_solid_box(rx0 + t, zb - 0.4, hw, rx1 - t, zb + t, hw + ph, rim_col)   # back
	else:
		var d := rh * 0.7                      # building depth behind the front wall (px)
		var e := 3.0                           # eave overhang toward the camera
		var zr := zf - d * 0.5                 # ridge
		var hr := zr - roof_top                # ridge height so that it projects onto the roof's top row
		var zb2 := zf - d
		var D2 := zf - zb2
		var side_u2 := _breaks(D2, [3.0, D2 - 3.0])
		# walls
		_grid_quad([x0, zf, hw], [x1, zf, hw], [x1, zf, 0.0], [x0, zf, 0.0], Vector3.BACK, 1, 1, front_shade, -1.0, front_u, front_v)
		_grid_quad([x0, zb2, hw], [x0, zf, hw], [x0, zf, 0.0], [x0, zb2, 0.0], Vector3.LEFT, 1, 1,
			func(u: float, v: float) -> float: return _wall_shade(u, v, D2, hw) * 0.96, x0 + 1.5, side_u2, front_v)
		_grid_quad([x1, zf, hw], [x1, zb2, hw], [x1, zb2, 0.0], [x1, zf, 0.0], Vector3.RIGHT, 1, 1,
			func(u: float, v: float) -> float: return _wall_shade(u, v, D2, hw), x1 - 1.5, side_u2, front_v)
		# gable ends (darker toward the eaves, they sit under the roof edge)
		_tri([[x0, zf, hw], [x0, zr, hr], [x0, zb2, hw]], Vector3.LEFT, x0 + 2.5, [0.84, 1.0, 0.84])
		_tri([[x1, zb2, hw], [x1, zr, hr], [x1, zf, hw]], Vector3.RIGHT, x1 - 2.5, [0.84, 1.0, 0.84])
		# front slope: from the eave (projects onto wall_top) up to the ridge (projects onto roof_top)
		var slope_n := Vector3(0, 1, 1)
		_quad([[rx0, zr, hr], [rx1, zr, hr], [rx1, zf + e, hw + e], [rx0, zf + e, hw + e]], slope_n, -1.0, [1.05, 1.05, 0.94, 0.94])
		# back slope (mostly hidden behind the front one)
		_quad([[rx1, zr, hr], [rx0, zr, hr], [rx0, zb2 - e, hw + e], [rx1, zb2 - e, hw + e]], Vector3(0, 1, -1))
		# eave board (fascia) hanging under the front edge of the roof, and the ridge cap
		var fas := _shade_col(roof_col, 0.5)
		_solid([[rx0, zf + e, hw + e], [rx1, zf + e, hw + e], [rx1, zf + e, hw + e - 1.5], [rx0, zf + e, hw + e - 1.5]], Vector3.BACK, fas, 0.95)
		_solid_box(rx0 - 0.3, zr - 0.6, hr - 0.4, rx1 + 0.3, zr + 0.6, hr + 0.6, _shade_col(roof_col, 1.32))
		# chimney: front face is the baked sprite, the rest is real geometry
		if b.has("chimney"):
			var c: Array = b.chimney
			var cx := float(c[0])
			var cy := float(c[1])
			var v_base := cy + 9.0
			var za := zf + e
			var ha := hw + e
			var t2 := clampf(((za - ha) - v_base) / ((za - ha) - (zr - hr)), 0.0, 1.0)
			var zc := lerpf(za, zr, t2)
			var hc := lerpf(ha, hr, t2)
			var top := hc + 10.0
			var brick := _atlas_col(cx + 3.0, cy + 4.0, Color("#a4523c"))
			_quad([[cx - 1.0, zc, top], [cx + 7.0, zc, top], [cx + 7.0, zc, hc], [cx - 1.0, zc, hc]], Vector3.BACK)
			var cd := 3.2
			_solid([[cx - 1.0, zc - cd, top], [cx - 1.0, zc, top], [cx - 1.0, zc, hc], [cx - 1.0, zc - cd, hc]], Vector3.LEFT, _shade_col(brick, 1.0), 0.95)
			_solid([[cx + 7.0, zc, top], [cx + 7.0, zc - cd, top], [cx + 7.0, zc - cd, hc], [cx + 7.0, zc, hc]], Vector3.RIGHT, _shade_col(brick, 0.72))
			_solid_box(cx - 1.4, zc - cd - 0.4, top - 0.2, cx + 7.4, zc + 0.5, top + 0.9, _shade_col(brick, 0.9))   # stone cap
			smoke_points.append(px_to_world(cx + 3.0, zc - cd * 0.5, top + 2.0))
	_emit_house_details(x0, x1, zf, wall_top, hw, roof_col, String(b.get("type", "house")))

## Window sills and door steps found from the label grid + the sprite's own pixels.
func _emit_house_details(x0: float, x1: float, zf: float, wall_top: float, hw: float, roof_col: Color, btype: String) -> void:
	var legend: Array = bake.get("legend", [])
	var labels: Array = bake.get("labels", [])
	var cw := int(bake.get("cw", 0))
	var ch := int(bake.get("ch", 0))
	var win := legend.find("window")
	var door := legend.find("door")
	if labels.is_empty():
		return
	var cx0 := int(floor(x0 / 16.0))
	var cx1 := int(floor((x1 - 0.5) / 16.0))
	var cy0 := int(floor((wall_top - 6.0) / 16.0))
	var cy1 := int(floor((zf - 1.0) / 16.0))
	for cy in range(maxi(cy0, 0), mini(cy1 + 1, ch)):
		for cx in range(maxi(cx0, 0), mini(cx1 + 1, cw)):
			var li := int(labels[cy * cw + cx])
			var px := float(cx) * 16.0
			var py := float(cy) * 16.0
			if li == win and win >= 0:
				var si := _sill_info(px, py)
				if not si.is_empty():
					var r: int = si[0]
					var ht := zf - (py + float(r))
					if ht > 2.0 and ht <= hw:
						var sc := _atlas_col(px + 8.0, py + float(r), Color("#f0ece4"))
						_solid_box(px + 1.4, zf, ht - 0.9, px + 14.6, zf + 1.3, ht + 0.1, _shade_col(sc, 0.98))
						if btype == "house":
							# shutters flank a window only on the building's outer sides (not between two windows)
							var shut := _shade_col(roof_col, 0.85)
							var left_free := cx == 0 or int(labels[cy * cw + cx - 1]) != win
							var right_free := cx == cw - 1 or int(labels[cy * cw + cx + 1]) != win
							if left_free:
								_solid_box(px + float(si[1]) - 3.0, zf, ht - 0.6, px + float(si[1]) - 0.8, zf + 0.9, ht + 8.4, shut)
							if right_free:
								_solid_box(px + float(si[2]) + 1.8, zf, ht - 0.6, px + float(si[2]) + 4.0, zf + 0.9, ht + 8.4, shut)
			elif li == door and door >= 0 and absf(py + 16.0 - (zf - 1.0)) <= 1.5:
				var sc2 := _atlas_col(px + 8.0, py + 15.0, Color("#b8bccb"))
				_solid_box(px + 3.0, zf, 0.0, px + 13.0, zf + 1.8, 1.0, _shade_col(sc2, 1.0))

## [row, x_first, x_last] of the sill painted in a window cell (a run of white bounded by dark outline), or [].
func _sill_info(px: float, py: float) -> Array:
	if atlas_img == null:
		return []
	for r in range(6, 16):
		var run := 0
		var best := 0
		var best_end := 0
		for x in range(1, 15):
			var c := _atlas_pix(px + float(x), py + float(r))
			if _is_white(c):
				run += 1
				if run > best:
					best = run
					best_end = x
			else:
				run = 0
		if best >= 9:
			var l := _atlas_pix(px, py + float(r))
			var rr := _atlas_pix(px + 15.0, py + float(r))
			# the siding highlight also runs edge to edge; a sill stops short of the cell edges
			if not (_is_white(l) and _is_white(rr)):
				return [r, best_end - best + 1, best_end]
	return []

static func _is_white(c: Color) -> bool:
	return c.a > 0.5 and c.r > 0.86 and c.g > 0.86 and c.b > 0.84

func _atlas_pix(x: float, z: float) -> Color:
	var ax := int(x) - int(_cur.get("sx", 0)) + int(_cur.get("ax", 0))
	var ay := int(z) - int(_cur.get("sy", 0)) + int(_cur.get("ay", 0))
	if ax < 0 or ay < 0 or ax >= atlas_img.get_width() or ay >= atlas_img.get_height():
		return Color(0, 0, 0, 0)
	return atlas_img.get_pixel(ax, ay)
