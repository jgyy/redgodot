class_name PxView3D
extends SubViewport
## A tiny transparent 3D render target that sits inside a Px layout exactly
## where upstream blits a sprite: add it as a child of a PxCanvas, then in the
## canvas's _draw() call `view.draw_at(self, x, y)` (logical 320x180 coords).
## It renders at `k` x the logical size (the canvas's 3x scale) so the model is
## crisp at 960x540, framed by an orthographic camera fitted to the model's
## bounds and anchored like upstream's sprites (bottom-centre or centre).
##
##   var v := PxView3D.new(64, 64); add_child(v); v.show_mon("CHARIZARD")
##   func _draw(): v.draw_at(self, 50, 34)

const K := 3

var logical := Vector2i(64, 64)
## "center" = model centred in the box; "bottom" = feet on the bottom edge.
var anchor := "center"
## Model yaw in degrees; negative turns the model to face screen-left like
## upstream's front sprites.
var yaw := -28.0
## Camera elevation in degrees (looking down on the model).
var pitch := 8.0
## Fraction of the box the model may fill.
var fill := 0.92
var spin := 0.0

var model: Node3D
var _pivot: Node3D
var _cam: Camera3D
var _anim: AnimationPlayer
var _key := ""

func _init(w: int = 64, h: int = 64) -> void:
	logical = Vector2i(w, h)
	size = logical * K
	transparent_bg = true
	own_world_3d = true
	render_target_update_mode = SubViewport.UPDATE_ALWAYS
	msaa_3d = Viewport.MSAA_4X
	world_3d = World3D.new()

	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.78, 0.8, 0.9)
	env.ambient_light_energy = 0.85
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-38, -35, 0)
	key.light_energy = 1.05
	add_child(key)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-20, 150, 0)
	rim.light_energy = 0.35
	add_child(rim)

	_cam = Camera3D.new()
	_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	_cam.keep_aspect = Camera3D.KEEP_HEIGHT
	_cam.near = 0.05
	_cam.far = 100.0
	_cam.current = true
	add_child(_cam)

	_pivot = Node3D.new()
	add_child(_pivot)

func set_logical_size(w: int, h: int) -> void:
	logical = Vector2i(w, h)
	size = logical * K
	_frame()

## Shows a Pokémon's generated model (godot/assets/models/pokemon/<SPECIES>.glb).
func show_mon(species: String) -> void:
	if _key == "mon:" + species:
		return
	_key = "mon:" + species
	var actor := PokemonActor.new()
	_set_model(actor)
	actor.setup(species)
	_anim = actor._anim
	_frame()

## Shows a character (cast.json key, e.g. "red", "oak", "blue").
func show_character(cast_key: String) -> void:
	if _key == "chr:" + cast_key:
		return
	_key = "chr:" + cast_key
	_set_model(CharacterModel.build(cast_key))
	_anim = CharacterModel.find_anim(model)
	if _anim:
		AnimUtil.fix_looping(_anim)
		if _anim.has_animation("Idle"):
			_anim.play("Idle")
	_frame()

## Shows the player's customised model (character creator, trainer card).
func show_look(look: PlayerLook) -> void:
	_key = "look:" + JSON.stringify(look.to_dict())
	var m := PlayerModel.build(look)
	if m == null:
		show_character("red")
		return
	_set_model(m)
	_anim = CharacterModel.find_anim(model)
	if _anim and _anim.has_animation("Idle"):
		_anim.play("Idle")
	_frame()

func play_clip(clip: String) -> void:
	if _anim and _anim.has_animation(clip):
		_anim.play(clip)

func clear() -> void:
	_key = ""
	if model:
		model.queue_free()
		model = null

func _set_model(m: Node3D) -> void:
	if model:
		_pivot.remove_child(model)
		model.queue_free()
	model = m
	_pivot.add_child(model)

func _process(dt: float) -> void:
	if spin != 0.0 and _pivot:
		_pivot.rotate_y(dt * spin)

