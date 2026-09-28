extends Node3D
## Title screen: shows the logo, a rotating starter preview, and lets the
## player pick Bulbasaur / Charmander / Squirtle to start a new game.

const STARTERS := ["BULBASAUR", "CHARMANDER", "SQUIRTLE"]

@onready var _slot: Node3D = $StarterSlot
var _actor: PokemonActor
var _starter_index := 0

func _ready() -> void:
	_actor = PokemonActor.new()
	_slot.add_child(_actor)
	_show_starter()
	_build_ui()

func _show_starter() -> void:
	_actor.setup(STARTERS[_starter_index])

func _build_ui() -> void:
	var ui := Control.new()
	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(ui)

	var title := Label.new()
	title.text = "POKEMON CLAUDE RED\n3D"
	title.add_theme_font_size_override("font_size", 40)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.set_anchors_preset(Control.PRESET_TOP_WIDE)
	title.position = Vector2(0, 30)
	ui.add_child(title)

	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	vbox.position = Vector2(-140, -160)
	ui.add_child(vbox)

	var hint := Label.new()
	hint.text = "Choose your starter"
	vbox.add_child(hint)

	var hbox := HBoxContainer.new()
	vbox.add_child(hbox)
	for i in range(STARTERS.size()):
		var b := Button.new()
		b.text = STARTERS[i]
		b.custom_minimum_size = Vector2(90, 40)
		b.pressed.connect(_on_pick.bind(i))
		b.mouse_entered.connect(_on_hover.bind(i))
		hbox.add_child(b)

func _on_hover(i: int) -> void:
	_starter_index = i
	_show_starter()

func _on_pick(i: int) -> void:
	_starter_index = i
	GameState.new_game(STARTERS[i])
	SceneRouter.goto_overworld()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("confirm"):
		GameState.new_game(STARTERS[_starter_index])
		SceneRouter.goto_overworld()
	elif event.is_action_pressed("move_left"):
		_starter_index = (_starter_index - 1 + STARTERS.size()) % STARTERS.size()
		_show_starter()
	elif event.is_action_pressed("move_right"):
		_starter_index = (_starter_index + 1) % STARTERS.size()
		_show_starter()
