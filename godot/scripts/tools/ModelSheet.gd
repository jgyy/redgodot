extends Node
## --scene=model_sheet : renders a contact sheet of generated 3D models (one cell per
## model, rendered one after another through a single SubViewport) and saves it to the
## --screenshot path, then quits.  Used to eyeball all 151 Pokemon / all characters.
##
## Flags: --kind=pokemon|characters  --species=A,B,C (default: every model in the manifest)
##        --view=front|back|side  --cols=N  --cell=PX  --yaw=DEG (3/4 turn, default -25 = toward the light)
##        --anim=Idle --anim_t=0.0 (pose to sample)  --labels=1  --toon=0 --outline=PX
##        --sprite_frame=M (Pokemon sized like upstream sprites: 64px frame = M metres, fixed camera)

var _vp: SubViewport
var _cam: Camera3D
var _stage: Node3D
var _label: Label
var _toon := true
var _frame_m := 0.0  # --sprite_frame=M: size Pokemon like upstream sprites, fixed camera
var _focus := Vector2.ZERO  # --focus=FRAC,HALF_M: zoom on a slice of the model (e.g. 0.93,0.14 = the head), for look-dev close-ups

func run(args: Dictionary, out_path: String) -> void:
	var kind: String = args.get("kind", "pokemon")
	var ids: Array = _ids(kind, args)
	# --poses=Idle:0,Walk:0.05,...  renders the FIRST species once per pose (clip:seconds) -- motion look-dev / clipping review
	var poses: Array = []
	if args.has("poses"):
		poses = Array(String(args["poses"]).split(",", false))
		var one: String = ids[0]
		ids = []
		for _p in poses:
			ids.append(one)
	var cols := maxi(1, int(args.get("cols", "12")))
	var cell := int(args.get("cell", "160"))
	var view: String = args.get("view", "front")
	var yaw := float(args.get("yaw", "-25"))
	var anim_name: String = args.get("anim", "Idle")
	var anim_t := float(args.get("anim_t", "0.0"))
	var labels: bool = args.get("labels", "1") != "0"
	_toon = args.get("toon", "1") != "0"
	_frame_m = float(args.get("sprite_frame", "0"))
	if args.has("focus"):
		var fp := String(args["focus"]).split(",")
		_focus = Vector2(float(fp[0]), float(fp[1]) if fp.size() > 1 else 0.15)
	var rows := int(ceil(float(ids.size()) / float(cols)))
	_build(cell)
	var sheet := Image.create(cols * cell, max(1, rows) * cell, false, Image.FORMAT_RGBA8)
	sheet.fill(Color(0.87, 0.91, 0.95))
	for i in range(ids.size()):
		var id: String = ids[i]
		var holder := Node3D.new()
		_stage.add_child(holder)
		var model: Node3D = _instantiate(kind, id)
		holder.add_child(model)
		if args.has("outline"):
			Toon.set_param(model, "width_px", float(args["outline"]))
		var ap := _find_anim(model)
		var pose_label := ""
		if poses.size() > i:
			var pp := String(poses[i]).split(":")
			anim_name = pp[0]
			anim_t = float(pp[1]) if pp.size() > 1 else 0.0
			pose_label = " %s %.2f" % [anim_name, anim_t]
		if ap:
			AnimUtil.fix_looping(ap)
			ap.playback_default_blend_time = 0.0   # paused poses: a pending cross-fade would hide the clip
			var nm := anim_name if ap.has_animation(anim_name) else "Idle"
			if ap.has_animation(nm):
				ap.play(nm)
				ap.seek(anim_t, true)
				ap.speed_scale = 0.0
		match view:
			"back":
				holder.rotation_degrees.y = 180.0 - yaw * 0.5
			"side":
				holder.rotation_degrees.y = 90.0
			_:
				holder.rotation_degrees.y = yaw
		await get_tree().process_frame
		_frame(holder)
		_label.text = ((id + pose_label) if labels else "")
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := _vp.get_texture().get_image()
		img.convert(Image.FORMAT_RGBA8)
		sheet.blit_rect(img, Rect2i(0, 0, cell, cell), Vector2i((i % cols) * cell, (i / cols) * cell))
		holder.queue_free()
		await get_tree().process_frame
	sheet.save_png(out_path)
	print("[ModelSheet] saved %s (%d models)" % [out_path, ids.size()])
	get_tree().quit()

func _ids(kind: String, args: Dictionary) -> Array:
	if args.has("species"):
		return Array(String(args["species"]).split(",", false))
	var out: Array = []
	var dir := "res://assets/models/%s/manifest.json" % ("characters" if kind == "characters" else "pokemon")
	var f := FileAccess.open(dir, FileAccess.READ)
	if f:
		var data: Variant = JSON.parse_string(f.get_as_text())
		if data is Dictionary:
			if kind == "characters":
				for k in (data as Dictionary).get("sprites", {}).keys():
					out.append(k)
			else:
				for k in (data as Dictionary).get("generated", []):
					out.append(k)
	return out

func _instantiate(kind: String, id: String) -> Node3D:
	if kind == "characters":
		return CharacterSkin.instantiate(id, _toon)
	var actor := PokemonActor.new()
	actor.setup(id)
	if _frame_m > 0.0:
		actor.use_sprite_scale(_frame_m)
	return actor

func _build(cell: int) -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(cell, cell)
	_vp.own_world_3d = true
	_vp.transparent_bg = false
	_vp.msaa_3d = Viewport.MSAA_4X
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.87, 0.91, 0.95)
	var we := WorldEnvironment.new()
	we.environment = env
	_vp.add_child(we)
	_cam = Camera3D.new()
	_cam.fov = 30.0
	_cam.current = true
	_vp.add_child(_cam)
	_stage = Node3D.new()
	_vp.add_child(_stage)
	_label = Label.new()
	_label.position = Vector2(4, 2)
	_label.add_theme_font_size_override("font_size", 11)
	_label.add_theme_color_override("font_color", Color(0.2, 0.2, 0.3))
	_vp.add_child(_label)

func _frame(holder: Node3D) -> void:
	var box := AABB()
	var first := true
	for mi in Toon._mesh_instances(holder):
		var inst: MeshInstance3D = mi
		if inst.mesh == null:
			continue
		var b: AABB = inst.global_transform * inst.mesh.get_aabb()
		box = b if first else box.merge(b)
		first = false
	if first or _frame_m > 0.0:
		var fm: float = _frame_m if _frame_m > 0.0 else 1.0
		box = AABB(Vector3(-fm * 0.5, 0, -fm * 0.5), Vector3(fm, fm, fm))
	if _focus.y > 0.0 and not first:
		var fcy := box.position.y + box.size.y * _focus.x
		box = AABB(Vector3(box.get_center().x - _focus.y, fcy - _focus.y, box.get_center().z - _focus.y), Vector3.ONE * _focus.y * 2.0)
	var c := box.get_center()
	var r: float = max(box.size.y, max(box.size.x, box.size.z)) * 0.5
	var dist: float = r / tan(deg_to_rad(_cam.fov * 0.5)) * 1.12
	var pitch := deg_to_rad(-10.0)
	_cam.position = c + Vector3(0, -sin(pitch), cos(pitch)) * dist
	_cam.look_at(c, Vector3.UP)
	_cam.near = max(0.01, dist * 0.05)
	_cam.far = dist * 4.0

func _find_anim(n: Node) -> AnimationPlayer:
	if n is AnimationPlayer:
		return n
	for c in n.get_children():
		var f := _find_anim(c)
		if f:
			return f
	return null
