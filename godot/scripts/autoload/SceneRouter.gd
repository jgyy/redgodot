extends Node
## Central scene-transition hub. The Main scene keeps a single child under
## %ActiveScene and this autoload swaps it out, so battle <-> overworld <-> menus
## don't need to know about each other directly.

signal battle_started(encounter: Dictionary)
signal battle_ended(result: String)

const OVERWORLD := "res://scenes/Overworld.tscn"
const BATTLE := "res://scenes/Battle.tscn"
const TITLE := "res://scenes/Title.tscn"

var _root: Node = null
var _active: Node = null
var _return_scene: PackedScene = null
var _return_state: Dictionary = {}

func register_root(root: Node) -> void:
	_root = root

func _swap(scene: PackedScene) -> Node:
	if _active:
		_active.queue_free()
	_active = scene.instantiate()
	_root.add_child(_active)
	return _active

func goto_title() -> void:
	_swap(load(TITLE))

func goto_overworld() -> void:
	_swap(load(OVERWORLD))

## Starts a battle, remembering where to return to. `encounter` describes the
## opponent(s): {kind:"wild", species, level} or {kind:"trainer", trainer_key, party}
func start_battle(encounter: Dictionary) -> void:
	_return_state = {"map": GameState.current_map, "cell": GameState.player_cell, "facing": GameState.player_facing}
	var battle_scene: Node = _swap(load(BATTLE))
	battle_started.emit(encounter)
	if battle_scene.has_method("setup"):
		battle_scene.setup(encounter)

func end_battle(result: String) -> void:
	battle_ended.emit(result)
	goto_overworld()
