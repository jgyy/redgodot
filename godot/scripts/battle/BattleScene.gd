extends Node3D
## Turn-based 3D battle scene. Scope for this pass: wild single-Pokemon battles
## (FIGHT + RUN), using the ported Gen-1 damage formula in BattleMath. Trainer
## battles are data-ready (pokedata.json trainerClasses/parties) but the
## party-switch UI is documented future work (see README roadmap).

@onready var _player_slot: Node3D = $PlayerSlot
@onready var _enemy_slot: Node3D = $EnemySlot
@onready var _camera: Camera3D = $Camera3D

var _player_actor: PokemonActor
var _enemy_actor: PokemonActor
var _player_mon: GameState.PartyMon
var _enemy_mon: GameState.PartyMon
var _encounter: Dictionary
var _rng := RandomNumberGenerator.new()
var _busy := false

var _ui: Control
var _msg_label: Label
var _player_hp_bar: ProgressBar
var _enemy_hp_bar: ProgressBar
var _move_buttons: Array = []
var _action_panel: Panel

func _ready() -> void:
	_rng.randomize()
	_build_ui()

func setup(encounter: Dictionary) -> void:
	_encounter = encounter
	_player_mon = GameState.first_healthy_mon()
	if _player_mon == null:
		_end_battle("player_had_no_mon")
		return

	_enemy_mon = GameState.PartyMon.new(encounter.get("species", "RATTATA"), encounter.get("level", 3))

	_player_actor = PokemonActor.new()
	_player_slot.add_child(_player_actor)
	_player_actor.setup(_player_mon.species_id)

	_enemy_actor = PokemonActor.new()
	_enemy_slot.add_child(_enemy_actor)
	_enemy_actor.setup(_enemy_mon.species_id)

	_refresh_hp_bars()
	var species_name: String = GameData.get_species(_enemy_mon.species_id).get("name", _enemy_mon.species_id)
	_say("A wild %s appeared!" % species_name)
	_show_action_menu()

func _build_ui() -> void:
	_ui = Control.new()
	_ui.name = "UI"
	_ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_ui)

	var msg_panel := PanelContainer.new()
	msg_panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	msg_panel.offset_top = -220
	msg_panel.offset_bottom = -152
	msg_panel.offset_left = 10
	msg_panel.offset_right = -10
	_ui.add_child(msg_panel)
	_msg_label = Label.new()
	_msg_label.autowrap_mode = TextServer.AUTOWRAP_WORD
	_msg_label.add_theme_font_size_override("font_size", 20)
	msg_panel.add_child(_msg_label)

	_enemy_hp_bar = _make_hp_bar()
	_enemy_hp_bar.set_anchors_preset(Control.PRESET_TOP_LEFT)
	_enemy_hp_bar.position = Vector2(20, 20)
	_ui.add_child(_enemy_hp_bar)

	_player_hp_bar = _make_hp_bar()
	_player_hp_bar.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_player_hp_bar.position = Vector2(-220, 260)
	_ui.add_child(_player_hp_bar)

	_action_panel = Panel.new()
	_action_panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	_action_panel.offset_top = -142
	_action_panel.offset_bottom = -10
	_action_panel.offset_left = 10
	_action_panel.offset_right = -10
	_action_panel.visible = false
	_ui.add_child(_action_panel)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.set_anchors_preset(Control.PRESET_FULL_RECT)
	_action_panel.add_child(grid)
	for i in range(4):
		var b := Button.new()
		b.text = "-"
		b.custom_minimum_size = Vector2(150, 40)
		b.pressed.connect(_on_move_pressed.bind(i))
		grid.add_child(b)
		_move_buttons.append(b)
	var run_btn := Button.new()
	run_btn.text = "RUN"
	run_btn.custom_minimum_size = Vector2(150, 40)
	run_btn.pressed.connect(_on_run_pressed)
	grid.add_child(run_btn)

func _make_hp_bar() -> ProgressBar:
	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(200, 24)
	bar.show_percentage = false
	return bar

func _refresh_hp_bars() -> void:
	_player_hp_bar.max_value = _player_mon.max_hp
	_player_hp_bar.value = _player_mon.hp
	_enemy_hp_bar.max_value = _enemy_mon.max_hp
	_enemy_hp_bar.value = _enemy_mon.hp

func _show_action_menu() -> void:
	_action_panel.visible = true
	for i in range(_move_buttons.size()):
		var btn: Button = _move_buttons[i]
		if i < _player_mon.moves.size():
			var mid: String = _player_mon.moves[i]
			btn.text = "%s (%d)" % [mid, _player_mon.pp.get(mid, 0)]
			btn.disabled = _player_mon.pp.get(mid, 0) <= 0
		else:
			btn.text = "-"
			btn.disabled = true

func _say(text: String) -> void:
	_msg_label.text = text

