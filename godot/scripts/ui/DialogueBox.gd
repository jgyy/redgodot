class_name DialogueBox
extends Control
## Bottom-of-screen text box for NPC/sign dialogue and story beats. Follows the
## project's overlay convention (see PartyMenu.gd): built entirely in code,
## hidden by default, toggled via input rather than a .tscn.
##
## Usage: dialogue_box.show_lines(["Line one.", "Line two."]) then `confirm`
## advances a line at a time; the box closes and emits `finished` after the
## last line (or immediately on `cancel`, which fast-forwards/skips).

signal finished

var _panel: PanelContainer
var _label: Label
var _hint: Label
var _lines: Array = []
var _index: int = 0

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	_panel = PanelContainer.new()
	_panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	_panel.offset_left = 16
	_panel.offset_right = -16
	_panel.offset_top = -128
	_panel.offset_bottom = -16
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.12, 0.14, 0.32, 0.96)
	style.border_color = Color(0.85, 0.25, 0.25)
	style.set_border_width_all(3)
	style.set_corner_radius_all(6)
	style.content_margin_left = 16
	style.content_margin_right = 16
	style.content_margin_top = 12
	style.content_margin_bottom = 12
	_panel.add_theme_stylebox_override("panel", style)
	add_child(_panel)

	var vbox := VBoxContainer.new()
	_panel.add_child(vbox)
	_label = Label.new()
	_label.autowrap_mode = TextServer.AUTOWRAP_WORD
	_label.add_theme_font_size_override("font_size", 20)
	_label.custom_minimum_size = Vector2(0, 64)
	vbox.add_child(_label)
	_hint = Label.new()
	_hint.text = "▼ (confirm to continue)"
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_hint.add_theme_font_size_override("font_size", 14)
	vbox.add_child(_hint)

func show_lines(lines: Array) -> void:
	_lines = lines.duplicate()
	_index = 0
	if _lines.is_empty():
		return
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_label.text = _lines[0]

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("confirm"):
		_advance()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("cancel"):
		_close()
		get_viewport().set_input_as_handled()

func _advance() -> void:
	_index += 1
	if _index >= _lines.size():
		_close()
		return
	_label.text = _lines[_index]

func _close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	finished.emit()
