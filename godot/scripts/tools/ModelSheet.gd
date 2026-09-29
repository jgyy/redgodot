extends Node
## --scene=model_sheet : renders a contact sheet of generated 3D models (one cell per
## model, rendered one after another through a single SubViewport) and saves it to the
## --screenshot path, then quits.  Used to eyeball all 151 Pokemon / all characters.
##
## Flags: --kind=pokemon|characters  --species=A,B,C (default: every model in the manifest)
##        --view=front|back|side  --cols=N  --cell=PX  --yaw=DEG (3/4 turn, default -25 = toward the light)
##        --anim=Idle --anim_t=0.0 (pose to sample)  --labels=1  --toon=0 --outline=PX
##        --focus=head (head close-up for eye checks; centre from eyes.json)  --focus_r=0.22 (radius as a share of body height)
##        --pitch=-10 (camera pitch, 0 = level)
##        --sprite_frame=M (Pokemon sized like upstream sprites: 64px frame = M metres, fixed camera)
## Environment props: --kind=props (assets/models/<--dir=world|tiles|battle|vfx>/*.glb drawn with the overworld's
##        prop shader) or --kind=kit (same glbs with their own textured materials); --species=a,b (default: every glb
##        of --dir, minus tree_*/bld_* unless --all=1); --view=game (the overworld camera: 60 degree pitch, Y stretched
##        by K like every placed prop) or --view=close (true proportions, 3/4 view, low camera)
##        --clips=Idle,Walk,Attack --tfrac=0.5   one cell per (species, clip) sampled at tfrac of the clip length
##        --strip=Attack --frames=6              one row per species: the clip sampled at N even steps (--cols is set to N)

var _vp: SubViewport
var _cam: Camera3D
var _stage: Node3D
var _label: Label
var _toon := true
var _eyes := {}
var _cur_id := ""
var _pitch_deg := -10.0
var _focus := ""
var _focus_r := 0.22
var _frame_m := 0.0  # --sprite_frame=M: size Pokemon like upstream sprites, fixed camera
var _pitch := -10.0   # camera pitch of the cell (degrees; props: -60 = the overworld camera)
var _world_mat: ShaderMaterial = null   # kind=props: the overworld's vertex-colour prop shader