func _on_move_pressed(index: int) -> void:
	if _busy or index >= _player_mon.moves.size():
		return
	_action_panel.visible = false
	_run_turn(_player_mon.moves[index])

func _on_run_pressed() -> void:
	if _busy:
		return
	if _encounter.get("kind", "wild") == "wild":
		_say("Got away safely!")
		_action_panel.visible = false
		await get_tree().create_timer(0.8).timeout
		_end_battle("ran")
	else:
		_say("Can't run from a trainer battle!")

func _run_turn(player_move_id: String) -> void:
	_busy = true
	var enemy_moves: Array = GameData.get_species(_enemy_mon.species_id).get("moves1", ["TACKLE"])
	var enemy_move_id: String = enemy_moves[_rng.randi_range(0, enemy_moves.size() - 1)] if not enemy_moves.is_empty() else "TACKLE"

	var player_first := _player_mon.stat("spd") >= _enemy_mon.stat("spd")
	if player_first:
		await _execute_move(_player_mon, _enemy_mon, _player_actor, _enemy_actor, player_move_id, true)
		if _enemy_mon.is_fainted():
			await _on_faint(false)
			return
		await _execute_move(_enemy_mon, _player_mon, _enemy_actor, _player_actor, enemy_move_id, false)
		if _player_mon.is_fainted():
			await _on_faint(true)
			return
	else:
		await _execute_move(_enemy_mon, _player_mon, _enemy_actor, _player_actor, enemy_move_id, false)
		if _player_mon.is_fainted():
			await _on_faint(true)
			return
		await _execute_move(_player_mon, _enemy_mon, _player_actor, _enemy_actor, player_move_id, true)
		if _enemy_mon.is_fainted():
			await _on_faint(false)
			return

	_busy = false
	_show_action_menu()

func _execute_move(attacker: GameState.PartyMon, defender: GameState.PartyMon,
		attacker_actor: PokemonActor, defender_actor: PokemonActor, move_id: String, attacker_is_player: bool) -> void:
	var move := GameData.get_move(move_id)
	if move.is_empty():
		return
	attacker.pp[move_id] = max(0, attacker.pp.get(move_id, 0) - 1)

	var atk_name: String = GameData.get_species(attacker.species_id).get("name", attacker.species_id)
	_say("%s used %s!" % [atk_name, move.get("name", move_id)])
	attacker_actor.play("Attack")
	await get_tree().create_timer(0.45).timeout

	var move_type: String = move.get("type", "NORMAL")
	var physical: bool = int(move.get("power", 0)) > 0
	var atk_stat: int = attacker.stat("atk" if physical else "spc")
	var def_stat: int = max(1, defender.stat("def" if physical else "spc"))

	if not BattleMath.accuracy_check(move.get("acc", 100), _rng):
		_say("But it missed!")
		return

	var is_crit := BattleMath.roll_crit(attacker.stat("spd"), false, _rng)
	var dmg := BattleMath.calc_damage(attacker.level, move.get("power", 0), atk_stat, def_stat,
		move_type, attacker.types(), defender.types(), is_crit, _rng)

	defender.hp = max(0, defender.hp - dmg)
	_refresh_hp_bars()
	if is_crit and dmg > 0:
		_say("A critical hit!")
		await get_tree().create_timer(0.4).timeout
	var eff := GameData.type_multiplier(move_type, defender.types())
	if eff > 1.0 and dmg > 0:
		_say("It's super effective!")
		await get_tree().create_timer(0.4).timeout
	elif eff < 1.0 and eff > 0.0 and dmg > 0:
		_say("It's not very effective...")
		await get_tree().create_timer(0.4).timeout
	elif eff == 0.0:
		_say("It had no effect...")
		await get_tree().create_timer(0.4).timeout

func _on_faint(player_fainted: bool) -> void:
	if player_fainted:
		_say("%s fainted!" % _player_mon.nickname)
		await get_tree().create_timer(1.0).timeout
		if GameState.party_wiped():
			_end_battle("player_wiped")
		else:
			_player_mon = GameState.first_healthy_mon()
			_player_actor.setup(_player_mon.species_id)
			_refresh_hp_bars()
			_busy = false
			_show_action_menu()
	else:
		var name: String = GameData.get_species(_enemy_mon.species_id).get("name", _enemy_mon.species_id)
		_say("Enemy %s fainted!" % name)
		var xp := BattleMath.xp_yield(GameData.get_species(_enemy_mon.species_id).get("baseExp", 50), _enemy_mon.level, false)
		_player_mon.xp += xp
		await get_tree().create_timer(1.0).timeout
		_say("Gained %d EXP. Points!" % xp)
		await get_tree().create_timer(1.0).timeout
		_end_battle("won")

func _end_battle(result: String) -> void:
	_busy = false
	SceneRouter.end_battle(result)
