extends Node
## Contact sheet of move animations: for each move in --moves=A,B,C (or --moves=all) freezes the animation at each
## fraction in --ts=0.15,0.35,0.55,0.8 and stacks the battle view crops into one PNG (one row per move).
##   godot4 --path godot --rendering-driver opengl3 -- --scene=vfx_sheet --screenshot=/tmp/sheet.png
##          --moves=FLAMETHROWER,THUNDERBOLT --ts=0.2,0.4,0.6,0.85 [--attacker=p|e] [--scale=0.5]
##          [--player=CHARIZARD --enemy=BLASTOISE --env=grass]
## Runs inside one battle scene, so a whole sheet takes seconds (needs a display: xvfb-run).

func run(battle: Node, args: Dictionary, out_png: String) -> void:
	var moves: Array = []
	var want := String(args.get("moves", "FLAMETHROWER"))
	if want == "all":
		moves = BattleVfx.MOVES.keys()
	else:
		moves = Array(want.split(","))
	var ts: Array = []
	for t in String(args.get("ts", "0.15,0.35,0.55,0.8")).split(","):
		ts.append(float(t))
	var k := String(args.get("attacker", "p"))
	var sc := float(args.get("scale", "0.5"))
	var crop := Rect2i(0, 40, 960, 380)
	var cw := int(crop.size.x * sc)
	var ch := int(crop.size.y * sc)
	var sheet := Image.create(cw * ts.size(), ch * moves.size(), false, Image.FORMAT_RGBA8)
	var total_frames := 0
	for mi in moves.size():
		var mv: String = moves[mi]
		var n: int = battle.vfx_frames(mv, k)
		total_frames += maxi(n, 0)
		print("[vfx_sheet] %s frames=%d" % [mv, n])
		for ti in ts.size():
			battle._frozen = false
			await battle._pose_vfx(mv, k, ts[ti])
			await RenderingServer.frame_post_draw
			var img := get_viewport().get_texture().get_image()
			var part := img.get_region(crop)
			if sc != 1.0:
				part.resize(cw, ch, Image.INTERPOLATE_LANCZOS)
			sheet.blit_rect(part, Rect2i(0, 0, cw, ch), Vector2i(ti * cw, mi * ch))
	sheet.save_png(out_png)
	print("[vfx_sheet] saved ", out_png, " (", moves.size(), " moves, ", total_frames, " total frames)")
	get_tree().quit()
	await get_tree().create_timer(3600.0).timeout
