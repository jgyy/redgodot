class_name BuildingBuilder
extends RefCounted
## Real 3D buildings for upstream's house blocks (types house / big / center / gym / mart).
##
## The baked sprite is used as a *colour and layout reference* only: roof, wall, trim and door colours are sampled from
## the building's own atlas pixels (so red / blue / green roofs and every wall tone stay faithful), the windows, doors
## and signs are found from the label grid + the sprite's glass pixels, and everything else is built here:
##  - hip roof with a true overhang, fascia boards, modelled shingle rows (lip + shadow riser per row, offset joints from
##    world.gdshader's roof pattern), hip caps, ridge cap, dormers, a 3D chimney with smoke, the Poke Ball emblem
##  - walls with plinth, corner posts, frieze / string courses and a procedural material (clapboard, brick, ashlar,
##    panels, plaster) laid on the 2D-art pixel grid
##  - Blender-modelled parts (pipeline/blender/env_buildings.py -> assets/models/world/bld_*.glb): recessed windows with
##    frames, sills, lintels and gradient glass, shutters, doors with steps / hinges / handles / doorbells, glass doors,
##    awnings, gym pillars, lanterns, dormers, chimney
##  - sign boards (Center / Mart / Gym plates keep the sprite's own lettering as a texture) mounted on thick boards
## Flat 'big' buildings keep the sprite's roof top (vents, dishes) and get a cornice + parapet. Anything the sampler
## cannot make sense of falls back to WorldBuilder's older sprite-derived house.

const TYPES := ["house", "big", "center", "gym", "mart"]
const K_MID := 0.72     # neutral ramp value of a tintable part (env_buildings.py _GREY[2])

var wb: WorldBuilder
var b: Dictionary
var type := "house"
# geometry (map px; h = height above the ground)
var x0 := 0.0
var x1 := 0.0
var zf := 0.0
var wall_top := 0.0
var roof_top := 0.0
var hw := 0.0
var rh := 0.0
var depth := 0.0
var zb2 := 0.0
var flat := false
var W := 0.0
var e_ov := 3.4          # eave overhang toward the camera
var s_ov := 2.6          # side overhang
var he := 0.0
var zr := 0.0
var hr := 0.0
var rx0 := 0.0
var rx1 := 0.0
var xr0 := 0.0
var xr1 := 0.0
# colours
var wall_col := Color("#e8dcc0")
var roof_col := Color("#a03828")
var trim_col := Color("#6a4a34")
var door_col := Color("#8a5a3a")
var wall_pid := 3
var pal := {}
var windows: Array = []    # Rect2 glass rects (map px)

static func supported(blk: Dictionary, builder: WorldBuilder) -> bool:
	if OS.has_environment("BLD_LEGACY") or not TYPES.has(String(blk.get("type", ""))):
		return false
	if builder.atlas_img == null:
		return false
	for k in ["x0", "x1", "roofTop", "wallTop", "wallBottom"]:
		if not blk.has(k):
			return false
	return float(blk.wallBottom) - float(blk.wallTop) >= 8.0 and float(blk.x1) - float(blk.x0) >= 16.0 and PropKit.mesh("bld_window") != null

func _init(builder: WorldBuilder, blk: Dictionary) -> void:
	wb = builder
	b = blk
	type = String(blk.get("type", "house"))

func emit() -> void:
	_measure()
	_sample_palette()
	_walls()
	if flat:
		_flat_roof()
	else:
		_hip_roof()
	_openings()
	_chimney()

# ------------------------------------------------------------------ measurement + colours
func _measure() -> void:
	x0 = float(b.x0) - 1.0
	x1 = float(b.x1) + 1.0
	zf = float(b.wallBottom) + 1.0
	wall_top = float(b.wallTop)
	roof_top = float(b.roofTop) - 1.0
	hw = zf - wall_top
	rh = wall_top - roof_top
	flat = bool(b.get("flat", false))
	W = x1 - x0
	depth = rh if flat else rh * 0.7
	zb2 = zf - depth
	he = hw + e_ov
	zr = zf - depth * 0.5
	hr = zr - roof_top
	rx0 = x0 - s_ov
	rx1 = x1 + s_ov
	var inset := minf((zf + e_ov) - zr, (rx1 - rx0) * 0.5 - 0.5)
	xr0 = rx0 + inset
	xr1 = rx1 - inset

