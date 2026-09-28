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
	"needle", "bone", "egg", "shard", "heart", "impact", "claw", "fist", "drop"]
const GLOWY := {"flame": 0.28, "spark": 0.3, "star": 0.25, "bubble": 0.12, "shard": 0.2, "note": 0.15}
## world size (in upstream pixels) of each 1 m nominal mesh per unit of `size`
const SHAPE_PX := {"dot": [1.0, 1.0], "flame": [2.0, 0.0], "spark": [0.0, 4.0], "star": [2.4, 0.0], "ring": [2.0, 0.0],
	"bubble": [2.1, 3.2], "leaf": [3.2, 0.0], "snow": [2.2, 1.0], "rock": [2.1, 0.0], "note": [0.0, 8.0], "z": [0.0, 8.0],
	"coin": [0.0, 5.0], "seed": [0.0, 3.4], "needle": [0.0, 8.0], "bone": [0.0, 11.0], "egg": [0.0, 7.5], "shard": [0.0, 7.0],
	"heart": [0.0, 5.5], "impact": [2.0, 0.0], "claw": [1.0, 0.0], "fist": [2.0, 0.0], "drop": [2.0, 0.0]}
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
	"ICE_BEAM": ["icebeam"], "BLIZZARD": ["blizzard"], "PSYBEAM": ["psybeam"], "BUBBLEBEAM": ["bubble"], "AURORA_BEAM": ["aurorabeam"], "HYPER_BEAM": ["solarbeam"],
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
var _plane_e := Vector3.ZERO
var _plane_p := Vector3.ZERO

