class_name OptionsMenu
extends Control
## Options screen (Start Menu's OPTION entry): TEXT SPEED and SOUND, backed by
## real GameState fields (GameState.text_speed feeds DialogueBox's future
## typewriter pacing; sound_on is read wherever SFX are triggered).

signal closed

const TEXT_SPEEDS := ["SLOW", "NORMAL", "FAST"]

var _rows: Array = []
var _index := 0

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(320, 200)
	panel.position = Vector2(-160, -100)
	add_child(panel)

	var root := VBoxContainer.new()
	panel.add_child(root)
	var title := Label.new()
	title.text = "OPTIONS"
	title.add_theme_font_size_override("font_size", 20)
	root.add_child(title)

	for _i in range(2):
		var l := Label.new()
		root.add_child(l)
		_rows.append(l)

	var hint := Label.new()
	hint.text = "(left/right: change, cancel: back)"
	hint.add_theme_font_size_override("font_size", 13)
	root.add_child(hint)

func open() -> void:
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_refresh()

func close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _refresh() -> void:
	var p0 := "▶ " if _index == 0 else "   "
	var p1 := "▶ " if _index == 1 else "   "
	_rows[0].text = "%sTEXT SPEED   %s" % [p0, TEXT_SPEEDS[TEXT_SPEEDS.find(GameState.text_speed)]]
	_rows[1].text = "%sSOUND        %s" % [p1, "ON" if GameState.sound_on else "OFF"]

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("move_up") or event.is_action_pressed("move_down"):
		_index = 1 - _index
		_refresh()
	elif event.is_action_pressed("move_left") or event.is_action_pressed("move_right") or event.is_action_pressed("confirm"):
		if _index == 0:
			var i := TEXT_SPEEDS.find(GameState.text_speed)
			GameState.text_speed = TEXT_SPEEDS[(i + 1) % TEXT_SPEEDS.size()]
		else:
			GameState.sound_on = not GameState.sound_on
		_refresh()
	elif event.is_action_pressed("cancel"):
		close()
		closed.emit()
	else:
		return
	get_viewport().set_input_as_handled()
