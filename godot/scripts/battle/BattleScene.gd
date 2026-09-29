extends Node3D
## 3D battle scene: stages upstream's BattleScene (src/game/battlescene.js) in
## 3D and implements the UI protocol BattleEngine drives (msg, anim, sync_hp,
## hit_flash, faint, send_out, ball_throw, ...). Everything animates in 60 Hz
## ticks like upstream, so timings match the 2D game frame for frame.
##
## Pieces: BattleStage (3D backdrop/platforms/camera), BattleHud (pixel UI),
## BattleVfx (move animations), BattleEngine (Gen 1 rules). Entry point:
## SceneRouter.start_battle(enc) / await SceneRouter.battle(enc) -> setup(enc).

signal tick

const HUD_SCRIPT := preload("res://scripts/battle/ui/BattleHud.gd")
const TINT_SHADER := preload("res://scripts/battle/actor_tint.gdshader")
const WAVE_SHADER := preload("res://scripts/battle/screen_wave.gdshader")
const BALL_COLORS := {"POKE_BALL": "#e04848", "GREAT_BALL": "#4878e0", "ULTRA_BALL": "#383838", "MASTER_BALL": "#8048c0", "SAFARI_BALL": "#6a9a3a"}
## trainer class -> cast.json look (upstream trainerpics.js CLASS_CAST)
const CLASS_CAST := {
	"YOUNGSTER": "youngster", "BUG_CATCHER": "youngster", "LASS": "girl", "SAILOR": "sailor", "JR_TRAINER_M": "little_boy",
	"JR_TRAINER_F": "cooltrainer_f", "POKEMANIAC": "super_nerd", "SUPER_NERD": "super_nerd", "HIKER": "hiker", "BIKER": "biker",
	"BURGLAR": "rocker", "ENGINEER": "balding_guy", "FISHER": "fisher", "SWIMMER": "swimmer", "CUE_BALL": "biker", "GAMBLER": "gambler",
	"BEAUTY": "beauty", "PSYCHIC_TR": "super_nerd", "ROCKER": "rocker", "JUGGLER": "gambler", "TAMER": "gentleman", "BIRD_KEEPER": "youngster",
	"BLACKBELT": "bruno", "RIVAL1": "blue", "RIVAL2": "blue", "RIVAL3": "blue", "PROF_OAK": "oak", "CHIEF": "gramps", "SCIENTIST": "scientist",
	"GIOVANNI": "giovanni", "ROCKET": "rocket", "COOLTRAINER_M": "cooltrainer_m", "COOLTRAINER_F": "cooltrainer_f", "BRUNO": "bruno",
	"BROCK": "brock", "MISTY": "misty", "LT_SURGE": "surge", "ERIKA": "erika", "KOGA": "koga", "BLAINE": "blaine", "SABRINA": "sabrina",
	"GENTLEMAN": "gentleman", "LORELEI": "lorelei", "CHANNELER": "channeler", "AGATHA": "agatha", "LANCE": "lance",
}

var encounter: Dictionary = {}
var engine: BattleEngine
var stage: BattleStage
var hud: BattleHud
var vfx: BattleVfx
var wave_rect: ColorRect
var result_outcome: Dictionary = {}

# presentation state (upstream BattleScene fields; k = "p" | "e")
var show := {"p": false, "e": false}
var hidden := {"p": false, "e": false}
var offs := {"p": Vector2.ZERO, "e": Vector2.ZERO}      # px offsets (lunges, shakes)
var vis := {"p": 1.0, "e": 1.0}
var clip := {"p": 1.0, "e": 1.0}
var scale_k := {"p": 1.0, "e": 1.0}
var subs := {"p": false, "e": false}
var shake := 0.0
var flash := 0.0
var flash_color := Color.WHITE
var darken := 0.0
var darken_color := Color("#100818")
var platform_slide := 1.0
var trainer_x := -1.0   # px x of the enemy trainer (-1 = hidden)
var player_pic_x := -1.0

var _holders := {}     # k -> Node3D (moves with offsets / slide)
var _models := {}      # k -> Node3D (normalised model root)
var _actors := {}      # k -> PokemonActor (or MissingNo block)
var _model_h := {"p": 1.0, "e": 1.0}
var _tints := {}       # k -> ShaderMaterial
var _species := {"p": "", "e": ""}
var _trainer_node: Node3D
var _player_trainer: Node3D
var _ball: Node3D
var _t := 0
var _acc := 0.0
var _inp := {}
var _frozen := false
var autoplay := false      # tests / demo: auto-advance text, pick moves
var _screenshot := false
var _wave_frames := 0
var _wave_amp := 0.0
var _wave_t := 0

# ------------------------------------------------------------------ setup
func _ready() -> void:
	pass

func _build(env_name: String, time_period: String) -> void:
	stage = BattleStage.new()
	stage.name = "Stage"
	add_child(stage)
	stage.build(env_name, time_period)
	for k in ["e", "p"]:
		var h := Node3D.new()
		h.name = "Holder_" + k
		(stage.enemy_anchor if k == "e" else stage.player_anchor).add_child(h)
		_holders[k] = h
	vfx = BattleVfx.new()
	vfx.name = "Vfx"
	add_child(vfx)
	vfx.setup(self, stage, 7)
	var layer := CanvasLayer.new()
	layer.layer = 5
	add_child(layer)
	wave_rect = ColorRect.new()
	wave_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	var sm := ShaderMaterial.new()
	sm.shader = WAVE_SHADER
	wave_rect.material = sm
	wave_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	wave_rect.visible = false
	layer.add_child(wave_rect)
	var hud_layer := CanvasLayer.new()
	hud_layer.layer = 10
	add_child(hud_layer)
	hud = HUD_SCRIPT.new()
	hud.name = "Hud"
	hud_layer.add_child(hud)

## SceneRouter entry point. enc: see SceneRouter.gd.
func setup(enc: Dictionary) -> void:
	encounter = enc
	var env_name: String = enc.get("env", "")
	if env_name == "":
		env_name = BattleStage.env_for_map(GameState.current_map, enc.get("surfing", false))
	_build(env_name, enc.get("time", ""))
	var opts := _engine_opts(enc)
	engine = BattleEngine.new(opts)
	_screenshot = enc.get("screenshot", false)
	autoplay = enc.get("autoplay", false)
	if _screenshot:
		return
	_run.call_deferred()

func _engine_opts(enc: Dictionary) -> Dictionary:
	var opts := {}
	if str(enc.get("kind", "wild")) == "trainer":
		var cls: String = enc.get("trainer_class", enc.get("trainer_key", "YOUNGSTER"))
		var n: int = int(enc.get("party_index", 1))
		opts = BattleEngine.trainer_opts(cls, n, enc)
	else:
		var sp: String = enc.get("species", "RATTATA")
		if sp.begins_with("MISSINGNO"):
			sp = "MISSINGNO"
			BattleEngine.ensure_glitch_species()
		var mon := GameState.PartyMon.new(sp, int(enc.get("level", 3)), {"random": true} if not enc.has("dvs") else enc["dvs"])
		mon.ot = "WILD"
		opts = {"kind": "wild", "enemy_party": [mon]}
		# Pokemon Tower: without the SILPH SCOPE every wild mon is an unidentifiable GHOST
		# (upstream src/scripts/mid.js); the restless soul is unveiled when you have it
		var scope: bool = int(GameState.bag.get("SILPH_SCOPE", 0)) > 0
		var tower := RegEx.create_from_string("^PokemonTower[1-7]F$").search(GameState.current_map) != null
		var ghost: bool = enc.get("ghost", false)
		if enc.get("restless_soul", false):
			ghost = not scope
			opts["no_catch"] = true
			opts["unveil"] = scope
		elif tower and not scope and not enc.has("ghost"):
			ghost = true
		if ghost:
			opts["ghost"] = true
			opts["no_catch"] = true
			mon.nickname = "GHOST"
		if enc.get("safari", false):
			opts["safari"] = true
	for k in ["no_run", "no_catch", "no_exp", "no_items", "seed"]:
		if enc.has(k):
			opts[k] = enc[k]
	return opts