func _pix(x: float, z: float) -> Color:
	return wb._atlas_pix(x, z)

## Most frequent colour of the pixels in a map-px rect that pass `keep` (Callable Color -> bool).
func _mode(rx: float, ry: float, rw: float, rhh: float, keep: Callable, fallback: Color) -> Color:
	var counts := {}
	var best := 0
	var best_c := fallback
	for yy in range(int(ry), int(ry + rhh)):
		for xx in range(int(rx), int(rx + rw)):
			var c := _pix(float(xx), float(yy))
			if c.a < 0.5 or not bool(keep.call(c)):
				continue
			var key := (int(c.r * 255.0) << 16) | (int(c.g * 255.0) << 8) | int(c.b * 255.0)
			var n: int = int(counts.get(key, 0)) + 1
			counts[key] = n
			if n > best:
				best = n
				best_c = c
	return Color(best_c.r, best_c.g, best_c.b, 1.0)

static func _luma(c: Color) -> float:
	return c.r * 0.3 + c.g * 0.59 + c.b * 0.11

static func _mix(a: Color, c: Color, t: float) -> Color:
	return Color(lerpf(a.r, c.r, t), lerpf(a.g, c.g, t), lerpf(a.b, c.b, t), 1.0)

static func _k(c: Color, k: float) -> Color:
	return Color(clampf(c.r * k, 0.0, 1.0), clampf(c.g * k, 0.0, 1.0), clampf(c.b * k, 0.0, 1.0), 1.0)

func _sample_palette() -> void:
	var rx := x0 + 14.0
	var rw := maxf(8.0, W - 28.0)
	var rl := func(c: Color) -> bool: return _luma(c) > 0.27 and _luma(c) < 0.93
	roof_col = _mode(rx, roof_top + 3.0, rw, maxf(4.0, rh - 6.0), rl, roof_col)
	var wl := func(c: Color) -> bool: return _luma(c) > 0.3 and not (c.b > c.r + 0.1)
	wall_col = _mode(x0 + 3.0, wall_top + 3.0, W - 6.0, maxf(4.0, hw - 6.0), wl, wall_col)
	if type == "gym":
		wall_pid = 5
	elif type == "house":
		wall_pid = 3
	elif wall_col.r > wall_col.g * 1.28 and wall_col.r > wall_col.b * 1.4 and _luma(wall_col) < 0.62:
		wall_pid = 4
	elif type == "center":
		wall_pid = 7
	else:
		wall_pid = 6
	trim_col = _k(wall_col, 0.62)
	door_col = Color("#8a5a3a")
	pal = {11: wall_col, 12: roof_col, 13: trim_col, 14: door_col, 15: _k(roof_col, 0.85)}

# ------------------------------------------------------------------ parts (Blender glbs)
func _lin2srgb(c: float) -> float:
	return c * 12.92 if c <= 0.0031308 else 1.055 * pow(c, 1.0 / 2.4) - 0.055

## Instance a Blender building part: origin at map px (x, z), height h; scl in sprite units; palette override.
func _part(name: String, x: float, z: float, h: float, scl: Vector3 = Vector3.ONE, pal_over: Dictionary = {}, flip_x: bool = false) -> void:
	var mesh := PropKit.mesh(name)
	if mesh == null:
		return
	var arr := mesh.surface_get_arrays(0)
	var vs: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var cols: PackedColorArray = arr[Mesh.ARRAY_COLOR]
	var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
	if idx.is_empty():
		idx = PackedInt32Array(range(vs.size()))
	var origin := wb.px_to_world(x, z, h)
	var K := WorldData.K
	var sx := scl.x * (-1.0 if flip_x else 1.0)
	var p := pal.duplicate()
	for k in pal_over.keys():
		p[k] = pal_over[k]
	var i := 0
	while i + 2 < idx.size():
		var tri: Array = []
		for j in range(3):
			var v := vs[idx[i + j]]
			tri.append(origin + Vector3(v.x * sx, v.y * K * scl.y, v.z * scl.z))
		var n: Vector3 = ((tri[1] - tri[0]).cross(tri[2] - tri[0]))
		if flip_x:
			n = -n
		n = n.normalized() if n.length_squared() > 1e-12 else Vector3.UP
		for j in range(3):
			var jj := j if not flip_x else (0 if j == 0 else (2 if j == 1 else 1))
			var ci := idx[i + jj]
			var c := cols[ci] if cols.size() > ci else Color(0.7, 0.7, 0.7, 1.0)
			var col := Color(_lin2srgb(c.r), _lin2srgb(c.g), _lin2srgb(c.b), 1.0)
			if c.a < 0.99:
				var slot := int(floor(c.a * 16.0))
				var base: Color = p.get(slot, Color(0.6, 0.6, 0.6))
				var kk := col.r / K_MID
				col = Color(clampf(base.r * kk, 0.0, 1.0), clampf(base.g * kk, 0.0, 1.0), clampf(base.b * kk, 0.0, 1.0), 1.0)
			wb._st.set_color(Color(col.r, col.g, col.b, 0.5))
			wb._st.set_normal(n)
			wb._st.set_uv(Vector2.ZERO)
			wb._st.add_vertex(tri[jj])
		i += 3

