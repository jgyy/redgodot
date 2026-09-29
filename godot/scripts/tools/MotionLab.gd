extends Node
## Motion lab: drives the real overworld player (simulated d-pad, like PlayTest) along a path and records what
## is on screen every rendered frame, to prove that walking is continuous: no positional pops, no speed
## discontinuities inside a chain of steps, the walk clip never restarting, a critically damped camera.
##   godot4 --path godot -- --scene=motion_lab --map=PalletTown --pc=10,9 --route=RRRRRRRR [--who=player|follower]
##          [--csv=/tmp/m.csv] [--screenshot=/tmp/strip.png] [--shots=8] [--follower=none]
## Prints a metrics block; --screenshot saves a strip of --shots frames (cropped around the player) taken evenly
## from the first frame of movement to the last. Needs a display (xvfb-run) for the strip only.

const CW := 260
const CH := 300

var _ow: Node = null
var _rows: Array = []
var _shots: Array = []

func run(args: Dictionary, out_png: String) -> void:
	_ow = get_tree().root.find_child("Overworld", true, false)
	if _ow == null:
		push_error("[motion_lab] no overworld")
		get_tree().quit(1)
		return
	_ow.no_encounters = true
	var path := String(args.get("route", "RRRRRRRR")).to_upper()
	var n_shots := int(args.get("shots", "8"))
	var csv := String(args.get("csv", ""))
	await _frames(20)
	if args.has("dump"):
		_dump_map()
	var start_cell: Vector2i = _ow.actor_cell("PLAYER")
	var dir_of := {"U": "up", "D": "down", "L": "left", "R": "right"}
	# expected cells along the path
	var cells: Array = [start_cell]
	for ch in path:
		var dv: Vector2i = OwActor.DIRS[dir_of[ch]]
		cells.append(cells[-1] + dv)
	var idx := 0
	var t0 := Time.get_ticks_usec()
	var guard := 0
	var moved := false
	var last_cell := start_cell
	var last_change := Time.get_ticks_msec()
	while guard < 4000:
		guard += 1
		var cur: Vector2i = _ow.actor_cell("PLAYER")
		if cur != last_cell:
			last_cell = cur
			last_change = Time.get_ticks_msec()
		elif Time.get_ticks_msec() - last_change > 6000:
			print("[motion_lab] stalled at %s (blocked route?)" % str(cur))
			break
		while idx < cells.size() - 1 and cur == cells[idx + 1]:
			idx += 1
		var want := ""
		if idx < path.length():
			want = "move_" + String(dir_of[path[idx]])
		_set_action(want)
		await get_tree().process_frame
		_record((Time.get_ticks_usec() - t0) / 1e6)
		if _ow.player.moving:
			moved = true
		if idx >= path.length() and not _ow.player.moving:
			break
	_set_action("")
	# let the camera and gait settle after the last step
	for i in 90:
		await get_tree().process_frame
		_record((Time.get_ticks_usec() - t0) / 1e6)
	_report(path, moved)
	if csv != "":
		var f := FileAccess.open(csv, FileAccess.WRITE)
		f.store_line("t,dt,px,py,pz,yaw,moving,anim,anim_pos,speed_scale,cx,cz,fx,fz,foot0,foot1")
		for r in _rows:
			f.store_line(",".join((r as Array).map(func(v): return str(v))))
	if out_png != "" and not _shots.is_empty():
		_save_strip(out_png, n_shots)
	get_tree().quit()
	await get_tree().create_timer(3600.0).timeout

## ASCII map of the current map (# blocked, g tall grass, ~ water, L down-ledge, P player) for choosing routes.
func _dump_map() -> void:
	var ml: MapLoader = _ow.map_loader()
	print("[motion_lab] map %s %dx%d" % [ml.map_name, ml.width, ml.height])
	for y in ml.height:
		var row := ""
		for x in ml.width:
			var c := Vector2i(x, y)
			var ch := "."
			if _ow.actor_cell("PLAYER") == c:
				ch = "P"
			elif ml.is_ledge_jump(c, "down"):
				ch = "L"
			elif ml.is_water(c):
				ch = "~"
			elif ml.is_tall_grass(c):
				ch = "g"
			elif not ml.passable(c):
				ch = "#"
			row += ch
		print("%2d %s" % [y, row])