func _run() -> void:
	await get_tree().process_frame
	if encounter.get("demo", false):
		await _run_demo()
		return
	await transition_in()
	var r: String = await engine.run(self)
	if engine.pay_day > 0 and (r == "win" or r == "caught"):
		GameState.money += engine.pay_day
		await msg(GameState.player_name + " picked up $%d!" % engine.pay_day)
	await _fade(12, true)
	await _evolutions()
	result_outcome = {"result": r, "money": GameState.money, "party_size": GameState.party.size()}
	print("[Battle] result: ", result_outcome)
	SceneRouter.end_battle(result_outcome)

# ------------------------------------------------------------------ tick loop
func _process(dt: float) -> void:
	_poll_input()
	if _frozen:
		return
	_acc += dt
	var n := 0
	while _acc >= 1.0 / 60.0 and n < 4:
		_acc -= 1.0 / 60.0
		n += 1
		_step()
	if n > 0:
		_inp.clear()
	# ticks are 60 Hz; what is shown is blended between the last two, so any display rate looks smooth
	vfx.interpolate(clampf(_acc * 60.0, 0.0, 1.0))

func _poll_input() -> void:
	for a in ["confirm", "cancel", "move_up", "move_down", "move_left", "move_right"]:
		if InputMap.has_action(a) and Input.is_action_just_pressed(a):
			_inp[a] = true

func pressed(a: String) -> bool:
	if _inp.get(a, false):
		_inp.erase(a)
		return true
	return false

## One 60 Hz frame.
func _step() -> void:
	_t += 1
	if hud:
		hud.t = _t
	vfx.step()
	_apply_visuals()
	_capture_interp()
	tick.emit()

func wait(n: int) -> void:
	for i in maxi(0, n):
		await tick

## Freezes the whole scene (screenshots): no more ticks.
func freeze() -> void:
	_frozen = true
	vfx.interpolate(1.0)

## The nodes the tick loop moves (platforms, holders, trainers, ball): remember this tick's pose for interpolation.
func _capture_interp() -> void:
	var it := vfx.interp
	for n in [stage.enemy_anchor, stage.player_anchor, stage.enemy_platform, stage.player_platform]:
		it.capture(n)
	for k in _holders:
		it.capture(_holders[k])
	for n in [_trainer_node, _player_trainer]:
		if n != null and is_instance_valid(n):
			it.capture(n, true)

func _apply_visuals() -> void:
	var sh := 0.0
	if shake > 0.0:
		# a decaying wobble (two incommensurate sines) instead of white noise: reads as a shake, not as jitter
		sh = (sin(_t * 2.3) * 0.6 + sin(_t * 3.7 + 1.3) * 0.4) * shake * 1.6
		shake = maxf(0.0, shake - 0.35 - shake * 0.03)
	if stage.camera:
		stage.camera.h_offset = -sh * 0.012
	if flash > 0.0:
		flash -= 0.12
	hud.flash_amt = maxf(0.0, minf(1.0, flash))
	hud.flash_color = flash_color
	hud.darken_amt = darken
	hud.darken_color = darken_color
	for k in ["e", "p"]:
		_apply_actor(k)
	# platform slide (intro): enemy side slides in from the left, player's from the right
	var w_e := vfx.px_world(stage.enemy_anchor.global_position) * 320.0
	var w_p := vfx.px_world(stage.player_anchor.global_position) * 320.0
	var cam_x := stage.camera.global_transform.basis.x
	var eoff := cam_x * (-(1.0 - platform_slide) * w_e)
	var poff := cam_x * ((1.0 - platform_slide) * w_p)
	stage.enemy_platform.position = Vector3(BattleStage.ENEMY_POS.x, BattleStage.ENEMY_POS.y - 0.14, BattleStage.ENEMY_POS.z) + eoff
	stage.enemy_anchor.position = BattleStage.ENEMY_POS + eoff
	stage.player_platform.position = Vector3(BattleStage.PLAYER_POS.x, BattleStage.PLAYER_POS.y - 0.14, BattleStage.PLAYER_POS.z) + poff
	stage.player_anchor.position = BattleStage.PLAYER_POS + poff
	if _trainer_node:
		_trainer_node.visible = trainer_x >= 0.0
		if trainer_x >= 0.0:
			_place_on_px(_trainer_node, stage.to_global(BattleStage.ENEMY_POS), trainer_x - 236.0)
	if _player_trainer:
		_player_trainer.visible = player_pic_x >= -200.0 and player_pic_x > -999.0 and _player_trainer.get_meta("on", false)
		if _player_trainer.visible:
			_place_on_px(_player_trainer, stage.to_global(BattleStage.PLAYER_POS), player_pic_x - 84.0)
	if _wave_frames > 0:
		_wave_t += 1
		var k2 := sin(minf(1.0, float(_wave_t) / _wave_frames) * PI)
		(wave_rect.material as ShaderMaterial).set_shader_parameter("amp", _wave_amp * k2 / 320.0)
		(wave_rect.material as ShaderMaterial).set_shader_parameter("phase", _wave_t * 0.35)

## `base`: the battler's resting spot. The trainer pics slide on their own (trainer_x / player_pic_x are absolute screen px
## like upstream), so they must not also inherit the platform slide that moves the anchors.
func _place_on_px(n: Node3D, base: Vector3, dx_px: float) -> void:
	var w := vfx.px_world(base)
	n.global_position = base + stage.camera.global_transform.basis.x * dx_px * w

func _apply_actor(k: String) -> void:
	if not _holders.has(k):
		return
	var h: Node3D = _holders[k]
	var anchor: Node3D = stage.enemy_anchor if k == "e" else stage.player_anchor
	var w := vfx.px_world(anchor.global_position)
	var cb := stage.camera.global_transform.basis
	var o: Vector2 = offs[k]
	if _actors.get(k) is PokemonActor:
		(_actors[k] as PokemonActor).sleeping = _mon(k).status == "SLP" and not _mon(k).is_fainted()
	var idle := 0.0
	if show[k] and _actors.has(k) and not _mon(k).is_fainted() and _mon(k).status != "SLP":
		idle = sin(_t / (22.0 if k == "e" else 26.0) + (0.0 if k == "e" else 2.0)) * 1.1
	var sink: float = (1.0 - float(clip[k])) * float(_model_h[k])
	h.position = anchor.global_transform.basis.inverse() * (cb.x * o.x * w + cb.y * (-(o.y + idle)) * w) - Vector3(0, sink, 0)
	h.scale = Vector3.ONE * maxf(0.001, float(scale_k[k]))
	h.visible = show[k] and not hidden[k] and float(vis[k]) > 0.0

func _mon(k: String) -> GameState.PartyMon:
	return engine.mon(engine.e if k == "e" else engine.p)

func key(side: Variant) -> String:
	return "p" if side == engine.p else "e"

