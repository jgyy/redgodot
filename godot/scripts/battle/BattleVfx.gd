class_name BattleVfx
extends Node3D
## Battle move/status animations: a port of upstream src/art/vfx.js (its particle
## system, primitives and every per-move recipe) that renders in 3D.
##
## Upstream animates in its 320x132 battle framebuffer at 60 fps. Here every
## particle keeps upstream's pixel-space simulation (position, velocity, drag,
## colour ramp, size) but is drawn as a Blender-generated mesh
## (assets/models/vfx/*.glb) placed on the slanted 3D plane through both
## battlers (BattleStage.px_to_world), scaled to upstream's pixel size at its
## depth, with additive glow sprites. Beams, bolts, rings, waves and ground
## shock rings are real 3D geometry. Time advances in 60 Hz ticks (`step()`),
## so a capture can freeze an effect at an exact frame (Main.gd --vfx_t).

signal ticked

const VFX_DIR := "res://assets/models/vfx/"
const SHAPES := ["dot", "flame", "spark", "star", "ring", "bubble", "leaf", "snow", "rock", "note", "z", "coin", "seed",
	"needle", "bone", "egg", "shard", "heart", "impact", "claw", "fist", "drop", "arrow"]
const GLOWY := {"flame": 0.28, "spark": 0.3, "star": 0.25, "bubble": 0.12, "shard": 0.2, "note": 0.15}
## world size (in upstream pixels) of each 1 m nominal mesh per unit of `size`
const SHAPE_PX := {"dot": [1.0, 1.0], "flame": [2.0, 0.0], "spark": [0.0, 4.0], "star": [2.4, 0.0], "ring": [2.0, 0.0],
	"bubble": [2.1, 3.2], "leaf": [3.2, 0.0], "snow": [2.2, 1.0], "rock": [2.1, 0.0], "note": [0.0, 8.0], "z": [0.0, 8.0],
	"coin": [0.0, 5.0], "seed": [0.0, 3.4], "needle": [0.0, 8.0], "bone": [0.0, 11.0], "egg": [0.0, 7.5], "shard": [0.0, 7.0],
	"heart": [0.0, 5.5], "impact": [2.0, 0.0], "claw": [1.0, 0.0], "fist": [2.0, 0.0], "drop": [2.0, 0.0], "arrow": [0.0, 7.0]}
## Particles are drawn this much larger than upstream's 320 px sprites so they read on a 960 px wide 3D view.
const PART_SCALE := 1.3
const MIN_SIZE := {"flame": 1.5, "star": 2.0, "ring": 1.0, "bubble": 1.5, "leaf": 3.0, "rock": 2.0}

const FIRE := ["#f86828", "#e83818", "#b82810"]
const WATER := ["#58a8f8", "#3878e0", "#2050b0"]
const ICE := ["#e8ffff", "#a8e8f8", "#58b8e8"]
const ELEC := ["#fff8a0", "#f8d830", "#e8a818"]
const GRASS := ["#a8e060", "#58b040", "#2a7a30"]
const PSY := ["#ffb0e0", "#f070c0", "#b040a0"]
const POIS := ["#d898f0", "#a050c8", "#6a2a8a"]
const WHITE := Color(1, 1, 1)

## move -> [recipe, arg] (upstream MOVES table, verbatim)
const MOVES := {
	"POUND": ["hit"], "KARATE_CHOP": ["cut"], "DOUBLESLAP": ["hit"], "COMET_PUNCH": ["punch"], "MEGA_PUNCH": ["punch"], "PAY_DAY": ["coins"],
	"FIRE_PUNCH": ["punch", "ember"], "ICE_PUNCH": ["punch", "icebeam"], "THUNDERPUNCH": ["punch", "thundershock"], "SCRATCH": ["claw"], "VICEGRIP": ["bite"],
	"GUILLOTINE": ["bite"], "RAZOR_WIND": ["wind"], "SWORDS_DANCE": ["swords"], "CUT": ["cut"], "GUST": ["wind"], "WING_ATTACK": ["wing"], "WHIRLWIND": ["wind"],
	"FLY": ["fly"], "BIND": ["wrap"], "SLAM": ["bighit"], "VINE_WHIP": ["vinewhip"], "STOMP": ["kick"], "DOUBLE_KICK": ["kick"], "MEGA_KICK": ["kick"], "JUMP_KICK": ["kick"],
	"ROLLING_KICK": ["kick"], "SAND_ATTACK": ["sand"], "HEADBUTT": ["bighit"], "HORN_ATTACK": ["needles", 1], "FURY_ATTACK": ["needles", 1], "HORN_DRILL": ["needles", 3],
	"TACKLE": ["hit"], "BODY_SLAM": ["bighit"], "WRAP": ["wrap"], "TAKE_DOWN": ["bighit"], "THRASH": ["bighit"], "DOUBLE_EDGE": ["bighit"], "TAIL_WHIP": ["tailwhip"],
	"POISON_STING": ["poisonsting"], "TWINEEDLE": ["needles", 2], "PIN_MISSILE": ["needles", 3], "LEER": ["leer"], "BITE": ["bite"], "GROWL": ["sound", "#ffffff"],
	"ROAR": ["sound", "#ffe0a0"], "SING": ["sing"], "SUPERSONIC": ["sound", "#f0f0a0"], "SONICBOOM": ["sound", "#ffffff"], "DISABLE": ["disable"], "ACID": ["poison"],
	"EMBER": ["ember"], "FLAMETHROWER": ["flamethrower"], "MIST": ["mist"], "WATER_GUN": ["watergun"], "HYDRO_PUMP": ["hydropump"], "SURF": ["surf"],
	"ICE_BEAM": ["icebeam"], "BLIZZARD": ["blizzard"], "PSYBEAM": ["psybeam"], "BUBBLEBEAM": ["bubble"], "AURORA_BEAM": ["aurorabeam"], "HYPER_BEAM": ["hyperbeam"],
	"PECK": ["needles", 1], "DRILL_PECK": ["needles", 3], "SUBMISSION": ["bighit"], "LOW_KICK": ["kick"], "COUNTER": ["counter"], "SEISMIC_TOSS": ["bighit"],
	"STRENGTH": ["bighit"], "ABSORB": ["drain"], "MEGA_DRAIN": ["drain"], "LEECH_SEED": ["leechseed"], "GROWTH": ["statup", "#a8e060"], "RAZOR_LEAF": ["razorleaf"],
	"SOLARBEAM": ["solarbeam"], "POISONPOWDER": ["powder", "#b070d8"], "STUN_SPORE": ["powder", "#f8e060"], "SLEEP_POWDER": ["powder", "#80d8a0"],
	"PETAL_DANCE": ["petaldance"], "STRING_SHOT": ["string"], "DRAGON_RAGE": ["dragonrage"], "FIRE_SPIN": ["firespin"], "THUNDERSHOCK": ["thundershock"],
	"THUNDERBOLT": ["thunderbolt"], "THUNDER_WAVE": ["thunderwave"], "THUNDER": ["thunder"], "ROCK_THROW": ["rocks", 2], "EARTHQUAKE": ["earthquake"],
	"FISSURE": ["fissure"], "DIG": ["dig"], "TOXIC": ["poison"], "CONFUSION": ["confusion"], "PSYCHIC_M": ["psychic"], "HYPNOSIS": ["hypnosis"], "MEDITATE": ["glow", "#f8a0d0"],
	"AGILITY": ["doubleteam"], "QUICK_ATTACK": ["quick"], "RAGE": ["rage"], "TELEPORT": ["teleport"], "NIGHT_SHADE": ["nightshade"], "MIMIC": ["mimic"],
	"SCREECH": ["sound", "#f8f8f8"], "DOUBLE_TEAM": ["doubleteam"], "RECOVER": ["heal"], "HARDEN": ["glow", "#ffffff"], "MINIMIZE": ["minimize"],
	"SMOKESCREEN": ["gas", "#404048"], "CONFUSE_RAY": ["confuseray"], "WITHDRAW": ["glow", "#b0d8ff"], "DEFENSE_CURL": ["glow", "#ffffff"], "BARRIER": ["shield", "#c0f0ff"],
	"LIGHT_SCREEN": ["shield", "#f8f8a0"], "HAZE": ["haze"], "REFLECT": ["shield", "#c0d0ff"], "FOCUS_ENERGY": ["focus"], "BIDE": ["bide"], "METRONOME": ["metronome"],
	"MIRROR_MOVE": ["glow"], "SELFDESTRUCT": ["explosion"], "EGG_BOMB": ["egg"], "LICK": ["lick"], "SMOG": ["gas", "#8a7a9a"], "SLUDGE": ["poison"], "BONE_CLUB": ["bone"],
	"FIRE_BLAST": ["fireblast"], "WATERFALL": ["hydropump"], "CLAMP": ["clamp"], "SWIFT": ["swift"], "SKULL_BASH": ["bighit"], "SPIKE_CANNON": ["needles", 3],
	"CONSTRICT": ["wrap"], "AMNESIA": ["glow", "#c0c0ff"], "KINESIS": ["glow", "#f8a0d0"], "SOFTBOILED": ["heal"], "HI_JUMP_KICK": ["kick"], "GLARE": ["leer"],
	"DREAM_EATER": ["drain", ["#ffb0e0", "#f070c0"]], "POISON_GAS": ["gas", "#b080d0"], "BARRAGE": ["egg"], "LEECH_LIFE": ["drain", ["#f8a0a0", "#e05050"]],
	"LOVELY_KISS": ["glow", "#ff90c0"], "SKY_ATTACK": ["skyattack"], "TRANSFORM": ["transform"], "BUBBLE": ["bubble"], "DIZZY_PUNCH": ["punch"], "SPORE": ["powder", "#d8c080"],
	"FLASH": ["glow", "#ffffff"], "PSYWAVE": ["psychic"], "SPLASH": ["splash"], "ACID_ARMOR": ["glow", "#a0c0ff"], "CRABHAMMER": ["punch", "watergun"],
	"EXPLOSION": ["explosion"], "FURY_SWIPES": ["claw", 2], "BONEMERANG": ["bone"], "REST": ["rest"], "ROCK_SLIDE": ["rocks", 6], "HYPER_FANG": ["bite"],
	"SHARPEN": ["glow", "#ffffff"], "CONVERSION": ["conversion"], "TRI_ATTACK": ["triattack"], "SUPER_FANG": ["bite"], "SLASH": ["claw", 3], "SUBSTITUTE": ["glow"],
	"STRUGGLE": ["hit"], "CHARGE": ["charge"], "DRAIN": ["drain"], "LEECH_SEED_DRAIN": ["seeddrain"], "HEAL_ITEM": ["healitem"], "ROCK_THROW_SAFARI": ["safariRock"],
	"FLY_CHARGE": ["fly_charge"], "DIG_CHARGE": ["dig_charge"], "BIDE_HIT": ["counter"], "HORN": ["needles", 2],
}

var scene: Node          # BattleScene (actor offsets, tint, shake, flash)
var stage: BattleStage
var rng := RandomNumberGenerator.new()
var parts: Array = []
var fx: Array = []
var frame := 0
var _meshes: Dictionary = {}
var _glow_tex: Texture2D
var interp := TickInterp.new()   # render-rate smoothing of everything the 60 Hz ticks move
var _plane_e := Vector3.ZERO
var _plane_p := Vector3.ZERO

func setup(the_scene: Node, the_stage: BattleStage, seed_v: int = 1) -> void:
	scene = the_scene
	stage = the_stage
	rng.seed = seed_v
	for s in SHAPES:
		_meshes[s] = _load_mesh(s)
	var gt: Texture2D = VfxTex.soft()
	_glow_tex = gt

func _load_mesh(s: String) -> Mesh:
	var path := VFX_DIR + s + ".glb"
	if ResourceLoader.exists(path):
		var ps: PackedScene = load(path)
		if ps:
			var inst := ps.instantiate()
			var mi := _find_mi(inst)
			var m: Mesh = mi.mesh if mi else null
			inst.free()
			if m:
				return m
	var sm := SphereMesh.new()
	sm.radius = 0.5
	sm.height = 1.0
	return sm

func _find_mi(n: Node) -> MeshInstance3D:
	if n is MeshInstance3D:
		return n
	for c in n.get_children():
		var f := _find_mi(c)
		if f:
			return f
	return null

func rand(a: float, b: float) -> float:
	return a + rng.randf() * (b - a)

# ------------------------------------------------------------------ time
## One 60 Hz frame: advance every particle and effect, then wake recipes.
func step() -> void:
	frame += 1
	interp.begin_tick()
	_refresh_plane()
	var i := parts.size() - 1
	while i >= 0:
		if not _update_particle(parts[i]):
			_free_part(parts[i])
			parts.remove_at(i)
		i -= 1
	var j := fx.size() - 1
	while j >= 0:
		var f: Dictionary = fx[j]
		if int(f.get("delay", 0)) > 0:
			f["delay"] = int(f["delay"]) - 1
		else:
			f["age"] = int(f.get("age", 0)) + 1
			var keep: bool = (f["update"] as Callable).call(f)
			if not keep:
				for n in f.get("nodes", []):
					if is_instance_valid(n):
						n.queue_free()
				fx.remove_at(j)
		j -= 1
	ticked.emit()

func wait(n: int) -> void:
	for i in maxi(0, n):
		await ticked

func clear() -> void:
	for p in parts:
		_free_part(p)
	parts.clear()
	for f in fx:
		for n in f.get("nodes", []):
			if is_instance_valid(n):
				n.queue_free()
	fx.clear()

## Place a node for this tick (world space) and remember it so interpolate() can blend between ticks.
func _put(n: Node3D, t: Transform3D) -> void:
	interp.put(n, t)

## Show the effects `alpha` (0..1) of the way between the last two ticks (called every rendered frame).
func interpolate(alpha: float) -> void:
	interp.apply(alpha)

