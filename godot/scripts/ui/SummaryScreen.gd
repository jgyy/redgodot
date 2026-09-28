class_name SummaryScreen
extends Control
## A party mon's Summary screen (opened by selecting it in PartyMenu): a live
## 3D preview of its real model plus INFO / STATS / MOVES tabs, cycled with
## left/right. `cancel` returns to PartyMenu.

signal closed

const TABS := ["INFO", "STATS", "MOVES"]

var _preview: Mon3DPreview
var _header: Label
var _tab_labels: Array = []
var _content: Label
var _mon: GameState.PartyMon
var _tab := 0

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(480, 360)
	panel.position = Vector2(-240, -180)
	add_child(panel)

	var root := VBoxContainer.new()
	panel.add_child(root)

	var top := HBoxContainer.new()
	root.add_child(top)
	_preview = Mon3DPreview.new()
	_preview.custom_minimum_size = Vector2(160, 160)
	top.add_child(_preview)

	var top_right := VBoxContainer.new()
	top.add_child(top_right)
	_header = Label.new()
	_header.add_theme_font_size_override("font_size", 22)
	top_right.add_child(_header)

	var tab_row := HBoxContainer.new()
	top_right.add_child(tab_row)
	for t in TABS:
		var l := Label.new()
		l.custom_minimum_size = Vector2(90, 0)
		tab_row.add_child(l)
		_tab_labels.append(l)

	_content = Label.new()
	_content.autowrap_mode = TextServer.AUTOWRAP_WORD
	_content.custom_minimum_size = Vector2(440, 160)
	root.add_child(_content)

	var hint := Label.new()
	hint.text = "(left/right: tab, cancel: back)"
	hint.add_theme_font_size_override("font_size", 13)
	root.add_child(hint)

func open_for(mon: GameState.PartyMon) -> void:
	_mon = mon
	_tab = 0
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_refresh()

func close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _refresh() -> void:
	if _mon == null:
		return
	_preview.show_species(_mon.species_id)
	var sp := GameData.get_species(_mon.species_id)
	_header.text = "No.%03d %s  Lv.%d" % [int(sp.get("dex", 0)), sp.get("name", _mon.species_id), _mon.level]
	for i in range(TABS.size()):
		_tab_labels[i].text = ("▶" if i == _tab else " ") + TABS[i]
	match _tab:
		0: _content.text = _info_text(sp)
		1: _content.text = _stats_text()
		_: _content.text = _moves_text()

func _info_text(sp: Dictionary) -> String:
	var types: Array = sp.get("types", [])
	return "OT           %s\nID No.       %05d\nSPECIES      %s\nTYPE         %s\nSTATUS       %s\nEXP. POINTS  %d" % [
		GameState.player_name, 0, sp.get("name", _mon.species_id), " / ".join(types),
		(_mon.status if _mon.status != "" else "OK"), _mon.xp,
	]

func _stats_text() -> String:
	return "HP    %d/%d\nATTACK   %d\nDEFENSE  %d\nSPEED    %d\nSPECIAL  %d" % [
		_mon.hp, _mon.max_hp, _mon.stat("atk"), _mon.stat("def"), _mon.stat("spd"), _mon.stat("spc"),
	]

func _moves_text() -> String:
	var lines: Array = []
	for m in _mon.moves:
		var mv := GameData.get_move(m)
		lines.append("%-14s PP %d/%d" % [mv.get("name", m), _mon.pp.get(m, 0), mv.get("pp", 0)])
	return "\n".join(lines) if not lines.is_empty() else "(no moves)"

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("move_left"):
		_tab = (_tab - 1 + TABS.size()) % TABS.size()
		_refresh()
	elif event.is_action_pressed("move_right"):
		_tab = (_tab + 1) % TABS.size()
		_refresh()
	elif event.is_action_pressed("cancel"):
		close()
		closed.emit()
	else:
		return
	get_viewport().set_input_as_handled()
