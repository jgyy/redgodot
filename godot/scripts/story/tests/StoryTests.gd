class_name StoryTests
extends RefCounted
## Story checks for TestSuite: runs the real ported map scripts against a fake
## Overworld/UI/battle host (like upstream tools/drive.js drives story.js in
## Node). Every script completes synchronously because the fakes never wait.

const FakeHost := preload("res://scripts/story/tests/StoryFakeHost.gd")
const FakeUI := preload("res://scripts/story/tests/StoryFakeUI.gd")

static var battles: Array = []        # encounters started
static var results: Array = []        # scripted results ("win" default)

static func _battle(enc: Dictionary) -> String:
	battles.append(enc)
	return str(results.pop_front()) if not results.is_empty() else "win"

static func run(suite: TestSuite) -> void:
	var saved := {
		"party": GameState.party, "bag": GameState.bag.duplicate(), "badges": GameState.badges.duplicate(),
		"money": GameState.money, "story": GameState.story_to_dict().duplicate(true), "map": GameState.current_map,
		"cell": GameState.player_cell, "facing": GameState.player_facing, "seen": GameState.seen_species.duplicate(),
		"caught": GameState.caught_species.duplicate(),
	}
	var host: Node = FakeHost.new()
	var ui: Node = FakeUI.new()
	Story.fast = true
	Story.host_override = host
	Story.ui_override = ui
	Story.battle_override = _battle
	battles = []
	results = []
	GameState.reset_story_state()
	GameState.party = []
	GameState.bag = {}
	GameState.badges = []
	GameState.money = 3000
	GameState.seen_species = {}
	GameState.caught_species = {}
	GameState.player_name = "RED"

	suite.check(Story.maps.size() > 150, "Story registered the ported map scripts (%d maps)" % Story.maps.size())
	suite.check(Story.maps.has("OaksLab") and Story.maps.has("PewterGym") and Story.maps.has("ChampionsRoom") and Story.maps.has("Daycare"),
		"pallet/early/late/extra modules all registered")
	_pallet(suite, host, ui)
	_parcel_and_dex(suite, host, ui)
	_mart(suite, host, ui)
	_nurse(suite, host, ui)
	_item_ball(suite, host, ui)
	_brock(suite, host, ui)
	_line_of_sight(suite, host, ui)
	_hidden_item(suite, host, ui)
	_mid_game(suite, host, ui)
	suite.check(Story.running == 0, "no story script left running")

	Story.fast = false
	Story.host_override = null
	Story.ui_override = null
	Story.battle_override = Callable()
	GameState.party = saved["party"]
	GameState.bag = saved["bag"]
	GameState.badges = saved["badges"]
	GameState.money = saved["money"]
	GameState.story_from_dict(saved["story"])
	GameState.current_map = saved["map"]
	GameState.player_cell = saved["cell"]
	GameState.player_facing = saved["facing"]
	GameState.seen_species = saved["seen"]
	GameState.caught_species = saved["caught"]
	host.free()
	ui.free()