func busy() -> bool:
	return not parts.is_empty() or not fx.is_empty()

# ------------------------------------------------------------------ coordinates
## upstream center(): battler centre in 320x132 px, taken from the real 3D model.
func center(k: String) -> Vector2:
	return scene.center_px(k)

func _refresh_plane() -> void:
	_plane_e = scene.center_world("e")
	_plane_p = scene.center_world("p")

func to3d(px: Vector2, lift: float = 0.0) -> Vector3:
	var w := stage.px_to_world(px, _plane_e, _plane_p)
	if lift != 0.0:
		w += (stage.camera.global_position - w).normalized() * lift
	return w

## world metres per upstream pixel at a world point
func px_world(at: Vector3) -> float:
	var cam := stage.camera
	var d := (at - cam.global_position).dot(-cam.global_transform.basis.z)
	return maxf(0.01, d) * 2.0 * tan(deg_to_rad(cam.fov) / 2.0) / 180.0

func _face_basis(rot: float) -> Basis:
	var cb := stage.camera.global_transform.basis
	return Basis(cb.z, -rot) * cb

# ------------------------------------------------------------------ materials / nodes
func _mat(c: Color, alpha: float = 1.0, additive: bool = false, fading: bool = false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(c, alpha)
	# the prop meshes carry a baked light-to-dark gradient in their vertex colours (pipeline/blender/gen_vfx.py)
	m.vertex_color_use_as_albedo = true
	if alpha < 1.0 or additive or fading:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if additive:
		m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.no_depth_test = false
	m.disable_receive_shadows = true
	return m


func _mesh_node(shape: String, c: Color, alpha: float = 1.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = _meshes.get(shape, _meshes["dot"])
	mi.material_override = _mat(c, alpha, false, true)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


func _glow_node(c: Color) -> MeshInstance3D:
	return _tex_node(_glow_tex, c, true)


# ------------------------------------------------------------------ particle system (vfx.js particle())
## o: x y vx vy ax ay drag life size shape cols spin rot delay grow shrink on_update, plus
##   glow (0..1 additive halo, default per shape), fade (fraction of life at which it starts to fade out, default 0.6;
##   1.0 = never), add (draw the mesh additively too), soft (start the size ramp over N frames, default 3).
func particle(o: Dictionary) -> Dictionary:
	var p := {"x": 0.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "ax": 0.0, "ay": 0.0, "drag": 1.0, "life": 30, "age": 0,
		"size": 1.0, "shape": "dot", "cols": [WHITE], "spin": 0.0, "rot": 0.0, "delay": 0, "grow": 0.0, "shrink": 0.0,
		"fade": 0.6, "soft": 3}
	p.merge(o, true)
	var cols: Array = []
	for c in p["cols"]:
		cols.append(c if c is Color else Color(str(c)))
	p["cols"] = cols
	parts.append(p)
	return p


func _free_part(p: Dictionary) -> void:
	for k in ["node", "glow_node", "core", "mid"]:
		if p.has(k) and is_instance_valid(p[k]):
			(p[k] as Node).queue_free()


func _update_particle(p: Dictionary) -> bool:
	if int(p["delay"]) > 0:
		p["delay"] = int(p["delay"]) - 1
		return true
	p["age"] = int(p["age"]) + 1
	if int(p["age"]) > int(p["life"]):
		return false
	p["vx"] = (p["vx"] + p["ax"]) * p["drag"]
	p["vy"] = (p["vy"] + p["ay"]) * p["drag"]
	p["x"] += p["vx"]
	p["y"] += p["vy"]
	p["rot"] += p["spin"]
	if p.has("on_update"):
		(p["on_update"] as Callable).call(p)
	var t: float = float(p["age"]) / float(p["life"])
	var cols: Array = p["cols"]
	var c: Color = ramp(cols, t)
	var shape: String = p["shape"]
	# opacity: fades out over the last part of its life instead of vanishing
	var fs: float = p["fade"]
	var fa := 1.0 if (fs >= 1.0 or t < fs) else clampf((1.0 - t) / (1.0 - fs), 0.0, 1.0)
	fa = fa * fa * (3.0 - 2.0 * fa)
	var base_a := 0.6 if shape == "bubble" else 1.0
	if not p.has("node"):
		p["node"] = _mesh_node(shape, c, base_a)
		var gl: float = p.get("glow", GLOWY.get(shape, 0.0))
		if gl > 0.0:
			p["glow_node"] = _glow_node(c)
		if shape == "flame":
			# upstream flame(): pale-yellow core and gold ring inside the coloured rim
			p["mid"] = _mesh_node("flame", Color("#f8c030"))
			p["core"] = _mesh_node("dot", Color("#fff8c0"))
	var node: MeshInstance3D = p["node"]
	_set_alpha(node, c, base_a * fa)
	var sz: float = p["size"]
	if float(p["grow"]) != 0.0:
		sz *= 1.0 + t * float(p["grow"])
	if float(p["shrink"]) != 0.0:
		sz *= 1.0 - t * float(p["shrink"])
	sz = maxf(sz, MIN_SIZE.get(shape, 0.0))
	var soft: int = p["soft"]
	if soft > 0 and int(p["age"]) < soft:
		sz *= Smooth.ease_out(float(p["age"]) / float(soft)) * 0.7 + 0.3   # pops in instead of appearing full size
	var spx: Array = SHAPE_PX.get(shape, [1.0, 0.0])
	var px_size: float = (float(spx[0]) * sz + float(spx[1])) * PART_SCALE
	var pos := to3d(Vector2(p["x"], p["y"]), 0.05)
	var s := px_world(pos) * px_size
	var b := _face_basis(float(p["rot"]))
	if shape in ["flame", "rock", "shard", "snow", "coin", "bone", "star"]:
		b = b * Basis(Vector3.UP, float(p["age"]) * 0.12 + float(p["x"]) * 0.01)
	_put(node, Transform3D(b.scaled(Vector3(s, s, s)), pos))
	if p.has("core"):
		var toward := (stage.camera.global_position - pos).normalized()
		var down := -stage.camera.global_transform.basis.y
		# the hot core burns out first: white-yellow -> gold -> the rim colour
		var mid_c := Color("#f8c030").lerp(c, t * 0.7)
		var core_c := Color("#fff8c0").lerp(Color("#f8c030"), t)
		_put((p["mid"] as Node3D), Transform3D(b.scaled(Vector3(s, s, s) * 0.72), pos + toward * s * 0.2 + down * s * 0.08))
		_put((p["core"] as Node3D), Transform3D(b.scaled(Vector3(s, s, s) * 0.5), pos + toward * s * 0.4 + down * s * 0.12))
		_set_alpha(p["mid"], mid_c, fa)
		_set_alpha(p["core"], core_c, fa)
	if p.has("glow_node"):
		var g: MeshInstance3D = p["glow_node"]
		var gl2: float = p.get("glow", GLOWY.get(shape, 0.0))
		var r := (sz * 1.8 + 2.0) * 2.4 * px_world(pos)
		_put(g, Transform3D(Basis().scaled(Vector3(r, r, r)), pos - stage.camera.global_transform.basis.z * -0.02))
		_set_alpha(g, c, gl2 * (1.0 - t * 0.5) * 0.9 * fa)
	return true


## Adds a per-frame effect; update(f) returns false when finished.
func add_fx(update: Callable, extra: Dictionary = {}) -> Dictionary:
	var f := {"age": 0, "update": update, "nodes": []}
	f.merge(extra, true)
	fx.append(f)
	return f


## Additive textured quad. billboard: always faces the camera; otherwise oriented by the caller (_face_basis).
func _tex_node(tex: Texture2D, c: Color, billboard: bool = true, alpha: float = 1.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(1, 1)
	mi.mesh = q
	var m := _mat(c, alpha, true)
	m.albedo_texture = tex
	m.no_depth_test = true          # glows must never be clipped by the battlers or the floor
	m.render_priority = 4
	if billboard:
		m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		m.billboard_keep_scale = true
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


func _set_alpha(n: MeshInstance3D, c: Color, a: float) -> void:
	(n.material_override as StandardMaterial3D).albedo_color = Color(c, clampf(a, 0.0, 1.0))


## Smooth colour ramp through `cols` over t (0..1).
static func ramp(cols: Array, t: float) -> Color:
	if cols.size() == 1:
		return cols[0]
	var f := clampf(t, 0.0, 1.0) * (cols.size() - 1)
	var i := mini(int(f), cols.size() - 2)
	return (cols[i] as Color).lerp(cols[i + 1], f - float(i))


# ------------------------------------------------------------------ primitives
func burst(x: float, y: float, kind: String) -> void:
	var capture := kind == "capture"
	var cols: Array = [WHITE, Color("#ffc0f0"), Color("#f080d0")] if capture else [WHITE, Color("#fff0a0"), Color("#f8c040")]
	var hot: Color = cols[1]
	flare(Vector2(x, y), 46.0, hot, 12, {"s0": 0.2, "a": 0.95})
	shockwave(Vector2(x, y), 3.0, 30.0, 14, hot)
	for i in 18:
		var a := i / 18.0 * TAU + rand(-0.1, 0.1)
		var v := rand(1.2, 3.0)
		particle({"x": x, "y": y, "vx": cos(a) * v, "vy": sin(a) * v, "drag": 0.9, "life": rand(16, 22), "shape": "spark" if i % 2 else "star",
			"size": 1.6 if i % 2 else 1.2, "cols": cols, "spin": rand(-0.2, 0.2), "glow": 0.3})
	streaks(Vector2(x, y), 8, 4.0, 26.0, 10.0, 10, hot, {"a": 0.8})


func sparkle_at(x: float, y: float) -> void:
	particle({"x": x + rand(-8, 8), "y": y + rand(-6, 6), "vy": -0.25, "life": 12, "shape": "star", "size": 2.0, "cols": [Color("#fff8a0"), Color("#ffe060")],
		"glow": 0.35, "spin": 0.08})


## Where an attack lands: hot core flash, spinning star, shock ring, sparks thrown away from the attacker, and for
## `big` hits streaks plus a camera shake that decays.
func impact(k: String, col: String = "", big: bool = false) -> void:
	var c := center(k)
	var cc := Color(col) if col != "" else WHITE
	var x := c.x + rand(-6, 6)
	var y := c.y + rand(-6, 6)
	var hot := cc.lerp(Color("#fff4b0"), 0.55)
	var R := 15.0 if big else 10.5
	var star := _mesh_node("impact", cc)
	var core := _tex_node(VfxTex.core(), WHITE, true)
	var glow := _glow_node(hot)
	var rot0 := rand(0.0, 1.0)
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > 11:
			return false
		var t := float(age) / 11.0
		# pop out with a little overshoot, then collapse
		var grow := Smooth.ease_out_back(minf(1.0, age / 3.0), 2.2)
		var shrink := 1.0 - Smooth.ease_in(maxf(0.0, (age - 4.0) / 7.0), 1.6)
		var r := R * grow * shrink
		var pos := to3d(Vector2(x, y), 0.3)
		var w := px_world(pos)
		_put(star, Transform3D(_face_basis(rot0 + age * 0.12) * Basis.from_scale(Vector3.ONE * w * r * 2.0), pos))
		_put(core, Transform3D(Basis().scaled(Vector3.ONE * w * (6.0 + R * 0.5) * (1.0 - t * 0.5)), pos))
		_put(glow, Transform3D(Basis().scaled(Vector3.ONE * w * r * 3.4), pos))
		_set_alpha(core, WHITE, 1.0 - Smooth.ease_in(t, 2.0))
		_set_alpha(glow, hot, 0.85 * pow(1.0 - t, 1.4))
		_set_alpha(star, cc, 1.0 - Smooth.ease_in(maxf(0.0, (t - 0.55) / 0.45), 1.5))
		return true, {"nodes": [star, core, glow]})
	shockwave(Vector2(x, y), 2.5, R * (2.6 if big else 2.0), 11, hot, {"a": 0.85})
	var away := 1.0 if k == "e" else -1.0     # thrown back toward the attacker's side of the screen... away from them
	for i in (14 if big else 8):
		var a := rand(0, TAU)
		var v := rand(1.2, 3.4)
		particle({"x": x, "y": y, "vx": cos(a) * v - away * 0.6, "vy": sin(a) * v, "drag": 0.86, "life": int(rand(11, 17)), "shape": "spark",
			"size": rand(1.0, 1.7), "cols": [WHITE, cc, cc.darkened(0.25)], "glow": 0.3})
	if big:
		streaks(Vector2(x, y), 8, 4.0, 30.0, 12.0, 10, hot, {"a": 0.8})
		scene.shake = maxf(scene.shake, 4.5)
	else:
		scene.shake = maxf(scene.shake, 1.2)
	await wait(8)


func lunge(k: String, dist: float = 14.0) -> void:
	# wind up a touch backward, strike forward fast, recover slowly: ticks of an eased curve, not a triangle wave
	var d := 1.0 if k == "p" else -1.0
	var frames := 14
	for i in range(1, frames + 1):
		var t := float(i) / frames
		var s: float
		if t < 0.22:
			s = -0.18 * Smooth.ease_out(t / 0.22)                              # anticipation
		elif t < 0.45:
			s = lerpf(-0.18, 1.0, Smooth.ease_in((t - 0.22) / 0.23, 1.6))      # strike
		else:
			s = 1.0 - Smooth.ease_out((t - 0.45) / 0.55, 2.0)                  # recover
		scene.offs[k] = Vector2(d * dist * s, -d * dist * s * 0.5)
		await wait(1)
	scene.offs[k] = Vector2.ZERO


func projectile(from: String, to: String, frames: int, shape: String, cols: Array, o: Dictionary = {}) -> void:
	var a: Vector2 = o.get("from_px", center(from))
	var b := center(to)
	var n: int = o.get("count", 1)
	var gap: int = o.get("gap", 3)
	var ease_pow: float = o.get("ease", 1.0)      # >1: accelerates like something thrown / launched
	for j in n:
		var sp: float = o.get("spread", 0.0)
		var off := Vector2(rand(-sp, sp), rand(-sp, sp)) if sp > 0 else Vector2.ZERO
		var arc: float = o.get("arc", 0.0)
		var trail_cols: Array = o.get("trail", [])
		var trail_size: float = o.get("trailSize", 2.0)
		var pd := particle({"delay": j * gap, "x": a.x, "y": a.y, "life": frames, "shape": shape, "size": o.get("size", 2.0), "cols": cols,
			"rot": atan2(b.y - a.y, b.x - a.x), "spin": o.get("spin", 0.0), "fade": 1.0, "glow": o.get("glow", GLOWY.get(shape, 0.0) + 0.1),
			"on_update": func(p: Dictionary) -> void:
				var tt := Smooth.ease_in(float(p["age"]) / frames, ease_pow)
				p["x"] = a.x + (b.x + off.x - a.x) * tt
				p["y"] = a.y + (b.y + off.y - a.y) * tt - sin(tt * PI) * arc})
		if not trail_cols.is_empty():
			var ref := pd
			trail(func() -> Variant:
				if int(ref["age"]) >= int(ref["life"]):
					return null
				return Vector2(ref["x"], ref["y"]), trail_cols, trail_size * 1.7, 10, {"a": 0.7, "delay": j * gap})
	await wait(frames + (n - 1) * gap)


## upstream beam(): a thick line from attacker to target that grows in, with a
## white core and colour bands; `wave` wobbles it (HYDRO PUMP), `rainbow` cycles
## colours (AURORA BEAM), `sparks` sprays particles at the tip. Here the beam also has a
## soft glow along its length, a muzzle flare where it leaves the attacker and a hot tip,
## grows out with an ease and pulses slightly.
func beam(from: String, to: String, frames: int, cols: Array, width: float, o: Dictionary = {}) -> void:
	var a: Vector2 = o.get("from_px", center(from))
	var b := center(to)
	var cs: Array = cols.map(func(c): return Color(c))
	var segs := 28
	# colour bands like upstream: white core (|w| < 0.3), then cs[0..n-1] outward
	var layers: Array = []
	var n := cs.size()
	for j in range(n, -1, -1):
		var row: Array = []
		for i in segs:
			var mi := MeshInstance3D.new()
			mi.mesh = _unit_box()
			mi.material_override = _mat(WHITE if j == 0 else cs[j - 1], 1.0, false, true)
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(mi)
			row.append(mi)
		layers.append({"j": j, "nodes": row, "frac": 0.3 if j == 0 else 0.3 + 0.7 * j / float(n)})
	var wave_amp: float = o.get("wave", 0.0)
	var rainbow: bool = o.get("rainbow", false)
	var sparks: String = o.get("sparks", "")
	var glow_col: Color = cs[0]
	var tip_glow := _glow_node(glow_col)
	var tip_core := _tex_node(VfxTex.core(), WHITE, true)
	var along := _tex_node(VfxTex.streak(), glow_col, false)
	var all_nodes: Array = [tip_glow, tip_core, along]
	for L in layers:
		all_nodes.append_array(L["nodes"])
	flare(a, width * 9.0, glow_col, 12, {"s0": 0.3, "a": 0.9})
	flare(a, width * 4.0, WHITE, 9, {"tex": VfxTex.core(), "a": 0.9})
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > frames:
			return false
		var grow := Smooth.ease_out(minf(1.0, age / 7.0), 2.0)
		var fade := Smooth.ease_out(float(frames - age) / 6.0, 1.5) if age > frames - 6 else 1.0
		var e := a + (b - a) * grow
		var dirv := (e - a)
		var ln := dirv.length()
		var nrm := Vector2(-dirv.y, dirv.x) / maxf(ln, 0.001)
		var wdt := width * fade * (1.0 + 0.07 * sin(age * 1.9))
		var cam_back := stage.camera.global_transform.basis.z
		for i in segs:
			var t0 := float(i) / segs
			var t1 := float(i + 1) / segs
			var w0 := sin(t0 * ln * 0.3 - age * 0.8) * wave_amp if wave_amp > 0 else 0.0
			var w1 := sin(t1 * ln * 0.3 - age * 0.8) * wave_amp if wave_amp > 0 else 0.0
			var p0 := a + dirv * t0 + nrm * w0
			var p1 := a + dirv * t1 + nrm * w1
			var mid := (p0 + p1) / 2.0
			var d := p1 - p0
			var pos := to3d(mid, 0.1)
			var w := px_world(pos)
			var bb := _face_basis(atan2(d.y, d.x))
			var taper := 0.5 + 0.5 * smoothstep(0.0, 0.14, t0)     # narrow where it leaves the mouth
			for li in layers.size():
				var L: Dictionary = layers[li]
				var node: MeshInstance3D = L["nodes"][i]
				node.visible = wdt > 0.2
				var th: float = 2.0 * wdt * float(L["frac"]) * taper
				var lc: Color = WHITE if int(L["j"]) == 0 else cs[int(L["j"]) - 1]
				if rainbow and int(L["j"]) > 0:
					lc = cs[int(fmod(t0 * ln * 0.2 + age * 0.5, cs.size()))]
				_set_alpha(node, lc, 1.0 if fade >= 1.0 else fade)
				_put(node, Transform3D(bb * Basis.from_scale(Vector3((d.length() + 0.6) * w, th * w, 0.02)), pos + cam_back * (0.004 * li)))
		var mid_all := to3d((a + e) / 2.0, 0.08)
		var wall := px_world(mid_all)
		_put(along, Transform3D(_face_basis(atan2(dirv.y, dirv.x)) * Basis.from_scale(Vector3((ln + wdt * 4.0) * wall, wdt * 4.4 * wall, 1.0)), mid_all))
		_set_alpha(along, glow_col, 0.55 * fade)
		var tip := to3d(e, 0.2)
		var gw := px_world(tip) * wdt * 7.0
		_put(tip_glow, Transform3D(Basis().scaled(Vector3(gw, gw, gw)), tip))
		_set_alpha(tip_glow, glow_col, 0.6 * fade * grow)
		var cw := px_world(tip) * wdt * 3.2
		_put(tip_core, Transform3D(Basis().scaled(Vector3(cw, cw, cw)), tip))
		_set_alpha(tip_core, WHITE, 0.9 * fade * grow)
		if sparks != "" and age % 2 == 0:
			particle({"x": e.x + rand(-4, 4), "y": e.y + rand(-4, 4), "vx": rand(-2, 2), "vy": rand(-2, 2), "life": 12, "shape": sparks, "cols": cs, "glow": 0.25})
		return true, {"nodes": all_nodes})
	await wait(frames)


var _box: BoxMesh
func _unit_box() -> BoxMesh:
	if _box == null:
		_box = BoxMesh.new()
		_box.size = Vector3.ONE
	return _box

## A jagged 3D lightning bolt between two px points, re-rolled every few frames (upstream bolt()), with a hot
## white core, a coloured sheath, branches, and a glow flash where it strikes.
func lightning(x0: float, y0: float, x1: float, y1: float, frames: int, col: String = "#f8e048") -> void:
	var cc := Color(col)
	var nodes: Array = []
	for i in 40:
		nodes.append(_mesh_node("dot", WHITE if i % 2 == 0 else cc))
	var glow := _glow_node(cc)
	var end_core := _tex_node(VfxTex.core(), WHITE, true)
	var start_glow := _glow_node(cc)
	nodes.append(glow)
	nodes.append(end_core)
	nodes.append(start_glow)
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > frames:
			return false
		var life_k := 1.0 - Smooth.ease_in(float(age) / float(frames), 3.0)
		for i in 40:
			(nodes[i] as MeshInstance3D).visible = false
		if age % 3 == 2:
			# the gap between re-strikes: only the afterglow stays
			var mid0 := to3d(Vector2(x1, y1), 0.2)
			var gw0 := px_world(mid0) * 26.0
			_put(glow, Transform3D(Basis().scaled(Vector3.ONE * gw0), mid0))
			_set_alpha(glow, cc, 0.3 * life_k)
			end_core.visible = false
			return true
		var pts: Array = [Vector2(x0, y0)]
		for i in range(1, 7):
			var tt := i / 7.0
			var jag := 7.0 * (1.0 - absf(tt - 0.5) * 0.8)
			pts.append(Vector2(x0 + (x1 - x0) * tt + rand(-jag, jag), y0 + (y1 - y0) * tt + rand(-3, 3)))
		pts.append(Vector2(x1, y1))
		var used := 0
		for i in pts.size() - 1:
			used = _bolt_seg(nodes, used, pts[i], pts[i + 1], 1.8)
			if rng.randf() < 0.35 and used < 34:
				var br: Vector2 = pts[i] + Vector2(rand(-16, 16), rand(6, 18))
				used = _bolt_seg(nodes, used, pts[i], br, 1.0)
		var mid := to3d(Vector2(x1, y1), 0.2)
		var gw := px_world(mid) * (46.0 if age % 3 == 0 else 38.0)
		glow.visible = true
		_put(glow, Transform3D(Basis().scaled(Vector3(gw, gw, gw)), mid))
		_set_alpha(glow, cc, 0.7 * life_k)
		end_core.visible = true
		var cw := px_world(mid) * 14.0
		_put(end_core, Transform3D(Basis().scaled(Vector3(cw, cw, cw)), mid))
		_set_alpha(end_core, WHITE, 0.95 * life_k)
		var st := to3d(Vector2(x0, y0), 0.2)
		var sg := px_world(st) * 16.0
		_put(start_glow, Transform3D(Basis().scaled(Vector3(sg, sg, sg)), st))
		_set_alpha(start_glow, cc, 0.5 * life_k)
		if age % 3 == 0:
			particle({"x": x1 + rand(-6, 6), "y": y1 + rand(-4, 4), "vx": rand(-2, 2), "vy": rand(-2.5, 0.5), "ay": 0.12, "life": 10, "shape": "spark",
				"size": 1.2, "cols": [WHITE, cc]})
		return true, {"nodes": nodes})
	await wait(frames)