func setup(the_scene: Node, the_stage: BattleStage, seed_v: int = 1) -> void:
	scene = the_scene
	stage = the_stage
	rng.seed = seed_v
	for s in SHAPES:
		_meshes[s] = _load_mesh(s)
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	gt.width = 64
	gt.height = 64
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
func _mat(c: Color, alpha: float = 1.0, additive: bool = false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(c, alpha)
	if alpha < 1.0 or additive:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if additive:
		m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.no_depth_test = false
	m.disable_receive_shadows = true
	return m

func _mesh_node(shape: String, c: Color, alpha: float = 1.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = _meshes.get(shape, _meshes["dot"])
	mi.material_override = _mat(c, alpha)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi

func _glow_node(c: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(1, 1)
	mi.mesh = q
	var m := _mat(c, 1.0, true)
	m.albedo_texture = _glow_tex
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.billboard_keep_scale = true
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi

# ------------------------------------------------------------------ particle system (vfx.js particle())
func particle(o: Dictionary) -> Dictionary:
	var p := {"x": 0.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "ax": 0.0, "ay": 0.0, "drag": 1.0, "life": 30, "age": 0,
		"size": 1.0, "shape": "dot", "cols": [WHITE], "spin": 0.0, "rot": 0.0, "delay": 0, "grow": 0.0, "shrink": 0.0}
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
	var c: Color = cols[mini(cols.size() - 1, int(t * cols.size()))]
	var shape: String = p["shape"]
	if not p.has("node"):
		p["node"] = _mesh_node(shape, c, 0.6 if shape == "bubble" else 1.0)
		var gl: float = p.get("glow", GLOWY.get(shape, 0.0))
		if gl > 0.0:
			p["glow_node"] = _glow_node(c)
		if shape == "flame":
			# upstream flame(): pale-yellow core and gold ring inside the coloured rim
			p["mid"] = _mesh_node("flame", Color("#f8c030"))
			p["core"] = _mesh_node("dot", Color("#fff8c0"))
	var node: MeshInstance3D = p["node"]
	var mat: StandardMaterial3D = node.material_override
	mat.albedo_color = Color(c, mat.albedo_color.a)
	var sz: float = p["size"]
	if float(p["grow"]) != 0.0:
		sz *= 1.0 + t * float(p["grow"])
	if float(p["shrink"]) != 0.0:
		sz *= 1.0 - t * float(p["shrink"])
	sz = maxf(sz, MIN_SIZE.get(shape, 0.0))
	var spx: Array = SHAPE_PX.get(shape, [1.0, 0.0])
	var px_size: float = float(spx[0]) * sz + float(spx[1])
	var pos := to3d(Vector2(p["x"], p["y"]), 0.05)
	var s := px_world(pos) * px_size
	var b := _face_basis(float(p["rot"]))
	if shape in ["flame", "rock", "shard", "snow", "coin", "bone", "star"]:
		b = b * Basis(Vector3.UP, float(p["age"]) * 0.12 + float(p["x"]) * 0.01)
	node.global_transform = Transform3D(b.scaled(Vector3(s, s, s)), pos)
	if p.has("core"):
		var toward := (stage.camera.global_position - pos).normalized()
		var down := -stage.camera.global_transform.basis.y
		(p["mid"] as Node3D).global_transform = Transform3D(b.scaled(Vector3(s, s, s) * 0.72), pos + toward * s * 0.2 + down * s * 0.08)
		(p["core"] as Node3D).global_transform = Transform3D(b.scaled(Vector3(s, s, s) * 0.5), pos + toward * s * 0.4 + down * s * 0.12)
	if p.has("glow_node"):
		var g: MeshInstance3D = p["glow_node"]
		var gl2: float = p.get("glow", GLOWY.get(shape, 0.0))
		var r := (sz * 1.8 + 2.0) * 2.4 * px_world(pos)
		g.global_transform = Transform3D(Basis().scaled(Vector3(r, r, r)), pos - stage.camera.global_transform.basis.z * -0.02)
		(g.material_override as StandardMaterial3D).albedo_color = Color(c, gl2 * (1.0 - t * 0.5) * 0.9)
	return true

## Adds a per-frame effect; update(f) returns false when finished.
func add_fx(update: Callable, extra: Dictionary = {}) -> Dictionary:
	var f := {"age": 0, "update": update, "nodes": []}
	f.merge(extra, true)
	fx.append(f)
	return f

# ------------------------------------------------------------------ primitives
func burst(x: float, y: float, kind: String) -> void:
	var cols: Array = [WHITE, Color("#ffc0f0"), Color("#f080d0")] if kind == "capture" else [WHITE, Color("#fff0a0"), Color("#f8c040")]
	for i in 16:
		var a := i / 16.0 * TAU
		var v := rand(1.2, 2.6)
		particle({"x": x, "y": y, "vx": cos(a) * v, "vy": sin(a) * v, "drag": 0.9, "life": 18, "shape": "spark" if i % 2 else "dot", "size": 2.0, "cols": cols})
	particle({"x": x, "y": y, "life": 14, "shape": "ring", "size": 3.0, "grow": 5.0, "cols": [WHITE, cols[1]]})

func sparkle_at(x: float, y: float) -> void:
	particle({"x": x + rand(-8, 8), "y": y + rand(-6, 6), "life": 6, "shape": "star", "size": 2.0, "cols": [Color("#fff8a0")]})

func impact(k: String, col: String = "", big: bool = false) -> void:
	var c := center(k)
	var cc := Color(col) if col != "" else WHITE
	var x := c.x + rand(-6, 6)
	var y := c.y + rand(-6, 6)
	var star := _mesh_node("impact", cc)
	var core := _mesh_node("dot", WHITE)
	var glow := _glow_node(Color("#fff4b0"))
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > 8:
			return false
		var r := (14.0 if big else 10.0) * (1.0 - absf(int(f["age"]) - 4) / 5.0)
		var pos := to3d(Vector2(x, y), 0.3)
		var w := px_world(pos)
		star.global_transform = Transform3D(_face_basis(0.3 + int(f["age"]) * 0.1).scaled(Vector3.ONE * w * r * 2.0), pos)
		core.global_transform = Transform3D(Basis().scaled(Vector3.ONE * w * 5.0), pos)
		glow.global_transform = Transform3D(Basis().scaled(Vector3.ONE * w * r * 3.2), pos)
		(glow.material_override as StandardMaterial3D).albedo_color = Color(cc, 0.8)
		return true, {"nodes": [star, core, glow]})
	for i in 6:
		var a := rand(0, TAU)
		particle({"x": x, "y": y, "vx": cos(a) * rand(1, 2.5), "vy": sin(a) * rand(1, 2.5), "drag": 0.85, "life": 12, "shape": "spark", "cols": [WHITE, cc]})
	if big:
		scene.shake = maxf(scene.shake, 4.0)
	await wait(8)

func lunge(k: String, dist: float = 14.0) -> void:
	var d := 1.0 if k == "p" else -1.0
	for i in 5:
		scene.offs[k].x += d * dist / 5.0
		scene.offs[k].y -= d * dist / 10.0
		await wait(1)
	for i in 5:
		scene.offs[k].x -= d * dist / 5.0
		scene.offs[k].y += d * dist / 10.0
		await wait(1)
	scene.offs[k] = Vector2.ZERO

func projectile(from: String, to: String, frames: int, shape: String, cols: Array, o: Dictionary = {}) -> void:
	var a := center(from)
	var b := center(to)
	var n: int = o.get("count", 1)
	var gap: int = o.get("gap", 3)
	for j in n:
		var sp: float = o.get("spread", 0.0)
		var off := Vector2(rand(-sp, sp), rand(-sp, sp)) if sp > 0 else Vector2.ZERO
		var arc: float = o.get("arc", 0.0)
		var trail: Array = o.get("trail", [])
		var trail_size: float = o.get("trailSize", 2.0)
		particle({"delay": j * gap, "x": a.x, "y": a.y, "life": frames, "shape": shape, "size": o.get("size", 2.0), "cols": cols,
			"rot": atan2(b.y - a.y, b.x - a.x), "spin": o.get("spin", 0.0),
			"on_update": func(p: Dictionary) -> void:
				var tt := float(p["age"]) / frames
				p["x"] = a.x + (b.x + off.x - a.x) * tt
				p["y"] = a.y + (b.y + off.y - a.y) * tt - sin(tt * PI) * arc
				if not trail.is_empty() and int(p["age"]) % 2 == 0:
					particle({"x": p["x"], "y": p["y"], "life": 8, "shape": "dot", "size": trail_size, "cols": trail})})
	await wait(frames + (n - 1) * gap)

## upstream beam(): a thick line from attacker to target that grows in, with a
## white core and colour bands; `wave` wobbles it (HYDRO PUMP), `rainbow` cycles
## colours (AURORA BEAM), `sparks` sprays particles at the tip.
func beam(from: String, to: String, frames: int, cols: Array, width: float, o: Dictionary = {}) -> void:
	var a := center(from)
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
			mi.material_override = _mat(WHITE if j == 0 else cs[j - 1])
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(mi)
			row.append(mi)
		layers.append({"j": j, "nodes": row, "frac": 0.3 if j == 0 else 0.3 + 0.7 * j / float(n)})
	var wave_amp: float = o.get("wave", 0.0)
	var rainbow: bool = o.get("rainbow", false)
	var sparks: String = o.get("sparks", "")
	var glow := _glow_node(cs[0])
	var all_nodes: Array = [glow]
	for L in layers:
		all_nodes.append_array(L["nodes"])
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > frames:
			return false
		var grow := minf(1.0, age / 6.0)
		var fade := (frames - age) / 5.0 if age > frames - 5 else 1.0
		var e := a + (b - a) * grow
		var dirv := (e - a)
		var ln := dirv.length()
		var nrm := Vector2(-dirv.y, dirv.x) / maxf(ln, 0.001)
		var wdt := width * fade
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
			for li in layers.size():
				var L: Dictionary = layers[li]
				var node: MeshInstance3D = L["nodes"][i]
				node.visible = wdt > 0.2
				var th: float = 2.0 * wdt * float(L["frac"])
				if rainbow and int(L["j"]) > 0:
					var ci := int(fmod(t0 * ln * 0.2 + age * 0.5, cs.size()))
					(node.material_override as StandardMaterial3D).albedo_color = cs[ci]
				node.global_transform = Transform3D(bb.scaled(Vector3((d.length() + 0.6) * w, th * w, 0.02)), pos + cam_back * (0.004 * li))
		var tip := to3d(e, 0.2)
		var gw := px_world(tip) * wdt * 6.0
		glow.global_transform = Transform3D(Basis().scaled(Vector3(gw, gw, gw)), tip)
		(glow.material_override as StandardMaterial3D).albedo_color = Color(cs[0], 0.6 * fade)
		if sparks != "" and age % 2 == 0:
			particle({"x": e.x + rand(-4, 4), "y": e.y + rand(-4, 4), "vx": rand(-2, 2), "vy": rand(-2, 2), "life": 10, "shape": sparks, "cols": cs})
		return true, {"nodes": all_nodes})
	await wait(frames)

var _box: BoxMesh
func _unit_box() -> BoxMesh:
	if _box == null:
		_box = BoxMesh.new()
		_box.size = Vector3.ONE
	return _box

## A jagged 3D lightning bolt between two px points, re-rolled each frame (upstream bolt()).
func lightning(x0: float, y0: float, x1: float, y1: float, frames: int, col: String = "#f8e048") -> void:
	var cc := Color(col)
	var nodes: Array = []
	for i in 40:
		nodes.append(_mesh_node("dot", WHITE if i % 2 == 0 else cc))
	var glow := _glow_node(cc)
	nodes.append(glow)
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > frames:
			return false
		for n in nodes:
			n.visible = false
		if age % 3 == 2:
			return true
		var pts: Array = [Vector2(x0, y0)]
		for i in range(1, 7):
			var tt := i / 7.0
			pts.append(Vector2(x0 + (x1 - x0) * tt + rand(-7, 7), y0 + (y1 - y0) * tt + rand(-3, 3)))
		pts.append(Vector2(x1, y1))
		var used := 0
		for i in pts.size() - 1:
			used = _bolt_seg(nodes, used, pts[i], pts[i + 1], 1.6)
			if rng.randf() < 0.3 and used < 36:
				var br: Vector2 = pts[i] + Vector2(rand(-14, 14), rand(6, 16))
				used = _bolt_seg(nodes, used, pts[i], br, 1.0)
		var mid := to3d(Vector2(x1, y1), 0.2)
		var gw := px_world(mid) * 40.0
		glow.visible = true
		glow.global_transform = Transform3D(Basis().scaled(Vector3(gw, gw, gw)), mid)
		(glow.material_override as StandardMaterial3D).albedo_color = Color(cc, 0.6)
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
	outer.global_transform = Transform3D(bb.scaled(Vector3(d.length() * w * 1.05, thick * 3.0 * w, thick * 3.0 * w)), pos)
	inner.global_transform = Transform3D(bb.scaled(Vector3(d.length() * w * 1.05, thick * 1.2 * w, thick * 1.2 * w)), pos - stage.camera.global_transform.basis.z * -0.02)
	return used + 2

func ring(k: String, frames: int, col: String, r0: float, r1: float, thick: int = 1) -> void:
	var c := center(k)
	var node := _mesh_node("ring", Color(col))
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > frames:
			return false
		var r := r0 + (r1 - r0) * int(f["age"]) / float(frames)
		var pos := to3d(c, 0.3)
		var w := px_world(pos) * r * 2.0
		node.global_transform = Transform3D(_face_basis(0).scaled(Vector3(w, w * (1.0 + thick * 0.4), w)), pos)
		return true, {"nodes": [node]})
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
		add_fx(func(f: Dictionary) -> bool:
			if int(f["age"]) > 10:
				return false
			var ln := minf(1.0, int(f["age"]) / 4.0) * 22.0
			var pos := to3d(Vector2(c.x + ox, c.y), 0.4)
			var w := px_world(pos)
			node.global_transform = Transform3D(_face_basis(0).scaled(Vector3(ln * w * 1.4, ln * w * 1.4, w * 2)), pos)
			edge.global_transform = Transform3D(_face_basis(0).scaled(Vector3(ln * w * 1.55, ln * w * 1.55, w * 3)), pos - stage.camera.global_transform.basis.z * 0.02)
			return true, {"nodes": [node, edge]})
		await wait(3)
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