# ------------------------------------------------------------------ actors
func _load_actor(k: String, sid: String) -> void:
	if _models.has(k) and is_instance_valid(_models[k]):
		_models[k].queue_free()
	_species[k] = sid
	var model_root := Node3D.new()
	model_root.name = "Model"
	_holders[k].add_child(model_root)
	_models[k] = model_root
	var actor: Node3D
	if k == "e" and engine.o.get("ghost", false) and not subs[k]:
		actor = GhostModel.new()
		model_root.add_child(actor)
	elif sid.begins_with("MISSINGNO") or sid.begins_with("GLITCH"):
		actor = MissingNoBlock.new()
		model_root.add_child(actor)
	else:
		var pa := PokemonActor.new()
		model_root.add_child(pa)
		pa.setup(sid)
		actor = pa
	_actors[k] = actor
	var anchor: Node3D = stage.enemy_anchor if k == "e" else stage.player_anchor
	var w := vfx.px_world(anchor.global_position)
	# upstream draws every battler in the same 64x64 frame; the player's back
	# sprite is the same size but nearer the camera here, so it reads a bit larger
	var frame_px := 64.0 if k == "e" else 64.0 * 1.2
	var sc := 1.0
	var sized := false
	if actor is PokemonActor:
		var s2: float = (actor as PokemonActor).use_sprite_scale(frame_px * w)
		sized = s2 != 1.0
	var aabb := _aabb_of(actor)
	if not sized:
		# no sprite metrics: fit the model's height to ~50 of the frame's 64 px
		var hm := GameData.species_height_m(sid) if GameData.species.has(sid) else 1.5
		var f := clampf(log(hm) / log(2.0), -2.0, 2.0)
		var target_px := (49.0 + 6.0 * f) * frame_px / 64.0
		sc = target_px * w / maxf(0.05, aabb.size.y)
		var size_xz := maxf(aabb.size.x, aabb.size.z)
		if size_xz * sc > frame_px * 1.1 * w:
			sc = frame_px * 1.1 * w / size_xz
	actor.scale = Vector3.ONE * sc
	actor.position = Vector3(-(aabb.position.x + aabb.size.x / 2.0) * sc, -aabb.position.y * sc, -(aabb.position.z + aabb.size.z / 2.0) * sc)
	var size_y := maxf(0.05, aabb.size.y)
	# enemy faces the player (3/4 view toward the lower-left); the player's mon is seen from behind
	model_root.rotation_degrees.y = float(encounter.get("rot_" + k, -10.0 if k == "e" else 180.0))
	_model_h[k] = size_y * sc
	var tm := ShaderMaterial.new()
	tm.shader = TINT_SHADER
	tm.set_shader_parameter("amt", 0.0)
	_tints[k] = tm
	_apply_overlay(actor, tm)

func _aabb_of(n: Node3D) -> AABB:
	var out := AABB()
	var first := true
	var inv := n.global_transform.affine_inverse()
	for mi in _mesh_instances(n):
		var gi: MeshInstance3D = mi
		if gi.mesh == null:
			continue
		var ab := inv * gi.global_transform * gi.mesh.get_aabb()
		if first:
			out = ab
			first = false
		else:
			out = out.merge(ab)
	if first:
		out = AABB(Vector3(-0.5, 0, -0.5), Vector3(1, 1, 1))
	return out

func _mesh_instances(n: Node) -> Array:
	var out: Array = []
	if n is MeshInstance3D:
		out.append(n)
	for c in n.get_children():
		out.append_array(_mesh_instances(c))
	return out

func _apply_overlay(n: Node, m: Material) -> void:
	for mi in _mesh_instances(n):
		(mi as GeometryInstance3D).material_overlay = m

func set_tint(k: String, c: Color, amt: float) -> void:
	if _actors.has(k) and _actors[k] is PokemonActor and is_instance_valid(_actors[k]):
		# the toon shader's own hit-flash uniform (mix toward colour by alpha)
		(_actors[k] as PokemonActor).set_shader_param("flash", Color(c.r, c.g, c.b, clampf(amt, 0.0, 1.0)))
		return
	if _tints.has(k):
		var tm: ShaderMaterial = _tints[k]
		tm.set_shader_parameter("tint", c)
		tm.set_shader_parameter("amt", clampf(amt, 0.0, 1.0))

## Battler centre (upstream center()) in world space / 320x132 pixels.
func center_world(k: String) -> Vector3:
	var anchor: Node3D = stage.enemy_anchor if k == "e" else stage.player_anchor
	var base := anchor.global_position
	if _holders.has(k):
		base = (_holders[k] as Node3D).global_position
	return base + Vector3.UP * _model_h[k] * (0.55 if k == "e" else 0.62)

func center_px(k: String) -> Vector2:
	return stage.world_to_px(center_world(k))

func ground_world(k: String) -> Vector3:
	return (stage.enemy_anchor if k == "e" else stage.player_anchor).global_position

func screen_wave(amp: float, frames: int) -> void:
	_wave_amp = amp
	_wave_frames = frames
	_wave_t = 0
	wave_rect.visible = frames > 0 and amp > 0.0

# ------------------------------------------------------------------ trainers & balls
func _humanoid(cast_key: String) -> Node3D:
	return CharacterSkin.instantiate(cast_key)

func _make_trainer(cls: String) -> void:
	var holder := Node3D.new()
	holder.name = "EnemyTrainer"
	stage.add_child(holder)
	var model := _humanoid(CLASS_CAST.get(cls, "youngster"))
	holder.add_child(model)
	_fit_height(model, 58.0 * vfx.px_world(stage.enemy_anchor.global_position))
	model.rotation_degrees.y = -20.0
	_trainer_node = holder
	holder.visible = false

func _make_player_trainer() -> void:
	var holder := Node3D.new()
	holder.name = "PlayerTrainer"
	stage.add_child(holder)
	var model := _humanoid("red")
	holder.add_child(model)
	_fit_height(model, 70.0 * vfx.px_world(stage.player_anchor.global_position))
	model.rotation_degrees.y = 170.0
	var anim := _find_anim(model)
	if anim:
		for nm in ["Throw", "Attack", "Idle"]:
			if anim.has_animation(nm):
				anim.play(nm)
				if nm != "Idle":
					anim.seek(anim.get_animation(nm).length * 0.45, true)
					anim.pause()
				break
	# the ball held up in the throwing hand (ref 088)
	var ball := _make_ball("POKE_BALL")
	holder.add_child(ball)
	var hgt := _aabb_of(model).size.y * model.scale.y
	if CharacterSkin.resolve_key("red") == "":
		_red_extras(holder, hgt)
	ball.position = Vector3(0.28 * hgt, hgt * 0.98, 0.0)
	ball.scale = Vector3.ONE * hgt * 0.1
	_player_trainer = holder
	holder.visible = false

## RED's cap and backpack for the generic humanoid (upstream playerBackPic:
## red cap with white front, yellow backpack) until a dedicated red.glb exists.
func _red_extras(holder: Node3D, hgt: float) -> void:
	var parts := [
		["sphere", Color("#e03838"), Vector3(0, hgt * 0.9, 0), Vector3(0.36, 0.2, 0.36)],
		["box", Color("#e03838"), Vector3(0, hgt * 0.875, -hgt * 0.14), Vector3(0.3, 0.03, 0.18)],
		["box", Color("#f0c850"), Vector3(0, hgt * 0.56, hgt * 0.12), Vector3(0.3, 0.28, 0.12)],
		["box", Color("#b08030"), Vector3(0, hgt * 0.52, hgt * 0.185), Vector3(0.22, 0.05, 0.02)],
	]
	for pdef in parts:
		var mi := MeshInstance3D.new()
		var mat := StandardMaterial3D.new()
		mat.albedo_color = pdef[1]
		if pdef[0] == "sphere":
			var sm := SphereMesh.new()
			sm.radius = 0.5
			sm.height = 1.0
			sm.is_hemisphere = true
			sm.material = mat
			mi.mesh = sm
		else:
			var bm := BoxMesh.new()
			bm.material = mat
			mi.mesh = bm
		mi.position = pdef[2]
		mi.scale = pdef[3] * hgt
		holder.add_child(mi)

