class_name Diorama
extends RefCounted
## Helpers for the title/intro 3D dioramas: they are framed so that every
## model, ridge and prop lands where upstream draws the matching sprite on
## its 320x180 screen. Positions are given in upstream's logical pixels and
## resolved through the live camera (ray -> ground plane / fixed depth).

const K := 3.0

## World point on the ground plane (y = ground_y) seen at logical pixel p.
static func ground_at(cam: Camera3D, p: Vector2, ground_y: float = 0.0) -> Vector3:
	var sp := p * K
	var o := cam.project_ray_origin(sp)
	var d := cam.project_ray_normal(sp)
	if absf(d.y) < 0.0001:
		return o + d * 20.0
	var t := (ground_y - o.y) / d.y
	return o + d * t

## World point at camera depth `depth` seen at logical pixel p.
static func at_depth(cam: Camera3D, p: Vector2, depth: float) -> Vector3:
	return cam.project_position(p * K, depth)

## Camera-space depth of a world point.
static func depth_of(cam: Camera3D, w: Vector3) -> float:
	return -(cam.global_transform.affine_inverse() * w).z

## Local-space AABB of every VisualInstance3D under n (rest pose).
static func bounds(n: Node, xf: Transform3D = Transform3D.IDENTITY) -> AABB:
	var out := AABB()
	var first := true
	var t := xf
	if n is Node3D:
		t = xf * (n as Node3D).transform
	if n is VisualInstance3D:
		out = t * (n as VisualInstance3D).get_aabb()
		first = false
	for c in n.get_children():
		var cb := bounds(c, t)
		if cb.size == Vector3.ZERO:
			continue
		if first:
			out = cb
			first = false
		else:
			out = out.merge(cb)
	return out

## Stands `node` on the ground under logical pixel `feet` (bottom-centre, like
## upstream's sprite anchors) and scales it so it is `height_px` logical
## pixels tall on screen. `node` should already contain its model.
static func stand(cam: Camera3D, node: Node3D, feet: Vector2, height_px: float, yaw_deg: float = 0.0) -> void:
	node.rotation_degrees = Vector3(0, yaw_deg, 0)
	node.scale = Vector3.ONE
	# bounds() applies node.transform itself: reset the position (stand() runs every frame in OakSpeech, the previous
	# frame's position leaked into b.position.y) and don't hand the rotation in twice
	node.position = Vector3.ZERO
	var b := bounds(node, Transform3D.IDENTITY)
	var h := maxf(b.size.y, 0.01)
	var pos := ground_at(cam, feet)
	var depth := depth_of(cam, pos)
	var f := (Px.H * K * 0.5) / tan(deg_to_rad(cam.fov) * 0.5)
	var world_h := height_px * K * depth / f
	var s := world_h / h
	node.scale = Vector3.ONE * s
	node.position = pos - Vector3(0, b.position.y * s, 0)

## Unshaded vertex-colour material (flat palette colours, like the 2D art).
static func flat_material(unshaded: bool = true) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.vertex_color_is_srgb = not compat()
	if unshaded:
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m

## A mountain ridge whose crest traces `crest(x)` (logical y for every logical
## x column 0..320) at camera depth `depth`, extruded `thick` world units away
## from the camera, down to logical y `base`. Crest band `band` px in `c_top`,
## body `c_body` (upstream title.js mountains).
static func ridge(cam: Camera3D, crest: Callable, depth: float, base: float, c_top: Color, c_body: Color, band: float = 2.0, thick: float = 3.0) -> MeshInstance3D:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var fwd := -cam.global_transform.basis.z
	var prev: Array = []
	for x in range(-2, 324, 2):
		var hy: float = crest.call(float(x))
		var top := at_depth(cam, Vector2(x, hy), depth)
		var mid := at_depth(cam, Vector2(x, hy + band), depth)
		var bot := at_depth(cam, Vector2(x, base), depth)
		var back := top + fwd * thick + Vector3(0, -thick * 0.35, 0)
		var col := [top, mid, bot, back]
		if not prev.is_empty():
			_quad(st, prev[0], col[0], col[1], prev[1], c_top, c_top)
			_quad(st, prev[1], col[1], col[2], prev[2], c_body, c_body.darkened(0.25))
			_quad(st, prev[3], col[3], col[0], prev[0], c_body.darkened(0.15), c_top)
		prev = col
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = flat_material()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

static func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, ctop: Color, cbot: Color) -> void:
	for v in [[a, ctop], [b, ctop], [c, cbot], [a, ctop], [c, cbot], [d, cbot]]:
		st.set_color(v[1])
		st.add_vertex(v[0])

## Full-screen backdrop quad at camera depth `depth` running `shader_code`
## (a spatial, unshaded shader that paints with SCREEN_UV).
static func backdrop(cam: Camera3D, shader_code: String, depth: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	var a := at_depth(cam, Vector2(-8, -8), depth)
	var b := at_depth(cam, Vector2(328, 188), depth)
	var right := cam.global_transform.basis.x
	var up := cam.global_transform.basis.y
	q.size = Vector2(absf((b - a).dot(right)), absf((b - a).dot(up)))
	mi.mesh = q
	var sh := Shader.new()
	sh.code = shader_code
	var mat := ShaderMaterial.new()
	mat.shader = sh
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# callers add it under a root at the world origin
	mi.transform = Transform3D(cam.global_transform.basis, at_depth(cam, Vector2(160, 90), depth))
	return mi

## GLSL helpers shared by the backdrop shaders: sRGB hex -> linear, the 4x4
## Bayer matrix and upstream's logical-pixel coordinate (0..320, 0..180).
## The Compatibility (GLES3) renderer writes unshaded colours straight to the
## sRGB framebuffer, Forward+ expects linear values: palette colours need the
## sRGB->linear conversion only on the latter.
static func compat() -> bool:
	return RenderingServer.get_current_rendering_method() == "gl_compatibility"

static func glsl_common() -> String:
	return GLSL_COMMON.replace("LIN_ON", "0.0" if compat() else "1.0")

const GLSL_COMMON := """
vec3 lin(vec3 c) { return mix(c, mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c)), LIN_ON); }
vec3 hexc(int h) { return lin(vec3(float((h >> 16) & 255), float((h >> 8) & 255), float(h & 255)) / 255.0); }
float bayer4(vec2 p) {
	int x = int(mod(p.x, 4.0)); int y = int(mod(p.y, 4.0));
	int m[16] = int[](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
	return (float(m[y * 4 + x]) + 0.5) / 16.0;
}
"""

## Plays the first animation named in `names` found under node.
static func play_anim(node: Node, names: Array) -> void:
	var ap := CharacterModel.find_anim(node)
	if ap == null:
		return
	AnimUtil.fix_looping(ap)
	for n in names:
		if ap.has_animation(n):
			ap.play(n)
			return
