class_name StartMenu
extends Control
## The `menu` action's top-level Start Menu (POKéDEX/POKéMON/ITEM/<name>/SHARE/
## SAVE/OPTION/EXIT), matching the original game's structure: selecting your
## own name opens the Trainer Card, and the Town Map is reached by picking the
## TOWN MAP item from the bag — both real mechanics from the source game, not
## flattened shortcuts. Owns (and lazily wires up) every start-menu-reachable
## sub-screen as a child, following the PartyMenu overlay convention.

var ROW_KEYS := ["POKéDEX", "POKéMON", "ITEM", "", "SHARE", "SAVE", "OPTION", "EXIT"]

var _panel: PanelContainer
var _list: VBoxContainer
var _row_labels: Array = []
var _index := 0
var _toast: DialogueBox

var party_menu: PartyMenu
var bag_menu: BagMenu
var pokedex_menu: PokedexMenu
var trainer_card: TrainerCard
var options_menu: OptionsMenu
var town_map: TownMap
var summary_screen: SummaryScreen

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	_panel = PanelContainer.new()
	_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_panel.custom_minimum_size = Vector2(260, 300)
	_panel.position = Vector2(-276, 16)
	add_child(_panel)
	_list = VBoxContainer.new()
	_panel.add_child(_list)
	for i in range(ROW_KEYS.size()):
		var l := Label.new()
		l.add_theme_font_size_override("font_size", 20)
		_list.add_child(l)
		_row_labels.append(l)

	# Submenus are added as siblings (children of our own parent), not children
	# of this Control: a child's `visible` is meaningless while an ancestor is
	# hidden, and StartMenu hides itself the moment any of these opens.
	var host := get_parent()
	_toast = DialogueBox.new()
	host.add_child(_toast)

	party_menu = PartyMenu.new(); host.add_child(party_menu)
	bag_menu = BagMenu.new(); host.add_child(bag_menu)
	pokedex_menu = PokedexMenu.new(); host.add_child(pokedex_menu)
	trainer_card = TrainerCard.new(); host.add_child(trainer_card)
	options_menu = OptionsMenu.new(); host.add_child(options_menu)
	town_map = TownMap.new(); host.add_child(town_map)
	summary_screen = SummaryScreen.new(); host.add_child(summary_screen)

	party_menu.closed.connect(open)
	bag_menu.closed.connect(open)
	pokedex_menu.closed.connect(open)
	trainer_card.closed.connect(open)
	options_menu.closed.connect(open)
	town_map.closed.connect(func(): bag_menu.open())
	summary_screen.closed.connect(func(): party_menu.open())
	party_menu.mon_selected.connect(func(m): summary_screen.open_for(m))
	bag_menu.item_selected.connect(_on_bag_item_selected)

func is_open() -> bool:
	return visible or party_menu.visible or bag_menu.visible or pokedex_menu.visible \
		or trainer_card.visible or options_menu.visible or town_map.visible or summary_screen.visible

func open() -> void:
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_index = 0
	_refresh()

func close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _refresh() -> void:
	ROW_KEYS[3] = GameState.player_name
	for i in range(ROW_KEYS.size()):
		var prefix := "▶ " if i == _index else "   "
		_row_labels[i].text = prefix + ROW_KEYS[i]

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("move_up"):
		_index = (_index - 1 + ROW_KEYS.size()) % ROW_KEYS.size()
		_refresh()
	elif event.is_action_pressed("move_down"):
		_index = (_index + 1) % ROW_KEYS.size()
		_refresh()
	elif event.is_action_pressed("confirm"):
		_activate(_index)
	elif event.is_action_pressed("cancel") or event.is_action_pressed("menu"):
		close()
	get_viewport().set_input_as_handled()

func _on_bag_item_selected(item_id: String) -> void:
	if item_id == "TOWN_MAP":
		bag_menu.close()
		town_map.open()

func _activate(i: int) -> void:
	match ROW_KEYS[i]:
		"POKéDEX":
			close(); pokedex_menu.open()
		"POKéMON":
			close(); party_menu.open()
		"ITEM":
			close(); bag_menu.open()
		"SHARE":
			close(); _toast.show_lines(["Link feature not available in this version."])
			_toast.finished.connect(open, CONNECT_ONE_SHOT)
		"SAVE":
			GameState.save()
			close(); _toast.show_lines(["%s saved the game!" % GameState.player_name])
			_toast.finished.connect(open, CONNECT_ONE_SHOT)
		"OPTION":
			close(); options_menu.open()
		"EXIT":
			close()
		_:
			close(); trainer_card.open()