func _bolt_seg(nodes: Array, used: int, a: Vector2, b: Vector2, thick: float) -> int:
	if used + 1 >= nodes.size() - 1:
		return used
	var mid := (a + b) / 2.0
	var d := b - a
	var pos := to3d(mid, 0.25)
	var w := px_world(pos)
	var bb := _face_basis(atan2(d.y, d.x))
	var outer: MeshInstance3D = nodes[used + 1]
	var inner: MeshInstance3D = nodes[used]
	outer.visible = true
	inner.visible = true
	_put(outer, Transform3D(bb.scaled(Vector3(d.length() * w * 1.05, thick * 3.0 * w, thick * 3.0 * w)), pos))
	_put(inner, Transform3D(bb.scaled(Vector3(d.length() * w * 1.05, thick * 1.2 * w, thick * 1.2 * w)), pos - stage.camera.global_transform.basis.z * -0.02))
	return used + 2

func ring(k: String, frames: int, col: String, r0: float, r1: float, thick: int = 1) -> void:
	var c := center(k)
	var cc := Color(col)
	shockwave(c, r0, r1, frames, cc, {"a": 0.55 + 0.2 * thick})
	flare(c, maxf(r0, r1) * 1.6, cc, frames, {"a": 0.35, "s0": 0.5})
	await wait(frames)


func flash(col: String = "#ffffff", amt: float = 0.8) -> void:
	scene.flash = amt
	scene.flash_color = Color(col)
	await wait(6)

func tint(k: String, col: String, frames: int) -> void:
	var cc := Color(col)
	for i in frames:
		scene.set_tint(k, cc, 0.6 * sin(float(i) / frames * PI))
		await wait(1)
	scene.set_tint(k, cc, 0.0)

func wave(amp: float, frames: int) -> void:
	scene.screen_wave(amp, frames)
	await wait(frames)
	scene.screen_wave(0.0, 0)

func darken(frames: int, col: String = "#100818", amt: float = 0.6) -> void:
	var cc := Color(col)
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > frames:
			scene.darken = 0.0
			return false
		scene.darken_color = cc
		scene.darken = amt * sin(float(f["age"]) / frames * PI)
		return true)
	await wait(frames)

func emit(k: String, n: int, o: Dictionary) -> void:
	var c := center(k)
	for i in n:
		var q := o.duplicate()
		var rx: float = o.get("rx", 12.0)
		var ry: float = o.get("ry", 10.0)
		var jx: float = o.get("jx", 0.0)
		var jy: float = o.get("jy", 0.0)
		q["x"] = c.x + rand(-rx, rx)
		q["y"] = c.y + rand(-ry, ry)
		q["vx"] = float(o.get("vx", 0.0)) + rand(-jx, jx)
		q["vy"] = float(o.get("vy", 0.0)) + rand(-jy, jy)
		q["delay"] = int(floor(rand(0, float(o.get("spreadT", 0)))))
		particle(q)

func screen_rain(n: int, frames: int, o: Dictionary) -> void:
	for i in n:
		var q := o.duplicate()
		q["x"] = rand(-20, 340)
		q["y"] = rand(-40, 0)
		q["delay"] = int(floor(rand(0, frames * 0.6)))
		q["life"] = o.get("life", 40)
		particle(q)
	await wait(frames)