func stat(k: String, up: bool, col: String = "") -> void:
	var c := center(k)
	var cols: Array = [Color(col if col != "" else "#fff0a0"), Color("#f8a040"), Color("#e05030")] if up else [Color("#c0e0ff"), Color("#6090e0"), Color("#3050a0")]
	for i in 18:
		particle({"x": c.x + rand(-20, 20), "y": c.y + (20.0 if up else -26.0) + rand(-6, 6), "vy": -2.0 if up else 2.0,
			"delay": int(floor(rand(0, 16))), "life": 16, "shape": "dot", "size": 1.0, "cols": cols})
	for i in 24:
		scene.set_tint(k, cols[1], 0.4 * sin(i / 24.0 * PI))
		await wait(1)
	scene.set_tint(k, cols[1], 0.0)

# ------------------------------------------------------------------ entry points
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
	match st:
		"PSN":
			emit(k, 10, {"life": 24, "shape": "bubble", "size": 2.0, "vy": -0.8, "cols": POIS, "spreadT": 14})
			await tint(k, "#b060d0", 24)
		"BRN":
			emit(k, 10, {"life": 20, "shape": "flame", "size": 2.0, "vy": -0.8, "cols": FIRE, "spreadT": 12})
			await tint(k, "#f86030", 24)
		"PAR":
			emit(k, 12, {"life": 12, "shape": "spark", "cols": ELEC, "spreadT": 18})
			await tint(k, "#f8e040", 24)
		"SLP":
			emit(k, 3, {"life": 36, "shape": "z", "vy": -0.6, "vx": 0.5, "cols": ["#e0e8ff"], "spreadT": 20, "rx": 4.0, "ry": 4.0})
			await wait(36)
		"FRZ":
			emit(k, 10, {"life": 24, "shape": "shard", "cols": ICE, "spreadT": 10})
			await tint(k, "#a0e0ff", 24)
		"CONF":
			var c := center(k)
			for i in 3:
				var a0 := i / 3.0 * TAU
				particle({"life": 36, "shape": "star", "size": 2.0, "cols": ["#fff8a0"], "on_update": func(p: Dictionary) -> void:
					var an := a0 + int(p["age"]) * 0.25
					p["x"] = c.x + cos(an) * 14
					p["y"] = c.y - 18 + sin(an) * 4})
			await wait(36)
		_:
			await wait(1)