func _fit_height(model: Node3D, h: float) -> void:
	var ab := _aabb_of(model)
	var sc := h / maxf(0.05, ab.size.y)
	model.scale = Vector3.ONE * sc
	model.position = Vector3(0, -ab.position.y * sc, 0)

func _find_anim(n: Node) -> AnimationPlayer:
	if n is AnimationPlayer:
		return n
	for c in n.get_children():
		var f := _find_anim(c)
		if f:
			return f
	return null

func _make_ball(item: String) -> Node3D:
	var path := "res://assets/models/vfx/poke_ball.glb"
	var n: Node3D
	if ResourceLoader.exists(path):
		n = (load(path) as PackedScene).instantiate()
		for mi in _mesh_instances(n):
			var gi: MeshInstance3D = mi
			for i in gi.mesh.get_surface_count():
				var m: Material = gi.mesh.surface_get_material(i)
				if m and m.resource_name == "ball_top":
					var d: StandardMaterial3D = (m as StandardMaterial3D).duplicate()
					d.albedo_color = Color(BALL_COLORS.get(item, "#e04848"))
					gi.set_surface_override_material(i, d)
	else:
		var mi2 := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.5
		sm.height = 1.0
		mi2.mesh = sm
		n = Node3D.new()
		n.add_child(mi2)
	return n

## Ball node placed at an upstream px position (with spin), for throws.
func _ball_at(item: String, px: Vector2, spin: float, tilt: float = 0.0) -> void:
	if _ball != null and str(_ball.get_meta("item", "")) != item:
		_ball.queue_free()
		_ball = null
	if _ball == null:
		_ball = _make_ball(item)
		_ball.set_meta("item", item)
		add_child(_ball)
	_ball.visible = true
	var pos := vfx.to3d(px, 0.3)
	var w := vfx.px_world(pos) * 11.0
	# put(), not a bare global_transform write: this runs after _capture_interp() in the tick, so the interpolation
	# record must be made here (capturing it next tick would feed the blended pose back in and make the ball lag)
	vfx.interp.put(_ball, Transform3D(Basis(Vector3(1, 0, 0), spin) * Basis(Vector3(0, 0, 1), tilt).scaled(Vector3(w, w, w)), pos))

func _ball_hide() -> void:
	if _ball:
		_ball.visible = false

# ------------------------------------------------------------------ UI protocol: text
func msg(text: String, opts: Dictionary = {}) -> void:
	var pages: Array = []
	for chunk in _fmt(text).split("\f"):
		var lines := Px.wrap_text(chunk, 286)
		var i := 0
		while i < lines.size():
			pages.append(lines.slice(i, i + 2))
			i += 2
	for pi in pages.size():
		hud.box = {"lines": pages[pi], "chars": 0, "waiting": false}
		var total: int = "\n".join(pages[pi]).length()
		while int(hud.box["chars"]) < total:
			hud.box["chars"] = int(hud.box["chars"]) + (4 if Input.is_action_pressed("confirm") else 2)
			await tick
		if opts.has("auto") and pi == pages.size() - 1:
			await wait(40 if opts["auto"] is bool else int(opts["auto"]))
			break
		hud.box["waiting"] = true
		var tw := 0
		while not (pressed("confirm") or pressed("cancel")):
			await tick
			tw += 1
			if autoplay and tw > 30:
				break
		_sfx("blip")
		hud.box["waiting"] = false

func _fmt(s: String) -> String:
	return s.replace("{PLAYER}", GameState.player_name).replace("{RIVAL}", GameState.rival_name)

# ------------------------------------------------------------------ UI protocol: intro
func intro(b: BattleEngine) -> void:
	hud.wild = b.wild
	hud.enemy_party = b.e.party
	hud.enemy = _mon("e")
	hud.player = _mon("p")
	hud.disp["p"] = _mon("p").hp
	hud.disp["e"] = _mon("e").hp
	hud.enemy_caught_before = GameState.caught_species.has(_mon("e").species_id)
	_load_actor("e", _mon("e").species_id)
	_load_actor("p", _mon("p").species_id)
	_make_player_trainer()
	if not b.wild:
		_make_trainer(str(b.trainer.get("cls", "YOUNGSTER")))
	platform_slide = 0.0
	player_pic_x = 84.0 + 320.0
	_player_trainer.set_meta("on", true)
	show["e"] = b.wild
	if not b.wild:
		trainer_x = 236.0 - 320.0
	set_tint("e", Color.BLACK, 0.7 if b.wild else 0.0)
	for i in range(1, 41):
		var t := 1.0 - pow(1.0 - i / 40.0, 2)
		platform_slide = t
		player_pic_x = 84.0 + 320.0 * (1.0 - t)
		if not b.wild:
			trainer_x = 236.0 - 320.0 * (1.0 - t)
		await tick
	platform_slide = 1.0
	if b.wild:
		for i in range(10, -1, -1):
			set_tint("e", Color.BLACK, i / 14.0)
			await tick
		set_tint("e", Color.BLACK, 0.0)
		_cry(_mon("e").species_id)
		await shiny_bounce("e")
		hud.boxes["e"] = true
		if b.o.get("ghost", false):
			await msg("Wild GHOST appeared!")
			await msg("Argh! There's no way to identify the GHOST!")
		elif b.o.get("unveil", false):
			# SILPH SCOPE unveils the restless soul (engine/battle/ghost_marowak_anim.asm)
			var real := _mon("e")
			var nick := real.nickname
			real.nickname = "GHOST"
			await msg("Wild GHOST appeared!")
			await msg("The SILPH SCOPE revealed who the GHOST really is!")
			engine.o["ghost"] = true
			for i in 48:
				var gshow: bool = (((i >> 2) % 2 == 0) if i < 24 else ((i >> 3) % 2 == 0)) and i < 44
				if i == 0 or gshow != bool(get_meta("gshow", true)):
					engine.o["ghost"] = gshow
					set_meta("gshow", gshow)
					_load_actor("e", real.species_id)
				await tick
			engine.o["ghost"] = false
			_load_actor("e", real.species_id)
			real.nickname = nick
			_cry(real.species_id)
			GameState.mark_seen(real.species_id)
			await msg("Wild " + real.display_name() + " appeared!")
		else:
			GameState.mark_seen(_mon("e").species_id)
			await msg("Wild " + _mon("e").display_name() + " appeared!")
	else:
		await msg(b.trainer_name() + " wants to fight!")
		for i in 20:
			trainer_x += 7.0
			await tick
		trainer_x = -1.0
		await msg(b.trainer_name() + " sent out " + _mon("e").display_name() + "!", {"auto": 16})
		await ball_open("e")
		hud.boxes["e"] = true
		GameState.mark_seen(_mon("e").species_id)
	await msg("Go! " + _mon("p").display_name() + "!", {"auto": 10})
	for i in 18:
		player_pic_x -= 9.0
		await tick
	player_pic_x = -1000.0
	await ball_open("p")
	hud.boxes["p"] = true

func shiny_bounce(k: String) -> void:
	for i in 12:
		offs[k] = Vector2(offs[k].x, -roundf(sin(i / 12.0 * PI) * 4.0))
		await tick
	offs[k] = Vector2(offs[k].x, 0)