# ------------------------------------------------------------------ walls
func _lerp3(a: Array, c: Array, t: float) -> Array:
	return wb._lerp3(a, c, t)

## Solid quad grid with baked AO shading (u along tl->tr, v down tl->bl) and a procedural material id.
func _gs(tl: Array, tr: Array, br: Array, bl: Array, normal: Vector3, us: Array, vs: Array, col: Color, pid: int, shade_fn: Callable) -> void:
	var alpha := 0.04 * float(pid) if pid > 0 else 0.5
	for j in range(vs.size() - 1):
		for i in range(us.size() - 1):
			var pts: Array = []
			var cs: Array = []
			for c in [[us[i], vs[j]], [us[i + 1], vs[j]], [us[i + 1], vs[j + 1]], [us[i], vs[j + 1]]]:
				var top := _lerp3(tl, tr, float(c[0]))
				var bot := _lerp3(bl, br, float(c[0]))
				pts.append(_lerp3(top, bot, float(c[1])))
				var s: float = float(shade_fn.call(float(c[0]), float(c[1])))
				cs.append(Color(col.r * s, col.g * s, col.b * s, 1.0))
			wb._solid_v(pts, normal, cs, alpha)

func _walls() -> void:
	var fv: Array = wb._breaks(hw, [4.0, 9.0])
	var fu: Array = wb._breaks(W, [3.0, W - 3.0])
	var fs := func(u: float, v: float) -> float: return wb._wall_shade(u, v, W, hw)
	_gs([x0, zf, hw], [x1, zf, hw], [x1, zf, 0.0], [x0, zf, 0.0], Vector3.BACK, fu, fv, wall_col, wall_pid, fs)
	var sd := maxf(depth, 4.0)
	var su: Array = wb._breaks(sd, [3.0, sd - 3.0])
	var ls := func(u: float, v: float) -> float: return wb._wall_shade(u, v, sd, hw) * 0.95
	var rs := func(u: float, v: float) -> float: return wb._wall_shade(u, v, sd, hw) * 0.82
	_gs([x0, zb2, hw], [x0, zf, hw], [x0, zf, 0.0], [x0, zb2, 0.0], Vector3.LEFT, su, fv, wall_col, wall_pid, ls)
	_gs([x1, zf, hw], [x1, zb2, hw], [x1, zb2, 0.0], [x1, zf, 0.0], Vector3.RIGHT, su, fv, wall_col, wall_pid, rs)
	# plinth (foundation) + its cap, corner posts, frieze under the eaves, string courses on tall walls
	var stone := _mix(_k(wall_col, 0.7), Color("#8a8ca4"), 0.45)
	wb._solid_box(x0 - 0.8, zb2, 0.0, x1 + 0.8, zf + 0.9, 3.2, stone)
	wb._solid_box(x0 - 1.1, zb2, 3.2, x1 + 1.1, zf + 1.2, 4.0, _k(stone, 1.18))
	var post := _k(wall_col, 0.78)
	for xs in [[x0 - 0.8, x0 + 2.2], [x1 - 2.2, x1 + 0.8]]:
		wb._solid_box(float(xs[0]), zf - 0.4, 4.0, float(xs[1]), zf + 0.8, hw - 2.6, post)
	wb._solid_box(x0 - 0.8, zf - 0.4, hw - 2.6, x1 + 0.8, zf + 1.0, hw, _k(wall_col, 0.86))
	if hw > 44.0:
		var py := wall_top
		while py < zf - 20.0:
			py += 16.0
			var h := zf - py
			if h > 12.0 and h < hw - 8.0:
				wb._solid_box(x0 - 0.4, zf - 0.2, h - 0.6, x1 + 0.4, zf + 0.8, h + 0.6, _k(wall_col, 0.84))