# ------------------------------------------------------------------ recipes (vfx.js R.*)
func r_hit(a: String, t: String, _ar: Variant) -> void:
	await lunge(a)
	await impact(t)

func r_bighit(a: String, t: String, _ar: Variant) -> void:
	await lunge(a, 22)
	await impact(t, "#f8e060", true)

func r_quick(a: String, t: String, _ar: Variant) -> void:
	var c := center(a)
	for i in 6:
		particle({"x": c.x, "y": c.y + rand(-10, 10), "vx": 7.0 if a == "p" else -7.0, "life": 12, "shape": "dot", "size": 1.0, "cols": [WHITE]})
	await lunge(a, 30)
	await impact(t)

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
		top.global_transform = Transform3D(_face_basis(PI * 0.25).scaled(Vector3(w, w * 0.5, w * 0.2)), p1)
		bot.global_transform = Transform3D(_face_basis(PI * 1.25).scaled(Vector3(w, w * 0.5, w * 0.2)), p2)
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
		fist.global_transform = Transform3D(_face_basis(0).scaled(Vector3(w, w, w)), pos)
		return true, {"nodes": [fist]})
	await wait(8)
	if ar != null:
		await call("r_" + str(ar), a, t, null)
	else:
		await impact(t, "", true)

func r_kick(a: String, t: String, _ar: Variant) -> void:
	await lunge(a, 18)
	await impact(t, "#f8f0c0", true)

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
	await projectile(a, t, 16, "flame", FIRE, {"count": 3, "gap": 5, "arc": 12.0, "size": 5.0, "trail": [Color("#f8c040"), Color("#e84818")], "trailSize": 3.0})
	emit(t, 18, {"life": 26, "shape": "flame", "size": 4.0, "vy": -1.0, "jx": 0.6, "cols": FIRE, "spreadT": 10, "rx": 16.0, "ry": 12.0})
	await flash("#f8a040", 0.25)
	await wait(18)