## Fits the orthographic camera to the model's rest-pose bounds.
func _frame() -> void:
	if model == null:
		return
	_pivot.rotation_degrees = Vector3(0, yaw, 0)
	var box := _bounds(model, Transform3D(Basis.from_euler(Vector3(0, deg_to_rad(yaw), 0)), Vector3.ZERO))
	if box.size == Vector3.ZERO:
		box = AABB(Vector3(-0.5, 0, -0.5), Vector3(1, 1, 1))
	var p := deg_to_rad(pitch)
	# camera basis: looking along -back, pitched down by `pitch`
	var back := Vector3(0, sin(p), cos(p))
	var up := Vector3(0, cos(p), -sin(p))
	var right := Vector3.RIGHT
	var vmin := INF
	var vmax := -INF
	var hmin := INF
	var hmax := -INF
	for i in 8:
		var c := box.get_endpoint(i)
		vmin = minf(vmin, c.dot(up))
		vmax = maxf(vmax, c.dot(up))
		hmin = minf(hmin, c.dot(right))
		hmax = maxf(hmax, c.dot(right))
	var aspect := float(logical.x) / float(logical.y)
	var ortho := maxf(vmax - vmin, (hmax - hmin) / aspect) / fill
	_cam.size = ortho
	var cv := (vmin + vmax) * 0.5
	if anchor == "bottom":
		cv = vmin + ortho * 0.5 - ortho * 0.02
	var ch := (hmin + hmax) * 0.5
	_cam.basis = Basis(right, up, back)
	_cam.position = right * ch + up * cv + back * 30.0

func _bounds(n: Node, xf: Transform3D) -> AABB:
	var out := AABB()
	var first := true
	var t := xf
	if n is Node3D:
		t = xf * (n as Node3D).transform
	if n is VisualInstance3D:
		var vi := n as VisualInstance3D
		var b := t * vi.get_aabb()
		out = b
		first = false
	for c in n.get_children():
		var cb := _bounds(c, t)
		if cb.size == Vector3.ZERO:
			continue
		if first:
			out = cb
			first = false
		else:
			out = out.merge(cb)
	return out

## Sprite-style 1px dark outline (upstream sprites are outlined in #1b1a2e):
## the render is stamped darkened at the 4 neighbouring logical pixels first.
var outline := true
const OUTLINE_MOD := Color(0.07, 0.07, 0.12, 1.0)

## Draws this view's frame into a PxCanvas at logical (x, y).
func draw_at(ci: CanvasItem, x: float, y: float, modulate: Color = Color.WHITE) -> void:
	var tex := get_texture()
	if outline:
		var om := Color(OUTLINE_MOD.r, OUTLINE_MOD.g, OUTLINE_MOD.b, modulate.a)
		for o in [Vector2(-1, 0), Vector2(1, 0), Vector2(0, -1), Vector2(0, 1)]:
			Px.blit(ci, tex, x + o.x, y + o.y, logical.x, logical.y, om)
	Px.blit(ci, tex, x, y, logical.x, logical.y, modulate)

## Like draw_at but only the top `rows` logical rows (party.js {sh: 30}).
func draw_clipped(ci: CanvasItem, x: float, y: float, rows: int) -> void:
	var tex := get_texture()
	var src := Rect2(0, 0, logical.x * K, rows * K)
	if outline:
		for o in [Vector2(-1, 0), Vector2(1, 0), Vector2(0, -1), Vector2(0, 1)]:
			ci.draw_texture_rect_region(tex, Rect2(x + o.x, y + o.y, logical.x, rows), src, OUTLINE_MOD)
	ci.draw_texture_rect_region(tex, Rect2(x, y, logical.x, rows), src)

func draw_scaled(ci: CanvasItem, x: float, y: float, w: float, h: float, modulate: Color = Color.WHITE) -> void:
	Px.blit(ci, get_texture(), x, y, w, h, modulate)