# ------------------------------------------------------------------ roofs
func _rows_quad(a0: Array, a1: Array, b1: Array, b0: Array, n: int, normal: Vector3, base: Color, sh: float, riser: bool, lift: float = 0.9) -> void:
	# a0->a1 = eave edge, b0->b1 = ridge edge; n shingle rows with a raised lower lip and a dark riser
	for k in range(n):
		var v0 := float(k) / float(n)
		var v1 := float(k + 1) / float(n)
		var l0 := _lerp3(a0, b0, v0)
		var r0 := _lerp3(a1, b1, v0)
		var l1 := _lerp3(a0, b0, v1)
		var r1 := _lerp3(a1, b1, v1)
		var l0h := [l0[0], l0[1], float(l0[2]) + lift]
		var r0h := [r0[0], r0[1], float(r0[2]) + lift]
		var tone := 0.9 + 0.13 * v1 + (0.02 if k % 2 == 0 else -0.02)
		var c := _k(base, tone * sh)
		wb._solid([l1, r1, r0h, l0h], normal, c, 1.0, 0.04 * float(1 + (k % 2)))
		if riser:
			wb._solid([l0h, r0h, r0, l0], Vector3.BACK, _k(base, 0.42), 1.0, 0.5)

func _hip_roof() -> void:
	var n := maxi(3, int(round(rh / 5.5)))
	var ze := zf + e_ov
	var a0 := [rx0, ze, he]
	var a1 := [rx1, ze, he]
	var b0 := [xr0, zr, hr]
	var b1 := [xr1, zr, hr]
	_rows_quad(a0, a1, b1, b0, n, Vector3(0, 1, 1), roof_col, 1.0, true)
	# side slopes (the left one is lit, like the sprite): rows parallel to the eave
	var lf := [rx0, ze, he]
	var lb := [rx0, zb2 - e_ov, he]
	wb._solid([lf, lb, b0], Vector3(-1, 1, 0), _k(roof_col, 1.1), 1.0, 0.04)
	var rf := [rx1, ze, he]
	var rb := [rx1, zb2 - e_ov, he]
	wb._solid([rb, rf, b1], Vector3(1, 1, 0), _k(roof_col, 0.78), 1.0, 0.08)
	# back slope (never seen from the game camera, but keeps the volume closed)
	wb._solid([b1, b0, [rx0, zb2 - e_ov, he], [rx1, zb2 - e_ov, he]], Vector3(0, 1, -1), _k(roof_col, 0.8))
	var dark := _k(roof_col, 0.5)
	var cap := _k(roof_col, 1.3)
	# fascia boards around the eaves + drip edge
	wb._solid([[rx0, ze, he], [rx1, ze, he], [rx1, ze, he - 2.4], [rx0, ze, he - 2.4]], Vector3.BACK, dark)
	wb._solid([[rx0, ze, he], [rx0, zb2 - e_ov, he], [rx0, zb2 - e_ov, he - 2.4], [rx0, ze, he - 2.4]], Vector3.LEFT, _k(dark, 1.1))
	wb._solid([[rx1, zb2 - e_ov, he], [rx1, ze, he], [rx1, ze, he - 2.4], [rx1, zb2 - e_ov, he - 2.4]], Vector3.RIGHT, _k(dark, 0.8))
	wb._solid_box(rx0 - 0.3, ze - 0.2, he - 0.5, rx1 + 0.3, ze + 0.7, he + 0.5, _k(dark, 1.5))
	# hip caps and ridge cap
	for pair in [[a0, b0, -1.0], [a1, b1, 1.0]]:
		var pa: Array = pair[0]
		var pb: Array = pair[1]
		var sx: float = pair[2]
		wb._solid([[float(pb[0]) - 0.9, pb[1], float(pb[2]) + 0.8], [float(pb[0]) + 0.9, pb[1], float(pb[2]) + 0.8],
			[float(pa[0]) + 0.9, pa[1], float(pa[2]) + 0.8], [float(pa[0]) - 0.9, pa[1], float(pa[2]) + 0.8]], Vector3.UP, cap, 0.92 if sx < 0.0 else 0.72)
	if xr1 > xr0 + 0.5:
		wb._solid_box(xr0 - 0.8, zr - 1.0, hr - 0.3, xr1 + 0.8, zr + 1.0, hr + 1.1, cap)
	_dormer()
	_emblem()

