class_name StartMenu
extends PxScreen
## Port of menus.js startMenu(): POKéDEX / POKéMON / ITEM / <name> / SHARE /
## SAVE / OPTION / EXIT in upstream's frame at (222, 6, 92 wide), over the live
## 3D overworld. Owns every start-menu sub-screen (as siblings, so they draw
## over it): party_menu, bag_menu, pokedex_menu, trainer_card, options_menu,
## town_map, summary_screen, pc_menu. Selecting a row hides this menu, runs the
## sub-screen, and comes back to the same row, like upstream's loop.

var sel := 0
var _items: Array = []
var _returning := false

var party_menu: PartyMenu
var bag_menu: BagMenu
var pokedex_menu: PokedexMenu
var trainer_card: TrainerCard
var options_menu: OptionsMenu
var town_map: TownMap
var summary_screen: SummaryScreen
var pc_menu: PCMenu

func _ready() -> void:
	super()
	var host := get_parent()
	party_menu = PartyMenu.new(); host.add_child(party_menu)
	bag_menu = BagMenu.new(); host.add_child(bag_menu)
	pokedex_menu = PokedexMenu.new(); host.add_child(pokedex_menu)
	trainer_card = TrainerCard.new(); host.add_child(trainer_card)
	options_menu = OptionsMenu.new(); host.add_child(options_menu)
	town_map = TownMap.new(); host.add_child(town_map)
	summary_screen = SummaryScreen.new(); host.add_child(summary_screen)
	pc_menu = PCMenu.new(); host.add_child(pc_menu)
	party_menu.summary_screen = summary_screen
	bag_menu.town_map = town_map
	bag_menu.party_menu = party_menu
	for s: PxScreen in [party_menu, bag_menu, pokedex_menu, trainer_card, options_menu]:
		s.closed.connect(_back)

func is_open() -> bool:
	if visible or busy:
		return true
	for s in [party_menu, bag_menu, pokedex_menu, trainer_card, options_menu, town_map, summary_screen, pc_menu]:
		if s and s.visible:
			return true
	return false

func _on_open() -> void:
	if not _returning:
		UI.sfx("menu")
	_returning = false
	_items = []
	if Story.flag("EVENT_GOT_POKEDEX"):
		_items.append("POKéDEX")
	if not GameState.party.is_empty():
		_items.append("POKéMON")
	_items.append_array(["ITEM", GameState.player_name, "SHARE", "SAVE", "OPTION", "EXIT"])
	sel = mini(sel, _items.size() - 1)

func _back() -> void:
	_returning = true
	open()

func _input_event(e: InputEvent) -> bool:
	var n := _items.size()
	if pressed(e, "move_up", true):
		sel = (sel + n - 1) % n
		UI.sfx("cursor")
	elif pressed(e, "move_down", true):
		sel = (sel + 1) % n
		UI.sfx("cursor")
	elif pressed(e, "confirm"):
		UI.sfx("select")
		_activate(_items[sel])
	elif pressed(e, "cancel") or pressed(e, "menu"):
		close()
	else:
		return false
	return true

func _activate(it: String) -> void:
	match it:
		"POKéDEX":
			close(); pokedex_menu.open()
		"POKéMON":
			close(); party_menu.open()
		"ITEM":
			close(); bag_menu.open()
		"SHARE":
			await say("Share a picture of your adventure! (Not available in this version.)")
		"SAVE":
			if await ask("Would you like to SAVE the game?"):
				if GameState.save():
					UI.sfx("save")
					await say(GameState.player_name + " saved the game!")
				else:
					await say("SAVE FAILED!")
		"OPTION":
			close(); options_menu.open()
		"EXIT":
			close()
		_:
			close(); trainer_card.open()

func _draw() -> void:
	Px.menu(self, _items, sel, 222, 6, 92, -1, 0, Px.frame_count())
