extends Node3D
## Root of the 3D overworld: builds the current map, places the player, follows
## with a fixed-angle 3rd-person camera (in the spirit of the original top-down
## view, tilted into 3D), and reacts to warps / route connections / wild encounters.

@onready var _map_root: Node3D = $MapRoot
@onready var _camera_rig: Node3D = $CameraRig
@onready var _camera: Camera3D = $CameraRig/Camera3D
@onready var _sun: DirectionalLight3D = $Sun

var _map_loader: MapLoader
var _player: Player

var _party_menu: PartyMenu

func _ready() -> void:
	_build_player()
	_load_current_map()
	_party_menu = PartyMenu.new()
	add_child(_party_menu)

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
