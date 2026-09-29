class_name MotionTests
extends RefCounted
## Motion-continuity contract of the overworld (OwActor + camera smoothing + AnimUtil), run from TestSuite.
## Actors are stepped by hand with fixed frame deltas, so every number here is deterministic.

const DT := 1.0 / 60.0

static func run(t: TestSuite, root: Node) -> void:
	_test_smooth(t)
	_test_chain(t, root)
	_test_stop_and_start(t, root)
	_test_turning(t, root)
	_test_hop(t, root)
	_test_fallback(t, root)
	_test_frame_rate(t, root)

static func _actor(root: Node, sprite: String) -> OwActor:
	var a := OwActor.new()
	root.add_child(a)
	a.setup(sprite)
	a.set_process(false)
	a.place(Vector2i(2, 2), "right")
	return a

static func _tick(a: OwActor, dt: float) -> void:
	a._process(dt)
	if a._anim:
		a._anim.advance(dt)

## Drive like the overworld does: whenever the actor is idle and `steps` remain, start the next step at once.
## Returns per-frame samples [{x, v, anim, anim_pos, moving}].
static func _walk(a: OwActor, n_steps: int, dt: float, settle_frames: int = 40) -> Array:
	# like the overworld: actors update first, then the controller may start the next step in the same frame
	var out: Array = []
	var left := n_steps
	var settle := settle_frames
	var guard := 0
	var px := a.position.x
	while guard < 4000 and settle > 0:
		if not a.moving and left > 0:
			a.start_move("right", 1.0, false, left > 1)
			left -= 1
		elif a.moving:
			a.stop_hint = left == 0
		px = a.position.x
		_tick(a, dt)
		if not a.moving and left > 0:
			a.start_move("right", 1.0, false, left > 1)
			left -= 1
		if left == 0 and not a.moving:
			settle -= 1
		out.append({"x": a.position.x, "v": (a.position.x - px) / dt, "anim": a._anim.current_animation if a._anim else "",
			"pos": a._anim.current_animation_position if a._anim else 0.0, "moving": a.moving, "cell": a.cell, "yaw": a._yaw})
		guard += 1
	return out

static func _test_smooth(t: TestSuite) -> void:
	# critically damped spring: converges, never overshoots a fixed target, same result at any frame rate
	var x := 0.0
	var v := 0.0
	var peak := 0.0
	for i in 240:
		var r := Smooth.damp(x, v, 1.0, 20.0, 1.0 / 60.0)
		x = r[0]
		v = r[1]
		peak = maxf(peak, x)
	t.check(absf(x - 1.0) < 0.001 and peak <= 1.0 + 1e-6, "Smooth.damp converges without overshoot (x=%.4f peak=%.4f)" % [x, peak])
	var a30 := [0.0, 0.0]
	var a144 := [0.0, 0.0]
	for i in 15:
		a30 = Smooth.damp(a30[0], a30[1], 1.0, 20.0, 1.0 / 30.0)
	for i in 72:
		a144 = Smooth.damp(a144[0], a144[1], 1.0, 20.0, 1.0 / 144.0)
	t.check(absf(float(a30[0]) - float(a144[0])) < 0.001, "Smooth.damp is frame-rate independent (%.4f vs %.4f)" % [a30[0], a144[0]])
	# a spring following a target moving at constant speed settles at lag v / omega (with half feed-forward)
	var cx := 0.0
	var cv := 0.0
	var tx := 0.0
	var speed := 3.75
	for i in 180:
		tx += speed / 60.0
		var r2 := Smooth.damp(cx, cv, tx + speed / 22.0, 22.0, 1.0 / 60.0)
		cx = r2[0]
		cv = r2[1]
	t.check(absf((tx - cx) - speed / 22.0) < 0.05, "camera spring lag at cruise is v / omega (%.3f)" % (tx - cx))
	# and stopping dead from that state never overshoots the resting point
	var peak2 := -1e9
	for i in 120:
		var r3 := Smooth.damp(cx, cv, tx, 22.0, 1.0 / 60.0)
		cx = r3[0]
		cv = r3[1]
		peak2 = maxf(peak2, cx - tx)
	t.check(peak2 <= 1e-4, "camera does not overshoot when the player stops dead (%.5f)" % peak2)