func ball_open(k: String) -> void:
	var c := center_px(k)
	var tx := c.x
	var ty := c.y
	var sx := tx + 40.0 if k == "e" else 40.0
	var sy := 20.0 if k == "e" else 120.0
	_sfx("ballthrow")
	for i in 17:
		var t := i / 16.0
		_ball_at("POKE_BALL", Vector2(sx + (tx - sx) * t, sy + (ty - sy) * t - sin(t * PI) * 26.0), i * 0.6)
		await tick
	_ball_hide()
	_sfx("ballpop")
	vfx.burst(tx, ty, "release")
	if _actors.get(k) is PokemonActor:
		(_actors[k] as PokemonActor).play_once("Spawn")
	show[k] = true
	scale_k[k] = 0.1
	set_tint(k, Color.WHITE, 1.0)
	for i in range(1, 13):
		# pops out of the ball with a small overshoot
		scale_k[k] = 0.1 + 0.9 * Smooth.ease_out_back(i / 12.0, 1.9)
		set_tint(k, Color("#ffd0f0"), 1.0 - i / 14.0)
		await tick
	scale_k[k] = 1.0
	set_tint(k, Color.WHITE, 0.0)
	_cry(_mon(k).species_id)
	await shiny_bounce(k)

# ------------------------------------------------------------------ UI protocol: choices
func choose_action(b: BattleEngine) -> Dictionary:
	var m := _mon("p")
	var queued: Array = encounter.get("auto_actions", [])
	if autoplay and not queued.is_empty():
		var a: String = queued.pop_front()
		await wait(20)
		if a.begins_with("item:"):
			return {"type": "item", "item": a.substr(5), "target": 0}
		if a.begins_with("switch:"):
			return {"type": "switch", "index": int(a.substr(7))}
		if a == "run":
			return {"type": "run"}
		return {"type": "fight", "slot": int(a.substr(6)) if a.begins_with("fight:") else 0}
	var items := ["FIGHT", "PKMN", "ITEM", "RUN"]
	if b.safari:
		items = ["BALL×%d" % BattleEngine.safari_balls(), "BAIT", "ROCK", "RUN"]
		var sa: int = await grid_menu(items, int(get_meta("last_action", 0)))
		set_meta("last_action", maxi(0, sa))
		return {"type": "safari", "what": ["ball", "bait", "rock", "run"][maxi(0, sa)]}
	while true:
		hud.box = {"lines": Px.wrap_text("What will " + m.display_name() + " do?", 150), "chars": 999, "waiting": false}
		var act: int = await grid_menu(items, int(get_meta("last_action", 0)))
		if act < 0:
			continue
		set_meta("last_action", act)
		match act:
			0:
				if m.status == "SLP" or m.status == "FRZ":
					return {"type": "fight", "slot": 0}
				var slot: int = await move_menu(b)
				if slot < 0:
					continue
				return {"type": "fight", "slot": slot}
			1:
				var idx: int = await party_menu(false)
				if idx < 0:
					continue
				return {"type": "switch", "index": idx}
			2:
				if engine.o.get("no_items", false):
					await msg("Items can't be used in this battle!")
					continue
				var r: Dictionary = await bag_menu()
				if r.is_empty():
					continue
				return {"type": "item", "item": r["item"], "target": r.get("target", -1)}
			3:
				return {"type": "run"}
	return {"type": "run"}

func grid_menu(items: Array, sel: int) -> int:
	hud.menu = {"kind": "action", "items": items, "sel": sel}
	var wait_t := 0
	while true:
		await tick
		wait_t += 1
		if autoplay and wait_t > 20:
			hud.menu = {}
			return 0
		if pressed("move_left") or pressed("move_right"):
			hud.menu["sel"] = int(hud.menu["sel"]) ^ 1
		if pressed("move_up") or pressed("move_down"):
			hud.menu["sel"] = int(hud.menu["sel"]) ^ 2
		if pressed("confirm"):
			var s: int = hud.menu["sel"]
			hud.menu = {}
			return s
		if pressed("cancel"):
			hud.menu["sel"] = 3
	return -1

func move_menu(b: BattleEngine) -> int:
	var moves := b.move_list(b.p)
	hud.menu = {"kind": "moves", "moves": moves, "sel": mini(int(get_meta("last_move", 0)), moves.size() - 1)}
	var wait_t := 0
	while true:
		await tick
		wait_t += 1
		var n := moves.size()
		var s: int = hud.menu["sel"]
		if autoplay and wait_t > 20:
			hud.menu = {}
			for i in n:
				if int(moves[i]["pp"]) > 0:
					return i
			return 0
		if pressed("move_left") and s % 2 == 1:
			s -= 1
		if pressed("move_right") and s % 2 == 0 and s + 1 < n:
			s += 1
		if pressed("move_up") and s >= 2:
			s -= 2
		if pressed("move_down") and s + 2 < n:
			s += 2
		hud.menu["sel"] = s
		if pressed("confirm"):
			hud.menu = {}
			set_meta("last_move", s)
			return s
		if pressed("cancel"):
			hud.menu = {}
			return -1
	return -1

func ask_yes_no(q: String) -> bool:
	hud.box = {"lines": Px.wrap_text(q, 200).slice(0, 2), "chars": 0, "waiting": false}
	while int(hud.box["chars"]) < q.length():
		hud.box["chars"] = int(hud.box["chars"]) + 2
		await tick
	var r: int = await _list_menu(["YES", "NO"], 262, 88, 52)
	return r == 0

func choose_index(items: Array, prompt: String) -> int:
	if prompt != "":
		hud.box = {"lines": [prompt], "chars": 999}
	return await _list_menu(items, 180, 40, -1)

func _list_menu(items: Array, x: int, y: int, w: int) -> int:
	hud.menu = {"kind": "choose" if w < 0 else "yesno", "items": items, "sel": 0, "x": x, "y": y, "w": w}
	var wait_t := 0
	while true:
		await tick
		wait_t += 1
		if autoplay and wait_t > 20:
			hud.menu = {}
			return 0
		var s: int = hud.menu["sel"]
		if pressed("move_up"):
			s = maxi(0, s - 1)
		if pressed("move_down"):
			s = mini(items.size() - 1, s + 1)
		hud.menu["sel"] = s
		if pressed("confirm"):
			hud.menu = {}
			return s
		if pressed("cancel"):
			hud.menu = {}
			return -1 if w < 0 else 1
	return -1

## item_target: picking the target of a bag item (upstream partyScreen `pick`): any mon may be chosen, including the one
## that is out and fainted ones (REVIVE); the item itself rejects invalid targets.
func party_menu(forced: bool, item_target: bool = false) -> int:
	var base_msg := "Use on which POKéMON?" if item_target else ("Bring out which POKéMON?" if forced else "Choose a POKéMON.")
	hud.screen = {"kind": "party", "sel": engine.p.idx, "msg": base_msg}
	var n := GameState.party.size()
	var wait_t := 0
	while true:
		await tick
		wait_t += 1
		if autoplay and wait_t > 20:
			for i in n:
				if not GameState.party[i].is_fainted() and i != engine.p.idx:
					hud.screen = {}
					return i
			hud.screen = {}
			return -1
		var s: int = hud.screen["sel"]
		if pressed("move_up"):
			s = n if s == 0 else s - 1
		if pressed("move_down"):
			s = (s + 1) % (n + 1)
		if pressed("move_left") and s > 0 and s < n:
			s = 0
		if pressed("move_right") and s == 0 and n > 1:
			s = 1
		hud.screen["sel"] = s
		if pressed("cancel") and not forced:
			hud.screen = {}
			return -1
		if pressed("confirm"):
			if s == n:
				if not forced:
					hud.screen = {}
					return -1
				continue
			var m: GameState.PartyMon = GameState.party[s]
			if m.is_fainted() and not item_target:
				await _screen_say(m.display_name() + " has no energy left to battle!", base_msg)
				continue
			if s == engine.p.idx and not forced and not item_target:
				await _screen_say(m.display_name() + " is already out!", base_msg)
				continue
			hud.screen = {}
			return s
	return -1

