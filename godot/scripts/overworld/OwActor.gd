class_name OwActor
extends Node3D
## One overworld character in 3D: the player, an NPC from a map's `objs`, or the walking partner Pokémon.
## Grid-locked like upstream's Actor (src/game/overworld.js): one cell per step, 16 frames per cell at walking
## speed, 2-cell hops over ledges, facing in four directions.

signal step_finished(actor: OwActor)

const FRAME := 1.0 / 60.0
const FOOT_Z := 0.8          # where in its cell (0..1, north->south) a character's feet stand: the 2D sprites
                             # stand on the bottom of their cell
const DIRS := {"down": Vector2i(0, 1), "up": Vector2i(0, -1), "left": Vector2i(-1, 0), "right": Vector2i(1, 0)}
const YAW := {"down": 0.0, "up": PI, "left": -PI / 2.0, "right": PI / 2.0}   # models face +Z (Blender -Y)
const CHAR_PX := 20.0        # height of a character sprite in the 2D game (px)
const LEAN_DEG := -30.0   # negative: top away from the camera, so the face turns up toward it

# --- continuous motion tuning (see start_move / _process) -------------------------------------------------
const TURN_RATE := 22.0        # 1/s: exponential pull of the model's yaw toward its facing
const TURN_MAX := 18.85        # rad/s cap on the turn speed (6 pi: a quarter turn in ~0.08 s)
const CHAIN_GRACE := 0.06      # s: a step started this soon after the last one continues its gait and speed
const IDLE_GRACE := 0.05       # s the walk clip is held after the last step before fading to Idle
const EASE_IN_T := 0.30        # first step of a walk: speed ramps up from EASE_IN_V0 x cruise over this many steps' time
const EASE_IN_V0 := 0.35
const EASE_OUT_T := 0.45       # when the walk ends the speed ramps down to EASE_OUT_V1 x cruise over this much
const EASE_OUT_V1 := 0.10
const BLEND_WALK := 0.14       # s crossfade Idle -> Walk / Run
const BLEND_IDLE := 0.22       # s crossfade Walk / Run -> Idle
const HOP_PX := 12.0           # ledge hop apex in px of 2D art

var cell := Vector2i.ZERO
var facing := "down"
var moving := false
var sprite := ""
var obj: Dictionary = {}     # the map object this actor was spawned from (NPCs)
var home := Vector2i.ZERO
var idle_t := 0.0
var scripted := false        # a script is driving it: no idle wandering
var is_mon := false
var is_object := false

var velocity := Vector3.ZERO      # world units / s over the last frame (the camera leads with it)
var speed_cells := 0.0            # ground speed in cells / s of the current step
var gait := 0.0                   # accumulated gait cycles: the walk clip's phase follows the distance walked
var fx: OwFx = null               # set by the overworld: footstep dust, landing puffs, ripples...
var fx_kind := "dust"             # what walking kicks up here: "dust" | "grass" | "sand" | "" (none)

var _model: Node3D
var _lean: Node3D
var _body: Node3D                 # bob / squash / roll pivot at the feet, between _lean and _model
var _anim: AnimationPlayer
var _shadow: MeshInstance3D
var _move_from := Vector3.ZERO
var _move_to := Vector3.ZERO
var _move_t := 0.0
var _move_dur := 0.2667
var _step_len := 1.0              # cells covered by the current step
var _jump := false
var _hop_k := 0.0
var _land_t := 99.0
var _since_end := 1e9             # s since the last step ended (chaining)
var stop_hint := true             # the owner is not asking for another step: slow down into the stop
var _base_dur := 0.2667           # nominal seconds of the step (its cruise speed is _step_len / _base_dur)
var _ein_T := 0.0                 # seconds of the speed ramp-up at the start of this step (0 when chained)
var _dec := false                 # decelerating into a stop
var _dec_t := 0.0
var _dec_p0 := 0.0
var _dec_v0 := 0.0
var _dec_u := 0.1
var _dec_v1 := 0.0
var _p_cells := 0.0               # cells covered so far in this step
var _yaw := 0.0
var _yaw_target := 0.0
var _clip := ""
var _clip_len := 0.8
var _gait_cells := 2.0
var _amp := 0.0                   # 0..1 how strongly the walk is playing (fades in / out)
var _breath := 0.0
var _foot := 0
var _ripple_t := 0.0
var _gesture := ""                # a gesture clip (Nod, Think, Laugh ...) currently playing
var _gesture_left := 0.0
var gesture_wait := -1.0          # s until this idle NPC picks its next gesture (set by the overworld)
var _proc_bob := false            # no Walk clip: bob and sway procedurally instead