static func _test_chain(t: TestSuite, root: Node) -> void:
	for spr in ["red", "mon:PIKACHU"]:
		var a := _actor(root, spr)
		var s := _walk(a, 8, DT)
		var walk_starts := 0
		var prev := ""
		var back := 0
		var prev_pos := 0.0
		var got_walk := false
		for f in s:
			if f["anim"] == "Walk" and prev != "Walk":
				walk_starts += 1
			if f["anim"] == "Walk" and prev == "Walk" and float(f["pos"]) < prev_pos - 0.3:
				back += 1   # only a loop wrap may go backwards, and wraps are by a whole clip length
			got_walk = got_walk or f["anim"] == "Walk"
			prev = f["anim"]
			prev_pos = float(f["pos"])
		t.check(got_walk and walk_starts == 1, "%s: Walk starts once for 8 chained steps (got %d)" % [spr, walk_starts])
		# pace: after the standing start, chained steps hold a constant 3.75 cells/s (16 frames per cell)
		var vs: Array = []
		var idx := 0
		for f in s:
			if f["moving"] and idx > 30 and idx < s.size() - 70:
				vs.append(float(f["v"]))
			idx += 1
		var vmin := 1e9
		var vmax := -1e9
		for v in vs:
			vmin = minf(vmin, v)
			vmax = maxf(vmax, v)
		t.check(vs.size() > 40 and vmin > 3.74 and vmax < 3.76, "%s: even pace through chained steps (%.4f..%.4f cells/s)" % [spr, vmin, vmax])
		t.check(a.cell == Vector2i(10, 2) and is_equal_approx(a.position.x, OwActor.cell_pos(Vector2i(10, 2)).x), "%s: eight steps land exactly on the cell" % spr)
		a.queue_free()

static func _test_stop_and_start(t: TestSuite, root: Node) -> void:
	var a := _actor(root, "red")
	# a single tap: eases in and out, covers exactly one cell, ends at rest
	a.start_move("right", 1.0, false, false)
	var frames := 0
	var vmax := 0.0
	var v_first := -1.0
	var v_last := 0.0
	var prev := a.position.x
	var jump_max := 0.0
	var v_prev := 0.0
	while a.moving and frames < 200:
		_tick(a, DT)
		var v := (a.position.x - prev) / DT
		prev = a.position.x
		if v_first < 0.0:
			v_first = v
		if frames > 0:
			jump_max = maxf(jump_max, absf(v - v_prev))
		v_prev = v
		if a.moving:
			v_last = v
		vmax = maxf(vmax, v)
		frames += 1
	t.check(is_equal_approx(a.position.x, OwActor.cell_pos(Vector2i(3, 2)).x), "a single tap lands exactly on the next cell")
	t.check(v_first < 2.0, "a standing start eases in (first-frame speed %.2f cells/s)" % v_first)
	t.check(v_last < 1.5, "a walk eases into its stop (last-moving-frame speed %.2f cells/s)" % v_last)
	t.check(frames >= 16 and frames <= 24, "a tap takes 16-24 frames (%d)" % frames)
	t.check(jump_max < 0.8, "speed never jumps between frames while easing (max %.2f cells/s per frame)" % jump_max)
	# ... and returns to Idle with a crossfade instead of staying in Walk
	for i in 30:
		_tick(a, DT)
	t.check(a._anim.current_animation == "Idle", "back to Idle after the last step")
	t.check(a._anim.playback_default_blend_time > 0.0, "clips crossfade (default blend %.2f s)" % a._anim.playback_default_blend_time)
	a.queue_free()