func _screen_say(t: String, restore: String = "Choose a POKéMON.") -> void:
	hud.screen["msg"] = t
	await wait(2)
	while not (pressed("confirm") or pressed("cancel")):
		await tick
	hud.screen["msg"] = restore

func bag_menu() -> Dictionary:
	var items: Array = []
	for id in GameState.bag.keys():
		if int(GameState.bag[id]) > 0 and not BattleEngine.KEY_ITEMS.has(id):
			items.append([id, int(GameState.bag[id])])
	hud.screen = {"kind": "bag", "items": items, "sel": 0, "scroll": 0}
	while true:
		await tick
		var s: int = hud.screen["sel"]
		var l := items.size() + 1
		if pressed("move_up"):
			s = maxi(0, s - 1)
		if pressed("move_down"):
			s = mini(l - 1, s + 1)
		var sc: int = hud.screen["scroll"]
		if s < sc:
			sc = s
		if s > sc + 6:
			sc = s - 6
		hud.screen["sel"] = s
		hud.screen["scroll"] = sc
		if pressed("cancel"):
			hud.screen = {}
			return {}
		if pressed("confirm"):
			if s >= items.size():
				hud.screen = {}
				return {}
			var id: String = items[s][0]
			if not BattleEngine.usable_in_battle(id):
				hud.screen["msg"] = "That can't be used here."
				await wait(2)
				while not (pressed("confirm") or pressed("cancel")):
					await tick
				hud.screen.erase("msg")
				continue
			if BattleEngine.needs_target(id):
				hud.screen = {}
				var tgt: int = await party_menu(false, true)
				if tgt < 0:
					hud.screen = {"kind": "bag", "items": items, "sel": s, "scroll": sc}
					continue
				return {"item": id, "target": tgt}
			hud.screen = {}
			return {"item": id}
	return {}

# ------------------------------------------------------------------ UI protocol: battle feedback
func refresh() -> void:
	await tick

func sync_hp(side: Variant) -> void:
	var k := key(side)
	var m := _mon(k)
	var target := float(m.hp)
	var stp := maxf(0.25, m.max_hp / 48.0)
	while absf(float(hud.disp[k]) - target) > 0.01:
		if hud.disp[k] > target:
			hud.disp[k] = maxf(target, hud.disp[k] - stp)
		else:
			hud.disp[k] = minf(target, hud.disp[k] + stp)
		await tick
	hud.disp[k] = target
	if k == "p" and m.hp > 0 and m.hp < m.max_hp / 5.0:
		_sfx("lowhp")

func hit_flash(side: Variant, eff: float) -> void:
	var k := key(side)
	_sfx("hit_super" if eff > 1.0 else ("hit_weak" if eff < 1.0 and eff > 0.0 else "hit"))
	vfx.hit_react(k, eff)
	var pa: PokemonActor = _actors[k] as PokemonActor if _actors.get(k) is PokemonActor else null
	if pa:
		pa.play_once("Hurt")
	var away := 1.0 if k == "e" else -1.0
	for i in 16:
		vis[k] = 0.0 if (i / 2) % 2 == 1 else 1.0
		# recoil: knocked back, then a damped rattle back to the spot
		var r := exp(-i * 0.28) * cos(i * 1.15)
		offs[k] = Vector2(away * (4.0 if eff > 1.0 else 2.6) * r if i < 12 else 0.0, offs[k].y)
		await tick
	vis[k] = 1.0
	offs[k] = Vector2(0, offs[k].y)

func faint(side: Variant) -> void:
	var k := key(side)
	_cry(_mon(k).species_id, "faint")
	if _actors.get(k) is PokemonActor:
		(_actors[k] as PokemonActor).play("Faint")
	var other := "p" if k == "e" else "e"
	if _actors.get(other) is PokemonActor and not _mon(other).is_fainted():
		(_actors[other] as PokemonActor).play_once("Victory")
	vfx.faint_fx(k)
	for i in 20:
		clip[k] = 1.0 - Smooth.ease_in(i / 20.0, 1.7)   # slumps slowly, then drops out of sight
		await tick
	show[k] = false
	clip[k] = 1.0
	hud.boxes[k] = false

func withdraw(side: Variant) -> void:
	var k := key(side)
	if k == "p":
		await msg(_mon(k).display_name() + ", come back!", {"auto": 8})
	for i in range(12, -1, -1):
		scale_k[k] = 1.0 - Smooth.ease_in(1.0 - i / 12.0, 1.8)   # sucked into the ball: slow start, fast finish
		set_tint(k, Color("#ff8080"), 1.0 - i / 12.0)
		await tick
	show[k] = false
	scale_k[k] = 1.0
	set_tint(k, Color.WHITE, 0.0)
	hud.boxes[k] = false

func send_out(side: Variant) -> void:
	var k := key(side)
	var m := _mon(k)
	hud.disp[k] = m.hp
	if k == "e":
		hud.enemy = m
	else:
		hud.player = m
	subs[k] = false
	hidden[k] = false
	_load_actor(k, m.species_id)
	if k == "p":
		await msg("Go! " + m.display_name() + "!", {"auto": 10})
	await ball_open(k)
	hud.boxes[k] = true

func exp_bar(m: GameState.PartyMon, from: int, to: int) -> void:
	hud.exp_disp = from
	var lo := m.exp_this()
	var hi := m.exp_to_next()
	var stp := maxf(1.0, (hi - lo) / 60.0)
	_sfx("exp")
	while hud.exp_disp < to:
		hud.exp_disp = minf(to, hud.exp_disp + stp)
		await tick
	hud.exp_disp = -1.0

func level_stats(m: GameState.PartyMon, old: Dictionary) -> void:
	_sfx("levelup")
	if m == _mon("p"):
		vfx.levelup_fx("p")
	hud.stats_box = {"m": m, "old": old, "phase": 0}
	await _wait_a()
	hud.stats_box["phase"] = 1
	await _wait_a()
	hud.stats_box = {}
	if m == _mon("p"):
		hud.disp["p"] = m.hp

func _wait_a() -> void:
	await tick
	var n := 0
	while not (pressed("confirm") or pressed("cancel")):
		await tick
		n += 1
		if autoplay and n > 30:
			break

func status_anim(side: Variant, st: String) -> void:
	await vfx.status(key(side), st)

func stat_anim(side: Variant, up: bool) -> void:
	await vfx.stat(key(side), up)

func anim(move_id: String, side: Variant, hit: int) -> void:
	var k := key(side)
	var pa: PokemonActor = _actors[k] as PokemonActor if _actors.get(k) is PokemonActor else null
	if pa and hit == 0 and (move_id == "CHARGE" or move_id.ends_with("_CHARGE")):
		pa.play("Charge")
	elif pa and hit == 0:
		# damaging moves swing the Attack clip, self-targeting ones the Special clip; both hand back to Idle
		# with a crossfade by themselves (PokemonActor.play_once queues it)
		pa.play_once("Special" if BattleVfx.is_status_move(move_id) and pa.has_anim("Special") else "Attack")
	await vfx.move(move_id, k, hit)
	if pa and is_instance_valid(pa) and pa.current_clip() not in [pa.idle_clip(), "Idle", "Attack", "Special", "Hurt"]:
		pa.play("Idle")

## The target of a missed move sidesteps it (Dodge clip + a slide on the stage).
func dodge(side: Variant) -> void:
	var k := key(side)
	if _actors.get(k) is PokemonActor:
		(_actors[k] as PokemonActor).play_once("Dodge")
	var away := 1.0 if k == "e" else -1.0
	for i in 14:
		offs[k] = Vector2(away * 7.0 * sin(i / 13.0 * PI), offs[k].y)
		await tick
	offs[k] = Vector2(0, offs[k].y)

