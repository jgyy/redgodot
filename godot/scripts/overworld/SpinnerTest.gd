extends Node
## --scene=ow_spinner_test : steps onto a Viridian Gym arrow tile and checks the ride ends on the stop tile
## (upstream fieldmoves.js afterStep).  Exits 1 on failure so CI can run it.

func run() -> void:
	GameState.new_game("CHARMANDER")
	GameState.current_map = "ViridianGym"
	GameState.player_cell = Vector2i(4, 13)
	SceneRouter.goto_overworld()
	await get_tree().create_timer(1.0).timeout
	var ow: Node = get_tree().root.find_child("Overworld", true, false)
	var ok: bool = ow != null and ow.cell_label(ow.player.cell) == "spinner_stop"
	if ok:
		ow._step_player("right", 1.0, ow.can_move(ow.player, "right"))
		await get_tree().create_timer(3.0).timeout
		ok = ow.player.cell == Vector2i(13, 13) and not ow.is_spinning()
	print("[spinner] ", "OK" if ok else "FAILED", " end cell ", ow.player.cell if ow else "-")
	get_tree().quit(0 if ok else 1)