func r_flamethrower(a: String, t: String, _ar: Variant) -> void:
	var A := center(a)
	var Bp := center(t)
	for i in 26:
		var ii := i
		particle({"delay": i, "life": 16, "shape": "flame", "size": 2.5, "grow": 0.8, "cols": [Color("#f8d048"), Color(FIRE[0]), Color(FIRE[1])],
			"on_update": func(p: Dictionary) -> void:
				var tt := int(p["age"]) / 16.0
				p["x"] = A.x + (Bp.x - A.x) * tt + sin(int(p["age"]) + ii) * 2
				p["y"] = A.y + (Bp.y - A.y) * tt + cos(int(p["age"]) * 1.3 + ii) * 3})
	await wait(36)
	await vortex(t, 20, FIRE)

func r_fireblast(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 18, "flame", FIRE, {"size": 6.0, "trail": [Color("#f8c040"), Color("#e84818")], "trailSize": 4.0})
	var c := center(t)
	for arm in [[0, -1], [0, 1], [-1, 0.2], [1, 0.2], [-0.7, 0.9], [0.7, 0.9]]:
		for i in 8:
			particle({"x": c.x, "y": c.y, "vx": arm[0] * i * 0.9, "vy": arm[1] * i * 0.9, "drag": 0.82, "life": 34, "shape": "flame", "size": 4.5, "cols": FIRE})
	scene.shake = 5.0
	await flash("#f8a040", 0.5)
	await wait(26)