func slash(k: String, n: int, col: String = "#ffffff") -> void:
	var c := center(k)
	var cc := Color(col)
	for j in n:
		var ox := (j - (n - 1) / 2.0) * 6.0
		var node := _mesh_node("claw", WHITE)
		var edge := _mesh_node("claw", cc)
		var glow := _tex_node(VfxTex.streak(), cc, false)
		add_fx(func(f: Dictionary) -> bool:
			var age: int = f["age"]
			if age > 12:
				return false
			var ln := Smooth.ease_out(minf(1.0, age / 4.0), 2.0) * 22.0
			var pos := to3d(Vector2(c.x + ox, c.y), 0.4)
			var w := px_world(pos)
			var fade := 1.0 - Smooth.ease_in(maxf(0.0, (age - 5.0) / 7.0), 1.5)
			_put(node, Transform3D(_face_basis(0) * Basis.from_scale(Vector3(ln * w * 1.4, ln * w * 1.4, w * 2)), pos))
			_put(edge, Transform3D(_face_basis(0) * Basis.from_scale(Vector3(ln * w * 1.55, ln * w * 1.55, w * 3)), pos - stage.camera.global_transform.basis.z * 0.02))
			_put(glow, Transform3D(_face_basis(-PI * 0.25) * Basis.from_scale(Vector3(ln * w * 2.2, w * 5.0, 1.0)), pos))
			_set_alpha(node, WHITE, fade)
			_set_alpha(edge, cc, fade)
			_set_alpha(glow, cc, 0.7 * fade)
			return true, {"nodes": [node, edge, glow]})
		if j == 0:
			flare(Vector2(c.x + ox, c.y), 28.0, cc, 9, {"a": 0.7})
		await wait(3)
	scene.shake = maxf(scene.shake, 1.0)
	await wait(8)


func vortex(k: String, frames: int, cols: Array, shape: String = "flame") -> void:
	var c := center(k)
	var cs: Array = cols.map(func(x): return Color(x))
	for i in 26:
		var a0 := rand(0, TAU)
		var r0 := rand(6, 22)
		particle({"delay": int(floor(rand(0, frames * 0.5))), "life": 24, "shape": shape, "size": 2.2, "cols": cs,
			"on_update": func(p: Dictionary) -> void:
				var a := a0 + int(p["age"]) * 0.35
				var r := r0 * (1.0 - int(p["age"]) / 40.0)
				p["x"] = c.x + cos(a) * r
				p["y"] = c.y + 8 - int(p["age"]) * 0.9 + sin(a) * r * 0.35})
	await wait(frames)

## Rising arrows and an aura ring: warm chevrons climb for a stat rise, cool ones sink for a drop.
func stat(k: String, up: bool, col: String = "") -> void:
	var c := center(k)
	var cols: Array = [Color(col if col != "" else "#fff0a0"), Color("#f8a040"), Color("#e05030")] if up else [Color("#c0e0ff"), Color("#6090e0"), Color("#3050a0")]
	var aura: Color = cols[1]
	shockwave(c + Vector2(0, 22), 6.0, 34.0, 20, aura, {"a": 0.7, "squash": 0.4})
	flare(c, 44.0, aura, 26, {"a": 0.45, "s0": 0.7})
	for i in 7:
		var col_i: Color = cols[0].lerp(cols[1], rand(0.0, 1.0))
		var x0 := c.x + (i - 3) * 6.5 + rand(-1.5, 1.5)
		var y0 := c.y + (24.0 if up else -30.0) + rand(-4, 4)
		var life := int(rand(20, 27))
		particle({"x": x0, "y": y0, "delay": int(i * 2.2), "life": life, "shape": "arrow", "size": rand(2.5, 3.1), "cols": [col_i, col_i.darkened(0.15)],
			"rot": 0.0 if up else PI, "glow": 0.3, "fade": 0.55, "soft": 5,
			"on_update": func(p: Dictionary) -> void:
				var tt := float(p["age"]) / float(life)
				var sp := 1.0 - Smooth.ease_in(tt, 2.0) * 0.55
				p["y"] = y0 + (-1.0 if up else 1.0) * Smooth.ease_out(tt, 1.6) * 54.0 * sp
				p["x"] = x0 + sin(tt * 5.0 + i) * 1.5})
	for i in 24:
		var t := float(i) / 24.0
		scene.set_tint(k, aura, 0.4 * sin(t * PI))
		await wait(1)
	scene.set_tint(k, aura, 0.0)


## A soft additive glow that pops and fades at a battle px position.
## o: s0/s1 (start/end size as a fraction of size_px), a (peak alpha), lift, delay (frames), tex, follow (Callable -> Vector2).
func flare(pos: Vector2, size_px: float, col: Color, frames: int, o: Dictionary = {}) -> void:
	var s0: float = o.get("s0", 0.35)
	var s1: float = o.get("s1", 1.0)
	var a0: float = o.get("a", 0.9)
	var lift: float = o.get("lift", 0.35)
	var tex: Texture2D = o.get("tex", _glow_tex)
	var follow: Callable = o.get("follow", Callable())
	var node := _tex_node(tex, col, true)
	node.visible = false
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > frames:
			return false
		var t := float(age) / float(frames)
		var p: Vector2 = follow.call() if follow.is_valid() else pos
		var w3 := to3d(p, lift)
		var w := px_world(w3) * size_px * lerpf(s0, s1, Smooth.ease_out(t))
		_put(node, Transform3D(Basis().scaled(Vector3(w, w, w)), w3))
		node.visible = true
		# quick swell, long soft fall-off
		var env := minf(1.0, t / 0.18) * pow(1.0 - t, 1.6)
		_set_alpha(node, col, a0 * env)
		return true, {"nodes": [node], "delay": int(o.get("delay", 0))})


## An expanding ring (thin, soft, additive) facing the camera, or lying on the ground plane (flat + at_world).
func shockwave(pos: Vector2, r0: float, r1: float, frames: int, col: Color, o: Dictionary = {}) -> void:
	var a0: float = o.get("a", 0.85)
	var lift: float = o.get("lift", 0.3)
	var flat: bool = o.get("flat", false)
	var at_world: Vector3 = o.get("at_world", Vector3.ZERO)
	var squash: float = o.get("squash", 1.0)
	var node := _tex_node(VfxTex.ring(), col, false)
	node.visible = false
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > frames:
			return false
		var t := float(age) / float(frames)
		var r := lerpf(r0, r1, Smooth.ease_out(t, 2.4))
		var w3 := at_world + Vector3(0, 0.03, 0) if flat else to3d(pos, lift)
		var d := px_world(w3) * r * 2.0 / 0.82
		var basis: Basis
		if flat:
			basis = Basis(Vector3.RIGHT, -PI / 2.0) * Basis.from_scale(Vector3(d, d * 0.62, 1.0))
		else:
			basis = _face_basis(0.0) * Basis.from_scale(Vector3(d, d * squash, 1.0))
		_put(node, Transform3D(basis, w3))
		node.visible = true
		_set_alpha(node, col, a0 * pow(1.0 - t, 1.3) * minf(1.0, t / 0.08 + 0.4))
		return true, {"nodes": [node], "delay": int(o.get("delay", 0))})


## Radial speed lines bursting out of a point (impacts, power-ups).
func streaks(pos: Vector2, n: int, r0: float, r1: float, len_px: float, frames: int, col: Color, o: Dictionary = {}) -> void:
	var nodes: Array = []
	var angs: Array = []
	var a_off := rand(0.0, TAU)
	for i in n:
		nodes.append(_tex_node(VfxTex.streak(), col, false))
		(nodes[i] as MeshInstance3D).visible = false
		angs.append(a_off + float(i) / n * TAU + rand(-0.12, 0.12))
	var a0: float = o.get("a", 0.9)
	var thick: float = o.get("thick", 1.6)
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > frames:
			return false
		var t := float(age) / float(frames)
		var r := lerpf(r0, r1, Smooth.ease_out(t, 2.0))
		var ln := len_px * (1.0 - t * 0.7)
		for i in n:
			var an: float = angs[i]
			var dirv := Vector2(cos(an), sin(an))
			var mid := pos + dirv * r
			var w3 := to3d(mid, 0.32)
			var w := px_world(w3)
			var node: MeshInstance3D = nodes[i]
			node.visible = true
			_put(node, Transform3D(_face_basis(an) * Basis.from_scale(Vector3(ln * w, thick * w * (1.0 - t * 0.5), 1.0)), w3))
			_set_alpha(node, col, a0 * pow(1.0 - t, 1.2))
		return true, {"nodes": nodes, "delay": int(o.get("delay", 0))})


## A camera-facing tapered ribbon following a moving point: `follow` returns its current px position (or null
## when the point is gone; the ribbon then drains). Colours run from the head (cols[0]) to the tail (last).
func trail(follow: Callable, cols: Array, width: float, keep: int = 12, o: Dictionary = {}) -> void:
	var cs: Array = cols.map(func(c): return c if c is Color else Color(str(c)))
	var mi := MeshInstance3D.new()
	var im := ImmediateMesh.new()
	mi.mesh = im
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD if o.get("add", true) else BaseMaterial3D.BLEND_MODE_MIX
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.no_depth_test = true
	m.render_priority = 3
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.extra_cull_margin = 16384.0
	add_child(mi)
	var pts: Array = []
	var alive := [true]
	var a0: float = o.get("a", 0.8)
	add_fx(func(f: Dictionary) -> bool:
		var head: Variant = follow.call() if alive[0] else null
		if head == null:
			alive[0] = false
			if not pts.is_empty():
				pts.pop_back()
			if pts.is_empty():
				return false
		else:
			pts.push_front(head)
			if pts.size() > keep:
				pts.pop_back()
		im.clear_surfaces()
		if pts.size() < 2:
			return true
		im.surface_begin(Mesh.PRIMITIVE_TRIANGLE_STRIP)
		for i in pts.size():
			var pi: Vector2 = pts[i]
			var prev: Vector2 = pts[maxi(i - 1, 0)]
			var nxt: Vector2 = pts[mini(i + 1, pts.size() - 1)]
			var dv := prev - nxt
			var nrm := Vector2(-dv.y, dv.x).normalized() if dv.length() > 0.001 else Vector2(0, 1)
			var u := float(i) / float(maxi(keep - 1, 1))
			var w3 := to3d(pi, 0.22)
			var wpx := width * pow(1.0 - u, 0.8) * px_world(w3)
			var col: Color = ramp(cs, u)
			col.a = a0 * pow(1.0 - u, 1.4)
			var side: Vector3 = to3d(pi + nrm, 0.22) - w3
			side = side.normalized() * wpx
			im.surface_set_color(col)
			im.surface_add_vertex(to_local(w3 + side))
			im.surface_set_color(col)
			im.surface_add_vertex(to_local(w3 - side))
		im.surface_end()
		return true, {"nodes": [mi], "delay": int(o.get("delay", 0))})


## Charge-up before a ranged attack: sparks converge on the attacker's mouth while a glow swells there.
## Returns the px position of the orb so the attack can start from it.
func charge_up(k: String, frames: int, col: Color, o: Dictionary = {}) -> Vector2:
	var c := center(k)
	var t := center(other(k))
	var dirv := (t - c).normalized()
	var origin := c + dirv * float(o.get("reach", 14.0)) + Vector2(0, float(o.get("dy", -3.0)))
	var size: float = o.get("size", 26.0)
	var shape: String = o.get("shape", "spark")
	flare(origin, size, col, frames + 6, {"s0": 0.05, "s1": 1.0, "a": 0.9, "lift": 0.4})
	flare(origin, size * 0.5, WHITE, frames + 4, {"s0": 0.05, "s1": 1.0, "a": 0.9, "tex": VfxTex.core(), "lift": 0.42})
	var n: int = o.get("count", int(frames * 1.4))
	for i in n:
		var a := rand(0, TAU)
		var R := rand(18.0, 34.0)
		var life := int(rand(8, 13))
		var d0 := int(rand(0, maxf(1.0, frames - life)))
		particle({"delay": d0, "life": life, "shape": shape, "size": rand(0.8, 1.3), "cols": [WHITE, col.lightened(0.3), col], "glow": 0.25, "fade": 0.75,
			"on_update": func(p: Dictionary) -> void:
				var tt := float(p["age"]) / float(life)
				var r := R * (1.0 - Smooth.ease_in(tt, 1.7))
				p["x"] = origin.x + cos(a + tt * 0.8) * r
				p["y"] = origin.y + sin(a + tt * 0.8) * r * 0.75})
	await wait(frames)
	return origin


## Run several coroutines at the same time and wait until every one has finished.
func par(calls: Array) -> void:
	var left := [calls.size()]
	for c in calls:
		_run_then(c, left)
	while left[0] > 0:
		await ticked


func _run_then(c: Callable, left: Array) -> void:
	await c.call()
	left[0] -= 1


## A physical hit: the attacker lunges and the impact lands at the peak of the strike (not after the recovery).
func strike(a: String, t: String, dist: float = 14.0, col: String = "", big: bool = false) -> void:
	await par([
		func() -> void: await lunge(a, dist),
		func() -> void:
			await wait(6)
			await impact(t, col, big)])


# ------------------------------------------------------------------ entry points
## Moves that act on the user (buffs, healing, status clouds) play the Special clip instead of Attack.
const STATUS_RECIPES := ["glow", "statup", "swords", "doubleteam", "minimize", "heal", "rest", "shield", "focus", "bide", "haze",
	"conversion", "mimic", "transform", "teleport", "metronome", "mist", "statdown", "leer", "tailwhip", "sound", "sing", "hypnosis",
	"powder", "string", "disable", "confuseray", "charge", "gas", "splash", "healitem"]

static func is_status_move(id: String) -> bool:
	var m: Array = MOVES.get(id, ["hit"])
	return STATUS_RECIPES.has(str(m[0]))

func other(k: String) -> String:
	return "p" if k == "e" else "e"