func _init() -> void:
	# actors update before the overworld controller, so a step that ends this frame can be followed by the next
	# one in the same frame (no idle frame between chained steps) and the camera reads this frame's position
	process_priority = -10

static func cell_pos(c: Vector2i) -> Vector3:
	return Vector3(c.x + 0.5, 0.0, c.y + FOOT_Z)

const OBJECT_SPRITES := ["poke_ball", "boulder", "pokedex", "clipboard", "paper", "fossil", "old_amber"]
## Every ground object has a 3D model (pipeline/blender/gen_world.py, gen_objprops.py); the atlas cards are a fallback.
const OBJECT_MESHES := {
	"poke_ball": "res://assets/models/world/pokeball.glb", "boulder": "res://assets/models/world/boulder.glb",
	"pokedex": "res://assets/models/world/pokedex.glb", "clipboard": "res://assets/models/world/clipboard.glb",
	"paper": "res://assets/models/world/paper.glb", "fossil": "res://assets/models/world/fossil.glb",
	"old_amber": "res://assets/models/world/old_amber.glb",
}
const CREATURE_DEFAULT := {"bird": "PIDGEY", "fairy": "CLEFAIRY", "seel": "SEEL", "snorlax": "SNORLAX", "monster": "NIDORAN_M"}

## upstream objsprites.js speciesFromLabel: the longest species name found in a text label
static func species_from_label(label: String) -> String:
	var up := label.to_upper()
	var best := ""
	for sp in GameData.species.keys():
		var k := String(sp).replace("_", "")
		if up.contains(k) and k.length() > best.replace("_", "").length():
			best = sp
	return best

## sprite: cast key for people, or "mon:SPECIES" for a Pokémon (follower). `o` is the map object (NPCs): its
## cast entry decides between a person, a Pokémon (creature objects, like upstream's objSprites) or an item
## (a 3D Poké Ball / boulder, or a small standing sprite).
func setup(sprite_key: String, px_height: float = CHAR_PX, o: Dictionary = {}) -> void:
	sprite = sprite_key
	for c in get_children():
		c.queue_free()
	_anim = null
	_gesture = ""            # a re-skinned actor has no gesture playing on its new model
	_gesture_left = 0.0
	gesture_wait = -1.0
	_body = null
	_lean = null
	_mount = null
	var def: Dictionary = GameData.cast.get(sprite_key, {})
	if def.has("creature"):
		var sp := String(o.get("species", GameData.species_override.get(String(o.get("id", "")), "")))
		if sp == "":
			sp = species_from_label(String(o.get("textLabel", "")))
		if sp == "":
			sp = String(CREATURE_DEFAULT.get(String(def.creature), "PIKACHU"))
		sprite_key = "mon:" + sp
		px_height = 26.0 if (def.creature == "snorlax" or sp == "SNORLAX") else 18.0
	if def.has("object"):
		_setup_object(sprite_key)
		return
	if sprite_key.begins_with("mon:"):
		is_mon = true
		_model = _load_mon(sprite_key.substr(4), px_height)
	else:
		_model = CharacterSkin.instantiate(sprite_key)
		if _model == null or _meshes(_model).is_empty():
			_model = _fallback()
		_fit_height(_model, px_height)
	# characters lean back toward the camera a little, so the steep game camera sees their faces the way
	# the 2D sprites show them
	_lean = Node3D.new()
	_lean.name = "Lean"
	_lean.rotation.x = deg_to_rad(LEAN_DEG)
	add_child(_lean)
	_body = Node3D.new()
	_body.name = "Body"
	_lean.add_child(_body)
	_body.add_child(_model)
	_anim = _find_anim(_model)
	AnimUtil.fix_looping(_anim)
	_proc_bob = _anim == null or not _anim.has_animation("Walk")
	_play("Idle")
	_shadow = _make_shadow(0.36 if not is_mon else 0.3)
	add_child(_shadow)
	face(facing, true)