func r_firespin(_a: String, t: String, _ar: Variant) -> void:
	await vortex(t, 34, FIRE)

func r_watergun(a: String, t: String, _ar: Variant) -> void:
	var A := center(a)
	var Bp := center(t)
	for i in 22:
		var ii := i
		particle({"delay": i, "life": 14, "shape": "drop", "size": 4.0, "cols": [Color("#e8f8ff"), Color("#78c0f8"), Color("#3878e0")],
			"on_update": func(p: Dictionary) -> void:
				var tt := int(p["age"]) / 14.0
				p["x"] = A.x + (Bp.x - A.x) * tt
				p["y"] = A.y + (Bp.y - A.y) * tt - sin(tt * PI) * 10 + sin(int(p["age"]) + ii)})
	await wait(26)
	emit(t, 18, {"life": 20, "shape": "dot", "size": 3.0, "vy": -2.2, "jy": 1.0, "jx": 2.0, "ay": 0.2, "cols": ["#e8f8ff", "#78c0f8"]})
	await wait(12)

func r_bubble(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 22, "bubble", [Color("#d0f0ff"), Color("#80c8f8")], {"count": 6, "gap": 4, "size": 3.0, "spread": 10.0, "arc": 8.0})
	await wait(8)

func r_hydropump(a: String, t: String, _ar: Variant) -> void:
	await beam(a, t, 30, WATER, 6.0, {"wave": 2.0})
	emit(t, 20, {"life": 20, "shape": "bubble", "size": 2.0, "vy": -2.0, "jx": 2.0, "ay": 0.12, "cols": WATER})
	scene.shake = 4.0
	await wait(10)

func r_surf(_a: String, _t: String, _ar: Variant) -> void:
	var sheet := MeshInstance3D.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	sheet.material_override = mat
	sheet.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(sheet)
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > 50:
			return false
		var top := 132.0 - sin(age / 50.0 * PI) * 100.0
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
				var pos := to3d(Vector2(xx, yy + (w * 3.0 if r == 0 else 0.0)), 0.9 + r * 0.02)
				row.append([pos, Color(c, 0.75)])
			grid.append(row)
		for r in rows:
			for ci in cols_n - 1:
				var q: Array = [grid[r][ci], grid[r][ci + 1], grid[r + 1][ci + 1], grid[r + 1][ci]]
				for idx in [0, 1, 2, 0, 2, 3]:
					st.set_color(q[idx][1])
					st.add_vertex(q[idx][0])
		sheet.mesh = st.commit()
		return true, {"nodes": [sheet]})
	scene.shake = 3.0
	await wait(50)

func r_clamp(a: String, t: String, _ar: Variant) -> void:
	await r_bite(a, t, null)