func _flat_roof() -> void:
	var zb := roof_top + hw
	var fx0 := x0 - 1.5
	var fx1 := x1 + 1.5
	wb._quad([[fx0, zb, hw], [fx1, zb, hw], [fx1, zf + 0.4, hw], [fx0, zf + 0.4, hw]], Vector3.UP)   # the sprite's roof top (vents, dishes)
	var rim := _mix(_k(roof_col, 1.15), Color("#a8aac0"), 0.35)
	var t := 1.3
	var ph := 1.7
	wb._solid_box(fx0, zf - t, hw, fx1, zf + 0.7, hw + ph, rim)
	wb._solid_box(fx0, zb, hw, fx0 + t, zf - t, hw + ph, _k(rim, 0.9))
	wb._solid_box(fx1 - t, zb, hw, fx1, zf - t, hw + ph, _k(rim, 0.75))
	wb._solid_box(fx0 + t, zb - 0.4, hw, fx1 - t, zb + t, hw + ph, _k(rim, 0.85))
	# coping stones along the parapet top and a cornice below it
	wb._solid_box(fx0 - 0.3, zf - t - 0.2, hw + ph, fx1 + 0.3, zf + 0.9, hw + ph + 0.7, _k(rim, 1.2))
	wb._solid_box(fx0 - 0.4, zf - 0.5, hw - 3.2, fx1 + 0.4, zf + 1.6, hw - 0.2, _k(wall_col, 0.9))

# ------------------------------------------------------------------ roof extras
## Point on the front slope at fraction t (0 = eave, 1 = ridge) and x.
func _slope(t: float, x: float) -> Array:
	return [x, lerpf(zf + e_ov, zr, t), lerpf(he, hr, t)]

func _dormer() -> void:
	if type != "house" or W < 60.0 or PropKit.mesh("bld_dormer") == null:
		return
	var cx := (x0 + x1) * 0.5 + 6.0
	if b.has("chimney") and absf(cx - (float(b.chimney[0]) + 3.0)) < 20.0:
		cx = (x0 + x1) * 0.5 - 14.0
	var s := _slope(0.34, cx)
	_part("bld_dormer", float(s[0]), float(s[1]), float(s[2]) + 1.0, Vector3.ONE)