## Items on the map: 3D Poké Ball, boulder, Pokédex, clipboard, paper, fossil and Old Amber (pipeline/blender).
func _setup_object(key: String) -> void:
	is_object = true
	var mesh_path: String = OBJECT_MESHES.get(key, "")
	_model = Node3D.new()
	_model.name = "Object"
	add_child(_model)
	if mesh_path != "" and ResourceLoader.exists(mesh_path):
		var ps: PackedScene = load(mesh_path)
		var inst := ps.instantiate()
		var mi := TileKit._find_mesh(inst)
		if mi:
			var m := MeshInstance3D.new()
			m.mesh = mi.mesh
			m.material_override = TileKit.prop_material()
			m.scale = Vector3(1.0, WorldData.K, 1.0)
			m.position = Vector3(0.0, 0.0, 0.8 - FOOT_Z)
			_model.add_child(m)
		inst.free()
	else:
		var idx := OBJECT_SPRITES.find(key)
		var q := QuadMesh.new()
		q.size = Vector2(1.0, WorldData.K)
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_texture = load("res://assets/maps/objects_atlas.png")
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		mat.uv1_scale = Vector3(1.0 / OBJECT_SPRITES.size(), 1.0, 1.0)
		mat.uv1_offset = Vector3(float(maxi(idx, 0)) / OBJECT_SPRITES.size(), 0.0, 0.0)
		q.material = mat
		var m2 := MeshInstance3D.new()
		m2.mesh = q
		m2.position = Vector3(0.0, WorldData.K * 0.5, 1.0 - FOOT_Z)
		_model.add_child(m2)
	face(facing)

## Raise a ground object (ball, Pokedex ...) onto the surface of the furniture it stands on.
func lift_object(y: float) -> void:
	if _model:
		_model.position.y = y

func _load_mon(species: String, px_height: float) -> Node3D:
	# the battle agent's PokemonActor: cel-shaded species model with Idle/Walk clips
	var m := PokemonActor.new()
	m.setup(species)
	_fit_height(m, px_height)
	return m

## Scale a model so its bounding box is `px` pixels of 2D art tall (the game camera's vertical scale).
func _fit_height(m: Node3D, px: float) -> void:
	var aabb := _model_aabb(m)
	var h := aabb.size.y
	if h <= 0.001:
		return
	# the model leans back by LEAN_DEG, so its projected height grows: size it so that on screen it is `px`
	# pixels of 2D art tall (a ground cell of 16 px shows as sin(pitch) cells)
	var pitch := deg_to_rad(WorldData.CAM_PITCH_DEG)
	var target := px / 16.0 * WorldData.CELL * sin(pitch) / cos(pitch - absf(deg_to_rad(LEAN_DEG)))
	var s := target / h
	var holder := m
	holder.scale = Vector3(s, s, s)
	holder.position.y = -aabb.position.y * s

static func _model_aabb(n: Node) -> AABB:
	var out := AABB()
	var first := true
	for mi in _meshes(n):
		var m: MeshInstance3D = mi
		if m.mesh == null:
			continue
		var a: AABB = _rel_xform(m, n) * m.mesh.get_aabb()
		if first:
			out = a
			first = false
		else:
			out = out.merge(a)
	return out

