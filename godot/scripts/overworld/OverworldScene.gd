extends Node3D
## Root of the 3D overworld: builds the current map, places the player, follows
## with a fixed-angle 3rd-person camera (in the spirit of the original top-down
## view, tilted into 3D), and reacts to warps / route connections / wild encounters.

@onready var _map_root: Node3D = $MapRoot
@onready var _camera_rig: Node3D = $CameraRig
@onready var _camera: Camera3D = $CameraRig/Camera3D
@onready var _sun: DirectionalLight3D = $Sun
@onready var _world_env: WorldEnvironment = $WorldEnvironment

var _map_loader: MapLoader
var _player: Player

var _start_menu: StartMenu
var _dialogue: DialogueBox

var _lighting_period := ""

func _ready() -> void:
	_build_player()
	_load_current_map()
	_update_lighting()
	_dialogue = DialogueBox.new()
	add_child(_dialogue)
	_start_menu = StartMenu.new()
	add_child(_start_menu)

func _update_lighting() -> void:
	var period := GameState.time_period()
	if period == _lighting_period:
		return
	_lighting_period = period
	LightingRig.apply(_sun, _world_env.environment, period)

func _build_player() -> void:
	_player = Player.new()
	_player.name = "Player"
	add_child(_player)
	_player.warped.connect(_on_player_warped)
	_player.encounter_triggered.connect(_on_encounter)

func _load_current_map() -> void:
	for c in _map_root.get_children():
		c.queue_free()
	_map_loader = MapLoader.new()
	_map_root.add_child(_map_loader)
	_map_loader.load_map(GameState.current_map)
	_player.place(_map_loader, GameState.player_cell)
	_update_camera()

func _process(_dt: float) -> void:
	if _player:
		_update_camera()
		_player.input_locked = _start_menu.is_open() or _dialogue.visible
	_update_lighting()

func _unhandled_input(event: InputEvent) -> void:
	if _dialogue.visible or _start_menu.is_open():
		return
	if event.is_action_pressed("menu"):
		_start_menu.open()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("confirm"):
		_try_interact()
		get_viewport().set_input_as_handled()

func _try_interact() -> void:
	if _player == null or _map_loader == null:
		return
	var target := _player.facing_cell()
	var npc := _map_loader.npc_at(target)
	if not npc.is_empty():
		_dialogue.show_lines(DialogueText.for_obj(npc))
		return
	var sign := _map_loader.sign_at(target)
	if not sign.is_empty():
		_dialogue.show_lines(DialogueText.for_sign(sign, _map_loader.map_name))

func _update_camera() -> void:
	if not _player:
		return
	var target := _player.global_position
	_camera_rig.global_position = _camera_rig.global_position.lerp(target, 0.2)

func _on_player_warped(payload: Dictionary) -> void:
	var to_map: String = payload.get("to", "")
	var target_map_data := GameData.get_map(to_map)
	if target_map_data.is_empty():
		push_warning("[Overworld] warp/connection target map not found: %s" % to_map)
		return

	var w2: int = target_map_data.get("w", 1)
	var h2: int = target_map_data.get("h", 1)
	var arrival := Vector2i(w2 / 2, h2 / 2)

	if payload.get("kind", "") == "warp":
		# Bidirectional warp: arrive at destination map's warps[warp index]
		# (the classic pokered encoding this source data also uses).
		var dest_warps: Array = target_map_data.get("warps", [])
		var idx: int = payload.get("warp_index", 0)
		if idx >= 0 and idx < dest_warps.size():
			var w = dest_warps[idx]
			arrival = Vector2i(int(w.get("x", 0)), int(w.get("y", 0)))
	else:
		# Route connection: enter from the edge that borders the map you left,
		# offset along that edge by the connection's declared alignment offset.
		var offset: Vector2i = payload.get("offset", Vector2i.ZERO)
		match payload.get("dir", ""):
			"north":
				arrival = Vector2i(clampi(_player.cell.x + offset.x, 0, w2 - 1), h2 - 1)
			"south":
				arrival = Vector2i(clampi(_player.cell.x + offset.x, 0, w2 - 1), 0)
			"west":
				arrival = Vector2i(w2 - 1, clampi(_player.cell.y + offset.y, 0, h2 - 1))
			"east":
				arrival = Vector2i(0, clampi(_player.cell.y + offset.y, 0, h2 - 1))

	GameState.current_map = to_map
	GameState.player_cell = arrival
	_load_current_map()

func _on_encounter(species: String, level: int) -> void:
	SceneRouter.start_battle({"kind": "wild", "species": species, "level": level})

## Docs/CI screenshot support (see Main.gd's --scene= menu-key handling):
## opens a given start-menu-reachable screen directly, bypassing input.
func open_menu_for_screenshot(key: String) -> void:
	match key:
		"start_menu": _start_menu.open()
		"party": _start_menu.party_menu.open()
		"summary":
			if not GameState.party.is_empty():
				_start_menu.summary_screen.open_for(GameState.party[0])
		"bag": _start_menu.bag_menu.open()
		"pokedex": _start_menu.pokedex_menu.open()
		"trainer_card": _start_menu.trainer_card.open()
		"town_map": _start_menu.town_map.open()
		"options": _start_menu.options_menu.open()

func show_dialogue_for_screenshot(lines: Array) -> void:
	_dialogue.show_lines(lines)
