class_name IntroCreatures
extends RefCounted
## The two "logo creatures" of upstream's opening (intro.js), rebuilt as real
## 3D models from the same geometry intro.js rasterises:
##   claude(R)  - the terracotta spark: a core with 12 tapered rays at
##                upstream's RAYS angles/lengths (widths 0.125R -> 0.09R), a face
##                with dot or squint eyes and blush.
##   gpt(R)     - the six-link knot: a puffy relief of the knot mask
##                (rout = R(0.8 + 0.2cos3s), rin = 0.3R/cos s) with the pinwheel
##                seams and bright bands carved in, and glowing teal eyes in the hole.
## Both face +Z (the camera) and are 2R wide; rotate them about Z to spin.
## Also: claude_sprite(R, spin, face) -> the 2D pixel version (the tiny icon on
## the LEVY ST. card), ported pixel for pixel.

const RAY_ANG := [0, 31, 58, 92, 118, 149, 178, 212, 238, 269, 297, 328]
const RAY_LEN := [1, 0.8, 0.96, 0.72, 0.9, 0.84, 1, 0.76, 0.94, 0.7, 0.9, 0.8]
const ORANGE := Color("#d97757")

static func _mat(c: Color, emissive: float = 0.0, rough: float = 0.55) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	if emissive > 0.0:
		m.emission_enabled = true
		m.emission = c
		m.emission_energy_multiplier = emissive
	return m

## The spark. Returns a Node3D with children "Body" (spins) and "Face" (stays upright).
static func claude(R: float) -> Node3D:
	var root := Node3D.new()
	var body := Node3D.new()
	body.name = "Body"
	root.add_child(body)
	var mat := _mat(ORANGE, 0.3, 0.6)
	var core := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = R * 0.33
	sm.height = R * 0.66
	core.mesh = sm
	core.scale = Vector3(1, 1, 0.62)
	core.material_override = mat
	body.add_child(core)
	for k in 12:
		var a := deg_to_rad(RAY_ANG[k])
		var l: float = RAY_LEN[k] * R
		var ray := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.bottom_radius = R * 0.125
		cyl.top_radius = R * 0.09
		cyl.height = l
		cyl.radial_segments = 10
		ray.mesh = cyl
		ray.material_override = mat
		# cylinder runs along +Y; lay it along screen angle a (screen y is down)
		var dir := Vector3(cos(a), -sin(a), 0)
		ray.basis = Basis(Vector3.BACK, -a - PI / 2.0) * Basis.from_scale(Vector3(1, 1, 0.62))
		ray.position = dir * l * 0.5
		body.add_child(ray)
		var tip := MeshInstance3D.new()
		var ts := SphereMesh.new()
		ts.radius = R * 0.09
		ts.height = R * 0.18
		tip.mesh = ts
		tip.scale = Vector3(1, 1, 0.62)
		tip.material_override = mat
		tip.position = dir * l
		body.add_child(tip)
	var face := Node3D.new()
	face.name = "Face"
	root.add_child(face)
	var ink := _mat(Color("#2a1208"), 0.0, 0.3)
	var px := R / 18.0  # one sprite pixel at R = 18
	for side in [-1, 1]:
		var eye := MeshInstance3D.new()
		eye.name = "Eye%d" % side
		var bm := BoxMesh.new()
		bm.size = Vector3(2.0 * px, 4.0 * px, px)
		eye.mesh = bm
		eye.material_override = ink
		eye.position = Vector3(side * 3.0 * px, -0.5 * px, R * 0.2)
		face.add_child(eye)
		var glint := MeshInstance3D.new()
		var gm := BoxMesh.new()
		gm.size = Vector3(px, px, px * 0.5)
		glint.mesh = gm
		glint.material_override = _mat(Color.WHITE, 0.6)
		glint.position = eye.position + Vector3(-0.5 * px, 1.5 * px, px * 0.6)
		glint.name = "Glint%d" % side
		face.add_child(glint)
		var blush := MeshInstance3D.new()
		var blm := SphereMesh.new()
		blm.radius = px * 0.8
		blm.height = px * 1.6
		blush.mesh = blm
		blush.material_override = _mat(Color("#f0907a"), 0.2)
		blush.position = Vector3(side * 4.5 * px, -3.5 * px, R * 0.19)
		face.add_child(blush)
	return root