static func _rel_xform(node: Node3D, root: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	var cur: Node = node
	while cur != null and cur != root:
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t

static func _meshes(n: Node) -> Array:
	var out: Array = []
	if n is MeshInstance3D:
		out.append(n)
	for c in n.get_children():
		out.append_array(_meshes(c))
	return out

func _fallback() -> Node3D:
	var root := Node3D.new()
	var body := MeshInstance3D.new()
	var cap := CapsuleMesh.new()
	cap.radius = 0.3
	cap.height = 1.4
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(GameData.cast.get(sprite, {}).get("shirt", "#c8a0d8"))
	cap.material = mat
	body.mesh = cap
	body.position.y = 0.7
	root.add_child(body)
	return root

func _make_shadow(r: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(r * 2.0, r * 0.9)
	q.orientation = PlaneMesh.FACE_Y
	var mat := ShaderMaterial.new()
	mat.shader = preload("res://scripts/overworld/shaders/blob_shadow.gdshader")
	q.material = mat
	mi.mesh = q
	mi.position = Vector3(0.05, 0.01, 0.0)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

static func _find_anim(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var f := _find_anim(c)
		if f:
			return f
	return null


## Plays one of a character's gesture clips (CharacterSkin.GESTURES, plus Talk / Wave / Cheer) for `secs` seconds
## (0 = once through), then returns to Idle.  Walking cancels it.  False if this actor has no such clip.
func gesture(clip: String, secs: float = 0.0) -> bool:
	if _anim == null or is_mon or is_object or moving or not _anim.has_animation(clip):
		return false
	_gesture = clip
	_gesture_left = secs if secs > 0.0 else _anim.get_animation(clip).length
	_anim.speed_scale = 1.0
	_anim.play(clip, 0.18)
	return true

func stop_gesture() -> void:
	if _gesture != "":
		_gesture = ""
		if _anim and _anim.has_animation("Idle"):
			_anim.play("Idle", BLEND_IDLE)

func is_gesturing() -> bool:
	return _gesture != ""

## The gestures an idle NPC of this look picks from (upstream has none of this: static sprites).
static func gesture_pool(sprite_key: String, o: Dictionary) -> Array:
	var k := sprite_key.to_lower()
	if k.contains("asleep"):
		return ["Sleep"]
	if k == "nurse":
		return ["Bow", "Nod", "Stretch"]
	for kid in ["youngster", "lass", "little", "boy", "girl", "kid"]:
		if k.contains(kid):
			return ["Dance", "Stretch", "Nod", "Laugh", "Point"]
	for old in ["old", "gramps", "granny", "fuji", "oak", "guru", "man_"]:
		if k.contains(old):
			return ["Stretch", "Think", "Nod", "Shake"]
	for sci in ["scientist", "gentleman", "nerd", "professor", "bill", "erika", "sabrina", "agatha"]:
		if k.contains(sci):
			return ["Think", "Nod", "Point", "Shake"]
	for cop in ["guard", "police", "officer", "sailor", "biker", "cool", "black", "lance", "koga", "bruno"]:
		if k.contains(cop):
			return ["Salute", "Stretch", "Nod", "Point"]
	if k.contains("rocket") or k.contains("giovanni"):
		return ["Laugh", "Point", "Shake", "Stretch"]
	if o.has("trainer"):
		return ["Stretch", "Point", "Shake", "Nod"]
	return ["Stretch", "Think", "Nod", "Shake"]

func _play(n: String) -> void:
	if _anim and _anim.has_animation(n) and _anim.current_animation != n:
		_anim.play(n)

var _mount: Node3D = null

## Ride something under the character (surfing: the lead Pokémon); "" = none.
func set_mount(key: String) -> void:
	if _mount:
		_mount.queue_free()
		_mount = null
	if _lean:
		_lean.position.y = 0.0
	if key == "" or not key.begins_with("mon:"):
		return
	_mount = Node3D.new()
	_mount.name = "Mount"
	var m := _load_mon(key.substr(4), 18.0)
	_mount.add_child(m)
	m.rotation.y = _yaw
	add_child(_mount)
	if _lean:
		_lean.position.y = WorldData.px_h(7.0)
	if fx and is_inside_tree():
		fx.splash(global_position, 5, 0.8)

func place(c: Vector2i, dir: String = "") -> void:
	cell = c
	moving = false
	_jump = false
	_hop_k = 0.0
	_since_end = 1e9
	speed_cells = 0.0
	velocity = Vector3.ZERO
	_amp = 0.0
	position = cell_pos(c)
	if dir != "":
		face(dir, true)
	_clip = ""
	_gesture = ""   # placed = teleported: whatever it was gesturing is over (an Idle pose is playing now)
	if _anim and _anim.has_animation("Idle"):
		_anim.speed_scale = 1.0
		_anim.play("Idle", 0.0)
	_update_body(0.0)

## Turn to a direction. The logical facing changes at once; the model swings round by the shortest arc.
func face(dir: String, snap: bool = false) -> void:
	if not YAW.has(dir):
		return
	facing = dir
	_yaw_target = YAW[dir]
	if snap or _model == null or not is_inside_tree():
		_yaw = _yaw_target
	_apply_yaw()

func _apply_yaw() -> void:
	if _model and not is_object:
		_model.rotation.y = _yaw
	if _mount and _mount.get_child_count() > 0:
		(_mount.get_child(0) as Node3D).rotation.y = _yaw

func facing_cell() -> Vector2i:
	return cell + DIRS.get(facing, Vector2i.ZERO)

## Start a one-cell step (or a two-cell ledge hop). speed: 1 walk, 2 run, 3 bike (upstream px per frame).
## `more`: another step is going to follow at once (a held d-pad, a scripted path), so the step does not slow
## down at its end; the owner can flip `stop_hint` while the step runs (d-pad released) and the actor then
## eases into the stop from whatever speed it has. A step that begins right after another one continues its
## speed and gait without a stop, and the time that passed since the last step ended is spent moving, so a
## held d-pad walks at an even pace. The walk-off after a standing start is a little slower to get going.
func start_move(dir: String, speed: float = 1.0, jump: bool = false, more: bool = false) -> void:
	face(dir)
	var dist := 2 if jump else 1
	var target: Vector2i = cell + DIRS[dir] * dist
	var chained := _since_end < CHAIN_GRACE
	_move_from = position
	_move_to = cell_pos(target)
	cell = target
	_step_len = float(dist)
	_base_dur = (16.0 * dist) / maxf(speed, 0.5) * FRAME
	_move_dur = _base_dur
	_jump = jump
	moving = true
	_hop_k = 0.0
	stop_hint = not more
	_dec = false
	_ein_T = 0.0 if (chained or jump) else EASE_IN_T * (16.0 * FRAME / maxf(speed, 0.5))
	_move_t = minf(_since_end, _base_dur * 0.5) if chained else 0.0
	_p_cells = _prog(_move_t)
	position = _move_from.lerp(_move_to, clampf(_p_cells / _step_len, 0.0, 1.0))
	_pick_clip(speed, jump)
	if not jump and fx and is_inside_tree() and _dust_ok() and not chained:
		fx.dust(global_position, 1, 0.6)

## Cells covered t seconds into the step while not decelerating: speed ramps from EASE_IN_V0 x cruise up to
## cruise over _ein_T (smoothstep), then holds.
func _prog(t: float) -> float:
	var vc := _step_len / _base_dur
	if _jump or _ein_T <= 0.0:
		return vc * t
	if t >= _ein_T:
		return vc * ((1.0 + EASE_IN_V0) * _ein_T * 0.5 + (t - _ein_T))
	var x := t / _ein_T
	return vc * (EASE_IN_V0 * t + (1.0 - EASE_IN_V0) * _ein_T * (x * x * x - 0.5 * x * x * x * x))

func _speed_at(t: float) -> float:
	var vc := _step_len / _base_dur
	if _jump or _ein_T <= 0.0 or t >= _ein_T:
		return vc
	var x := t / _ein_T
	return vc * lerpf(EASE_IN_V0, 1.0, x * x * (3.0 - 2.0 * x))

## Begin slowing into the stop once the remaining distance is what a standard-length ramp-down would cover
## (or right away if the release came later than that: a shorter, firmer stop). Speed is continuous throughout.
func _maybe_start_decel() -> void:
	if _dec or _jump or not stop_hint:
		return
	var vc := _step_len / _base_dur
	var v := _speed_at(_move_t)
	var v1 := EASE_OUT_V1 * vc
	var rem := _step_len - _p_cells
	var std_dist := EASE_OUT_T * _base_dur * (v + v1) * 0.5
	if rem > std_dist:
		return
	_dec = true
	_dec_t = _move_t
	_dec_p0 = _p_cells
	_dec_v0 = v
	_dec_u = maxf(2.0 * rem / (v + v1), 0.001)
	_dec_v1 = v1

## Which clip plays for this step and how many cells one gait cycle spans (a stride per cell for a person,
## a hop-trot per cell for a Pokémon; running and biking stretch the cycle so the legs keep up).
func _pick_clip(speed: float, jump: bool) -> void:
	_clip = ""
	if _anim == null or jump:
		return
	var run := speed >= 1.5
	if run and _anim.has_animation("Run") and speed < 2.5:
		_clip = "Run"
	elif _anim.has_animation("Walk"):
		_clip = "Walk"
	if _clip == "":
		return
	_clip_len = maxf(0.05, _anim.get_animation(_clip).length)
	# Walk clips are 16 frames: people = one full two-step gait per cell (0.267 s), Pokémon = one cycle per two cells (0.533 s)
	var base := 2.0 if is_mon else 1.0
	_gait_cells = base if speed < 1.5 else (base * 1.5 if speed < 2.5 else base * 3.0)

func _dust_ok() -> bool:
	return fx_kind != "" and not is_object

func _process(dt: float) -> void:
	if dt <= 0.0:
		return
	_since_end += dt
	var prev_pos := position
	if moving:
		_move_t += dt
		var p_old := _p_cells
		var over := -1.0
		if _jump:
			_p_cells = _step_len * clampf(_move_t / _base_dur, 0.0, 1.0)
			_hop_k = clampf(_move_t / _base_dur, 0.0, 1.0)
			if _move_t >= _base_dur:
				over = _move_t - _base_dur
		else:
			if not _dec:
				_p_cells = _prog(_move_t)
			_maybe_start_decel()
			if _dec:
				var ds := _move_t - _dec_t
				var x := clampf(ds / _dec_u, 0.0, 1.0)
				# speed glides from where it was down to a crawl: v0 + (v1 - v0) * smoothstep(t)
				_p_cells = _dec_p0 + _dec_v0 * minf(ds, _dec_u) + (_dec_v1 - _dec_v0) * _dec_u * (x * x * x - 0.5 * x * x * x * x)
				if ds >= _dec_u:
					_p_cells = _step_len
					over = ds - _dec_u
			else:
				if _p_cells >= _step_len:
					over = (_p_cells - _step_len) / (_step_len / _base_dur)
		position = _move_from.lerp(_move_to, clampf(_p_cells / _step_len, 0.0, 1.0))
		speed_cells = (_p_cells - p_old) / dt if over < 0.0 else (_step_len - p_old) / dt
		if over >= 0.0:
			moving = false
			var was_jump := _jump
			_jump = false
			_hop_k = 0.0
			_dec = false
			position = _move_to
			_since_end = over
			if was_jump:
				_land_t = 0.0
				if fx:
					fx.land(global_position)
			step_finished.emit(self)
	else:
		speed_cells = 0.0
	velocity = (position - prev_pos) / dt
	_update_facing(dt)
	_update_gait(dt)
	_update_body(dt)

func _update_facing(dt: float) -> void:
	var d := angle_difference(_yaw, _yaw_target)
	if absf(d) < 0.002:
		if _yaw != _yaw_target:
			_yaw = _yaw_target
			_apply_yaw()
		return
	var step := d * (1.0 - exp(-TURN_RATE * dt))
	step = clampf(step, -TURN_MAX * dt, TURN_MAX * dt)
	_yaw += step
	_apply_yaw()

func _update_gait(dt: float) -> void:
	if _gesture != "":
		if moving:
			_gesture = ""
		else:
			_gesture_left -= dt
			if _gesture_left <= 0.0:
				stop_gesture()
	var v := speed_cells if moving else 0.0
	if moving and _clip != "":
		gait += v * dt / _gait_cells
	elif moving:
		gait += v * dt / (1.0 if is_mon else 2.0)
	_amp = move_toward(_amp, 1.0 if moving and not _jump else 0.0, dt * 7.0)
	if _anim:
		var walking := (moving or (_since_end < IDLE_GRACE and _gesture == "")) and _clip != ""
		if walking:
			if _anim.current_animation != _clip:
				_anim.play(_clip, BLEND_WALK)
			# the clip runs as fast as the feet travel: one cycle per _gait_cells of ground, whatever its length
			_anim.speed_scale = maxf(0.0, _clip_len * v / _gait_cells)
		elif _gesture == "":
			if _anim.has_animation("Idle") and _anim.current_animation != "Idle":
				_anim.play("Idle", BLEND_IDLE)
			_anim.speed_scale = 1.0
	# a puff of dust on every foot-fall while running or biking, a faint one when walking
	if moving and not _jump and fx and _dust_ok():
		var f := int(floor(gait * 2.0))
		if f != _foot:
			_foot = f
			var run := v > 5.0
			fx.dust(global_position, 1, 1.2 if run else 0.4)

## Bob, squash and stretch, hop arc, landing squash, idle breathing and the surf rocking; all continuous.
func _update_body(dt: float) -> void:
	_breath += dt
	var y := 0.0
	var sx := 1.0
	var sy := 1.0
	var roll := 0.0
	var lift := 0.0
	if _hop_k > 0.0 or _jump:
		var k := clampf(_hop_k, 0.0, 1.0)
		lift = 4.0 * k * (1.0 - k)
		y = lift * WorldData.px_h(HOP_PX)
		var crouch := clampf(1.0 - k / 0.16, 0.0, 1.0)      # coil before the jump
		sy = 1.0 - 0.16 * crouch + 0.10 * sin(clampf(k, 0.0, 1.0) * PI)
		sx = 1.0 / sqrt(sy)
	if _land_t < 1.0:
		_land_t += dt
		var s := exp(-_land_t * 15.0) * cos(_land_t * 32.0)   # squash on landing, a little rebound
		sy *= 1.0 - 0.22 * s
		sx *= 1.0 + 0.13 * s
	if _amp > 0.001:
		if _proc_bob or is_mon:
			var amp_px := 1.0 if is_mon else 0.9
			y += WorldData.px_h(amp_px) * absf(sin(TAU * gait)) * _amp
		if _proc_bob:
			roll += sin(TAU * gait) * deg_to_rad(2.2) * _amp
			sy *= 1.0 + 0.03 * absf(cos(TAU * gait)) * _amp
	if is_mon and _amp < 0.999:
		# slow breathing when standing about
		var b := 0.5 + 0.5 * sin(_breath * TAU / 1.6)
		y += WorldData.px_h(0.5) * b * (1.0 - _amp)
		sy *= 1.0 + 0.012 * b * (1.0 - _amp)
	if _body:
		_body.position.y = y
		_body.scale = Vector3(sx, sy, sx)
		_body.rotation.z = roll
	if _shadow:
		var sh := 1.0 - 0.4 * lift
		_shadow.scale = Vector3(sh, 1.0, sh)
	if _mount:
		var rock := sin(_breath * TAU / 1.7)
		var mb := WorldData.px_h(0.9) * rock
		_mount.position.y = mb
		_mount.rotation.z = sin(_breath * TAU / 2.3) * 0.035
		if _lean:
			_lean.position.y = WorldData.px_h(7.0) + mb
		_ripple_t -= dt
		if _ripple_t <= 0.0 and fx and is_inside_tree():
			_ripple_t = 0.16 if moving else 1.3
			fx.ripple(global_position + Vector3(0, 0, 0.05), 0.95 if moving else 0.7, 0.9, 0.5 if moving else 0.3)
