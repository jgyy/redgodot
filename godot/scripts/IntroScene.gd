extends Node3D
## The opening, ported from upstream's intro.js (a parody of Red's intro):
##  1. the opening title card (frames 0-329): the shooting star, the mark
##     blooming out of it, the wordmark wipe, GAMES / presents / VIBE CODED
##     credit - a 2D title card, drawn by IntroOverlay with upstream's code.
##  2. The letterboxed battle (frames 330-695): CLAUDE vs CHATGPT on a night
##     meadow before a data-centre skyline. Here the world is real 3D: the sky
##     dome (gradient, stars, crescent moon), 14 server-tower blocks with
##     blinking window lights, the striped meadow, and the two creatures as 3D
##     models (IntroCreatures) acting out upstream's exact choreography (pan-in,
##     hops, wind-up with aura, energy shots, dodge, lunge, the spinning leap and
##     the clash). Screen-space sparks, slashes, rays, white-out and letterbox are
##     drawn on top by IntroOverlay at upstream's coordinates.
## Any key skips (the first press only "turns the sound on", like upstream).
## seek(frame) jumps to a frame (Main.gd --scene=intro --intro_frame=N).

const PRESENTS := 330
const BATTLE := 366
const TOP := 22
const BOT := 150
const HC := 1.2           # camera height (world units)
const ACTOR_Y := 134.0    # upstream feet line of the actors (logical px)

const SKY_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, fog_disabled;
uniform float pan = 0.0;
uniform float bt = 0.0;
uniform float shx = 0.0;
uniform vec2 stars[60];   // upstream hash2(i,5,1)*480, hash2(i,6,1)*60
//COMMON
bool disc(vec2 p, vec2 c, float r) {
	float dy = (p.y + 0.5 - c.y) / r;
	if (abs(dy) > 1.0) return false;
	float hw = r * sqrt(1.0 - dy * dy);
	return p.x >= floor(c.x - hw + 0.5) && p.x < floor(c.x + hw + 0.5);
}
void fragment() {
	vec2 p = floor(SCREEN_UV * vec2(320.0, 180.0));
	float k = (p.y - 22.0) / 128.0;
	vec3 c = k < 0.7 ? mix(hexc(0x0a0e2a), hexc(0x2c1d58), k / 0.7) : mix(hexc(0x2c1d58), hexc(0x6a3a6a), (k - 0.7) / 0.3);
	for (int i = 0; i < 60; i++) {
		float fi = float(i);
		float sx = mod(mod(stars[i].x - pan * 0.15, 320.0) + 320.0, 320.0);
		float sy = floor(22.0 + stars[i].y);
		if (p == vec2(floor(sx), sy) && mod(bt + fi * 11.0, 70.0) > 8.0) c = mod(fi, 7.0) != 0.0 ? hexc(0xc8d0ff) : vec3(1.0);
	}
	if (disc(p, vec2(62.0 - pan * 0.1 + shx, 44.0), 9.0)) c = hexc(0xf4ecd0);
	if (disc(p, vec2(66.0 - pan * 0.1 + shx, 41.0), 8.0)) c = hexc(0x0e1230);
	ALBEDO = c;
}
"""

const GROUND_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, fog_disabled;
uniform float cam_z = 0.0;
uniform float d_near = 1.0;
uniform float d_far = 10.0;
//COMMON
varying vec3 wpos;
void vertex() { wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	float d = cam_z - wpos.z;
	if (d > d_far - 0.18) { ALBEDO = hexc(0x4a8a5a); }
	else {
		float k = clamp((d_far - d) / (d_far - d_near), 0.0, 1.0);
		float stripe = mod(floor((wpos.x + wpos.z * 1.5) / 0.22), 2.0);
		ALBEDO = mix(hexc(0x1c3c2c), hexc(0x2e6a3e), clamp(k * 0.8 + stripe * 0.08, 0.0, 1.0));
	}
}
"""

