class_name PokedexMenu
extends Control
## The National Pokedex (Start Menu's POKéDEX entry): scrollable list of all
## 151 species in dex order, marking species GameState has seen/caught, with
## a live 3D preview of the selected species and SEEN/OWN totals.

signal closed

var _list: VBoxContainer
var _scroll: ScrollContainer
var _rows: Array = []
var _index := 0
var _preview: Mon3DPreview
var _totals_label: Label
var _species_ids: Array = []  # GameData.dex_order with its leading null (unused dex #0) dropped

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(560, 380)
	panel.position = Vector2(-280, -190)
	add_child(panel)

	var root := HBoxContainer.new()
	panel.add_child(root)

	_scroll = ScrollContainer.new()
	_scroll.custom_minimum_size = Vector2(300, 360)
	root.add_child(_scroll)
	_list = VBoxContainer.new()
	_scroll.add_child(_list)

	var right := VBoxContainer.new()
	root.add_child(right)
	_preview = Mon3DPreview.new()
	_preview.custom_minimum_size = Vector2(200, 200)
	right.add_child(_preview)
	_totals_label = Label.new()
	right.add_child(_totals_label)
	var hint := Label.new()
	hint.text = "(up/down: browse, cancel: back)"
	hint.add_theme_font_size_override("font_size", 13)
	right.add_child(hint)

func open() -> void:
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	if _rows.is_empty():
		_build_rows()
	_refresh()

func close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _build_rows() -> void:
	_species_ids = GameData.dex_order.filter(func(sid): return sid != null and sid != "")
	for sid in _species_ids:
		var l := Label.new()
		l.name = sid
		_list.add_child(l)
		_rows.append(l)

func _refresh() -> void:
	var seen := 0
	var owned := 0
	for i in range(_species_ids.size()):
		var sid: String = _species_ids[i]
		var sp := GameData.get_species(sid)
		var mark := "   "
		if GameState.caught_species.has(sid):
			mark = " ● "
			owned += 1
			seen += 1
		elif GameState.seen_species.has(sid):
			mark = " ○ "
			seen += 1
		var prefix := "▶" if i == _index else " "
		var label: Label = _rows[i]
		label.text = "%s%03d%s%s" % [prefix, int(sp.get("dex", i + 1)), mark, sp.get("name", sid)]
	_totals_label.text = "SEEN  %d\nOWN   %d" % [seen, owned]
	if not _species_ids.is_empty():
		_preview.show_species(_species_ids[_index])

func _unhandled_input(event: InputEvent) -> void:
	if not visible or _species_ids.is_empty():
		return
	if event.is_action_pressed("move_up"):
		_index = (_index - 1 + _species_ids.size()) % _species_ids.size()
		_refresh()
		_scroll.scroll_vertical = max(0, _index * 20 - 100)
	elif event.is_action_pressed("move_down"):
		_index = (_index + 1) % _species_ids.size()
		_refresh()
		_scroll.scroll_vertical = max(0, _index * 20 - 100)
	elif event.is_action_pressed("cancel"):
		close()
		closed.emit()
	else:
		return
	get_viewport().set_input_as_handled()
