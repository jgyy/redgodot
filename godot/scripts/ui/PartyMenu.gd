class_name PartyMenu
extends Control
## Minimal start-menu party overview: press `menu` to open/close, shows each
## party member's name/level/HP. (Bag/Pokedex/Save screens are documented
## roadmap items, not implemented in this pass.)

var _panel: PanelContainer
var _list: VBoxContainer

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	_panel = PanelContainer.new()
	_panel.set_anchors_preset(Control.PRESET_CENTER)
	_panel.custom_minimum_size = Vector2(280, 240)
	_panel.position = Vector2(-140, -120)
	add_child(_panel)

	var vbox := VBoxContainer.new()
	_panel.add_child(vbox)
	var title := Label.new()
	title.text = "PARTY"
	title.add_theme_font_size_override("font_size", 22)
	vbox.add_child(title)
	_list = VBoxContainer.new()
	vbox.add_child(_list)
	var hint := Label.new()
	hint.text = "(START to close)"
	vbox.add_child(hint)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("menu"):
		visible = not visible
		mouse_filter = Control.MOUSE_FILTER_STOP if visible else Control.MOUSE_FILTER_IGNORE
		if visible:
			_refresh()
		get_viewport().set_input_as_handled()

func _refresh() -> void:
	for c in _list.get_children():
		c.queue_free()
	for m in GameState.party:
		var sp := GameData.get_species(m.species_id)
		var l := Label.new()
		l.text = "%s  Lv.%d  HP %d/%d" % [sp.get("name", m.species_id), m.level, m.hp, m.max_hp]
		_list.add_child(l)