func r_thundershock(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	await lightning(c.x - 10, c.y - 30, c.x, c.y, 14, ELEC[1])
	emit(t, 10, {"life": 14, "shape": "spark", "cols": ELEC, "jx": 2.0, "jy": 2.0})
	await wait(6)

func r_thunderbolt(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	for i in 3:
		scene.flash = 0.4
		scene.flash_color = Color("#fff8c0")
		await lightning(c.x + rand(-30, 30), c.y - 40, c.x, c.y, 8, ELEC[1])
	emit(t, 16, {"life": 18, "shape": "spark", "cols": ELEC, "jx": 3.0, "jy": 3.0})
	await wait(10)

func r_thunder(_a: String, t: String, _ar: Variant) -> void:
	var c := center(t)
	await darken(12, "#000010", 0.5)
	scene.flash = 1.0
	scene.flash_color = WHITE
	await lightning(c.x, 0, c.x, c.y + 10, 24, "#f8f090")
	scene.shake = 6.0
	emit(t, 20, {"life": 20, "shape": "spark", "cols": ELEC, "jx": 3.0, "jy": 3.0})
	await wait(10)

func r_thunderwave(_a: String, t: String, _ar: Variant) -> void:
	for i in 3:
		await ring(t, 8, ELEC[1], 2, 22)
	emit(t, 8, {"life": 12, "shape": "spark", "cols": ELEC})
	await wait(8)

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
				nodes[i].global_transform = Transform3D(_face_basis(PI * 0.5).scaled(Vector3(w, w, w)), pos)
			return true, {"nodes": nodes})
		await wait(6)
	await impact(t)

func r_razorleaf(a: String, t: String, _ar: Variant) -> void:
	await projectile(a, t, 20, "leaf", [Color("#98e058"), Color("#58b040")], {"count": 10, "gap": 2, "spread": 14.0, "arc": 18.0, "spin": 0.45, "size": 3.0})
	await slash(t, 2, "#c8f0a0")
	await impact(t)

func r_solarbeam(a: String, t: String, _ar: Variant) -> void:
	await beam(a, t, 34, ["#fff8c0", "#f8f070", "#a8e060"], 9.0, {"sparks": "star"})
	scene.shake = 4.0
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
	for i in 30:
		particle({"x": c.x + rand(-18, 18), "y": c.y - 34 + rand(-6, 6), "vy": rand(0.6, 1.2), "vx": rand(-0.3, 0.3),
			"delay": int(floor(rand(0, 18))), "life": 30, "shape": "dot", "size": 2.0, "glow": 0.15, "cols": [cc, cc.lightened(0.3)]})
	await wait(40)

func r_petaldance(_a: String, t: String, _ar: Variant) -> void:
	await vortex(t, 36, ["#ffb0d0", "#f880b0", "#ffe0f0"], "leaf")
	await impact(t)

func r_icebeam(a: String, t: String, _ar: Variant) -> void:
	await beam(a, t, 28, ICE, 5.0, {"sparks": "snow"})
	emit(t, 10, {"life": 26, "shape": "shard", "cols": ICE, "jx": 1.0, "jy": 1.0})
	await wait(12)

func r_blizzard(_a: String, t: String, _ar: Variant) -> void:
	add_fx(func(f: Dictionary) -> bool:
		if int(f["age"]) > 70:
			scene.darken = 0.0
			return false
		scene.darken_color = Color("#e8f0ff")
		scene.darken = sin(int(f["age"]) / 70.0 * PI) * 0.35
		return true)
	await screen_rain(160, 56, {"shape": "snow", "size": 2.0, "vx": -4.0, "vy": 2.6, "cols": [WHITE, Color("#c8f0ff")], "life": 60})
	emit(t, 16, {"life": 34, "shape": "shard", "cols": ICE, "rx": 18.0, "ry": 14.0})
	scene.shake = 4.0
	await wait(14)

func r_aurorabeam(a: String, t: String, _ar: Variant) -> void:
	await beam(a, t, 30, ["#ff8080", "#f8d860", "#80f080", "#80c0ff", "#c080ff"], 5.0, {"rainbow": true})
	await wait(4)

func r_mist(a: String, t: String, col: Variant) -> void:
	var cc: String = str(col) if col != null else "#e8f0ff"
	emit(t if t != "" else a, 24, {"life": 40, "shape": "dot", "size": 5.0, "grow": 1.0, "rx": 26.0, "ry": 16.0, "vx": 0.3, "cols": [cc, Color(cc).darkened(0.1)], "spreadT": 10})
	await wait(46)

func r_psychic(_a: String, t: String, _ar: Variant) -> void:
	await ring(t, 10, "#f070c0", 4, 30, 2)
	await wave(5, 40)
	await tint(t, "#f890d0", 14)

func r_confusion(_a: String, t: String, _ar: Variant) -> void:
	await tint(t, "#f070c0", 10)
	await wave(3, 26)

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
		node.global_transform = Transform3D(_face_basis(PI / 4).scaled(Vector3(w, w, w)), pos)
		m.albedo_color = Color(cc, al * 0.6)
		edge.global_transform = Transform3D(_face_basis(0).scaled(Vector3(w * 1.4, w * 1.4, w * 1.4)), pos)
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

## Shock rings roll out across the real ground under the target, rocks jump up.
func r_earthquake(_a: String, t: String, _ar: Variant) -> void:
	var tgt: Vector3 = scene.ground_world(t)
	var rings: Array = []
	for k in 3:
		rings.append(_mesh_node("ring", Color("#fff0c8"), 0.6))
	add_fx(func(f: Dictionary) -> bool:
		var age: int = f["age"]
		if age > 44:
			return false
		for k in 3:
			var r := fmod(age * 3.0 + k * 20.0, 60.0) * 2.2
			var pos := tgt + Vector3(0, 0.03, 0)
			var w := px_world(pos) * r * 2.0
			rings[k].global_transform = Transform3D(Basis().scaled(Vector3(w, w * 0.4, w)), pos)
			(rings[k].material_override as StandardMaterial3D).albedo_color = Color("#fff0c8", 0.6 * (1.0 - r / 132.0))
		return true, {"nodes": rings})
	for i in 4:
		scene.shake = 9.0
		for k in 10:
			particle({"x": rand(0, 320), "y": rand(80, 128), "vy": rand(-3.5, -1), "vx": rand(-0.5, 0.5), "ay": 0.25, "life": 22, "shape": "rock", "size": rand(2, 3.5), "cols": ["#b09070"]})
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
		tongue.global_transform = Transform3D(_face_basis(PI).scaled(Vector3(w, w * 2.0, w)), pos)
		return true, {"nodes": [tongue]})
	await wait(16)
	await impact(t)