const TOWER_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, fog_disabled;
uniform float wpp = 0.06;
uniform vec3 half_size = vec3(1.0);
uniform float b = 0.0;
uniform float bt = 0.0;
//COMMON
float h2(float x, float y, float s) { return fract(sin(x * 12.9898 + y * 78.233 + s * 37.719) * 43758.5453); }
varying vec3 lp;
void vertex() { lp = VERTEX; }
void fragment() {
	vec3 c = hexc(0x161634);
	vec2 q = vec2((lp.x + half_size.x) / wpp, (half_size.y - lp.y) / wpp);   // upstream px from the top-left
	if (q.y < 1.0) c = hexc(0x2a2a5a);
	if (abs(lp.z - half_size.z) < 0.001) {
		vec2 px = floor(q);
		float w = floor(2.0 * half_size.x / wpp + 0.5);
		if (mod(px.x - 3.0, 3.0) == 0.0 && px.x >= 3.0 && px.x < w - 3.0 && mod(px.y - 4.0, 5.0) == 0.0 && px.y >= 4.0) {
			bool on = h2(px.x + b, px.y, floor(bt / 8.0) + b) > 0.55;
			c = on ? (h2(px.x, px.y, b) > 0.8 ? hexc(0xff6a5a) : hexc(0x58f0b0)) : hexc(0x23234a);
		}
	}
	ALBEDO = c;
}
"""

const BLOB_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, depth_draw_never, fog_disabled;
uniform float strength = 0.35;
void fragment() {
	float r = length(UV - vec2(0.5)) * 2.0;
	ALBEDO = vec3(0.0);
	ALPHA = (r < 1.0 ? 1.0 : 0.0) * strength;
}
"""

