extends SceneTree
## Contact sheet of environment glbs (props, tile kit), for eyeballing pipeline/blender/env_*.py output:
##   xvfb-run -a /opt/godot/godot4 --path godot --rendering-driver opengl3 --script res://scripts/tools/EnvSheet.gd -- \
##       --dir=res://assets/models/world --out=/tmp/sheet.png [--mode=game|kit] [--cols=6] [--cell=200] [--only=a,b] [--yaw=-25]
## mode=game draws each model the way the overworld does (prop shader, vertical scale K, the 60 degree camera),
## mode=kit draws it lit, unscaled, from a 3/4 view (textured kit models keep their own materials).

var _args := {}
var _vp: SubViewport
var _cam: Camera3D
var _stage: Node3D
var _label: Label

func _init() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and a.contains("="):
			var kv := a.substr(2).split("=", true, 1)
			_args[kv[0]] = kv[1]
	_run.call_deferred()

func _files(dir_path: String) -> Array:
	var out: Array = []
	if _args.has("only"):
		for n in String(_args["only"]).split(",", false):
			out.append(n + ".glb")
		return out
	var d := DirAccess.open(dir_path)
	if d == null:
		return out
	for f in d.get_files():
		if f.ends_with(".glb"):
			out.append(f)
	out.sort()
	return out

func _run() -> void:
	var dir_path: String = _args.get("dir", "res://assets/models/world")
	var mode: String = _args.get("mode", "kit")
	var cols := int(_args.get("cols", "6"))
	var cell := int(_args.get("cell", "200"))
	var yaw := float(_args.get("yaw", "-25"))
	var files := _files(dir_path)
	var rows := int(ceil(float(files.size()) / float(cols)))
	_build(cell, mode)
	var sheet := Image.create(cols * cell, maxi(1, rows) * cell, false, Image.FORMAT_RGBA8)
	sheet.fill(Color(0.87, 0.91, 0.95))
	var game_mat: ShaderMaterial = null
	if mode == "game":
		game_mat = ShaderMaterial.new()
		game_mat.shader = load("res://scripts/overworld/shaders/tree.gdshader")
		game_mat.set_shader_parameter("detail_tex", load("res://assets/models/tiles/env_detail.png"))
		game_mat.set_shader_parameter("detail_on", true)
		game_mat.set_shader_parameter("sway", 0.0)
	for i in range(files.size()):
		var path: String = dir_path + "/" + String(files[i])
		if not ResourceLoader.exists(path):
			continue
		var ps: PackedScene = load(path)
		var model: Node3D = ps.instantiate()
		var holder := Node3D.new()
		_stage.add_child(holder)
		holder.add_child(model)
		if mode == "game":
			holder.scale = Vector3(1.0, WorldData.K, 1.0)
			for mi in _meshes(model):
				(mi as MeshInstance3D).material_override = game_mat
		holder.rotation_degrees.y = yaw if mode == "kit" else 0.0
		await process_frame
		_frame(holder, mode)
		_label.text = String(files[i]).get_basename()
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := _vp.get_texture().get_image()
		img.convert(Image.FORMAT_RGBA8)
		sheet.blit_rect(img, Rect2i(0, 0, cell, cell), Vector2i((i % cols) * cell, (i / cols) * cell))
		holder.queue_free()
		await process_frame
	sheet.save_png(String(_args.get("out", "/tmp/env_sheet.png")))
	print("[EnvSheet] saved ", _args.get("out", "/tmp/env_sheet.png"), " (", files.size(), " models)")
	quit()

func _meshes(n: Node) -> Array:
	var out: Array = []
	if n is MeshInstance3D:
		out.append(n)
	for c in n.get_children():
		out.append_array(_meshes(c))
	return out

func _build(cell: int, mode: String) -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(cell, cell)
	_vp.own_world_3d = true
	_vp.msaa_3d = Viewport.MSAA_4X
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(_vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.87, 0.91, 0.95) if mode == "kit" else Color(0.55, 0.72, 0.42)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.75, 0.78, 0.85)
	env.ambient_light_energy = 0.7
	var we := WorldEnvironment.new()
	we.environment = env
	_vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -35, 0)
	sun.light_energy = 1.0
	_vp.add_child(sun)
	_cam = Camera3D.new()
	_cam.current = true
	_vp.add_child(_cam)
	_stage = Node3D.new()
	_vp.add_child(_stage)
	_label = Label.new()
	_label.position = Vector2(4, 2)
	_label.add_theme_font_size_override("font_size", 11)
	_label.add_theme_color_override("font_color", Color(0.15, 0.15, 0.25))
	_vp.add_child(_label)

func _frame(holder: Node3D, mode: String) -> void:
	var box := AABB()
	var first := true
	for mi in _meshes(holder):
		var inst: MeshInstance3D = mi
		if inst.mesh == null:
			continue
		var b: AABB = inst.global_transform * inst.mesh.get_aabb()
		box = b if first else box.merge(b)
		first = false
	if first:
		box = AABB(Vector3(-0.5, 0, -0.5), Vector3(1, 1, 1))
	var c := box.get_center()
	var r: float = maxf(box.size.y, maxf(box.size.x, box.size.z)) * 0.5
	if mode == "game":
		_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		_cam.size = maxf(r * 2.3, 1.6)
		var pitch := deg_to_rad(-WorldData.CAM_PITCH_DEG)
		_cam.position = c + Vector3(0, -sin(pitch), cos(pitch)) * 20.0
		_cam.look_at(c, Vector3.UP)
	else:
		_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		_cam.fov = 30.0
		var dist: float = r / tan(deg_to_rad(_cam.fov * 0.5)) * 1.15
		var pitch2 := deg_to_rad(-24.0)
		_cam.position = c + Vector3(0, -sin(pitch2), cos(pitch2)) * dist
		_cam.look_at(c, Vector3.UP)
	_cam.near = 0.05
	_cam.far = 100.0