func _emblem() -> void:
	if type != "center":
		return
	# the sprite's Poke Ball: find the white pixels on the roof, redraw it as a disc lying on the slope
	var sx := 0.0
	var sy := 0.0
	var n := 0
	for yy in range(int(roof_top + 2), int(wall_top - 2)):
		for xx in range(int(x0 + 6), int(x1 - 6)):
			var c := _pix(float(xx), float(yy))
			if c.a > 0.5 and minf(c.r, minf(c.g, c.b)) > 0.93:
				sx += float(xx)
				sy += float(yy)
				n += 1
	if n < 10:
		return
	sx /= float(n)
	sy /= float(n)
	var t := clampf((wall_top - sy) / maxf(1.0, wall_top - roof_top), 0.05, 0.95)
	var s := _slope(t, sx)
	var dz := zr - (zf + e_ov)
	var dh := hr - he
	var L := sqrt(dz * dz + dh * dh)
	var screen_per_unit := absf(dz - dh) / L
	var rw := 5.2 * L / maxf(0.5, absf(dz - dh))
	var ru := 5.2
	var nrm := Vector3(0, 1, 1)
	var up := [0.0, 0.7, 0.7]          # lift off the slope (keeps the screen position)
	var pts := func(a: float, r: float) -> Array:
		return [float(s[0]) + cos(a) * ru * r, float(s[1]) + (dz / L) * sin(a) * rw * r + float(up[1]), float(s[2]) + (dh / L) * sin(a) * rw * r + float(up[2])]
	var segs := 20
	for i in range(segs):
		var a0 := TAU * float(i) / float(segs)
		var a1 := TAU * float(i + 1) / float(segs)
		var am := (a0 + a1) * 0.5
		# screen-up half is red, lower half white, a black band across the middle
		var yv := sin(am)
		var c := Color("#e04848") if yv > 0.16 else (Color("#f6f6fa") if yv < -0.16 else Color("#1b1a2e"))
		wb._solid([pts.call(0.0, 0.0), pts.call(a0, 1.0), pts.call(a1, 1.0)], nrm, c, 1.0)
		# outline ring
		var o0: Array = pts.call(a0, 1.0)
		var o1: Array = pts.call(a1, 1.0)
		var q0: Array = pts.call(a0, 1.18)
		var q1: Array = pts.call(a1, 1.18)
		wb._solid([o0, o1, q1, q0], nrm, Color("#1b1a2e"), 1.0)
	for i in range(10):     # centre button
		var a0 := TAU * float(i) / 10.0
		var a1 := TAU * float(i + 1) / 10.0
		var pp := func(a: float, r: float) -> Array:
			return [float(s[0]) + cos(a) * ru * r, float(s[1]) + (dz / L) * sin(a) * rw * r + 1.0, float(s[2]) + (dh / L) * sin(a) * rw * r + 1.0]
		wb._solid([pp.call(0.0, 0.0), pp.call(a0, 0.34), pp.call(a1, 0.34)], nrm, Color("#ffffff"), 1.0)

func _chimney() -> void:
	if not b.has("chimney") or flat:
		return
	var c: Array = b.chimney
	var cx := float(c[0])
	var cy := float(c[1])
	var v_base := cy + 9.0
	var za := zf + e_ov
	var t := clampf(((za - he) - v_base) / ((za - he) - (zr - hr)), 0.0, 1.0)
	var zc := lerpf(za, zr, t)
	var hc := lerpf(he, hr, t)
	var brick := wb._atlas_col(cx + 3.0, cy + 4.0, Color("#a4523c"))
	_part("bld_chimney", cx + 3.0, zc - 1.5, hc - 0.5, Vector3(8.0 / 6.0, 1.0, 1.0), {11: brick, 13: _k(brick, 1.35)})
	wb.smoke_points.append(wb.px_to_world(cx + 3.0, zc - 1.5, hc + 11.5))

# ------------------------------------------------------------------ windows, doors, signs
func _glass_rect(px: float, py: float) -> Rect2:
	var minx := 1e9
	var maxx := -1.0
	var miny := 1e9
	var maxy := -1.0
	var cnt := 0
	for yy in range(int(py) - 1, int(py) + 17):
		for xx in range(int(px), int(px) + 16):
			var c := _pix(float(xx), float(yy))
			if c.a > 0.5 and c.b > c.r + 0.1 and c.b > 0.35 and c.g < c.b:
				cnt += 1
				minx = minf(minx, float(xx))
				maxx = maxf(maxx, float(xx))
				miny = minf(miny, float(yy))
				maxy = maxf(maxy, float(yy))
	if cnt < 8 or maxx - minx < 3.0 or maxy - miny < 2.0:
		return Rect2(px + 3.0, py + 4.0, 10.0, 8.0)
	return Rect2(minx, miny, maxx - minx + 1.0, maxy - miny + 1.0)

