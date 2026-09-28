class_name PartyMenu
extends Control
## Party overview reached from the Start Menu's POKéMON entry: lists each
## party member's name/level/HP, navigable with up/down; `confirm` opens that
## mon's Summary screen, `cancel` returns to the Start Menu.

signal closed
signal mon_selected(mon: GameState.PartyMon)

var _panel: PanelContainer
var _list: VBoxContainer
var _rows: Array = []
var _index := 0

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	_panel = PanelContainer.new()
	_panel.set_anchors_preset(Control.PRESET_CENTER)
	_panel.custom_minimum_size = Vector2(360, 280)
	_panel.position = Vector2(-180, -140)
	add_child(_panel)

	var vbox := VBoxContainer.new()
	_panel.add_child(vbox)
	var title := Label.new()
	title.text = "PARTY — choose a POKéMON"
	title.add_theme_font_size_override("font_size", 20)
	vbox.add_child(title)
	_list = VBoxContainer.new()
	vbox.add_child(_list)
	var hint := Label.new()
	hint.text = "(confirm: summary, cancel: back)"
	hint.add_theme_font_size_override("font_size", 13)
	vbox.add_child(hint)

func open() -> void:
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_index = 0
	_refresh()

func close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _refresh() -> void:
	for c in _list.get_children():
		c.queue_free()
	_rows.clear()
	for i in range(GameState.party.size()):
		var m: GameState.PartyMon = GameState.party[i]
		var sp := GameData.get_species(m.species_id)
		var l := Label.new()
		var prefix := "▶ " if i == _index else "   "
		l.text = "%s%s  Lv.%d  HP %d/%d" % [prefix, sp.get("name", m.species_id), m.level, m.hp, m.max_hp]
		_list.add_child(l)
		_rows.append(l)

func _unhandled_input(event: InputEvent) -> void:
	if not visible or GameState.party.is_empty():
		if visible and event.is_action_pressed("cancel"):
			close(); closed.emit(); get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("move_up"):
		_index = (_index - 1 + GameState.party.size()) % GameState.party.size()
		_refresh()
	elif event.is_action_pressed("move_down"):
		_index = (_index + 1) % GameState.party.size()
		_refresh()
	elif event.is_action_pressed("confirm"):
		close()
		mon_selected.emit(GameState.party[_index])
	elif event.is_action_pressed("cancel"):
		close()
		closed.emit()
	else:
		return
	get_viewport().set_input_as_handled()