func run(args: Dictionary, out_path: String) -> void:
	var kind: String = args.get("kind", "pokemon")
	var ids: Array = _ids(kind, args)
	var cols := maxi(1, int(args.get("cols", "12")))
	var cell := int(args.get("cell", "160"))
	var view: String = args.get("view", "front")
	var yaw := float(args.get("yaw", "-25"))
	var is_env := kind == "props" or kind == "kit"
	if is_env:
		_pitch = -60.0 if view == "game" else -22.0
		if view == "game":
			yaw = 0.0
		elif not args.has("yaw"):
			yaw = -32.0
		_world_mat = TileKit._prop_shader_material({}, 0.0, Color("#1b1a2e"), 0.03) if kind == "props" else null
	var anim_name: String = args.get("anim", "Idle")
	var anim_t := float(args.get("anim_t", "0.0"))
	var labels: bool = args.get("labels", "1") != "0"
	_toon = args.get("toon", "1") != "0"
	_frame_m = float(args.get("sprite_frame", "0"))
	_focus = args.get("focus", "")
	_pitch_deg = float(args.get("pitch", "-10"))
	_focus_r = float(args.get("focus_r", "0.22"))
	if _focus != "":
		var ef := FileAccess.open("res://assets/models/pokemon/eyes.json", FileAccess.READ)
		if ef:
			var parsed: Variant = JSON.parse_string(ef.get_as_text())
			if parsed is Dictionary:
				_eyes = (parsed as Dictionary).get("species", {})
	# cells: (species, clip, time in [0,1) of the clip; -1 = anim_t seconds)
	var cells: Array = []
	if args.has("strip"):
		var n := maxi(2, int(args.get("frames", "6")))
		cols = n
		for id in ids:
			for k in n:
				cells.append([id, String(args["strip"]), float(k) / float(n)])
	elif args.has("clips"):
		var cl: PackedStringArray = String(args["clips"]).split(",", false)
		cols = cl.size()
		for id in ids:
			for c in cl:
				cells.append([id, c, float(args.get("tfrac", "0.5"))])
	else:
		for id in ids:
			cells.append([id, anim_name, -1.0])
	var rows := int(ceil(float(cells.size()) / float(cols)))
	_dir = String(args.get("dir", "world"))
	_build(cell)
	var sheet := Image.create(cols * cell, max(1, rows) * cell, false, Image.FORMAT_RGBA8)
	sheet.fill(Color(0.87, 0.91, 0.95))
	for i in range(cells.size()):
		var id: String = cells[i][0]
		_cur_id = id
		var holder := Node3D.new()
		_stage.add_child(holder)
		var model: Node3D = _instantiate(kind, id)
		holder.add_child(model)
		if is_env:
			_style_env(model, view == "game")
		if args.has("outline"):
			Toon.set_param(model, "width_px", float(args["outline"]))
		var ap := _find_anim(model)
		if ap:
			AnimUtil.fix_looping(ap)
			ap.playback_default_blend_time = 0.0   # paused poses: a pending cross-fade would hide the clip
			var want: String = cells[i][1]
			var nm := want if ap.has_animation(want) else "Idle"
			if ap.has_animation(nm):
				ap.play(nm)
				var tt := anim_t if float(cells[i][2]) < 0.0 else float(cells[i][2]) * ap.get_animation(nm).length
				ap.seek(tt, true)
				ap.speed_scale = 0.0
		match view if not is_env else "env":
			"env":
				holder.rotation_degrees.y = yaw
			"back":
				holder.rotation_degrees.y = 180.0 - yaw * 0.5
			"side":
				holder.rotation_degrees.y = 90.0
			_:
				holder.rotation_degrees.y = yaw
		await get_tree().process_frame
		_frame(holder)
		_label.text = ((id if cells[i][1] == anim_name and not args.has("strip") and not args.has("clips") else "%s %s" % [id, cells[i][1]]) if labels else "")
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
	if kind == "props" or kind == "kit":
		var names: Array = []
		var d := String(args.get("dir", "world"))
		var da := DirAccess.open("res://assets/models/%s" % d)
		if da:
			for fn in da.get_files():
				if fn.ends_with(".glb"):
					var nm := fn.get_basename()
					if args.get("all", "0") == "1" or not (nm.begins_with("tree_tree") or nm.begins_with("bld_") or nm.begins_with("emote_") or nm.ends_with("_set")):
						names.append(nm)
		names.sort()
		return names
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
	if kind == "props" or kind == "kit":
		var dir := String(_dir)
		var ps: PackedScene = load("res://assets/models/%s/%s.glb" % [dir, id])
		var holder := Node3D.new()
		if ps:
			holder.add_child(ps.instantiate())
		return holder
	if kind == "characters":
		return CharacterSkin.instantiate(id, _toon)
	var actor := PokemonActor.new()
	actor.idle_variety = false   # sheets sample paused poses
	actor.setup(id)
	if _frame_m > 0.0:
		actor.use_sprite_scale(_frame_m)
	return actor

var _dir := "world"

## Props: the overworld's shader (or the kit's own materials); the game view stretches Y by K exactly like PropKit does.
func _style_env(model: Node3D, game_view: bool) -> void:
	if _world_mat:
		for mi in Toon._mesh_instances(model):
			(mi as MeshInstance3D).material_override = _world_mat
	if game_view:
		model.scale = Vector3(1.0, WorldData.K, 1.0)

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
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.72, 0.74, 0.8)
	var we := WorldEnvironment.new()
	we.environment = env
	_vp.add_child(we)
	_cam = Camera3D.new()
	_cam.fov = 30.0
	_cam.current = true
	_vp.add_child(_cam)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.light_energy = 1.1
	_vp.add_child(sun)
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
	var c := box.get_center()
	var r: float = max(box.size.y, max(box.size.x, box.size.z)) * 0.5
	if _focus == "head" and not first:
		# head centre + radius come from eyes.json (written by pokemon_mesh_fix.py); fall back to the top of the box
		var rec: Dictionary = _eyes.get(_cur_id, {})
		if rec.has("focus"):
			var actor: Node3D = holder.get_child(0)
			c = actor.to_global(Vector3(rec["focus"][0], rec["focus"][1], rec["focus"][2]))
			r = maxf(0.05, float(rec.get("focus_r", box.size.y * _focus_r)) * actor.global_transform.basis.get_scale().y)
		else:
			c = Vector3(box.get_center().x, box.end.y - box.size.y * 0.15, box.get_center().z)
			r = box.size.y * _focus_r
	var dist: float = r / tan(deg_to_rad(_cam.fov * 0.5)) * (1.5 if _world_mat or _pitch < -15.0 else 1.12)
	var pitch := deg_to_rad(_pitch_deg if _focus == "head" else _pitch)
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