func hide_side(side: Variant, h: bool) -> void:
	hidden[key(side)] = h
	await tick

func substitute(side: Variant, on: bool) -> void:
	var k := key(side)
	for i in 8:
		vis[k] = 1.0 - i / 8.0
		await tick
	subs[k] = on
	if on:
		if _models.has(k):
			(_models[k] as Node3D).queue_free()
		var root := Node3D.new()
		_holders[k].add_child(root)
		_models[k] = root
		var doll := _substitute_doll()
		root.add_child(doll)
		var w := vfx.px_world((stage.enemy_anchor if k == "e" else stage.player_anchor).global_position)
		doll.scale = Vector3.ONE * w * 60.0
		_actors[k] = doll
	else:
		_load_actor(k, _mon(k).species_id)
	for i in 8:
		vis[k] = i / 8.0
		await tick
	vis[k] = 1.0

func _substitute_doll() -> Node3D:
	var n := Node3D.new()
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color("#e8d8a8")
	for spec in [[Vector3(0, 0.45, 0), 0.45], [Vector3(0, 1.05, 0), 0.32], [Vector3(-0.2, 1.4, 0), 0.1], [Vector3(0.2, 1.4, 0), 0.1]]:
		var mi := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = spec[1]
		sm.height = spec[1] * 2.0
		sm.material = mat
		mi.mesh = sm
		mi.position = spec[0]
		n.add_child(mi)
	return n

func transform_to(side: Variant, sp: String) -> void:
	var k := key(side)
	for i in 16:
		set_tint(k, Color.WHITE, i / 16.0)
		await tick
	_load_actor(k, sp)
	for i in range(16, -1, -1):
		set_tint(k, Color.WHITE, i / 16.0)
		await tick
	set_tint(k, Color.WHITE, 0.0)

func flee(side: Variant) -> void:
	var k := key(side)
	for i in 16:
		offs[k] = offs[k] + Vector2(6.0 if k == "e" else -6.0, 0)
		await tick
	show[k] = false
	offs[k] = Vector2.ZERO

func trainer_says(text: String) -> void:
	if text != "":
		await msg(text)

func dex_entry(_sp: String) -> void:
	await tick

func trainer_defeated(b: BattleEngine) -> void:
	_music("victory_leader" if b.o.get("boss", false) else "victory")
	trainer_x = 236.0 + 120.0
	for i in 24:
		trainer_x -= 5.0
		await tick
	trainer_x = 236.0
	await msg(GameState.player_name + " defeated " + b.trainer_name() + "!")
	var wt: String = str(b.trainer.get("win_text", ""))
	if wt != "":
		await msg(wt)
	var money := b.prize_money()
	if money > 0:
		GameState.money += money
		await msg(GameState.player_name + " got $%d for winning!" % money)

## Ball throw + shakes (upstream ballThrow), in 3D.
func ball_throw(item: String, shakes: int, caught: bool) -> void:
	var c := center_px("e")
	var tx := c.x
	var ty := c.y - 4.0
	_sfx("ballthrow")
	for i in 19:
		var t := i / 18.0
		_ball_at(item, Vector2(60 + (tx - 60) * t, 110 + (ty - 110) * t - sin(t * PI) * 50.0), i * 0.6)
		await tick
	_sfx("ballpop")
	vfx.burst(tx, ty + 6, "capture")
	for i in 13:
		scale_k["e"] = 1.0 - i / 12.0
		set_tint("e", Color("#ff90d0"), i / 12.0)
		await tick
	show["e"] = false
	scale_k["e"] = 1.0
	set_tint("e", Color.WHITE, 0.0)
	var gy := stage.world_to_px(ground_world("e")).y - 6.0
	# the ball drops under gravity and bounces on the ground with energy loss until it comes to rest
	var y := ty
	var vy := 0.0
	var rolled := 0.0
	for i in 70:
		vy += 0.42
		y += vy
		if y >= gy:
			y = gy
			if vy > 1.4:
				_sfx("hit_weak")
				vy = -vy * 0.48
				rolled += 0.9
			else:
				vy = 0.0
		_ball_at(item, Vector2(tx + rolled * (1.0 - exp(-i * 0.12)) * 2.0, y), rolled * i * 0.05)
		await tick
		if vy == 0.0 and y >= gy and i > 12:
			break
	tx += rolled * 2.0
	await wait(20)
	for k in mini(3, shakes):
		for i in 16:
			var a := sin(i / 16.0 * TAU) * 3.0
			_ball_at(item, Vector2(tx + a, gy), 0.0, a * 0.2)
			await tick
		_sfx("shake")
		await wait(24)
	if caught:
		_sfx("caught")
		for i in 40:
			if _t % 10 < 5:
				vfx.sparkle_at(tx, gy - 8)
			await tick
	else:
		_ball_hide()
		vfx.burst(tx, gy - 6, "release")
		show["e"] = true
		for i in 11:
			scale_k["e"] = i / 10.0
			await tick
		scale_k["e"] = 1.0

# ------------------------------------------------------------------ transitions & evolution
func transition_in() -> void:
	_sfx("battle_start")
	var snap: Variant = encounter.get("_snapshot")
	if snap is Texture2D:
		var kind: String = str(encounter.get("transition", "wild" if encounter.get("kind", "wild") == "wild" else "trainer"))
		var tr := BattleTransition.new(snap, kind)
		add_child(tr)
		hud.fade = 1.0   # the battle underneath stays hidden until the wipe has covered the screen
		for i in int(BattleTransition.FRAMES.get(kind, 62)):
			tr.set_frame(i)
			await tick
		tr.queue_free()
	# the battle scene fades in from the transition's black
	for i in 10:
		hud.fade = 1.0 - i / 10.0
		await tick
	hud.fade = 0.0

func _fade(frames: int, out: bool) -> void:
	for i in frames + 1:
		hud.fade = float(i) / frames if out else 1.0 - float(i) / frames
		await tick

func _evolutions() -> void:
	for m in GameState.party:
		var pm: GameState.PartyMon = m
		if pm.leveled_in_battle and not pm.is_fainted():
			pm.leveled_in_battle = false
			var evo := pm.evo_by_level()
			if evo != "":
				await evolve(pm, evo)
		pm.leveled_in_battle = false

## 3D evolution sequence (upstream EvoScene): silhouette flicker between the
## two models, speeding up, rising sparkles, white flash, new form.
func evolve(m: GameState.PartyMon, to: String) -> void:
	var evo := EvolutionStage.new()
	add_child(evo)
	evo.build(self, m.species_id, to)
	hud.boxes = {"e": false, "p": false}
	hud.box = {}
	hud.screen = {"kind": "evo", "text": ""}
	await _fade(8, false)
	_music("evolution")
	await _evo_say("What? " + m.display_name() + " is evolving!")
	var period := 50
	var cancelled := false
	for k in 22:
		evo.show_form(k % 2 == 1, true)
		for i in period:
			if pressed("cancel"):
				cancelled = true
				break
			if i % 3 == 0:
				evo.spark_up()
			await tick
		if cancelled:
			break
		period = maxi(3, int(floor(period * 0.8)))
	if cancelled:
		evo.show_form(false, false)
		await _evo_say("Huh? " + m.display_name() + " stopped evolving!")
		evo.queue_free()
		hud.screen = {}
		return
	evo.show_form(true, false)
	evo.burst()
	for i in 30:
		flash = 1.0 - i / 30.0    # _apply_visuals owns hud.flash_amt (it would overwrite a direct write every tick)
		flash_color = Color.WHITE
		await tick
	_cry(to)
	var old_name := m.display_name()
	m.evolve_to(to)
	GameState.caught_species[to] = true
	GameState.mark_seen(to)
	await _evo_say("Congratulations! Your " + old_name + " evolved into " + str(GameData.get_species(to).get("name", to)) + "!")
	for mv in m.moves_at_level(m.level):
		await engine.learn_move(m, mv)
	evo.queue_free()
	hud.screen = {}

