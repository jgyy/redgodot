class_name TrainerCard
extends Control
## The player's own Trainer Card (Start Menu's <name> row): name/ID/money/
## Pokedex-seen count/play time plus a row of the 8 Kanto Gym badges, filled
## in as GameState.badges is actually earned.

signal closed

const BADGES := ["BOULDER", "CASCADE", "THUNDER", "RAINBOW", "SOUL", "MARSH", "VOLCANO", "EARTH"]

var _info_label: Label
var _badge_row: HBoxContainer
var _badge_labels: Array = []

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(420, 300)
	panel.position = Vector2(-210, -150)
	add_child(panel)

	var root := VBoxContainer.new()
	panel.add_child(root)
	var title := Label.new()
	title.text = "TRAINER CARD"
	title.add_theme_font_size_override("font_size", 20)
	root.add_child(title)

	_info_label = Label.new()
	root.add_child(_info_label)

	var badge_title := Label.new()
	badge_title.text = "BADGES"
	root.add_child(badge_title)
	_badge_row = HBoxContainer.new()
	root.add_child(_badge_row)
	for b in BADGES:
		var l := Label.new()
		l.custom_minimum_size = Vector2(46, 0)
		_badge_row.add_child(l)
		_badge_labels.append(l)

	var hint := Label.new()
	hint.text = "(cancel: back)"
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
	var seconds := int(GameState.play_seconds)
	_info_label.text = "NAME     %s\nID No.   %05d\nMONEY    $%d\nPOKéDEX  %d\nTIME     %d:%02d" % [
		GameState.player_name, 0, GameState.money, GameState.seen_species.size(),
		seconds / 60, seconds % 60,
	]
	for i in range(BADGES.size()):
		_badge_labels[i].text = ("●\n" if GameState.badges.has(BADGES[i]) else "○\n") + str(i + 1)

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("cancel") or event.is_action_pressed("confirm"):
		close()
		closed.emit()
		get_viewport().set_input_as_handled()