func _set_action(want: String) -> void:
	for a in ["move_up", "move_down", "move_left", "move_right"]:
		var should: bool = (a == want)
		if Input.is_action_pressed(a) != should:
			var ev := InputEventAction.new()
			ev.action = a
			ev.pressed = should
			Input.parse_input_event(ev)

func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame

func _foot_positions() -> Array:
	var out: Array = []
	var p: OwActor = _ow.player
	var sk := _find_skel(p)
	if sk:
		for i in sk.get_bone_count():
			var nm := sk.get_bone_name(i).to_lower()
			if nm.contains("foot") or nm.contains("leg"):
				out.append((sk.global_transform * sk.get_bone_global_pose(i)).origin)
	return out

func _find_skel(n: Node) -> Skeleton3D:
	if n is Skeleton3D:
		return n
	for c in n.get_children():
		var f := _find_skel(c)
		if f:
			return f
	return null

func _record(t: float) -> void:
	var p: OwActor = _ow.player
	var f: OwActor = _ow.follower   # null with --follower=none
	var cam: Node3D = _ow.get_node("CameraRig")
	var ap: AnimationPlayer = p._anim
	var feet := _foot_positions()
	var f0: Vector3 = feet[0] if feet.size() > 0 else Vector3.ZERO
	var f1: Vector3 = feet[1] if feet.size() > 1 else Vector3.ZERO
	_rows.append([t, get_process_delta_time(), p.position.x, p.position.y, p.position.z, p._yaw, 1 if p.moving else 0,
		ap.current_animation if ap else "", snappedf(ap.current_animation_position, 0.0001) if ap else 0.0,
		ap.speed_scale if ap else 0.0, cam.position.x, cam.position.z, f.position.x if f else 0.0, f.position.z if f else 0.0, f0.x, f1.x])
	if (p.moving or _rows.size() > 1 and _rows[-2][6] == 1) and _shots.size() < 400 and DisplayServer.get_name() != "headless":
		var img := get_viewport().get_texture().get_image()
		_shots.append(img.get_region(Rect2i(img.get_width() / 2 - CW / 2, img.get_height() / 2 - CH / 2 - 20, CW, CH)))