static func _test_turning(t: TestSuite, root: Node) -> void:
	var a := _actor(root, "red")
	a.face("right", true)
	a.face("up")   # right = +90 deg, up = 180 deg: a quarter turn the short way round
	t.check(a.facing == "up", "logical facing changes at once")
	var yaw0 := a._yaw
	var total := 0.0
	var max_step := 0.0
	var prev := yaw0
	for i in 60:
		_tick(a, DT)
		var d := angle_difference(prev, a._yaw)
		total += absf(d)
		max_step = maxf(max_step, absf(d))
		prev = a._yaw
	t.check(absf(angle_difference(a._yaw, PI)) < 0.01, "yaw settles on the facing")
	t.check(total < PI / 2.0 + 0.05, "turns by the shortest arc (%.1f deg travelled)" % rad_to_deg(total))
	t.check(max_step <= OwActor.TURN_MAX * DT + 1e-4, "turn speed is capped (%.1f deg/frame)" % rad_to_deg(max_step))
	# left -> up -> left again: no spin the long way round
	a.face("left", true)
	a.face("up")
	var trav := 0.0
	prev = a._yaw
	for i in 60:
		_tick(a, DT)
		trav += absf(angle_difference(prev, a._yaw))
		prev = a._yaw
	t.check(trav < PI / 2.0 + 0.05, "left -> up is a quarter turn (%.1f deg)" % rad_to_deg(trav))
	# place() snaps
	a.place(Vector2i(4, 4), "down")
	t.check(a._yaw == 0.0, "place() snaps the facing")
	a.queue_free()

static func _test_hop(t: TestSuite, root: Node) -> void:
	var a := _actor(root, "red")
	a.start_move("right", 2.0, true, false)
	var n := 0
	var peak := 0.0
	var start_x := a.position.x
	var mono := true
	var px := start_x
	while a.moving and n < 200:
		_tick(a, DT)
		peak = maxf(peak, a._body.position.y)
		if a.position.x < px - 1e-6:
			mono = false
		px = a.position.x
		n += 1
	t.check(n >= 15 and n <= 18, "a ledge hop takes 16 frames (%d)" % n)
	t.check(a.cell == Vector2i(4, 2) and is_equal_approx(a.position.x, OwActor.cell_pos(Vector2i(4, 2)).x), "a hop lands two cells on")
	t.check(peak > WorldData.px_h(9.0) and peak <= WorldData.px_h(OwActor.HOP_PX) * 1.001, "hop apex is %.3f (px_h 12 = %.3f)" % [peak, WorldData.px_h(12.0)])
	t.check(mono and is_equal_approx(a.position.y, 0.0), "the hop lifts the body, not the actor: shadow and camera stay on the ground")
	# landing squash decays back to rest
	var squashed := false
	for i in 60:
		_tick(a, DT)
		if a._body.scale.y < 0.95:
			squashed = true
	t.check(squashed, "landing squashes the body")
	t.check(absf(a._body.scale.y - 1.0) < 0.01 and absf(a._body.position.y) < 0.01, "and it settles back to rest")
	a.queue_free()

static func _test_fallback(t: TestSuite, root: Node) -> void:
	# a character with no animation clips at all still walks (procedural bob) without touching a null player
	var a := OwActor.new()
	root.add_child(a)
	a.setup("no_such_sprite_key_xyz")
	a.set_process(false)
	a._anim = null          # as if the model had no clips at all
	a._proc_bob = true
	a.place(Vector2i(2, 2), "down")
	a.start_move("down", 1.0, false, true)
	var bobbed := false
	var n := 0
	while a.moving and n < 100:
		a._process(DT)
		if a._body and a._body.position.y > 0.005:
			bobbed = true
		n += 1
	t.check(a.cell == Vector2i(2, 3) and not a.moving, "an actor without clips still completes its step")
	t.check(bobbed, "and bobs procedurally when it has no Walk clip")
	a.queue_free()

static func _test_frame_rate(t: TestSuite, root: Node) -> void:
	# the same 6-step chain at 30, 60 and 144 fps arrives at the same place in (nearly) the same time
	var times: Array = []
	for fps in [30.0, 60.0, 144.0]:
		var a := _actor(root, "red")
		var elapsed := 0.0
		var left := 6
		var guard := 0
		while (left > 0 or a.moving) and guard < 5000:
			if not a.moving and left > 0:
				a.start_move("right", 1.0, false, left > 1)
				left -= 1
			a._process(1.0 / fps)
			elapsed += 1.0 / fps
			guard += 1
		times.append(elapsed)
		t.check(a.cell == Vector2i(8, 2) and is_equal_approx(a.position.x, OwActor.cell_pos(Vector2i(8, 2)).x), "6 steps land on the cell at %d fps" % int(fps))
		a.queue_free()
	t.check(absf(float(times[0]) - float(times[2])) < 0.09 and absf(float(times[1]) - float(times[2])) < 0.05,
		"walk time is frame-rate independent (%.3f / %.3f / %.3f s)" % [times[0], times[1], times[2]])