const AURA_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, cull_front, shadows_disabled, depth_draw_never, fog_disabled;
uniform float strength = 0.2;
void fragment() {
	float rim = 1.0 - abs(dot(NORMAL, VIEW));
	ALBEDO = vec3(0.063, 0.64, 0.5);
	ALPHA = strength * (0.55 + rim);
}
"""

var t := 0
var _time := 0.0
var done := false
var sound_asked := false
var shake := 0
var parts: Array = []

# choreography state (upstream names)
var pan := 150.0
var shx := 0.0
var gx := 96.0
var gy := 132.0
var g_scale := 1.0
var g_rot := 0
var g_eyes := "eyes"
var cx := 236.0
var cy := 134.0
var c_spin := 0
var c_face := "eyes"

var _cam: Camera3D
var _cam_z := 10.0
var _f := 1.0
var _d_a := 1.0
var _wpp := 0.01
var _sky_mat: ShaderMaterial
var _tower_mats: Array = []
var towers: Array = []   # [{top: Vector3, b: int}] for steam puffs
var _gpt: Node3D
var _claude: Node3D
var _aura: MeshInstance3D
var _shots: Array = []
var _blob_g: MeshInstance3D
var _blob_c: MeshInstance3D
var _overlay: IntroOverlay
var _gpt_r := 24.0
var _last_face := ""
var _last_eyes := ""

func _ready() -> void:
	_build_stage()
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	_overlay = IntroOverlay.new()
	_overlay.scene = self
	layer.add_child(_overlay)
	var au := UI.audio()
	if au and au.has_method("stop_music"):
		au.stop_music()

var _hold := false

## Jumps to a 60 fps frame; hold = true freezes the clock there (captures).
func seek(frame: int, hold: bool = false) -> void:
	_time = frame / 60.0
	t = frame
	_hold = hold
	parts.clear()

# ---------------------------------------------------------------- stage
func _mat_shader(code: String) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = Shader.new()
	m.shader.code = code.replace("//COMMON", Diorama.glsl_common())
	return m

func _build_stage() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.72, 0.72, 0.85)
	env.ambient_light_energy = 0.7
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var moon := DirectionalLight3D.new()
	moon.rotation_degrees = Vector3(-35, -35, 0)
	moon.light_color = Color(0.96, 0.96, 1.0)
	moon.light_energy = 1.1
	add_child(moon)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-10, 160, 0)
	rim.light_color = Color(1.0, 0.72, 0.55)
	rim.light_energy = 0.5
	add_child(rim)

	_cam = Camera3D.new()
	_cam.fov = 30.0
	_cam.position = Vector3(0, HC, _cam_z)
	_cam.far = 300.0
	_cam.current = true
	add_child(_cam)
	_f = (Px.H * Diorama.K * 0.5) / tan(deg_to_rad(_cam.fov) * 0.5)
	_d_a = HC * _f / ((ACTOR_Y - 90.0) * Diorama.K)
	_wpp = Diorama.K * _d_a / _f
	var d_h := HC * _f / ((112.0 - 90.0) * Diorama.K)

	# sky dome: rides with the camera, parallax done in the shader like upstream
	var sky := Diorama.backdrop(_cam, SKY_SHADER.replace("//COMMON", Diorama.glsl_common()), 250.0)
	sky.transform = _cam.global_transform.affine_inverse() * sky.transform
	_sky_mat = sky.material_override
	var st := PackedVector2Array()
	for i in 60:
		st.append(Vector2(SfxSynth.hash2(i, 5, 1) * 480.0, SfxSynth.hash2(i, 6, 1) * 60.0))
	_sky_mat.set_shader_parameter("stars", st)
	_cam.add_child(sky)

	# meadow, from under the camera to the horizon line (y = 112)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(120, d_h + 1.0)
	ground.mesh = pm
	var gm := _mat_shader(GROUND_SHADER)
	gm.set_shader_parameter("cam_z", _cam_z)
	gm.set_shader_parameter("d_near", _d_a * 0.6)
	gm.set_shader_parameter("d_far", d_h)
	ground.material_override = gm
	ground.position = Vector3(0, 0, _cam_z + 1.0 - (d_h + 1.0) * 0.5)
	add_child(ground)

	# the data-centre skyline: parallax 0.45 => towers at depth d_a / 0.45
	var d_s := _d_a / 0.45
	var wpp_s := Diorama.K * d_s / _f
	for b in 14:
		var w := 22 + int(SfxSynth.hash2(b, 1, 7) * 26.0)
		var h := 18 + int(SfxSynth.hash2(b, 2, 7) * 34.0)
		var x0 := b * 34 - 20
		var y0 := 104 - h
		var top_y := HC - (y0 - 90.0) * wpp_s
		var bottom_y := -1.5
		var hs := Vector3(w * wpp_s * 0.5, (top_y - bottom_y) * 0.5, w * wpp_s * 0.4)
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = hs * 2.0
		mi.mesh = bm
		var tm := _mat_shader(TOWER_SHADER)
		tm.set_shader_parameter("wpp", wpp_s)
		tm.set_shader_parameter("half_size", hs)
		tm.set_shader_parameter("b", float(b))
		mi.material_override = tm
		mi.position = Vector3((x0 + w * 0.5 - 160.0) * wpp_s, (top_y + bottom_y) * 0.5, _cam_z - d_s - hs.z)
		add_child(mi)
		_tower_mats.append(tm)
		towers.append({"b": b, "top": Vector3(mi.position.x, top_y, _cam_z - d_s), "x0": x0, "w": w, "y0": y0})

	# the creatures
	_gpt = IntroCreatures.gpt(_gpt_r * _wpp)
	add_child(_gpt)
	_claude = IntroCreatures.claude(18.0 * _wpp)
	add_child(_claude)
	var aura_mesh := SphereMesh.new()
	aura_mesh.radius = 1.0
	aura_mesh.height = 2.0
	_aura = MeshInstance3D.new()
	_aura.mesh = aura_mesh
	_aura.material_override = _mat_shader(AURA_SHADER)
	add_child(_aura)
	for i in 5:
		var s := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 2.5 * _wpp
		sm.height = 5.0 * _wpp
		s.mesh = sm
		var m := StandardMaterial3D.new()
		m.albedo_color = Color("#10a37f")
		m.emission_enabled = true
		m.emission = Color("#10a37f")
		m.emission_energy_multiplier = 1.5
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		s.material_override = m
		add_child(s)
		_shots.append(s)
	_blob_g = _blob()
	_blob_c = _blob()

func _blob() -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = PlaneMesh.new()
	mi.material_override = _mat_shader(BLOB_SHADER)
	add_child(mi)
	return mi

## Stage pixel (pan = 0, no shake) -> world point on the actors' plane.
func stage(px: float, py: float) -> Vector3:
	return Vector3((px - 160.0) * _wpp, HC - (py - 90.0) * _wpp, _cam_z - _d_a)

## Stage pixel -> screen pixel (upstream X()).
func X(x: float) -> float:
	return roundf(x + pan + shx)

# ---------------------------------------------------------------- timeline
func _process(dt: float) -> void:
	if done:
		return
	if not _hold:
		_time += dt
	var target := int(_time * 60.0)
	if target - t > 30:
		t = target - 1  # a hitch or a seek: don't replay a backlog
	while t < target and not done:
		t += 1
		_step()
	_choreograph()
	_apply_3d()
	_overlay.queue_redraw()

func _sfx(n: String) -> void:
	UI.sfx(n)

func _step() -> void:
	var bt := t - PRESENTS
	if t == 12:
		_sfx("teleport")
	if bt == 0:
		var au := UI.audio()
		if au and au.has_method("music"):
			au.music("IntroBattle")
	if bt == 72 or bt == 100 or bt == 190 or bt == 296:
		_sfx("jump")
	if bt == 262:
		_sfx("hit")
	if bt == 352:
		_sfx("hit_super")
		shake = 12
	if shake > 0:
		shake -= 1
	for p in parts:
		p.x += p.vx
		p.y += p.vy
		p.vy += p.get("g", 0.0)
		p.life -= 1
	parts = parts.filter(func(p): return p.life > 0)
	# particle spawns (upstream spawns them while drawing)
	var land := 62
	if t >= 12 and t < land and t % 2 == 0:
		var k := clampf((t - 12) / float(land - 12), 0.0, 1.0)
		var sx := lerpf(360.0, 160.0, _ease(k))
		var sy := lerpf(-20.0, 58.0, _ease(k))
		parts.append({"x": sx, "y": sy, "vx": (SfxSynth.hash2(t, 1, 9) - 0.2) * 1.2, "vy": SfxSynth.hash2(t, 2, 9) * 0.8,
			"g": 0.03, "life": 26, "c": IntroOverlay.IVORY if t % 4 != 0 else IntroOverlay.ORANGE, "battle": false})
	if bt >= 290 and bt < 352 and bt % 3 == 0:
		parts.append({"x": cx + (SfxSynth.hash2(bt, 3, 1) - 0.5) * 20.0, "y": cy - 18.0, "vx": 0.0, "vy": 0.4, "life": 16,
			"c": IntroOverlay.ORANGE, "battle": true})
	if t >= PRESENTS + BATTLE:
		_finish()

static func _ease(x: float) -> float:
	if x <= 0.0:
		return 0.0
	if x >= 1.0:
		return 1.0
	return x * x * (3.0 - 2.0 * x)

func _hop(bt: int, t0: int, t1: int, h: float) -> float:
	if bt >= t0 and bt < t1:
		return -sin(float(bt - t0) / (t1 - t0) * PI) * h
	return 0.0

## drawBattle()'s actor maths, verbatim.
func _choreograph() -> void:
	var bt := t - PRESENTS
	pan = roundf(lerpf(150.0, 0.0, _ease(bt / 70.0)))
	shx = (((shake % 2) * 2 - 1) * ceilf(shake / 4.0)) if shake > 0 else 0.0
	gx = 96.0
	gy = 132.0
	g_scale = 1.0
	g_rot = int(floor(bt / 5.0))
	g_eyes = "eyes"
	cx = 236.0
	cy = 134.0
	c_spin = 0
	c_face = "eyes"
	cy += _hop(bt, 72, 96, 10) + _hop(bt, 100, 124, 10)
	if bt >= 130:
		g_scale = 1.0 + 0.12 * _ease((bt - 130) / 30.0)
		g_rot = int(floor(bt / 2.0))
		g_eyes = "mad"
	if bt >= 190:
		var k := _ease((bt - 190) / 24.0)
		cx += 30.0 * k
		cy += -sin(minf(1.0, (bt - 190) / 24.0) * PI) * 14.0
	if bt >= 244:
		var k2 := _ease((bt - 244) / 20.0)
		gx = lerpf(96.0, 176.0, k2 * k2)
	if bt >= 290:
		var k3 := minf(1.0, (bt - 290) / 62.0)
		cx = lerpf(266.0, gx + 4.0, k3)
		cy = lerpf(134.0, 124.0, k3) - sin(k3 * PI) * 78.0
		c_spin = int(floor(bt * 1.5))
		c_face = "squint"
	if bt >= 352:
		cy = 124.0

func _apply_3d() -> void:
	var bt := t - PRESENTS
	var battle := bt >= 0
	_cam.position = Vector3(-(pan + shx) * _wpp, HC, _cam_z)
	_sky_mat.set_shader_parameter("pan", pan)
	_sky_mat.set_shader_parameter("bt", float(bt))
	_sky_mat.set_shader_parameter("shx", 0.0)
	for m: ShaderMaterial in _tower_mats:
		m.set_shader_parameter("bt", float(maxi(bt, 0)))
	for n in [_gpt, _claude, _aura, _blob_g, _blob_c]:
		n.visible = battle
	# CHATGPT: R = round(24 * gScale), centre at (gx, gy - R + 2)
	var R := roundf(24.0 * g_scale)
	_gpt.position = stage(gx, gy - R + 2.0)
	_gpt.scale = Vector3.ONE * (R / _gpt_r)
	(_gpt.get_node("Body") as Node3D).rotation.z = -float(g_rot % 12) * PI / 36.0
	if g_eyes != _last_eyes:
		_last_eyes = g_eyes
		IntroCreatures.gpt_eyes(_gpt, g_eyes, _gpt_r * _wpp)
	_aura.visible = battle and bt >= 130 and bt < 352
	if _aura.visible:
		_aura.position = stage(gx, gy - R)
		_aura.scale = Vector3.ONE * (R + 6.0) * _wpp
		(_aura.material_override as ShaderMaterial).set_shader_parameter("strength", 0.18 + 0.12 * sin(bt / 3.0))
	# CLAUDE: centre at (cx, cy - 18 + 2)
	_claude.position = stage(cx, cy - 16.0)
	(_claude.get_node("Body") as Node3D).rotation.z = -float(c_spin % 48) * PI / 24.0
	if c_face != _last_face:
		_last_face = c_face
		IntroCreatures.claude_face(_claude, c_face, 18.0 * _wpp)
	# shadows: ellipseBlend at (gx,134) rx 18*gScale ry 3, (cx,136) rx 11 ry 2
	_place_blob(_blob_g, gx, 134.0, 18.0 * g_scale, 0.35)
	_place_blob(_blob_c, cx, 136.0, 11.0, 0.35 * (1.0 - minf(1.0, (134.0 - cy) / 90.0)))
	# CHATGPT's energy shots
	for i in 5:
		var s: MeshInstance3D = _shots[i]
		var k := (bt - 160 - i * 9) / 30.0
		s.visible = battle and bt >= 160 and bt < 240 and k >= 0.0 and k <= 1.0
		if s.visible:
			var sx := lerpf(gx + 20.0, 238.0, k)
			var sy := lerpf(110.0, 124.0, k) - sin(k * PI) * 18.0
			s.position = stage(sx, roundf(sy))

func _place_blob(mi: MeshInstance3D, px: float, py: float, rx: float, strength: float) -> void:
	var p := Diorama.ground_at(_cam, Vector2(X(px), py))
	var d := Diorama.depth_of(_cam, p)
	var w := Diorama.K * d / _f
	(mi.mesh as PlaneMesh).size = Vector2(rx * 2.0 * w, rx * 2.0 * w * 0.35)
	mi.position = p + Vector3(0, 0.005, 0)
	(mi.material_override as ShaderMaterial).set_shader_parameter("strength", maxf(0.0, strength))

# ---------------------------------------------------------------- input / exit
func _unhandled_input(event: InputEvent) -> void:
	if done or not event.is_pressed() or event.is_echo():
		return
	if not (event is InputEventKey or event is InputEventMouseButton or event is InputEventJoypadButton):
		return
	if t <= 8:
		return
	get_viewport().set_input_as_handled()
	if not sound_asked:
		sound_asked = true
		return
	_finish()

func _finish() -> void:
	if done:
		return
	done = true
	SceneRouter.goto_title()