func _openings() -> void:
	var legend: Array = wb.bake.get("legend", [])
	var labels: Array = wb.bake.get("labels", [])
	var cw := int(wb.bake.get("cw", 0))
	var ch := int(wb.bake.get("ch", 0))
	if labels.is_empty():
		return
	var cx0 := maxi(0, int(floor(x0 / 16.0)))
	var cx1 := mini(cw - 1, int(floor((x1 - 0.5) / 16.0)))
	var cy0 := maxi(0, int(floor((wall_top - 4.0) / 16.0)))
	var cy1 := mini(ch - 1, int(floor((zf - 1.0) / 16.0)))
	var lab := func(cx: int, cy: int) -> String:
		if cx < 0 or cy < 0 or cx >= cw or cy >= ch:
			return ""
		return String(legend[int(labels[cy * cw + cx])])
	windows.clear()
	var doors: Array = []
	var signs: Array = []     # [label, px, py, cells]
	var trim_seen := false
	for cy in range(cy0, cy1 + 1):
		var cx := cx0
		while cx <= cx1:
			var l: String = lab.call(cx, cy)
			var px := float(cx) * 16.0
			var py := float(cy) * 16.0
			if l == "window" or l == "window_big":
				var r := _glass_rect(px, py)
				windows.append(r)
				if not trim_seen:
					trim_seen = true
					var fc := _pix(r.position.x - 1.0, r.position.y + r.size.y * 0.5)
					if fc.a > 0.5 and _luma(fc) < 0.75:
						trim_col = fc
						pal[13] = fc
				var wname := "bld_window_big" if l == "window_big" else "bld_window"
				var gw := 12.0 if l == "window_big" else 10.0
				var gh := 12.0 if l == "window_big" else 9.0
				var cols := 2.0
				_part(wname, r.position.x + r.size.x * 0.5, zf, zf - (r.position.y + r.size.y),
					Vector3(clampf(r.size.x / gw, 0.85, 1.2), clampf(r.size.y / gh, 0.8, 1.2), 1.0))
				cols += 0.0
			elif l == "door":
				doors.append(Vector2(px, py))
			elif l.begins_with("sign_"):
				var n := 1
				while cx + n <= cx1 and String(lab.call(cx + n, cy)) == l:
					n += 1
				signs.append([l, px, py, n])
				cx += n - 1
			cx += 1
	if type == "house":
		_shutters()
	for d in doors:
		var dv: Vector2 = d
		if absf(dv.y + 16.0 - (zf - 1.0)) <= 2.0:
			_door(dv.x, dv.y, lab, cx0, cx1)
	for s in signs:
		_sign(String(s[0]), float(s[1]), float(s[2]), int(s[3]))

func _shutters() -> void:
	for r in windows:
		var rr: Rect2 = r
		var left_free := true
		var right_free := true
		for o in windows:
			var orr: Rect2 = o
			if orr == rr or absf(orr.position.y - rr.position.y) > 6.0:
				continue
			if absf((orr.position.x + orr.size.x) - rr.position.x) < 9.0:
				left_free = false
			if absf(orr.position.x - (rr.position.x + rr.size.x)) < 9.0:
				right_free = false
		var hgt := zf - (rr.position.y + rr.size.y)
		var sc := Vector3(1.0, clampf((rr.size.y + 1.6) / 9.6, 0.5, 1.6), 1.0)
		if left_free:
			_part("bld_shutter", rr.position.x - 3.4, zf, hgt - 0.4, sc)
		if right_free:
			_part("bld_shutter", rr.position.x + rr.size.x + 3.4, zf, hgt - 0.4, sc)

func _door(px: float, py: float, lab: Callable, cx0: int, cx1: int) -> void:
	var cx := int(px / 16.0)
	var cy := int(py / 16.0)
	var glass_door := type == "center" or type == "mart"
	var dcx := px + 8.0
	# sample the door's own colour and horizontal extent from the sprite
	var minx := 1e9
	var maxx := -1.0
	var sumc := Color(0, 0, 0, 0)
	var cnt := 0
	for yy in range(int(py) - 1, int(py) + 16):
		for xx in range(int(px), int(px) + 16):
			var c := _pix(float(xx), float(yy))
			if c.a < 0.5:
				continue
			var brown := c.r > c.b + 0.14 and c.r < 0.75 and _luma(c) < 0.5 and c.r > c.g
			var gl := c.b > c.r + 0.1 and _luma(c) > 0.3
			if (glass_door and gl) or (not glass_door and brown):
				minx = minf(minx, float(xx))
				maxx = maxf(maxx, float(xx))
				sumc += c
				cnt += 1
	var wsc := 1.0
	if cnt >= 12 and maxx - minx > 4.0:
		dcx = (minx + maxx + 1.0) * 0.5
		wsc = clampf((maxx - minx + 1.0) / 10.0, 0.8, 1.25)
		if not glass_door:
			door_col = Color(sumc.r / cnt, sumc.g / cnt, sumc.b / cnt, 1.0)
			pal[14] = door_col
	var hsc := clampf(minf(14.0, hw - 4.0) / 14.0, 0.6, 1.0)
	_part("bld_glassdoor" if glass_door else "bld_door", dcx, zf, 0.0, Vector3(wsc, hsc, 1.0))
	var door_h := 14.0 * hsc
	var wl: String
	if glass_door:
		var trim_over := {13: _k(roof_col, 1.0)}
		# striped awning over the doors of Poke Centers / Marts
		_part("bld_awning", dcx, zf, door_h + 7.4, Vector3(1.3, 1.0, 0.85), trim_over)
	elif type == "gym":
		var lp: String = lab.call(cx - 1, cy)
		var rp: String = lab.call(cx + 1, cy)
		for side in [[-1.0, lp], [1.0, rp]]:
			if String(side[1]) == "wall":
				_part("bld_pillar", dcx + float(side[0]) * 10.2, zf, 0.0, Vector3(1.0, clampf((hw - 4.0) / 16.0, 0.5, 1.4), 1.0), {11: _k(wall_col, 1.12)})
	# a lantern on the wall beside the door where there is plain wall
	for side in [1.0, -1.0]:
		var nl: String = lab.call(cx + int(side), cy)
		if nl == "wall" and (type == "house" or type == "big" or type == "gym"):
			_part("bld_lamp", dcx + side * 10.4, zf, minf(8.0, hw - 6.0))
			break