## Switches the spark's face between "eyes" and "squint" (intro.js faces).
static func claude_face(n: Node3D, face: String, R: float) -> void:
	var f := n.get_node_or_null("Face")
	if f == null:
		return
	var px := R / 18.0
	for side in [-1, 1]:
		var eye: MeshInstance3D = f.get_node("Eye%d" % side)
		var bm: BoxMesh = eye.mesh
		if face == "squint":
			bm.size = Vector3(3.0 * px, px, px)
			eye.position = Vector3(side * 3.0 * px, -px, R * 0.2)
		else:
			bm.size = Vector3(2.0 * px, 4.0 * px, px)
			eye.position = Vector3(side * 3.0 * px, -0.5 * px, R * 0.2)
		(f.get_node("Glint%d" % side) as Node3D).visible = face != "squint"

## The knot, as a puffy relief mesh. Child "Body" (rotate about Z) + "Eyes".
static func gpt(R: float) -> Node3D:
	var root := Node3D.new()
	var body := MeshInstance3D.new()
	body.name = "Body"
	body.mesh = _knot_mesh(R)
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.vertex_color_is_srgb = not Diorama.compat()
	m.roughness = 0.35
	m.metallic_specular = 0.6
	body.material_override = m
	root.add_child(body)
	var eyes := Node3D.new()
	eyes.name = "Eyes"
	root.add_child(eyes)
	var px := R / 24.0
	for side in [-1, 1]:
		var e := MeshInstance3D.new()
		e.name = "Eye%d" % side
		var bm := BoxMesh.new()
		bm.size = Vector3(2.0 * px, 2.0 * px, px)
		e.mesh = bm
		e.material_override = _mat(Color("#c8fff0"), 2.0)
		e.position = Vector3(side * 2.5 * px, 0.0, R * 0.05)
		eyes.add_child(e)
	return root

static func gpt_eyes(n: Node3D, mode: String, R: float) -> void:
	var px := R / 24.0
	var eyes := n.get_node_or_null("Eyes")
	if eyes == null:
		return
	for side in [-1, 1]:
		var e: MeshInstance3D = eyes.get_node("Eye%d" % side)
		(e.mesh as BoxMesh).size = Vector3(2.0 * px, px if mode == "mad" else 2.0 * px, px)

static func _knot_color(dx: float, dy: float, R: float) -> Array:
	# returns [inside, color, relief 0..1] for a point relative to the centre (sprite px, y down)
	var r := sqrt(dx * dx + dy * dy)
	var th := atan2(dy, dx)
	var sec := fposmod(fposmod(th, PI / 3.0) + PI / 3.0, PI / 3.0) - PI / 6.0
	var rout := R * (0.8 + 0.2 * cos(sec * 3.0))
	var rin := R * 0.3 / cos(sec)
	if r >= rout or r <= rin:
		return [false, Color.BLACK, 0.0]
	var col := Color("#e4e7ec")
	var relief := 1.0
	for k in 6:
		var ang := k * PI / 3.0 + 0.35 + (r - R * 0.3) / (R * 0.7) * 0.95
		var d := fposmod(th - ang + PI, TAU) - PI
		var pxd := d * r
		if absf(pxd) < 0.75:
			col = Color("#4a525c")
			relief = 0.55
			break
		if pxd > 0.75 and pxd < 2.2:
			col = Color("#ffffff")
			relief = 1.08
	var u := clampf((r - rin) / (rout - rin), 0.0, 1.0)
	return [true, col, pow(sin(u * PI), 0.6) * relief]