## upstream vfx.move(sc, id, k, hit)
func move(id: String, k: String, hit: int = 0) -> void:
	var m: Array = MOVES.get(id, ["hit"])
	var t := other(k)
	if hit > 0 and not ["needles", "claw"].has(m[0]):
		await impact(t)
		return
	var ar: Variant = m[1] if m.size() > 1 else null
	if m[0] == "drain" and id == "DRAIN":
		await r_drain(k, t, null)
		return
	var fn := "r_" + str(m[0])
	if has_method(fn):
		await call(fn, k, t, ar)
	else:
		await r_hit(k, t, null)
	scene.offs[k] = Vector2.ZERO

func status(k: String, st: String) -> void:
	var c := center(k)
	match st:
		"PSN":
			# purple bubbles wobbling up out of the mon, sickly glow
			flare(c, 46.0, Color("#a050c8"), 30, {"a": 0.4, "s0": 0.7})
			for i in 12:
				var x0 := c.x + rand(-16, 16)
				var y0 := c.y + rand(4, 20)
				var life := int(rand(22, 30))
				particle({"x": x0, "y": y0, "delay": int(rand(0, 16)), "life": life, "shape": "bubble", "size": rand(2.0, 3.4), "cols": POIS, "glow": 0.25, "fade": 0.5,
					"on_update": func(p: Dictionary) -> void:
						var tt := float(p["age"]) / float(life)
						p["y"] = y0 - Smooth.ease_out(tt, 1.4) * 34.0
						p["x"] = x0 + sin(tt * 9.0 + x0) * 3.0})
			await tint(k, "#b060d0", 30)
		"BRN":
			# embers and small flames licking up, orange flicker
			for i in 12:
				var x0 := c.x + rand(-14, 14)
				var y0 := c.y + rand(2, 18)
				var life := int(rand(18, 26))
				particle({"x": x0, "y": y0, "delay": int(rand(0, 14)), "life": life, "shape": "flame" if i % 3 else "spark", "size": rand(2.0, 3.2), "cols": FIRE,
					"on_update": func(p: Dictionary) -> void:
						var tt := float(p["age"]) / float(life)
						p["y"] = y0 - Smooth.ease_out(tt, 1.5) * 26.0
						p["x"] = x0 + sin(tt * 8.0 + x0) * 2.0})
			for i in 16:
				scene.set_tint(k, Color("#f86030"), 0.35 * (0.6 + 0.4 * sin(i * 1.3)) * sin(float(i) / 16.0 * PI))
				await wait(1)
			scene.set_tint(k, Color("#f86030"), 0.0)
			await wait(8)
		"PAR":
			# short crackling arcs jumping across the body
			for i in 4:
				var a0 := center(k) + Vector2(rand(-18, -6), rand(-16, 16))
				var a1 := center(k) + Vector2(rand(6, 18), rand(-16, 16))
				lightning(a0.x, a0.y, a1.x, a1.y, 6, ELEC[1])
			emit(k, 12, {"life": 14, "shape": "spark", "cols": ELEC, "spreadT": 18, "jx": 1.5, "jy": 1.5})
			await tint(k, "#f8e040", 26)
		"SLP":
			# Zs drift up and to the side, growing as they go
			for i in 3:
				var x0 := c.x + 6.0 + i * 3.0
				var y0 := c.y - 10.0
				var life := 34
				particle({"x": x0, "y": y0, "delay": i * 9, "life": life, "shape": "z", "size": 1.3 + i * 0.5, "cols": ["#e8f0ff", "#b8c8f8"], "glow": 0.25, "fade": 0.55, "soft": 5,
					"on_update": func(p: Dictionary) -> void:
						var tt := float(p["age"]) / float(life)
						p["y"] = y0 - Smooth.ease_out(tt, 1.3) * 24.0
						p["x"] = x0 + tt * 12.0 + sin(tt * 7.0) * 2.5
						p["rot"] = sin(tt * 5.0) * 0.18})
			await wait(40)
		"FRZ":
			# an ice block snaps around the mon
			var block := _mesh_node("shard", Color("#b8f0ff"), 0.4)
			var block2 := _mesh_node("shard", Color("#e8ffff"), 0.35)
			flare(c, 54.0, Color("#a8e8f8"), 26, {"a": 0.45})
			add_fx(func(f: Dictionary) -> bool:
				var age: int = f["age"]
				if age > 30:
					return false
				var grow := Smooth.ease_out_back(minf(1.0, age / 8.0), 1.6)
				var fade := 1.0 - Smooth.ease_in(maxf(0.0, (age - 22.0) / 8.0), 1.5)
				var pos := to3d(c + Vector2(0, 2), 0.7)
				var w := px_world(pos)
				_put(block, Transform3D(_face_basis(0.0) * Basis.from_scale(Vector3(38.0, 50.0, 30.0) * w * grow), pos))
				_put(block2, Transform3D(_face_basis(0.25) * Basis.from_scale(Vector3(30.0, 42.0, 24.0) * w * grow), pos + Vector3(0, w * 2.0, 0)))
				_set_alpha(block, Color("#b8f0ff"), 0.4 * fade)
				_set_alpha(block2, Color("#e8ffff"), 0.35 * fade)
				return true, {"nodes": [block, block2]})
			emit(k, 14, {"life": 26, "shape": "shard", "cols": ICE, "spreadT": 12, "rx": 16.0, "ry": 18.0, "glow": 0.3})
			shockwave(c, 4.0, 34.0, 16, Color("#c8f4ff"))
			await tint(k, "#a0e0ff", 30)
		"CONF":
			# stars circle the head
			var head := c + Vector2(0, -20)
			for i in 4:
				var a0 := i / 4.0 * TAU
				particle({"life": 44, "shape": "star", "size": 2.6, "cols": ["#fff8a0", "#ffe060"], "glow": 0.35, "fade": 0.8, "spin": 0.06, "soft": 6,
					"on_update": func(p: Dictionary) -> void:
						var an := a0 + int(p["age"]) * 0.22
						p["x"] = head.x + cos(an) * 15.0
						p["y"] = head.y + sin(an) * 4.5})
			await wait(44)
		_:
			await wait(1)


## Extra emphasis when a hit lands on `k`: super effective hits flash and throw a starburst, resisted ones
## just puff dully. (The move's own impact() has already played.)
func hit_react(k: String, eff: float) -> void:
	var c := center(k)
	if eff > 1.0:
		flare(c, 62.0, Color("#fff4c0"), 10, {"a": 0.95})
		shockwave(c, 4.0, 40.0, 14, Color("#fff0a0"), {"a": 1.0})
		shockwave(c, 2.0, 26.0, 11, WHITE, {"delay": 3})
		streaks(c, 12, 8.0, 46.0, 15.0, 12, Color("#ffe890"))
		for i in 6:
			var an := rand(0, TAU)
			particle({"x": c.x, "y": c.y, "vx": cos(an) * rand(1.5, 3.5), "vy": sin(an) * rand(1.5, 3.5), "drag": 0.9, "life": 20, "shape": "star",
				"size": rand(1.2, 1.8), "cols": [Color("#fff8a0"), Color("#ffd040")], "glow": 0.35, "spin": rand(-0.2, 0.2)})
		scene.flash = maxf(scene.flash, 0.3)
		scene.flash_color = Color("#fff8d8")
		scene.shake = maxf(scene.shake, 5.0)
	elif eff > 0.0 and eff < 1.0:
		for i in 7:
			particle({"x": c.x + rand(-8, 8), "y": c.y + rand(-6, 6), "vx": rand(-0.6, 0.6), "vy": rand(-0.7, -0.1), "life": 24, "shape": "dot",
				"size": rand(1.6, 2.6), "grow": 0.8, "cols": [Color("#d8d8e0"), Color("#8a8a98")], "glow": 0.0, "fade": 0.4})


## A fainting battler crumbles into drifting dust.
func faint_fx(k: String) -> void:
	var c := center(k)
	var base: Vector3 = scene.ground_world(k)
	for i in 22:
		var x := c.x + rand(-14, 14)
		particle({"x": x, "y": c.y + rand(-14, 16), "vx": rand(-0.25, 0.25), "vy": rand(-0.9, -0.2), "ay": -0.005, "life": int(rand(22, 34)), "delay": int(rand(0, 14)),
			"shape": "dot", "size": rand(1.0, 2.0), "grow": 0.6, "cols": [Color("#f0f0f8"), Color("#a8a8c0"), Color("#606078")], "glow": 0.08, "fade": 0.35})
	shockwave(Vector2.ZERO, 6.0, 46.0, 20, Color("#d8d8f0"), {"flat": true, "at_world": base, "a": 0.5})


## Level-up: a column of sparkles rises off the mon inside a soft golden glow.
func levelup_fx(k: String) -> void:
	var c := center(k)
	var col := Color("#ffe27a")
	flare(c, 64.0, col, 40, {"a": 0.55, "s0": 0.6})
	shockwave(c + Vector2(0, 24), 5.0, 38.0, 22, col, {"a": 0.7, "squash": 0.42})
	shockwave(c + Vector2(0, 24), 5.0, 30.0, 22, WHITE, {"a": 0.5, "squash": 0.42, "delay": 6})
	for i in 30:
		var x0 := c.x + rand(-18, 18)
		var y0 := c.y + 26.0
		var life := int(rand(24, 36))
		var rise := rand(46, 60)
		particle({"x": x0, "y": y0, "delay": int(rand(0, 26)), "life": life, "shape": "star", "size": rand(1.7, 2.8), "cols": [WHITE, col, Color("#ffb030")],
			"glow": 0.4, "spin": rand(-0.1, 0.1),
			"on_update": func(p: Dictionary) -> void:
				var tt := float(p["age"]) / float(life)
				p["y"] = y0 - Smooth.ease_out(tt, 1.8) * rise
				p["x"] = x0 + sin(tt * 6.0 + x0) * 3.0})


## A soft glowing lane (additive streak) from one px point to another that grows out over `grow` frames, holds, and
## fades over the last 8: heat haze / water spray / energy bloom behind a stream of particles.
func lane(p0: Vector2, p1: Vector2, width: float, col: Color, frames: int, o: Dictionary = {}) -> void:
	var grow: int = o.get("grow", 10)
	var a0: float = o.get("a", 0.5)
	var node := _tex_node(VfxTex.streak(), col, false)
	node.visible = false
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > frames:
			return false
		var g := Smooth.ease_out(minf(1.0, float(age) / grow), 1.8)
		var fade := 1.0 if age < frames - 8 else float(frames - age) / 8.0
		var e := p0 + (p1 - p0) * g
		var dirv := e - p0
		var mid := to3d((p0 + e) * 0.5, 0.06)
		var w := px_world(mid)
		var wob := 1.0 + 0.08 * sin(age * 1.3)
		node.visible = true
		_put(node, Transform3D(_face_basis(atan2(dirv.y, dirv.x)) * Basis.from_scale(Vector3((dirv.length() + width) * w, width * wob * w, 1.0)), mid))
		_set_alpha(node, col, a0 * fade)
		return true, {"nodes": [node], "delay": int(o.get("delay", 0))})


# ------------------------------------------------------------------ recipes (vfx.js R.*)
func r_hyperbeam(a: String, t: String, _ar: Variant) -> void:
	var mouth := await charge_up(a, 16, Color("#ffb060"), {"size": 40.0, "reach": 14.0, "count": 36})
	await beam(a, t, 34, ["#fff4e0", "#ffc070", "#f07030"], 11.0, {"sparks": "spark", "from_px": mouth})
	var c := center(t)
	flare(c, 110.0, Color("#ffb060"), 22, {"a": 1.0})
	shockwave(c, 4.0, 64.0, 18, Color("#ffd090"))
	shockwave(c, 2.0, 40.0, 14, WHITE, {"delay": 3})
	scene.shake = 9.0
	await flash("#ffe8c0", 0.6)
	await wait(8)


func r_hit(a: String, t: String, _ar: Variant) -> void:
	await strike(a, t, 14.0)

func r_bighit(a: String, t: String, _ar: Variant) -> void:
	await strike(a, t, 22.0, "#f8e060", true)

func r_quick(a: String, t: String, _ar: Variant) -> void:
	var c := center(a)
	for i in 6:
		particle({"x": c.x, "y": c.y + rand(-10, 10), "vx": 7.0 if a == "p" else -7.0, "life": 12, "shape": "dot", "size": 1.0, "cols": [WHITE]})
	await strike(a, t, 30.0)

func r_claw(_a: String, t: String, ar: Variant) -> void:
	await slash(t, int(ar) if ar != null else 3)

func r_cut(_a: String, t: String, _ar: Variant) -> void:
	await slash(t, 1, "#c0e0ff")
	await impact(t)

func r_bite(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	var top := _mesh_node("claw", WHITE)
	var bot := _mesh_node("claw", WHITE)
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > 14:
			return false
		var g := maxf(0.0, 12.0 - int(f["age"]) * 1.4)
		var p1 := to3d(Vector2(c.x, c.y - g - 4), 0.4)
		var p2 := to3d(Vector2(c.x, c.y + g + 4), 0.4)
		var w := px_world(p1) * 22.0
		_put(top, Transform3D(_face_basis(PI * 0.25).scaled(Vector3(w, w * 0.5, w * 0.2)), p1))
		_put(bot, Transform3D(_face_basis(PI * 1.25).scaled(Vector3(w, w * 0.5, w * 0.2)), p2))
		return true, {"nodes": [top, bot]})
	await wait(10)
	await impact(t)

func r_punch(a: String, t: String, ar: Variant) -> void:
	var c := center(t)
	var fist := _mesh_node("fist", Color("#f8d8b0"))
	fist.material_override = null
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color("#f8d8b0")
	fist.material_override = fm
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > 10:
			return false
		var r := 3.0 + int(f["age"])
		var pos := to3d(c, 0.6)
		var w := px_world(pos) * r * 2.0
		_put(fist, Transform3D(_face_basis(0).scaled(Vector3(w, w, w)), pos))
		return true, {"nodes": [fist]})
	await wait(8)
	if ar != null:
		await call("r_" + str(ar), a, t, null)
	else:
		await impact(t, "", true)

