class_name OakSpeech
extends Node3D
## NEW GAME: port of title.js OakIntro + newGameIntro(). The pale radial
## backdrop and oval stage of upstream, with the real 3D models standing on
## the stage where upstream blits its pictures (bottom edge y=120): PROF.OAK,
## NIDORINO, RED, the rival; each cross-fades in/out like upstream's alpha
## ramp. Real text from text.json (OakSpeechText1...), the NEW NAME / preset
## name menus and the naming keyboard, then RED shrinks away, the screen goes
## white and the adventure starts in RED's room.

const BG_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, fog_disabled;
//COMMON
void fragment() {
	vec2 p = floor(SCREEN_UV * vec2(320.0, 180.0));
	float d = length(vec2(p.x - 160.0, (p.y - 70.0) * 1.4));
	ALBEDO = mix(hexc(0xf8f4e8), hexc(0xc8d8e8), min(1.0, d / 220.0));
}
"""

var who := "oak"
var x := 160.0
var alpha := 1.0
var shrink := 1.0

var _cam: Camera3D
var _stage: Node3D
var _models := {}
var _heights := {"oak": 60.0, "mon": 46.0, "red": 60.0, "blue": 60.0}
var _layer: CanvasLayer

func _init() -> void:
	name = "Intro"  # Audio follows "Intro" with the oak_intro song

func _ready() -> void:
	GameState.start_new_adventure()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#f8f4e8")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.85, 0.87, 0.95)
	env.ambient_light_energy = 0.8
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-40, -25, 0)
	key.light_energy = 0.95
	add_child(key)
	_cam = Camera3D.new()
	_cam.fov = 30.0
	_cam.position = Vector3(0, 1.4, 9.0)
	_cam.rotation_degrees = Vector3(-4, 0, 0)
	_cam.current = true
	add_child(_cam)
	add_child(Diorama.backdrop(_cam, BG_SHADER.replace("//COMMON", Diorama.glsl_common()), 60.0))
	_build_stage()
	for k in ["oak", "mon", "red", "blue"]:
		var holder := Node3D.new()
		if k == "mon":
			var a := PokemonActor.new()
			holder.add_child(a)
			a.setup("NIDORINO")
		else:
			holder.add_child(CharacterModel.build({"oak": "oak", "red": "red", "blue": "blue"}[k]))
			Diorama.play_anim(holder, ["Idle"])
		add_child(holder)
		holder.visible = false
		_models[k] = holder
	_layer = CanvasLayer.new()
	_layer.layer = 10
	add_child(_layer)
	_fade_canvas = FadeCanvas.new()
	_layer.add_child(_fade_canvas)
	_run()

var _fade_canvas: FadeCanvas

## ellipse(160,118,56,10) + ellipse(160,117,52,8): the stage, as a real disc.
func _build_stage() -> void:
	_stage = Node3D.new()
	add_child(_stage)
	var c := Diorama.ground_at(_cam, Vector2(160, 118))
	var depth := Diorama.depth_of(_cam, c)
	var f := (Px.H * Diorama.K * 0.5) / tan(deg_to_rad(_cam.fov) * 0.5)
	var wpp := Diorama.K * depth / f  # world units per logical pixel at the stage
	for spec in [[56.0, 0.0, Color("#b8c8d8")], [52.0, 0.02, Color("#d0dce8")]]:
		var mi := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = spec[0] * wpp
		cyl.bottom_radius = spec[0] * wpp
		cyl.height = 0.04
		mi.mesh = cyl
		var m := StandardMaterial3D.new()
		m.albedo_color = spec[2]
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mi.material_override = m
		mi.position = c + Vector3(0, -0.02 + spec[1], 0)
		_stage.add_child(mi)

func _process(_dt: float) -> void:
	for k in _models:
		var n: Node3D = _models[k]
		n.visible = k == who and alpha > 0.0
	var cur: Node3D = _models.get(who)
	if cur == null:
		return
	Diorama.stand(_cam, cur, Vector2(x, 120), _heights[who] * shrink, 0.0 if who != "mon" else -30.0)
	_set_alpha(cur, alpha)

func _set_alpha(n: Node, a: float) -> void:
	if n is GeometryInstance3D:
		(n as GeometryInstance3D).transparency = 1.0 - a
	for c in n.get_children():
		_set_alpha(c, a)

func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame

func _fade_pic(out: bool) -> void:
	for i in 11:
		alpha = (10 - i) / 10.0 if out else i / 10.0
		await _frames(1)

func _say(label: String, opts: Dictionary = {}) -> void:
	await UI.say(GameText.get_text(label, label), opts)

func _run() -> void:
	await _fade_canvas.fade(20, Color.BLACK, false)
	await _say("OakSpeechText1")
	await _fade_pic(true)
	who = "mon"
	x = 160
	await _fade_pic(false)
	var au := UI.audio()
	if au and au.has_method("cry"):
		au.cry("NIDORINO")
	await _say("OakSpeechText2A")
	await _say("OakSpeechText2B")
	await _fade_pic(true)
	who = "red"
	x = 200
	for i in 11:
		alpha = i / 10.0
		x = 200 - i * 4
		await _frames(1)
	await _say("IntroducePlayerText", {"no_wait": true})
	var r: int = await UI.choose(["NEW NAME", "RED", "ASH", "JACK"], {"x": 6, "y": 6, "w": 100, "no_cancel": true})
	_close_boxes()
	if r == 0:
		GameState.player_name = await NamingScreen.ask_name(_layer, "YOUR NAME?", "RED", 7)
	else:
		GameState.player_name = ["", "RED", "ASH", "JACK"][r]
	await _say("YourNameIsText")
	await _fade_pic(true)
	who = "blue"
	x = 160
	await _fade_pic(false)
	await _say("IntroduceRivalText", {"no_wait": true})
	r = await UI.choose(["NEW NAME", "BLUE", "GARY", "JOHN"], {"x": 6, "y": 6, "w": 100, "no_cancel": true})
	_close_boxes()
	if r == 0:
		GameState.rival_name = await NamingScreen.ask_name(_layer, "RIVAL's NAME?", "BLUE", 7)
	else:
		GameState.rival_name = ["", "BLUE", "GARY", "JOHN"][r]
	await _say("HisNameIsText")
	await _fade_pic(true)
	# character creator (upstream customizer.js): boy / girl, hair, face, clothes ... then RED walks back on stage
	_fade_canvas.visible = false
	var chosen: PlayerLook = await CharacterCreator.run(_layer, GameState.player_look())
	GameState.set_look(chosen)
	_fade_canvas.visible = true
	_rebuild_player_model()
	who = "red"
	x = 160
	await _fade_pic(false)
	await _say("OakSpeechText3")
	UI.sfx("shrink")
	for i in 30:
		shrink = 1.0 - i / 34.0
		await _frames(1)
	await _fade_canvas.fade(30, Color.WHITE, true)
	GameState.clock_running = true
	SceneRouter.goto_overworld()

## The stage's RED is rebuilt from the look picked in the creator.
func _rebuild_player_model() -> void:
	var holder: Node3D = _models["red"]
	for c in holder.get_children():
		c.queue_free()
	holder.add_child(CharacterModel.build("red"))
	Diorama.play_anim(holder, ["Idle"])

## no_wait boxes stay up under the menu (ui.js); drop them once answered.
func _close_boxes() -> void:
	for c in UI.layer.get_children():
		if c is DialogueBox:
			c.queue_free()