static func _pallet(suite: TestSuite, host: Node, ui: Node) -> void:
	host.load_map("PalletTown", Vector2i(10, 2), "up")
	suite.check(not host.is_actor_shown("PALLETTOWN_OAK"), "Oak is hidden in Pallet Town at the start")
	host.walk("U")
	suite.check(ui.said_has("[PalletTownOakHeyWaitDontGoOutText]"), "Oak calls out when the player reaches the grass edge")
	suite.check(ui.said_has("[PalletTownOakItsUnsafeText]"), "Oak: it's unsafe")
	suite.check(host.calls.has("emote:PLAYER:!"), "'!' emote over the player")
	suite.check(Story.flag("EVENT_FOLLOWED_OAK_INTO_LAB"), "EVENT_FOLLOWED_OAK_INTO_LAB set")
	suite.check(host.map == "OaksLab", "warped into Oak's Lab (got %s)" % host.map)
	suite.check(host.warps.size() > 0 and host.warps[0][1] == Vector2i(5, 11), "lab entry at (5,11)")
	suite.check(Story.flag("EVENT_OAK_ASKED_TO_CHOOSE_MON"), "lab enter script ran: Oak asks to choose")
	suite.check(host.actor_cell("PLAYER") == Vector2i(5, 4), "player followed Oak to (5,4) (got %s)" % host.actor_cell("PLAYER"))
	suite.check(host.is_actor_shown("OAKSLAB_OAK1") and not host.is_actor_shown("OAKSLAB_OAK2"), "Oak swapped to his desk object")
	suite.check(ui.said_has("[OaksLabOakChooseMonText]"), "Oak's choose-a-POKéMON line")
	# starter pick: YES to Charmander, NO to the nickname
	ui.answers = [true, false]
	host.talk("OAKSLAB_CHARMANDER_POKE_BALL")
	suite.check(GameState.party.size() == 1 and GameState.party[0].species_id == "CHARMANDER", "received CHARMANDER")
	suite.check(GameState.starter == "CHARMANDER" and Story.flag("EVENT_GOT_STARTER"), "starter recorded")
	suite.check(not Story.is_shown("OAKSLAB_CHARMANDER_POKE_BALL", "OaksLab"), "picked ball hidden")
	suite.check(not Story.is_shown("OAKSLAB_SQUIRTLE_POKE_BALL", "OaksLab"), "rival took the SQUIRTLE ball")
	suite.check(host.actor_cell("OAKSLAB_RIVAL") == Vector2i(7, 4), "rival walked below his ball (got %s)" % host.actor_cell("OAKSLAB_RIVAL"))
	suite.check(ui.said_has("[OaksLabRivalIllTakeThisOneText]"), "rival: I'll take this one")
	# rival battle on the way out
	host.walk("DD")
	suite.check(battles.size() == 1 and battles[0].get("trainer_class") == "RIVAL1" and int(battles[0].get("party_index")) == 1,
		"RIVAL1 battle with party 1 (SQUIRTLE)")
	suite.check(battles.size() == 1 and battles[0].get("no_blackout") == true, "lab rival battle can't black out")
	suite.check(Story.flag("EVENT_BATTLED_RIVAL_IN_OAKS_LAB"), "EVENT_BATTLED_RIVAL_IN_OAKS_LAB set")
	suite.check(ui.said_has("[OaksLabRivalSmellYouLaterText]"), "rival: smell you later")
	suite.check(not host.is_actor_shown("OAKSLAB_RIVAL"), "rival left the lab")

static func _parcel_and_dex(suite: TestSuite, host: Node, ui: Node) -> void:
	host.load_map("ViridianMart", Vector2i(3, 7), "up")
	suite.check(Story.bag_has("OAKS_PARCEL") and Story.flag("EVENT_GOT_OAKS_PARCEL"), "Viridian Mart clerk hands over OAK's PARCEL")
	suite.check(ui.said_has("[ViridianMartClerkParcelQuestText]"), "parcel quest text")
	suite.check(host.actor_cell("PLAYER") == Vector2i(2, 5), "player walked up to the counter (got %s)" % host.actor_cell("PLAYER"))
	host.load_map("OaksLab", Vector2i(5, 3), "up")
	host.talk("OAKSLAB_OAK1")
	suite.check(Story.flag("EVENT_OAK_GOT_PARCEL") and not Story.bag_has("OAKS_PARCEL"), "Oak took the parcel")
	suite.check(Story.flag("EVENT_GOT_POKEDEX"), "received the POKéDEX")
	suite.check(ui.said_has("[OaksLabOakGotPokedexText]"), "got-POKéDEX line")
	suite.check(not host.is_actor_shown("OAKSLAB_POKEDEX1") and not host.is_actor_shown("OAKSLAB_RIVAL"), "dexes taken, rival gone")
	suite.check(Story.is_shown("ROUTE22_RIVAL1", "Route22") and Story.flag("EVENT_1ST_ROUTE22_RIVAL_BATTLE"), "rival now waits on Route 22")