func r_kick(a: String, t: String, _ar: Variant) -> void:
	await strike(a, t, 18.0, "#f8f0c0", true)

func r_wrap(_a: String, t: String, _ar: Variant) -> void:
	for i in 3:
		await ring(t, 8, "#e8c080", 26, 8, 2)
	await impact(t)

func r_needles(a: String, t: String, ar: Variant) -> void:
	await projectile(a, t, 12, "needle", [WHITE, Color("#d0d0d8")], {"count": int(ar) if ar != null else 2, "gap": 4, "spread": 6.0})
	await impact(t)

func r_poisonsting(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 12, "needle", [Color("#c070e0")], {"count": 1})
	await impact(t, "#c070e0")

func r_ember(a: String, t: String, _ar: Variant) -> void:
	var mouth := await charge_up(a, 6, Color("#f8a038"), {"size": 15.0, "reach": 14.0, "count": 6})
	await projectile(a, t, 16, "flame", FIRE, {"count": 3, "gap": 5, "arc": 12.0, "size": 4.5, "from_px": mouth, "ease": 1.25,
		"trail": [Color("#f8c040"), Color("#e84818")], "trailSize": 2.6})
	var c := center(t)
	flare(c, 44.0, Color("#ffa040"), 14, {"a": 0.85})
	shockwave(c, 3.0, 22.0, 12, Color("#ffb060"))
	emit(t, 18, {"life": 26, "shape": "flame", "size": 3.6, "vy": -1.0, "jx": 0.6, "cols": FIRE, "spreadT": 10, "rx": 16.0, "ry": 12.0})
	await flash("#f8a040", 0.25)
	await wait(18)


func r_flamethrower(a: String, t: String, _ar: Variant) -> void:
	var mouth := await charge_up(a, 10, Color("#f8a038"), {"size": 26.0, "reach": 15.0})
	var bp := center(t)
	var jet: Array = [Color("#fffbd0"), Color("#f8d048"), Color(FIRE[0]), Color(FIRE[1]), Color("#5a2010")]
	flare(mouth, 36.0, Color("#ffb040"), 44, {"a": 0.8, "s0": 0.9, "s1": 1.0})
	lane(mouth, bp, 26.0, Color("#ff7a20"), 44, {"a": 0.42, "grow": 12})
	lane(mouth, bp, 13.0, Color("#ffd060"), 44, {"a": 0.5, "grow": 12})
	for i in 70:
		var d := int(i * 0.5)
		var lat := rand(-1.0, 1.0)
		var ph := rand(0.0, TAU)
		var life := 15
		particle({"delay": d, "life": life, "shape": "flame", "size": rand(2.4, 3.3), "grow": 1.8, "cols": jet, "glow": 0.42, "fade": 0.68,
			"x": mouth.x, "y": mouth.y,
			"on_update": func(p: Dictionary) -> void:
				var tt := float(p["age"]) / float(life)
				var age: int = p["age"]
				p["x"] = mouth.x + (bp.x - mouth.x) * tt + sin(age * 0.9 + ph) * 2.6 * tt
				p["y"] = mouth.y + (bp.y - mouth.y) * tt + lat * 12.0 * tt * tt + cos(age * 1.1 + ph) * 1.8 * tt - tt * 4.0})
		if i % 2 == 0:
			var dirv := (bp - mouth).normalized()
			particle({"delay": d + 3, "x": mouth.x + dirv.x * 12.0, "y": mouth.y + dirv.y * 12.0, "vx": dirv.x * rand(2.0, 4.5), "vy": dirv.y * rand(2.0, 4.5) + rand(-1.6, 0.4),
				"ay": -0.03, "drag": 0.96, "life": 24, "shape": "spark", "size": rand(0.8, 1.4), "cols": [Color("#fff0a0"), Color("#f88828"), Color("#a83010")], "glow": 0.3})
	await wait(38)
	flare(bp, 64.0, Color("#ff9038"), 22, {"a": 0.9})
	shockwave(bp, 4.0, 32.0, 14, Color("#ffb060"))
	scene.shake = maxf(scene.shake, 2.5)
	await par([func() -> void: await vortex(t, 22, FIRE), func() -> void: await tint(t, "#f86030", 26)])


func r_fireblast(a: String, t: String, _ar: Variant) -> void:
	var mouth := await charge_up(a, 12, Color("#f87028"), {"size": 32.0, "reach": 15.0})
	await projectile(a, t, 18, "flame", FIRE, {"size": 6.5, "from_px": mouth, "ease": 1.5, "trail": [Color("#f8c040"), Color("#e84818")], "trailSize": 4.0})
	var c := center(t)
	flare(c, 90.0, Color("#ff8030"), 26, {"a": 0.95})
	shockwave(c, 4.0, 52.0, 18, Color("#ffa050"))
	shockwave(c, 2.0, 34.0, 14, Color("#fff0b0"), {"delay": 2})
	# the classic five-armed blaze ("大")
	for arm in [[0, -1], [0, 1], [-1, 0.2], [1, 0.2], [-0.7, 0.9], [0.7, 0.9]]:
		for i in 8:
			particle({"x": c.x, "y": c.y, "vx": arm[0] * i * 0.9, "vy": arm[1] * i * 0.9, "drag": 0.82, "life": 34, "shape": "flame", "size": 4.5, "cols": FIRE, "glow": 0.3})
	scene.shake = 7.0
	await flash("#f8a040", 0.55)
	await wait(26)


func r_firespin(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	flare(c, 50.0, Color("#ff7028"), 40, {"a": 0.55, "s0": 0.5})
	shockwave(c + Vector2(0, 20), 4.0, 26.0, 20, Color("#ffa050"), {"squash": 0.45})
	await par([func() -> void: await vortex(t, 34, FIRE), func() -> void: await tint(t, "#f86030", 34)])


func r_watergun(a: String, t: String, _ar: Variant) -> void:
	var mouth := await charge_up(a, 6, Color("#78c0f8"), {"size": 16.0, "reach": 14.0, "count": 7, "shape": "dot"})
	var bp := center(t)
	for i in 24:
		var ph := rand(0, TAU)
		particle({"delay": i, "life": 14, "shape": "drop", "size": 3.2, "cols": [Color("#f4fcff"), Color("#78c0f8"), Color("#3878e0")], "glow": 0.18,
			"on_update": func(p: Dictionary) -> void:
				var tt := float(p["age"]) / 14.0
				var age: int = p["age"]
				p["x"] = mouth.x + (bp.x - mouth.x) * tt
				p["y"] = mouth.y + (bp.y - mouth.y) * tt - sin(tt * PI) * 9.0 + sin(age * 0.8 + ph) * 1.2
				p["rot"] = atan2(bp.y - mouth.y, bp.x - mouth.x) + PI * 0.5})
	await wait(26)
	shockwave(bp, 3.0, 24.0, 12, Color("#a8d8ff"))
	flare(bp, 38.0, Color("#78c0f8"), 12, {"a": 0.6})
	emit(t, 20, {"life": 22, "shape": "drop", "size": 2.0, "vy": -2.4, "jy": 1.0, "jx": 2.2, "ay": 0.22, "cols": ["#f4fcff", "#78c0f8"]})
	await wait(12)


func r_bubble(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 22, "bubble", [Color("#d0f0ff"), Color("#80c8f8")], {"count": 8, "gap": 3, "size": 4.0, "spread": 12.0, "arc": 8.0})
	await wait(8)

func r_hydropump(a: String, t: String, _ar: Variant) -> void:
	var mouth := await charge_up(a, 12, Color("#58a8f8"), {"size": 30.0, "reach": 15.0, "shape": "dot"})
	await beam(a, t, 30, WATER, 6.5, {"wave": 2.0, "from_px": mouth})
	var c := center(t)
	flare(c, 70.0, Color("#78c0f8"), 20, {"a": 0.7})
	shockwave(c, 4.0, 46.0, 16, Color("#a8d8ff"))
	emit(t, 26, {"life": 22, "shape": "bubble", "size": 2.0, "vy": -2.2, "jx": 2.4, "ay": 0.12, "cols": WATER})
	emit(t, 18, {"life": 22, "shape": "drop", "size": 2.2, "vy": -2.6, "jx": 2.4, "jy": 1.0, "ay": 0.24, "cols": ["#f4fcff", "#78c0f8"]})
	scene.shake = 5.0
	await wait(12)


func r_surf(_a: String, t: String, _ar: Variant) -> void:
	var sheet := MeshInstance3D.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	sheet.material_override = mat
	sheet.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sheet.extra_cull_margin = 16384.0
	add_child(sheet)
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > 50:
			return false
		# rises with an ease-out, holds, then drains
		var rise := sin(clampf(age / 50.0, 0.0, 1.0) * PI)
		var top := 132.0 - Smooth.ease_out(rise, 1.6) * 104.0
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var cols_n := 33
		var rows := 14
		var grid: Array = []
		for r in rows + 1:
			var row: Array = []
			var yy := top + (136.0 - top) * pow(r / float(rows), 1.3)
			for ci in cols_n:
				var xx := -8.0 + ci * 10.5
				var w := sin(xx * 0.08 + age * 0.3 + yy * 0.1)
				var c := WHITE if yy < top + 3 + w * 2 else (Color("#a8d8ff") if w > 0.7 else Color("#3a80e0"))
				var depth_shade := 1.0 - 0.25 * float(r) / rows
				c = Color(c.r * depth_shade, c.g * depth_shade, c.b, 1.0)
				var pos := to3d(Vector2(xx, yy + (w * 3.0 if r == 0 else 0.0)), 0.9 + r * 0.02)
				row.append([pos, Color(c, 0.78)])
			grid.append(row)
		for r in rows:
			for ci in cols_n - 1:
				var q: Array = [grid[r][ci], grid[r][ci + 1], grid[r + 1][ci + 1], grid[r + 1][ci]]
				for idx in [0, 1, 2, 0, 2, 3]:
					st.set_color(q[idx][1])
					st.add_vertex(q[idx][0])
		sheet.mesh = st.commit()
		# spray thrown off the crest
		if age % 2 == 0 and age < 42:
			for j in 3:
				particle({"x": rand(0, 320), "y": top + rand(-2, 4), "vx": rand(-0.6, 0.6), "vy": rand(-2.4, -0.8), "ay": 0.16, "life": 16, "shape": "dot",
					"size": rand(1.0, 2.0), "cols": [Color("#ffffff"), Color("#bfe4ff")], "glow": 0.15})
		return true, {"nodes": [sheet]})
	scene.shake = 3.5
	await wait(24)
	await tint(t, "#78b0f8", 20)
	await wait(6)


func r_clamp(a: String, t: String, _ar: Variant) -> void:
	await r_bite(a, t, null)

