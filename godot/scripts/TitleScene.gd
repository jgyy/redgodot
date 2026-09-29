extends Node3D
## Title screen: a real 3D diorama of upstream's title.js (dusk sky with
## twinkling stars, two ranges of purple/green mountains, the dark hatched
## meadow, RED, the cycling partner Pokémon and a hovering CHARIZARD), framed
## so every piece lands where upstream draws it on its 320x180 screen, under
## a Px overlay with the baked logo.js logo, PRESS START and the footer.
## A/START opens upstream's menu (CONTINUE / NEW GAME / OPTION); NEW GAME
## runs Oak's speech (OakSpeech.gd), CONTINUE loads the save.

const TITLE_MONS := ["CHARMANDER", "SQUIRTLE", "BULBASAUR", "WEEDLE", "NIDORAN_M", "SCYTHER", "PIKACHU", "CLEFAIRY",
	"RHYDON", "ABRA", "GASTLY", "DITTO", "PIDGEOTTO", "ONIX", "PONYTA", "MAGIKARP"]
## Upstream's cycle starts at CHARMANDER; start on BULBASAUR like reference 001.
const FIRST_MON := 2

const SKY_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, fog_disabled;
uniform float t = 0.0;
//COMMON
void fragment() {
	vec2 p = floor(SCREEN_UV * vec2(320.0, 180.0));
	float k = p.y / 180.0;
	vec3 c = mix(hexc(0x1a2a6a), hexc(0xe87858), clamp((k - 0.2) * 1.3, 0.0, 1.0));
	if (bayer4(p) < fract(k * 12.0)) c = mix(c, hexc(0xf8b068), 0.08);
	for (int i = 0; i < 40; i++) {
		vec2 s = vec2(float((i * 97) % 320), float((i * 53) % 70));
		if (p == s && mod(t + float(i * 7), 90.0) > 10.0) c = hexc(0xf0f0ff);
	}
	ALBEDO = c;
}
"""

const GROUND_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, fog_disabled;
//COMMON
varying vec3 wpos;
void vertex() { wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	// title.js ground: 1-in-7 diagonal hatch of #2a4a3a over #1a2e28, laid on the 3D meadow
	float d = fract((wpos.x + wpos.z * 1.2) * 2.6);
	ALBEDO = d < 0.16 ? hexc(0x2a4a3a) : hexc(0x1a2e28);
}
"""