## Sign plates keep the sprite's lettering / icon as a texture on a real board with a mounting bracket.
func _sign(l: String, px: float, py: float, cells: int) -> void:
	var bg := wall_col
	var minx := 1e9
	var maxx := -1.0
	var miny := 1e9
	var maxy := -1.0
	for yy in range(int(py), int(py) + 16):
		for xx in range(int(px) - 1, int(px) + 16 * cells + 1):
			var c := _pix(float(xx), float(yy))
			if c.a < 0.5:
				continue
			if absf(c.r - bg.r) + absf(c.g - bg.g) + absf(c.b - bg.b) > 0.5 or _luma(c) < 0.3:
				minx = minf(minx, float(xx))
				maxx = maxf(maxx, float(xx))
				miny = minf(miny, float(yy))
				maxy = maxf(maxy, float(yy))
	if maxx < 0.0 or maxx - minx < 5.0 or maxy - miny < 4.0:
		return
	var bx0 := minx
	var bx1 := maxx + 1.0
	var htop := zf - miny
	var hbot := zf - (maxy + 1.0)
	var depth_b := 1.8
	var zs := zf + depth_b
	# textured face (UV taken on the wall plane so the sprite pixels stay exactly as painted)
	var pts := [[bx0, zs, htop], [bx1, zs, htop], [bx1, zs, hbot], [bx0, zs, hbot]]
	for i in [0, 1, 2, 0, 2, 3]:
		var p: Array = pts[i]
		wb._st.set_color(Color(wb.NEUTRAL * 1.1, wb.NEUTRAL * 1.1, wb.NEUTRAL * 1.1, 1.0))
		wb._st.set_normal(Vector3.BACK)
		wb._st.set_uv(wb._uv(float(p[0]), zf, float(p[2])))
		wb._st.add_vertex(wb.px_to_world(float(p[0]), float(p[1]), float(p[2])))
	var edge := Color("#26283e")
	wb._solid_box(bx0 - 0.8, zf, hbot - 0.8, bx1 + 0.8, zs - 0.05, hbot, edge)       # bottom
	wb._solid_box(bx0 - 0.8, zf, htop, bx1 + 0.8, zs - 0.05, htop + 0.8, _k(edge, 1.3))   # top
	wb._solid_box(bx0 - 0.8, zf, hbot, bx0, zs - 0.05, htop, _k(edge, 1.1))
	wb._solid_box(bx1, zf, hbot, bx1 + 0.8, zs - 0.05, htop, _k(edge, 0.8))
	# brackets: steel pins through the board's side rails into the wall
	var steel := Color("#8490a4")
	var hm := (htop + hbot) * 0.5
	wb._solid_box(bx0 - 2.0, zf, hm - 0.7, bx0 - 0.8, zs - 0.05, hm + 0.7, steel)
	wb._solid_box(bx1 + 0.8, zf, hm - 0.7, bx1 + 2.0, zs - 0.05, hm + 0.7, _k(steel, 0.8))