func r_thundershock(a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	var mouth := await charge_up(a, 6, Color("#f8e048"), {"size": 16.0, "reach": 12.0, "count": 8})
	await lightning(mouth.x, mouth.y, c.x, c.y, 12, ELEC[1])
	flare(c, 46.0, Color("#fff070"), 12, {"a": 0.8})
	emit(t, 12, {"life": 14, "shape": "spark", "cols": ELEC, "jx": 2.0, "jy": 2.0, "glow": 0.35})
	await tint(t, "#f8e040", 12)


func r_thunderbolt(a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	await charge_up(a, 8, Color("#f8e048"), {"size": 20.0, "reach": 4.0, "count": 12})
	for i in 3:
		scene.flash = 0.4
		scene.flash_color = Color("#fff8c0")
		flare(c, 60.0, Color("#fff070"), 9, {"a": 0.8})
		await lightning(c.x + rand(-30, 30), c.y - 46, c.x, c.y, 8, ELEC[1])
	shockwave(c, 3.0, 32.0, 12, Color("#fff070"))
	emit(t, 18, {"life": 18, "shape": "spark", "cols": ELEC, "jx": 3.0, "jy": 3.0, "glow": 0.35})
	scene.shake = maxf(scene.shake, 3.0)
	for i in 3:
		var a0 := c + Vector2(rand(-14, -4), rand(-12, 12))
		var a1 := c + Vector2(rand(4, 14), rand(-12, 12))
		lightning(a0.x, a0.y, a1.x, a1.y, 6, ELEC[1])
	await tint(t, "#f8e040", 12)


func r_thunder(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	await darken(12, "#000010", 0.5)
	scene.flash = 1.0
	scene.flash_color = WHITE
	flare(c, 90.0, Color("#fff8a0"), 20, {"a": 1.0})
	shockwave(Vector2.ZERO, 6.0, 48.0, 18, Color("#fff8a0"), {"flat": true, "at_world": scene.ground_world(t), "a": 0.8})
	await lightning(c.x, 0, c.x, c.y + 10, 24, "#f8f090")
	scene.shake = 7.0
	emit(t, 24, {"life": 20, "shape": "spark", "cols": ELEC, "jx": 3.5, "jy": 3.5, "glow": 0.35})
	await tint(t, "#f8e040", 10)


func r_thunderwave(a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	for i in 3:
		shockwave(c, 2.0, 24.0, 12, Color(ELEC[1]), {"delay": i * 4})
	flare(c, 46.0, Color("#fff070"), 20, {"a": 0.5})
	for i in 4:
		var a0 := c + Vector2(rand(-16, -4), rand(-14, 14))
		var a1 := c + Vector2(rand(4, 16), rand(-14, 14))
		lightning(a0.x, a0.y, a1.x, a1.y, 8, ELEC[1])
	emit(t, 12, {"life": 14, "shape": "spark", "cols": ELEC, "glow": 0.35})
	await wait(20)


func r_vinewhip(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	for k in 2:
		var nodes: Array = []
		for i in 12:
			nodes.append(_mesh_node("leaf", Color("#3a9a38")))
		var kk := k
		add_fx(func(f: Dictionary) -> bool:
			if int(f["age"]) > 10:
				return false
			for i in 12:
				var x := c.x - 12 + i * 2
				var y := c.y - 10 + sin(i * 0.8 + int(f["age"])) * 6 + kk * 8
				var pos := to3d(Vector2(x, y), 0.4)
				var w := px_world(pos) * 4.0
				_put(nodes[i], Transform3D(_face_basis(PI * 0.5).scaled(Vector3(w, w, w)), pos))
			return true, {"nodes": nodes})
		await wait(6)
	await impact(t)

func r_razorleaf(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 20, "leaf", [Color("#98e058"), Color("#58b040")], {"count": 14, "gap": 2, "spread": 16.0, "arc": 18.0, "spin": 0.45, "size": 4.2,
		"trail": [Color("#b8f070"), Color("#58b040")], "trailSize": 1.5})
	await slash(t, 2, "#c8f0a0")
	await impact(t)

func r_solarbeam(a: String, t: String, _ar: Variant) -> void:
	# gather sunlight, then fire it
	var mh := [Vector2.ZERO]
	await par([func() -> void: await darken(20, "#101800", 0.3), func() -> void:
		mh[0] = await charge_up(a, 18, Color("#f8f070"), {"size": 38.0, "reach": 14.0, "shape": "star", "count": 34})])
	var mouth: Vector2 = mh[0]
	await beam(a, t, 34, ["#fff8c0", "#f8f070", "#a8e060"], 9.0, {"sparks": "star", "from_px": mouth})
	var c := center(t)
	flare(c, 80.0, Color("#f8f8a0"), 18, {"a": 0.9})
	shockwave(c, 4.0, 42.0, 14, Color("#f8f8a0"))
	scene.shake = 5.0
	await wait(6)


func r_charge(a: String, _t: String, _ar: Variant) -> void:
	var c := center(a)
	for i in 20:
		var ang := rand(0, TAU)
		particle({"delay": i, "life": 14, "shape": "spark", "cols": [Color("#fff8c0"), Color("#f8e070")], "on_update": func(p: Dictionary) -> void:
			var r := 30.0 * (1.0 - int(p["age"]) / 14.0)
			p["x"] = c.x + cos(ang) * r
			p["y"] = c.y + sin(ang) * r})
	await tint(a, "#ffffff", 30)

func r_drain(a: String, t: String, col: Variant) -> void:
	var A := center(a)
	var Bp := center(t)
	var cols: Array = (col as Array).map(func(x): return Color(x)) if col is Array else [Color("#c8f888"), Color("#78d048")]
	for i in 14:
		var off := rand(-10, 10)
		particle({"delay": i * 2, "life": 22, "shape": "dot", "size": 3.0, "cols": cols, "glow": 0.25, "on_update": func(p: Dictionary) -> void:
			var tt := int(p["age"]) / 22.0
			p["x"] = Bp.x + (A.x - Bp.x) * tt + sin(tt * PI) * off
			p["y"] = Bp.y + (A.y - Bp.y) * tt - sin(tt * PI) * 20})
	await wait(40)
	await tint(a, (col as Array)[0] if col is Array else "#c8f888", 12)

func r_leechseed(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 20, "seed", [Color("#8a5a2a")], {"count": 3, "gap": 3, "arc": 22.0, "spread": 8.0})
	emit(t, 6, {"life": 20, "shape": "leaf", "cols": GRASS, "vy": -0.4})
	await wait(12)

func r_seeddrain(a: String, _t: String, _ar: Variant) -> void:
	await r_drain(other(a), a, ["#e8f898", "#a8d848"])

func r_powder(_a: String, t: String, col: Variant) -> void:
	var c := center(t)
	var cc := Color(str(col))
	flare(c + Vector2(0, -28), 60.0, cc, 44, {"a": 0.28, "s0": 0.6})
	for i in 44:
		var x0 := c.x + rand(-20, 20)
		var y0 := c.y - 40 + rand(-6, 6)
		var vy := rand(0.5, 1.1)
		var ph := rand(0, TAU)
		particle({"x": x0, "y": y0, "vy": vy, "vx": rand(-0.25, 0.25), "delay": int(rand(0, 18)), "life": 34, "shape": "dot", "size": rand(2.0, 3.6), "glow": 0.3, "cols": [cc.lightened(0.5), cc, cc.darkened(0.2)], "fade": 0.6,
			"on_update": func(p: Dictionary) -> void:
				var age: int = p["age"]
				p["x"] += sin(age * 0.3 + ph) * 0.35})
	await wait(44)


func r_petaldance(_a: String, t: String, _ar: Variant) -> void:
	await vortex(t, 36, ["#ffb0d0", "#f880b0", "#ffe0f0"], "leaf")
	await impact(t)

func r_icebeam(a: String, t: String, _ar: Variant) -> void:
	var mouth := await charge_up(a, 10, Color("#a8e8f8"), {"size": 26.0, "reach": 15.0, "shape": "snow"})
	await beam(a, t, 28, ICE, 5.0, {"sparks": "snow", "from_px": mouth})
	var c := center(t)
	flare(c, 60.0, Color("#c8f4ff"), 18, {"a": 0.8})
	shockwave(c, 3.0, 38.0, 14, Color("#d8f8ff"))
	emit(t, 14, {"life": 28, "shape": "shard", "cols": ICE, "jx": 1.2, "jy": 1.2, "glow": 0.3})
	await tint(t, "#a0e0ff", 16)
	await wait(6)


func r_blizzard(_a: String, t: String, _ar: Variant) -> void:
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > 70:
			scene.darken = 0.0
			return false
		scene.darken_color = Color("#e8f0ff")
		scene.darken = sin(int(f["age"]) / 70.0 * PI) * 0.35
		return true)
	# wind-blown snow plus long streaks of driven ice
	for i in 26:
		var y0 := rand(-10, 132)
		particle({"delay": int(rand(0, 40)), "x": rand(-20, 340), "y": y0, "vx": -7.0, "vy": 2.2, "life": 30, "shape": "dot", "size": 0.9, "cols": [WHITE], "glow": 0.0, "fade": 0.7})
	await screen_rain(230, 56, {"shape": "snow", "size": 2.8, "vx": -4.0, "vy": 2.6, "cols": [WHITE, Color("#c8f0ff")], "life": 60, "glow": 0.12})
	var c := center(t)
	shockwave(c, 4.0, 46.0, 18, Color("#d8f8ff"))
	emit(t, 20, {"life": 34, "shape": "shard", "cols": ICE, "rx": 18.0, "ry": 14.0, "glow": 0.3})
	scene.shake = 5.0
	await tint(t, "#a0e0ff", 16)
	await wait(6)


func r_aurorabeam(a: String, t: String, _ar: Variant) -> void:
	await beam(a, t, 30, ["#ff8080", "#f8d860", "#80f080", "#80c0ff", "#c080ff"], 5.0, {"rainbow": true})
	await wait(4)

func r_mist(a: String, t: String, col: Variant) -> void:
	var cc: String = str(col) if col != null else "#e8f0ff"
	emit(t if t != "" else a, 24, {"life": 40, "shape": "dot", "size": 5.0, "grow": 1.0, "rx": 26.0, "ry": 16.0, "vx": 0.3, "cols": [cc, Color(cc).darkened(0.1)], "spreadT": 10})
	await wait(46)

func r_psychic(a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	await charge_up(a, 10, Color("#f070c0"), {"size": 26.0, "reach": 6.0, "dy": -12.0, "count": 16, "shape": "ring"})
	for i in 3:
		shockwave(c, 4.0, 34.0, 16, Color("#f890d0"), {"delay": i * 5, "a": 0.9})
	flare(c, 60.0, Color("#f070c0"), 40, {"a": 0.5})
	await par([func() -> void: await wave(5, 40), func() -> void:
		await wait(6)
		await tint(t, "#f890d0", 22)])


func r_confusion(a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	await charge_up(a, 6, Color("#f070c0"), {"size": 18.0, "reach": 6.0, "dy": -12.0, "count": 8, "shape": "ring"})
	shockwave(c, 4.0, 28.0, 14, Color("#f890d0"))
	await par([func() -> void: await tint(t, "#f070c0", 16), func() -> void: await wave(3, 26)])


func r_psybeam(a: String, t: String, _ar: Variant) -> void:
	var A := center(a)
	var Bp := center(t)
	for i in 10:
		particle({"delay": i * 2, "life": 16, "shape": "ring", "size": 4.0, "cols": PSY, "on_update": func(p: Dictionary) -> void:
			var tt := int(p["age"]) / 16.0
			p["x"] = A.x + (Bp.x - A.x) * tt
			p["y"] = A.y + (Bp.y - A.y) * tt
			p["size"] = 3.0 + sin(int(p["age"])) * 2})
	await wait(36)
	await wave(3, 16)

func r_hypnosis(a: String, t: String, _ar: Variant) -> void:
	var A := center(a)
	var Bp := center(t)
	for i in 4:
		particle({"delay": i * 5, "life": 22, "shape": "ring", "size": 5.0, "cols": ["#f8a0e0"], "on_update": func(p: Dictionary) -> void:
			var tt := int(p["age"]) / 22.0
			p["x"] = A.x + (Bp.x - A.x) * tt
			p["y"] = A.y + (Bp.y - A.y) * tt + sin(int(p["age"]) * 0.6) * 6})
	await wait(40)

func r_shield(a: String, _t: String, col: Variant) -> void:
	var c := center(a)
	var cc := Color(str(col) if col != null else "#b8e0ff")
	var node := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(1, 1, 0.05)
	node.mesh = bm
	var m := _mat(cc, 0.4)
	node.material_override = m
	add_child(node)
	var edge := _mesh_node("ring", cc)
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > 36:
			return false
		var al := sin(int(f["age"]) / 36.0 * PI) * 0.6
		var pos := to3d(Vector2(c.x + (18.0 if a == "p" else -18.0), c.y), 0.8)
		var w := px_world(pos) * 34.0
		_put(node, Transform3D(_face_basis(PI / 4).scaled(Vector3(w, w, w)), pos))
		m.albedo_color = Color(cc, al * 0.6)
		_put(edge, Transform3D(_face_basis(0).scaled(Vector3(w * 1.4, w * 1.4, w * 1.4)), pos))
		(edge.material_override as StandardMaterial3D).albedo_color = cc
		edge.visible = al > 0.15
		return true, {"nodes": [node, edge]})
	await wait(36)

func r_heal(a: String, _t: String, _ar: Variant) -> void:
	emit(a, 18, {"life": 26, "shape": "star", "size": 2.0, "vy": -1.0, "cols": ["#f0ffc0", "#a8f0a0"], "spreadT": 16})
	await tint(a, "#c8ffb0", 30)

func r_rest(a: String, t: String, _ar: Variant) -> void:
	emit(a, 4, {"life": 40, "shape": "z", "vy": -0.6, "vx": 0.4, "cols": ["#e0e8ff"], "spreadT": 24})
	await r_heal(a, t, null)

func r_rocks(_a: String, t: String, ar: Variant) -> void:
	var c := center(t)
	var n: int = int(ar) if ar != null else 4
	for i in n:
		var x0 := c.x + rand(-20, 20)
		particle({"x": x0, "y": c.y - 70, "vy": 4.0, "ay": 0.35, "delay": i * 5, "life": 17, "shape": "rock", "size": rand(4, 6.5), "cols": ["#a08868"],
			"on_update": func(p: Dictionary) -> void:
				if int(p["age"]) == 16:
					scene.shake = maxf(scene.shake, 3.0)
					for k in 5:
						particle({"x": p["x"], "y": p["y"] + 4, "vx": rand(-1.5, 1.5), "vy": rand(-2, -0.5), "ay": 0.2, "life": 14, "shape": "dot", "size": 3.0, "cols": ["#d8c8a8", "#a89878"]})})
	await wait(18 + n * 5)
	await impact(t, "#d0b890", true)

func r_earthquake(_a: String, t: String, _ar: Variant) -> void:
	var tgt: Vector3 = scene.ground_world(t)
	var gnd: Vector3 = scene.ground_world("p" if t == "e" else "e")
	# shock rings roll out over the real ground under both battlers, rocks jump up
	for k in 4:
		shockwave(Vector2.ZERO, 8.0, 120.0, 24, Color("#fff0c8"), {"flat": true, "at_world": tgt, "a": 0.7, "delay": k * 8})
		shockwave(Vector2.ZERO, 8.0, 100.0, 24, Color("#e8d0a0"), {"flat": true, "at_world": gnd, "a": 0.5, "delay": k * 8 + 3})
	for i in 4:
		scene.shake = 9.0
		for k in 10:
			particle({"x": rand(0, 320), "y": rand(80, 128), "vy": rand(-3.5, -1), "vx": rand(-0.5, 0.5), "ay": 0.25, "life": 22, "shape": "rock", "size": rand(2, 3.5), "cols": ["#b09070"]})
		for k in 5:
			particle({"x": rand(0, 320), "y": rand(100, 130), "vy": rand(-1.4, -0.4), "vx": rand(-0.4, 0.4), "life": 26, "shape": "dot", "size": rand(2.0, 3.5), "grow": 1.0,
				"cols": [Color("#d8c8a8"), Color("#a89878")], "glow": 0.0, "fade": 0.3})
		await wait(11)


func r_fissure(a: String, t: String, _ar: Variant) -> void:
	await darken(20, "#200c08", 0.5)
	await r_earthquake(a, t, null)

func r_dig(a: String, t: String, _ar: Variant) -> void:
	emit(t, 16, {"life": 20, "shape": "rock", "size": 1.8, "vy": -3.0, "jx": 2.0, "ay": 0.3, "cols": ["#b08a60"]})
	await r_bighit(a, t, null)

func r_sand(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 14, "dot", [Color("#e8d098"), Color("#c8a870")], {"count": 20, "gap": 1, "spread": 14.0, "size": 2.0})
	await wait(4)

func r_poison(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 16, "bubble", POIS.map(func(x): return Color(x)), {"count": 5, "gap": 3, "arc": 16.0, "size": 3.0})
	emit(t, 10, {"life": 22, "shape": "bubble", "size": 2.0, "vy": -0.8, "cols": POIS, "spreadT": 10})
	await wait(20)

func r_gas(a: String, t: String, col: Variant) -> void:
	await r_mist(a, t, col if col != null else "#b080d0")

func r_lick(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	var tongue := _mesh_node("drop", Color("#f07898"))
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > 16:
			return false
		var pos := to3d(Vector2(c.x, c.y - 4 + (int(f["age"]) - 8)), 0.6)
		var w := px_world(pos) * 8.0
		_put(tongue, Transform3D(_face_basis(PI).scaled(Vector3(w, w * 2.0, w)), pos))
		return true, {"nodes": [tongue]})
	await wait(16)
	await impact(t)

func r_nightshade(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	flare(c, 60.0, Color("#6030a0"), 36, {"a": 0.55})
	for i in 22:
		var a0 := rand(0.0, TAU)
		var r0 := rand(16.0, 34.0)
		particle({"delay": int(rand(0, 14)), "life": 26, "shape": "dot", "size": rand(1.2, 2.2), "cols": [Color("#d0a0ff"), Color("#6a30a0"), Color("#201038")], "glow": 0.25, "fade": 0.6,
			"on_update": func(p: Dictionary) -> void:
				var tt := float(p["age"]) / 26.0
				var an := a0 + tt * 2.6
				var r := r0 * (1.0 - Smooth.ease_in(tt, 1.6) * 0.85)
				p["x"] = c.x + cos(an) * r
				p["y"] = c.y + sin(an) * r * 0.7})
	await par([func() -> void: await darken(30, "#100020", 0.7), func() -> void:
		await wait(8)
		await tint(t, "#402060", 16)])


func r_confuseray(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 30, "dot", [Color("#ffffa0"), Color("#f8d048")], {"size": 6.0, "arc": 12.0, "trail": [Color("#f0e080")], "trailSize": 3.0})
	await wait(4)

func r_dragonrage(_a: String, t: String, _ar: Variant) -> void:
	await vortex(t, 36, ["#80a0ff", "#4060e0", "#b0c8ff"])
	scene.shake = 4.0
	await wait(6)

func r_wind(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	for i in 20:
		var a0 := rand(0, TAU)
		particle({"delay": int(floor(rand(0, 12))), "life": 18, "shape": "dot", "size": 1.0, "cols": [WHITE, Color("#d0e8ff")], "on_update": func(p: Dictionary) -> void:
			var r := 18.0 - int(p["age"]) * 0.6
			var an := a0 + int(p["age"]) * 0.5
			p["x"] = c.x + cos(an) * r
			p["y"] = c.y + sin(an) * r * 0.5})
	await wait(26)
	await impact(t)

func r_wing(a: String, t: String, _ar: Variant) -> void:
	await par([func() -> void: await lunge(a, 16), func() -> void:
		await wait(5)
		await slash(t, 2, "#e0e8ff")])

func r_sound(a: String, _t: String, col: Variant) -> void:
	var A := center(a)
	var cc := Color(str(col) if col != null else "#ffffff")
	for i in 5:
		var arc_nodes: Array = []
		for k in 13:
			arc_nodes.append(_mesh_node("dot", cc))
		add_fx(func(f: Dictionary) -> bool:
			if int(f["age"]) > 16:
				return false
			var r := 6.0 + int(f["age"]) * 3.0
			var dir := 0.0 if a == "p" else PI
			for k in 13:
				var an := dir + (k - 6) * 0.08
				var pos := to3d(Vector2(A.x + cos(an) * r, A.y + sin(an) * r), 0.3)
				var w := px_world(pos) * 1.6
				_put(arc_nodes[k], Transform3D(Basis().scaled(Vector3(w, w, w)), pos))
			return true, {"nodes": arc_nodes, "delay": i * 4})
	await wait(36)

func r_sing(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 30, "note", [Color("#f8f8ff")], {"count": 5, "gap": 5, "arc": 16.0, "spread": 10.0})
	await wait(6)

func r_statup(a: String, _t: String, col: Variant) -> void:
	await stat(a, true, str(col) if col != null else "")

func r_statdown(_a: String, t: String, col: Variant) -> void:
	await stat(t, false, str(col) if col != null else "")

func r_swords(a: String, _t: String, _ar: Variant) -> void:
	var c := center(a)
	for i in 3:
		var a0 := i / 3.0 * TAU
		particle({"life": 30, "shape": "needle", "size": 4.2, "cols": ["#e0e8f8"], "glow": 0.3, "on_update": func(p: Dictionary) -> void:
			var an := a0 + int(p["age"]) * 0.25
			p["x"] = c.x + cos(an) * 18
			p["y"] = c.y + sin(an) * 8
			p["rot"] = PI / 2})
	await wait(30)
	await stat(a, true)

func r_glow(a: String, _t: String, col: Variant) -> void:
	await tint(a, str(col) if col != null else "#ffffff", 24)

func r_doubleteam(a: String, _t: String, _ar: Variant) -> void:
	for i in 20:
		scene.offs[a].x = (-1.0 if i % 4 < 2 else 1.0) * 8.0
		scene.vis[a] = 0.5 if i % 2 else 1.0
		await wait(1)
	scene.offs[a] = Vector2.ZERO
	scene.vis[a] = 1.0

func r_minimize(a: String, _t: String, _ar: Variant) -> void:
	for i in 12:
		scene.scale_k[a] = 1.0 - i / 24.0
		await wait(1)
	await wait(10)
	scene.scale_k[a] = 1.0

func r_explosion(a: String, t: String, _ar: Variant) -> void:
	var c := center(a)
	await flash("#ffffff", 1.0)
	flare(c, 120.0, Color("#ffc060"), 24, {"a": 1.0})
	shockwave(c, 4.0, 80.0, 20, Color("#ffd090"))
	shockwave(c, 2.0, 56.0, 16, WHITE, {"delay": 2})
	shockwave(Vector2.ZERO, 6.0, 90.0, 22, Color("#ffe0a0"), {"flat": true, "at_world": scene.ground_world(a), "a": 0.7})
	for i in 40:
		var an := rand(0, TAU)
		var v := rand(1, 5)
		particle({"x": c.x, "y": c.y, "vx": cos(an) * v, "vy": sin(an) * v, "drag": 0.92, "life": 30, "shape": "flame", "size": 3.2, "cols": [Color("#fff0b0")] + FIRE.map(func(x): return Color(x)) + [Color("#402018")], "glow": 0.3})
	for i in 14:
		var an := rand(0, TAU)
		particle({"x": c.x, "y": c.y, "vx": cos(an) * rand(0.4, 1.6), "vy": sin(an) * rand(0.4, 1.6) - 0.3, "drag": 0.94, "life": 40, "shape": "dot", "size": rand(3.0, 5.0), "grow": 1.2,
			"cols": [Color("#605858"), Color("#302828")], "glow": 0.0, "fade": 0.35, "delay": 4})
	scene.shake = 10.0
	await wait(30)
	await impact(t, "#f8a040", true)


func r_splash(a: String, _t: String, _ar: Variant) -> void:
	for k in 3:
		for i in 8:
			scene.offs[a].y = -sin(i / 8.0 * PI) * 10.0
			await wait(1)
	scene.offs[a].y = 0.0
	emit(a, 8, {"life": 16, "shape": "drop", "size": 2.0, "vy": -2.0, "jx": 2.0, "ay": 0.25, "ry": 2.0, "cols": WATER})
	await wait(8)

func r_swift(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 16, "star", [Color("#fff8a0"), Color("#f8d048")], {"count": 6, "gap": 3, "spread": 12.0, "arc": 10.0, "size": 4.2,
		"trail": [Color("#fff8a0"), Color("#f8b030")], "trailSize": 1.6})
	await impact(t)

func r_coins(a: String, t: String, _ar: Variant) -> void:
	await r_hit(a, t, null)
	emit(t, 10, {"life": 26, "shape": "coin", "vy": -2.5, "jx": 2.0, "ay": 0.25, "cols": ["#f8d048"]})
	await wait(16)

func r_bone(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 16, "bone", [Color("#f0e8d0")], {"spin": 0.6, "arc": 10.0})
	await impact(t, "", true)

func r_egg(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 18, "egg", [Color("#f8f0d8")], {"arc": 20.0})
	await r_explosionSmall(a, t, null)

func r_explosionSmall(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	for i in 14:
		var an := rand(0, TAU)
		particle({"x": c.x, "y": c.y, "vx": cos(an) * 2, "vy": sin(an) * 2, "drag": 0.9, "life": 18, "shape": "flame", "size": 2.0, "cols": FIRE})
	scene.shake = 4.0
	await wait(14)

func r_triattack(a: String, t: String, _ar: Variant) -> void:
	await r_ember(a, t, null)
	await r_icebeam(a, t, null)
	await r_thundershock(a, t, null)

func r_string(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 16, "dot", [WHITE], {"count": 10, "gap": 1, "spread": 8.0, "trail": [Color("#f0f0f0")], "trailSize": 1.0})
	var c := center(t)
	var threads: Array = []
	for i in 9:
		threads.append(_mesh_node("dot", WHITE))
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > 30:
			return false
		for k in 9:
			var i := -16 + k * 4
			var pos := to3d(c, 0.5)
			var w := px_world(pos)
			var ang := atan2(32.0, -2.0 * i)
			_put(threads[k], Transform3D(_face_basis(ang).scaled(Vector3(36 * w, 0.8 * w, 0.8 * w)), pos))
		return true, {"nodes": threads})
	await wait(30)

func r_metronome(a: String, _t: String, _ar: Variant) -> void:
	var c := center(a)
	var hand := _mesh_node("needle", WHITE)
	for i in 24:
		var an := sin(i * 0.5) * 0.8 - PI / 2
		var pos := to3d(Vector2(c.x + cos(an) * 5, c.y - 10 + sin(an) * 5), 0.5)
		var w := px_world(pos) * 10.0
		_put(hand, Transform3D(_face_basis(an).scaled(Vector3(w, w, w)), pos))
		await wait(1)
	hand.queue_free()

func r_transform(a: String, _t: String, _ar: Variant) -> void:
	await tint(a, "#ffffff", 20)

func r_teleport(a: String, _t: String, _ar: Variant) -> void:
	emit(a, 16, {"life": 20, "shape": "star", "cols": ["#fff8c0"], "vy": -2.0})
	for i in 12:
		scene.vis[a] = float(i % 2)
		await wait(1)
	scene.vis[a] = 0.0
	await wait(10)

func r_disable(_a: String, t: String, _ar: Variant) -> void:
	await ring(t, 14, "#e04040", 22, 10, 2)

func r_rage(a: String, t: String, _ar: Variant) -> void:
	await tint(a, "#ff4040", 12)
	await r_hit(a, t, null)

func r_bide(a: String, _t: String, _ar: Variant) -> void:
	await tint(a, "#ff8040", 20)

func r_counter(a: String, t: String, _ar: Variant) -> void:
	await strike(a, t, 24.0, "#f86040", true)

func r_focus(a: String, _t: String, _ar: Variant) -> void:
	emit(a, 16, {"life": 20, "shape": "dot", "size": 1.0, "vy": -3.0, "cols": ["#fff0a0", "#f8a040"], "spreadT": 12, "ry": 4.0})
	await tint(a, "#f8c060", 20)

func r_fly(a: String, t: String, _ar: Variant) -> void:
	await strike(a, t, 30.0, "", true)

func r_skyattack(a: String, t: String, _ar: Variant) -> void:
	await tint(a, "#ffffff", 10)
	await strike(a, t, 34.0, "#fff0a0", true)
	await flash("#ffffff", 0.6)

func r_leer(a: String, t: String, _ar: Variant) -> void:
	emit(a, 2, {"life": 20, "shape": "star", "size": 3.0, "rx": 6.0, "ry": 4.0, "cols": ["#ffe0e0", "#f06060"]})
	await wait(20)
	await stat(t, false)

func r_tailwhip(a: String, t: String, _ar: Variant) -> void:
	for i in 16:
		scene.offs[a].x = sin(i * 0.8) * 5.0
		await wait(1)
	scene.offs[a].x = 0.0
	await stat(t, false)

func r_haze(a: String, _t: String, _ar: Variant) -> void:
	await r_mist(a, "p", "#a0a0b0")

func r_conversion(a: String, _t: String, _ar: Variant) -> void:
	await tint(a, "#80f0ff", 20)

func r_mimic(a: String, _t: String, _ar: Variant) -> void:
	await tint(a, "#f0f0ff", 16)

func r_recharge(_a: String, _t: String, _ar: Variant) -> void:
	await wait(10)

func r_healitem(a: String, t: String, _ar: Variant) -> void:
	await r_heal(a, t, null)

func r_safariRock(_a: String, _t: String, _ar: Variant) -> void:
	await projectile("p", "e", 16, "rock", [Color("#a09078")], {"arc": 20.0, "size": 3.0})
	await impact("e")

func r_fly_charge(a: String, _t: String, _ar: Variant) -> void:
	for i in 14:
		scene.offs[a].y -= 5.0
		await wait(1)
	scene.offs[a].y = 0.0

func r_dig_charge(a: String, _t: String, _ar: Variant) -> void:
	emit(a, 14, {"life": 18, "shape": "rock", "size": 1.8, "vy": -2.0, "jx": 2.0, "ay": 0.25, "cols": ["#b08a60"]})
	for i in 12:
		scene.clip[a] = 1.0 - i / 12.0
		await wait(1)
	scene.clip[a] = 1.0