static func _mart(suite: TestSuite, host: Node, ui: Node) -> void:
	host.load_map("ViridianMart", Vector2i(1, 5), "left")
	GameState.money = 3000
	ui.choices = [0, 0, -1, 2]   # BUY, POKé BALL, back, QUIT
	ui.quantities = [3]
	ui.answers = [true]
	host.talk("VIRIDIANMART_CLERK")
	suite.check(Story.bag_count("POKE_BALL") == 3, "bought 3 POKé BALLs (have %d)" % Story.bag_count("POKE_BALL"))
	suite.check(GameState.money == 2400, "paid $600 (money %d)" % GameState.money)
	suite.check(ui.menus.has(["BUY", "SELL", "QUIT"]), "mart BUY/SELL/QUIT menu")
	suite.check(ui.said_has("[PokemartThankYouText]"), "mart farewell")
	# sell one back for half price
	ui.choices = [1, 0, -1, 2]
	ui.quantities = [1]
	ui.answers = [true]
	host.talk("VIRIDIANMART_CLERK")
	suite.check(Story.bag_count("POKE_BALL") == 2 and GameState.money == 2500, "sold a POKé BALL for $100")

static func _nurse(suite: TestSuite, host: Node, ui: Node) -> void:
	GameState.last_outdoor = "ViridianCity"
	host.load_map("ViridianPokecenter", Vector2i(3, 3), "up")
	var m: Object = GameState.party[0]
	m.set("hp", 1)
	m.set("status", "PSN")
	ui.answers = [true]
	host.talk("VIRIDIANPOKECENTER_NURSE")
	suite.check(int(m.get("hp")) == int(m.get("max_hp")) and m.get("status") == "", "nurse healed the party")
	suite.check(ui.said_has("[PokemonFightingFitText]"), "fighting fit!")
	suite.check(GameState.last_heal_town.get("map", "") == "ViridianCity", "blackout point = Viridian City")
	suite.check(host.actor_dir("VIRIDIANPOKECENTER_NURSE") == "down", "nurse turns back to the player")

static func _item_ball(suite: TestSuite, host: Node, _ui: Node) -> void:
	host.load_map("Route2", Vector2i(13, 55), "up")
	host.talk("ROUTE2_MOON_STONE")
	suite.check(Story.bag_has("MOON_STONE"), "item ball: found MOON STONE")
	suite.check(not host.is_actor_shown("ROUTE2_MOON_STONE") and not Story.is_shown("ROUTE2_MOON_STONE", "Route2"), "item ball stays picked up")

static func _brock(suite: TestSuite, host: Node, ui: Node) -> void:
	host.load_map("PewterGym", Vector2i(4, 2), "up")
	battles.clear()
	host.talk("PEWTERGYM_BROCK")
	suite.check(battles.size() == 1 and battles[0].get("trainer_class") == "BROCK" and battles[0].get("music") == "gym_leader", "Brock battle (gym leader theme)")
	suite.check(Story.has_badge("BOULDERBADGE") and Story.flag("EVENT_BEAT_BROCK"), "BOULDERBADGE earned")
	suite.check(Story.bag_has("TM_BIDE") and Story.flag("EVENT_GOT_TM34"), "received TM34 BIDE")
	suite.check(Story.flag("EVENT_BEAT_PEWTER_GYM_TRAINER_0"), "gym trainer marked beaten")
	suite.check(not Story.is_shown("PEWTERCITY_YOUNGSTER", "PewterCity"), "Pewter gym guide stands down")
	suite.check(not Story.flag("EVENT_1ST_ROUTE22_RIVAL_BATTLE"), "Route 22 first rival battle cleared by the badge")
	ui.said.clear()
	host.talk("PEWTERGYM_BROCK")
	suite.check(ui.said_has("[PewterGymBrockPostBattleAdviceText]") and battles.size() == 1, "Brock post-battle advice, no rematch")