const SHADOW_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, depth_draw_never, fog_disabled;
void fragment() {
	float r = length(UV - vec2(0.5)) * 2.0;
	ALBEDO = vec3(0.02, 0.04, 0.05);
	ALPHA = smoothstep(1.0, 0.55, r) * 0.55;
}
"""

@onready var _cam: Camera3D = $Camera3D

var _overlay: TitleOverlay
var _sky_mat: ShaderMaterial
var _red: Node3D
var _mon: Node3D
var _mon_actor: PokemonActor
var _mon_home := Vector3.ZERO
var _cz: Node3D
var _cz_home := Vector3.ZERO
var _px_world := 0.01
var _time := 0.0
var t := 0
var _mon_idx := -1
var _menu_open := false
var done := false

func _ready() -> void:
	_build_world()
	_overlay = TitleOverlay.new()
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	layer.add_child(_overlay)
	_audio_music("title")

func _audio_music(song: String) -> void:
	var a := UI.audio()
	if a and a.has_method("music"):
		a.music(song)

# ---------------------------------------------------------------- 3D world
func _build_world() -> void:
	# dusk lighting: warm key from the front-left, sunset rim from behind-right
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-35, -30, 0)
	key.light_color = Color(1.0, 0.88, 0.76)
	key.light_energy = 0.95
	add_child(key)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-15, 150, 0)
	rim.light_color = Color(1.0, 0.6, 0.42)
	rim.light_energy = 0.7
	add_child(rim)
	var common := Diorama.glsl_common()
	var sky := Diorama.backdrop(_cam, SKY_SHADER.replace("//COMMON", common), 95.0)
	_sky_mat = sky.material_override
	add_child(sky)
	# where the meadow meets the front range: upstream's ground band starts at y=150
	var horizon := Diorama.ground_at(_cam, Vector2(160, 150))
	var d_front := Diorama.depth_of(_cam, horizon)
	var back := Diorama.ridge(_cam, func(x: float) -> float: return 120.0 - 30.0 * absf(sin(x * 0.012 + 1.0)) - 10.0 * sin(x * 0.05),
		d_front + 25.0, 184.0, Color("#6a4a8a"), Color("#3a2a5a"), 2.0, 6.0)
	add_child(back)
	var front := Diorama.ridge(_cam, func(x: float) -> float: return 138.0 - 18.0 * absf(sin(x * 0.02 + 3.0)) - 6.0 * sin(x * 0.09),
		d_front + 0.5, 184.0, Color("#4a6a5a"), Color("#1e3a34"), 2.0, 4.0)
	add_child(front)
	# the meadow
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	# from just behind the camera to the foot of the front range
	var z_far := _cam.global_position.z - d_front * 0.999
	var z_near := _cam.global_position.z + 2.0
	pm.size = Vector2(80, z_near - z_far)
	ground.mesh = pm
	var gm := ShaderMaterial.new()
	gm.shader = Shader.new()
	gm.shader.code = GROUND_SHADER.replace("//COMMON", common)
	ground.material_override = gm
	ground.position = Vector3(_cam.position.x, 0, (z_near + z_far) * 0.5)
	add_child(ground)

	var f := (Px.H * Diorama.K * 0.5) / tan(deg_to_rad(_cam.fov) * 0.5)
	# RED: title.js castPortrait('red') bottom-centre at (54, 168), 64 px tall
	_red = Node3D.new()
	_red.add_child(CharacterModel.build("red"))
	add_child(_red)
	Diorama.stand(_cam, _red, Vector2(54, 167), 62.0, 12.0)
	Diorama.play_anim(_red, ["Idle"])
	_add_shadow(_red.position, 0.55 * _red.scale.x)
	# the cycling partner (64 px sprite blitted at (86, 108))
	_mon = Node3D.new()
	add_child(_mon)
	_mon_actor = PokemonActor.new()
	_mon.add_child(_mon_actor)
	_set_title_mon(FIRST_MON)
	# CHARIZARD: 128 px sprite at (188, 60), bobbing
	_cz = Node3D.new()
	var cza := PokemonActor.new()
	_cz.add_child(cza)
	cza.setup("CHARIZARD")
	add_child(_cz)
	Diorama.stand(_cam, _cz, Vector2(256, 176), 102.0, -20.0)
	_cz_home = _cz.position
	_add_shadow(_cz.position, 1.2 * _cz.scale.x)
	_px_world = Diorama.K * Diorama.depth_of(_cam, _cz_home) / f

func _set_title_mon(i: int) -> void:
	if i == _mon_idx:
		return
	_mon_idx = i
	_mon_actor.setup(TITLE_MONS[i])
	Diorama.stand(_cam, _mon, Vector2(119, 169), 44.0, -32.0)
	_mon_home = _mon.position

func _add_shadow(at: Vector3, radius: float) -> void:
	var mi := MeshInstance3D.new()
	var q := PlaneMesh.new()
	q.size = Vector2(radius * 2.4, radius * 1.2)
	mi.mesh = q
	var m := ShaderMaterial.new()
	m.shader = Shader.new()
	m.shader.code = SHADOW_SHADER
	mi.material_override = m
	mi.position = at + Vector3(0, 0.01, 0)
	add_child(mi)

## --title_t=N freezes the title clock at frame N (deterministic captures).
var _frozen_t := -1

func _enter_tree() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--title_t="):
			_frozen_t = int(a.substr(10))

func _process(dt: float) -> void:
	_time += dt
	t = int(_time * 60.0) if _frozen_t < 0 else _frozen_t
	_overlay.t = t
	_sky_mat.set_shader_parameter("t", float(t))
	# Charizard hover: round(sin(t / 25) * 2) px
	_cz.position = _cz_home + Vector3(0, -roundf(sin(t / 25.0) * 2.0) * _px_world, 0)
	# partner cycle: slides in over 16 frames, out over the last 16
	var cyc := (int(t / 180.0) + FIRST_MON) % TITLE_MONS.size()
	var phase := t % 180
	var slide := 1.0 - phase / 16.0 if phase < 16 else ((phase - 164) / 16.0 if phase > 164 else 0.0)
	if t < 16:
		slide = 0.0  # the first partner is already standing when the title fades in
	_set_title_mon(cyc)
	var d := Diorama.depth_of(_cam, _mon_home)
	var f := (Px.H * Diorama.K * 0.5) / tan(deg_to_rad(_cam.fov) * 0.5)
	_mon.position = _mon_home + _cam.global_transform.basis.x * (roundf(slide * -120.0) * Diorama.K * d / f)

# ---------------------------------------------------------------- flow
func _unhandled_input(event: InputEvent) -> void:
	if _menu_open or done or t <= 30 or not event.is_pressed():
		return
	if event.is_action_pressed("confirm") or event.is_action_pressed("menu"):
		get_viewport().set_input_as_handled()
		_open_menu()

func _open_menu() -> void:
	_menu_open = true
	UI.sfx("select")
	while true:
		var opts: Array = (["CONTINUE"] if GameState.has_save() else []) + ["NEW GAME", "OPTION", "WHO'S THAT?"]
		var r := await PxMenu.pick(_overlay.get_parent(), opts, {"x": 6, "y": 6, "w": 150, "no_cancel": true})
		if opts[r] == "OPTION":
			var om := OptionsMenu.new()
			_overlay.get_parent().add_child(om)
			om.open()
			await om.closed
			om.queue_free()
			continue
		if opts[r] == "WHO'S THAT?":
			var wp := WtpScreen.new()
			_overlay.get_parent().add_child(wp)
			wp.open()
			await wp.closed
			wp.queue_free()
			continue
		done = true
		await _overlay.fade(20, Color.BLACK, true)
		if opts[r] == "CONTINUE":
			GameState.load_save()
			SceneRouter.goto_overworld()
		else:
			SceneRouter.goto_oak_speech()
		return