func _report(path: String, moved: bool) -> void:
	var n := _rows.size()
	var first := -1
	var last := -1
	for i in n:
		if _rows[i][6] == 1:
			if first < 0:
				first = i
			last = i
	print("[motion_lab] path=%s frames=%d moving frames %d..%d moved=%s" % [path, n, first, last, str(moved)])
	if first < 0:
		return
	# --- player position: speed per frame (cells/s)
	var speeds: Array = []
	var pops := 0
	for i in range(first + 1, last + 1):
		var dt: float = _rows[i][1]
		var dx: float = _rows[i][2] - _rows[i - 1][2]
		var dz: float = _rows[i][4] - _rows[i - 1][4]
		speeds.append(sqrt(dx * dx + dz * dz) / maxf(dt, 1e-4))
	# steady-state (ignore ramp of the first/last step: 1.2 steps at each end)
	var lo := int(speeds.size() * 0.0)
	var mid_lo := 0
	var mid_hi := speeds.size()
	var step_frames := 16
	mid_lo = mini(speeds.size(), step_frames + 2)
	mid_hi = maxi(mid_lo, speeds.size() - step_frames - 2)
	var vmax := 0.0
	var vmin := 1e9
	var dv_max := 0.0
	for i in range(mid_lo, mid_hi):
		vmax = maxf(vmax, speeds[i])
		vmin = minf(vmin, speeds[i])
		if i > mid_lo:
			dv_max = maxf(dv_max, absf(speeds[i] - speeds[i - 1]))
	print("[motion_lab] steady speed cells/s: min %.3f max %.3f (nominal 3.75)  max frame-to-frame change %.3f" % [vmin if vmin < 1e8 else 0.0, vmax, dv_max])
	# --- frame time jitter
	var dts: Array = _rows.slice(first, last + 1).map(func(r): return float(r[1]))
	print("[motion_lab] dt ms: min %.1f max %.1f" % [float(dts.min()) * 1000.0, float(dts.max()) * 1000.0])
	# --- animation restarts and phase
	var walk_starts := 0
	var restarts := 0
	var prev_anim := ""
	var prev_pos := 0.0
	# the generated Walk clip is one 16-frame cell (~0.27 s), the legacy one 0.8 s: a wrap is only a natural loop end
	# when the previous sample was in the last quarter of the *actual* clip length
	var walk_len := 0.8
	var pa: AnimationPlayer = _ow.player._anim
	if pa and pa.has_animation("Walk"):
		walk_len = pa.get_animation("Walk").length
	for i in range(first, n):
		var a: String = _rows[i][7]
		var ap: float = _rows[i][8]
		if a == "Walk" and prev_anim != "Walk":
			walk_starts += 1
		if a == "Walk" and prev_anim == "Walk" and ap < prev_pos - 0.001 and prev_pos < 0.75 * walk_len:
			restarts += 1   # jumped backwards without reaching the end of the loop
		prev_anim = a
		prev_pos = ap
	print("[motion_lab] Walk clip starts: %d (1 = played once for the whole chain)  mid-loop restarts: %d" % [walk_starts, restarts])
	# --- camera follow: offset to the player (cells) in the steady part, and overshoot when stopping
	var off_min := 1e9
	var off_max := -1e9
	var cam_speed_jump := 0.0
	var cs_prev := 0.0
	for i in range(first + 1, n):
		var dt: float = _rows[i][1]
		var cvx: float = (_rows[i][10] - _rows[i - 1][10]) / maxf(dt, 1e-4)
		var cvz: float = (_rows[i][11] - _rows[i - 1][11]) / maxf(dt, 1e-4)
		var cs := sqrt(cvx * cvx + cvz * cvz)
		if i > first + 1:
			cam_speed_jump = maxf(cam_speed_jump, absf(cs - cs_prev))
		cs_prev = cs
		if i >= first + mid_lo and i <= first + mid_hi:
			var ox: float = _rows[i][10] - _rows[i][2]
			var oz: float = (_rows[i][11] - _rows[i][4]) - (0.5 - OwActor.FOOT_Z)
			var o := sqrt(ox * ox + oz * oz) * (1.0 if (ox + oz) >= 0.0 else -1.0)
			off_min = minf(off_min, o)
			off_max = maxf(off_max, o)
	print("[motion_lab] camera - player offset while walking (cells): %.3f .. %.3f; max camera speed change per frame %.2f cells/s" % [off_min, off_max, cam_speed_jump])
	var cam_final := Vector2(_rows[n - 1][10], _rows[n - 1][11])
	var cam_start := Vector2(_rows[first][10], _rows[first][11])
	var dirv := (cam_final - cam_start).normalized()
	var beyond := 0.0
	for i in range(last, n):
		var c := Vector2(_rows[i][10], _rows[i][11])
		beyond = maxf(beyond, (c - cam_final).dot(dirv))
	print("[motion_lab] camera overshoot past the resting point after stopping: %.4f cells" % beyond)
	# --- yaw: max angular step per frame
	var yaw_step := 0.0
	for i in range(first, n):
		if i > 0:
			yaw_step = maxf(yaw_step, absf(angle_difference(float(_rows[i - 1][5]), float(_rows[i][5]))))
	print("[motion_lab] max yaw change per frame: %.1f deg" % rad_to_deg(yaw_step))

func _save_strip(out_png: String, n_shots: int) -> void:
	var imgs: Array = _shots.filter(func(i): return i != null)
	if imgs.is_empty():
		return
	var strip := Image.create(CW * n_shots, CH, false, Image.FORMAT_RGBA8)
	for k in n_shots:
		var src: Image = imgs[int(float(k) / maxf(1.0, n_shots - 1.0) * (imgs.size() - 1))]
		strip.blit_rect(src, Rect2i(0, 0, CW, CH), Vector2i(k * CW, 0))
	strip.save_png(out_png)
	print("[motion_lab] strip saved ", out_png)