static func _line_of_sight(suite: TestSuite, host: Node, ui: Node) -> void:
	host.load_map("Route3", Vector2i(13, 6), "left")
	battles.clear()
	host.walk("L")
	suite.check(host.calls.has("emote:ROUTE3_YOUNGSTER1:!"), "trainer spots the player ('!')")
	suite.check(host.actor_cell("ROUTE3_YOUNGSTER1") == Vector2i(11, 6), "trainer walks up to the player (got %s)" % host.actor_cell("ROUTE3_YOUNGSTER1"))
	suite.check(host.actor_dir("PLAYER") == "left", "player turns to face the trainer")
	suite.check(battles.size() == 1 and battles[0].get("trainer_class") == "BUG_CATCHER" and int(battles[0].get("party_index")) == 4, "BUG CATCHER #4 battle")
	suite.check(ui.said_has("[Route3Youngster1BattleText]"), "pre-battle line")
	suite.check(Story.flag("EVENT_BEAT_ROUTE_3_TRAINER_0"), "trainer defeat flag set")
	host.walk("R")
	host.walk("L")
	suite.check(battles.size() == 1, "beaten trainer doesn't engage again")
	ui.said.clear()
	host.talk("ROUTE3_YOUNGSTER1")
	suite.check(ui.said_has("[Route3Youngster1AfterBattleText]"), "after-battle talk")
	# a loss blacks out to the last healed town with half the money
	GameState.money = 1000
	results = ["lose"]
	host.load_map("Route3", Vector2i(13, 7), "right")
	host.walk("R")    # (14,7): YOUNGSTER2 at (14,4) looks down 3 cells
	suite.check(battles.size() == 2 and battles[1].get("trainer_class") == "YOUNGSTER", "second trainer engages from 3 cells")
	suite.check(host.map == "ViridianCity" and GameState.money == 500, "loss: blacked out to Viridian City, money halved")
	suite.check(not Story.flag("EVENT_BEAT_ROUTE_3_TRAINER_1"), "lost battle leaves the trainer undefeated")

static func _hidden_item(suite: TestSuite, host: Node, _ui: Node) -> void:
	var found := ""
	var at := Vector2i.ZERO
	for h in GameData.maps.get("ViridianCity", {}).get("hidden", []):
		if h.get("fn", "") == "HiddenItems":
			found = str(h.get("arg", ""))
			at = Vector2i(int(h["x"]), int(h["y"]))
	if found == "":
		return
	host.load_map("ViridianCity", at + Vector2i(0, 1), "up")
	var before := Story.bag_count(found)
	Story.on_interact_cell(at, "up")
	suite.check(Story.bag_count(found) == before + 1, "hidden item found (%s)" % found)
	Story.on_interact_cell(at, "up")
	suite.check(Story.bag_count(found) == before + 1, "hidden item can't be found twice")

static func _mid_game(suite: TestSuite, host: Node, ui: Node) -> void:
	# Silph Co. card-key doors are closed on entry and open with the CARD KEY
	host.load_map("SilphCo2F", Vector2i(4, 6), "up")
	suite.check(host.blocked.has(Vector2i(4, 4)) and host.blocked.has(Vector2i(5, 4)), "Silph 2F card-key door closed")
	Story.on_interact_cell(Vector2i(4, 4), "up")
	suite.check(ui.said_has("[CardKeyFailText]") and host.blocked.has(Vector2i(4, 4)), "no CARD KEY: door stays shut")
	Story.bag_add("CARD_KEY")
	Story.on_interact_cell(Vector2i(4, 4), "up")
	suite.check(Story.flag("EVENT_SILPH_CO_2_UNLOCKED_DOOR1") and not host.blocked.has(Vector2i(4, 4)), "CARD KEY opens the door")
	# gift Pokémon: Eevee on the Celadon Mansion roof
	host.load_map("CeladonMansionRoofHouse", Vector2i(4, 4), "up")
	ui.answers = [false]
	host.talk("CELADONMANSION_ROOF_HOUSE_EEVEE_POKEBALL")
	suite.check(Story.party_has("EEVEE") and not host.is_actor_shown("CELADONMANSION_ROOF_HOUSE_EEVEE_POKEBALL"), "EEVEE gift received")
	# elevators remember the floor you came from, and the panel changes the exits
	host.load_map("CeladonMart3F", Vector2i(1, 1), "up")
	host.load_map("CeladonMartElevator", Vector2i(1, 3), "up")
	suite.check(Story.warp_redirects.get("CeladonMartElevator", []) == ["CeladonMart3F", 2], "elevator exits back to 3F")
	ui.choices = [4]
	Story.on_sign({"text": "TEXT_CELADONMARTELEVATOR"})
	suite.check(Story.warp_redirects.get("CeladonMartElevator", []) == ["CeladonMart5F", 2], "elevator panel: 5F")
	suite.check(Story.warp_dest_at(Vector2i(1, 3)).get("map", "") == "CeladonMart5F", "elevator warp now leads to 5F")