func _evo_say(t: String) -> void:
	hud.screen["text"] = t
	await tick
	var n := 0
	while not (pressed("confirm") or pressed("cancel")):
		await tick
		n += 1
		if autoplay and n > 30:
			break
	hud.screen["text"] = ""

# ------------------------------------------------------------------ audio (optional autoload)
func _sfx(n: String) -> void:
	var a := get_node_or_null("/root/Audio")
	if a and a.has_method("sfx"):
		a.sfx(n)

func _cry(sp: String, kind: String = "") -> void:
	var a := get_node_or_null("/root/Audio")
	if a and a.has_method("cry"):
		if kind != "":
			a.cry(sp, kind)
		else:
			a.cry(sp)

func _music(n: String) -> void:
	var a := get_node_or_null("/root/Audio")
	if a and a.has_method("music"):
		a.music(n)

# ------------------------------------------------------------------ screenshot / debug states
## Poses the battle in one of the reference states without running the flow:
## state: "idle" (both out, boxes, empty text box), "intro" (wild intro with
## the player's trainer seen from behind), "message" (text in the box),
## "menu" (FIGHT/PKMN/ITEM/RUN), "moves" (move menu), "vfx" (a move frozen
## at a fraction `vfx_t` of its animation). Options: text, enemy_hp (0..1),
## move, attacker ("p"|"e"), vfx_t, waiting (bool: show ▼).
func pose(state: String, o: Dictionary) -> void:
	hud.wild = engine.wild
	hud.enemy_party = engine.e.party
	hud.enemy = _mon("e")
	hud.player = _mon("p")
	if o.has("enemy_hp"):
		_mon("e").hp = maxi(1, roundi(_mon("e").max_hp * float(o["enemy_hp"])))
	hud.disp["p"] = _mon("p").hp
	hud.disp["e"] = _mon("e").hp
	_load_actor("e", _mon("e").species_id)
	_load_actor("p", _mon("p").species_id)
	show["e"] = true
	show["p"] = state != "intro"
	hud.boxes["e"] = true
	hud.boxes["p"] = state != "intro"
	platform_slide = 1.0
	var text: String = o.get("text", "")
	if text != "":
		hud.box = {"lines": Px.wrap_text(_fmt(text), 286).slice(0, 2), "chars": 999, "waiting": o.get("waiting", false)}
	match state:
		"intro":
			_make_player_trainer()
			_player_trainer.set_meta("on", true)
			player_pic_x = 84.0
			if text == "":
				hud.box = {"lines": ["Wild " + _mon("e").display_name() + " appeared!"], "chars": 999}
		"menu":
			hud.box = {"lines": Px.wrap_text("What will " + _mon("p").display_name() + " do?", 150), "chars": 999}
			hud.menu = {"kind": "action", "items": ["FIGHT", "PKMN", "ITEM", "RUN"], "sel": 0}
		"moves":
			hud.menu = {"kind": "moves", "moves": engine.move_list(engine.p), "sel": 0}
	for i in 2:
		_step()
	if state == "transition":   # --snap=<png of the overworld> --tkind=wild|trainer|boss --vfx_t=<frame 0..1>
		var img := Image.load_from_file(str(o.get("snap", "")))
		var kind := str(o.get("tkind", "wild"))
		if img:
			var tr := BattleTransition.new(ImageTexture.create_from_image(img), kind)
			add_child(tr)
			tr.set_frame(float(o.get("vfx_t", 0.5)) * float(BattleTransition.FRAMES.get(kind, 62)))
	if state == "vfx":
		await _pose_vfx(str(o.get("move", "TACKLE")), str(o.get("attacker", "p")), float(o.get("vfx_t", 0.55)))

## A move id, or "status:PSN" / "stat:up" / "stat:down" / "levelup" / "faint" / "hit:2.0" to preview those effects.
func _run_vfx(move_id: String, k: String) -> void:
	if move_id.begins_with("status:"):
		await vfx.status(k, move_id.substr(7))
	elif move_id.begins_with("stat:"):
		await vfx.stat(k, move_id.substr(5) == "up")
	elif move_id == "levelup":
		vfx.levelup_fx(k)
		await vfx.wait(60)
	elif move_id == "faint":
		vfx.faint_fx(k)
		await vfx.wait(30)
	elif move_id.begins_with("hit:"):
		vfx.hit_react(k, float(move_id.substr(4)))
		await vfx.wait(24)
	else:
		await vfx.move(move_id, k, 0)

## Runs a move animation to completion synchronously; returns its length in
## frames, or -1 if it never finishes (used by the tests on every move).
func vfx_frames(move_id: String, k: String) -> int:
	var done := [false]
	var run1 := func() -> void:
		await _run_vfx(move_id, k)
		done[0] = true
	run1.call()
	var total := 0
	while not done[0] and total < 900:
		_step()
		total += 1
	vfx.clear()
	for kk in ["e", "p"]:
		offs[kk] = Vector2.ZERO
		vis[kk] = 1.0
		clip[kk] = 1.0
		scale_k[kk] = 1.0
	return total if done[0] else -1

func _pose_vfx(move_id: String, k: String, frac: float) -> void:
	# pass 1: count the animation's frames; pass 2: replay to `frac` and freeze
	var total := 0
	var done := [false]
	var run1 := func() -> void:
		await _run_vfx(move_id, k)
		done[0] = true
	run1.call()
	while not done[0] and total < 600:
		_step()
		total += 1
	vfx.clear()
	for kk in ["e", "p"]:
		offs[kk] = Vector2.ZERO
		vis[kk] = 1.0
		clip[kk] = 1.0
		scale_k[kk] = 1.0
		set_tint(kk, Color.WHITE, 0.0)
	shake = 0.0
	flash = 0.0
	darken = 0.0
	screen_wave(0, 0)
	vfx.rng.seed = 7
	var cap := maxi(1, int(floor(total * frac)))
	var run2 := func() -> void:
		await _run_vfx(move_id, k)
	run2.call()
	for i in cap:
		_step()
	shake = 0.0
	stage.camera.h_offset = 0.0
	freeze()

# ------------------------------------------------------------------ the old man's catching demo
## Viridian City's old man shows how to catch (upstream src/scripts/pallet.js
## catchDemo): his back on the player platform, a wild WEEDLE, one POKé BALL.
## The player's party and bag are untouched; returns "caught".
func _run_demo() -> void:
	hud.wild = true
	hud.enemy = _mon("e")
	hud.disp["e"] = _mon("e").hp
	_load_actor("e", _mon("e").species_id)
	var holder := Node3D.new()
	stage.add_child(holder)
	var old_man := _humanoid("old_man")
	holder.add_child(old_man)
	_fit_height(old_man, 70.0 * vfx.px_world(stage.player_anchor.global_position))
	old_man.rotation_degrees.y = 180.0
	_player_trainer = holder
	_player_trainer.set_meta("on", true)
	player_pic_x = 84.0
	show["e"] = true
	hud.boxes["e"] = true
	platform_slide = 1.0
	await _fade(10, false)
	await msg("Wild " + _mon("e").display_name() + " appeared!")
	await msg("OLD MAN used POKé BALL!")
	await ball_throw("POKE_BALL", 3, true)
	await msg("All right! " + str(GameData.get_species(_mon("e").species_id).get("name", "")) + " was caught!")
	await _fade(12, true)
	result_outcome = {"result": "caught", "money": GameState.money, "demo": true}
	SceneRouter.end_battle(result_outcome)