func r_nightshade(_a: String, t: String, _ar: Variant) -> void:
	await darken(30, "#100020", 0.7)
	await tint(t, "#402060", 16)

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
	await lunge(a, 16)
	await slash(t, 2, "#e0e8ff")

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
				arc_nodes[k].global_transform = Transform3D(Basis().scaled(Vector3(w, w, w)), pos)
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
		particle({"life": 30, "shape": "needle", "size": 2.0, "cols": ["#e0e8f8"], "glow": 0.2, "on_update": func(p: Dictionary) -> void:
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
	for i in 40:
		var an := rand(0, TAU)
		var v := rand(1, 5)
		particle({"x": c.x, "y": c.y, "vx": cos(an) * v, "vy": sin(an) * v, "drag": 0.92, "life": 30, "shape": "flame", "size": 3.0, "cols": FIRE})
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
	await projectile(a, t, 16, "star", [Color("#fff8a0"), Color("#f8d048")], {"count": 5, "gap": 3, "spread": 12.0, "arc": 10.0, "size": 3.0})
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
			threads[k].global_transform = Transform3D(_face_basis(ang).scaled(Vector3(36 * w, 0.8 * w, 0.8 * w)), pos)
		return true, {"nodes": threads})
	await wait(30)

func r_metronome(a: String, _t: String, _ar: Variant) -> void:
	var c := center(a)
	var hand := _mesh_node("needle", WHITE)
	for i in 24:
		var an := sin(i * 0.5) * 0.8 - PI / 2
		var pos := to3d(Vector2(c.x + cos(an) * 5, c.y - 10 + sin(an) * 5), 0.5)
		var w := px_world(pos) * 10.0
		hand.global_transform = Transform3D(_face_basis(an).scaled(Vector3(w, w, w)), pos)
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
	await lunge(a, 24)
	await impact(t, "#f86040", true)

func r_focus(a: String, _t: String, _ar: Variant) -> void:
	emit(a, 16, {"life": 20, "shape": "dot", "size": 1.0, "vy": -3.0, "cols": ["#fff0a0", "#f8a040"], "spreadT": 12, "ry": 4.0})
	await tint(a, "#f8c060", 20)

func r_fly(a: String, t: String, _ar: Variant) -> void:
	await lunge(a, 30)
	await impact(t, "", true)

func r_skyattack(a: String, t: String, _ar: Variant) -> void:
	await tint(a, "#ffffff", 10)
	await lunge(a, 34)
	await impact(t, "#fff0a0", true)
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