static func _knot_mesh(R: float) -> ArrayMesh:
	# sample the mask in sprite pixels (R = 24, as drawn in the battle), then scale to world
	var rp := 24.0
	var sc := R / rp
	var n := 104
	var span := rp * 1.04
	var step := 2.0 * span / n
	var H := rp * 0.24
	var grid := []
	for j in n + 1:
		var row := []
		for i in n + 1:
			row.append(_knot_color(-span + i * step, -span + j * step, rp))
		grid.append(row)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var sgn := [1.0, -0.55]
	for face in 2:
		for j in n:
			for i in n:
				var c: Array = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
				if not (c[0][0] and c[1][0] and c[2][0] and c[3][0]):
					continue
				var pts: Array = []
				for q in 4:
					var ii: int = i + (1 if q == 1 or q == 2 else 0)
					var jj: int = j + (1 if q >= 2 else 0)
					pts.append(Vector3(-span + ii * step, -(-span + jj * step), c[q][2] * H * sgn[face]) * sc)
				# q0..q3 run TL,TR,BR,BL on screen; world y = -screen y keeps that clockwise seen from +Z, and Godot's
				# front faces are clockwise, so the front (face 0) winds 0-1-2 and the back face the reverse
				var order := [0, 1, 2, 0, 2, 3] if face == 0 else [0, 2, 1, 0, 3, 2]
				for o in order:
					st.set_color(c[o][1] if face == 0 else Color("#9aa2ae"))
					st.add_vertex(pts[o])
	st.generate_normals()
	return st.commit()

## intro.js claudeSprite(R, spinStep, face) as a pixel image (2D icon use).
static func claude_sprite(R: float, spin_step: int, face: String) -> ImageTexture:
	var S := int(ceil(R * 2.0 + 4.0))
	var c := S / 2.0
	var img := Image.create(S, S, false, Image.FORMAT_RGBA8)
	var spin := spin_step * PI / 24.0
	for y in S:
		for x in S:
			var dx := x + 0.5 - c
			var dy := y + 0.5 - c
			var hit := dx * dx + dy * dy < (R * 0.31) * (R * 0.31)
			var k := 0
			while not hit and k < 12:
				var a := deg_to_rad(RAY_ANG[k]) + spin
				var ux := cos(a)
				var uy := sin(a)
				var ln: float = RAY_LEN[k] * R
				var tt := maxf(0.0, minf(ln, dx * ux + dy * uy))
				var qx := dx - ux * tt
				var qy := dy - uy * tt
				var w := R * (0.125 - 0.035 * tt / ln)
				hit = qx * qx + qy * qy < w * w
				k += 1
			if hit:
				img.set_pixel(x, y, ORANGE)
	_finish(img, Color("#5a2414"), Color("#f2a888"), Color("#aa4e34"))
	var cx := int(floor(c))
	var cy := int(floor(c)) + 1
	var ink := Color("#2a1208")
	for ex in [cx - 4, cx + 2]:
		if face == "squint":
			for i in 3:
				_ps(img, ex + i, cy, ink)
			_ps(img, ex + (2 if ex < cx else 0), cy - 1, ink)
		else:
			for yy in 4:
				for xx in 2:
					_ps(img, ex + xx, cy - 2 + yy, ink)
			_ps(img, ex, cy - 2, Color.WHITE)
	_ps(img, cx - 5, cy + 3, Color("#f0907a"))
	_ps(img, cx + 4, cy + 3, Color("#f0907a"))
	return ImageTexture.create_from_image(img)

static func _ps(img: Image, x: int, y: int, c: Color) -> void:
	if x >= 0 and y >= 0 and x < img.get_width() and y < img.get_height():
		img.set_pixel(x, y, c)

## intro.js finish(): 1px outline + lit up-left / shaded down-right bevel.
static func _finish(img: Image, line: Color, lite: Color, dark: Color) -> void:
	var w := img.get_width()
	var h := img.get_height()
	var src := img.duplicate() as Image
	var filled := func(x: int, y: int) -> bool: return x >= 0 and y >= 0 and x < w and y < h and src.get_pixel(x, y).a > 0.0
	for y in h:
		for x in w:
			if filled.call(x, y):
				if not filled.call(x - 1, y - 1) or not filled.call(x, y - 1):
					img.set_pixel(x, y, lite)
				elif not filled.call(x + 1, y + 1) or not filled.call(x, y + 1):
					img.set_pixel(x, y, dark)
			elif filled.call(x - 1, y) or filled.call(x + 1, y) or filled.call(x, y - 1) or filled.call(x, y + 1):
				img.set_pixel(x, y, line)
