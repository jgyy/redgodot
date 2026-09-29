extends RefCounted
## POKeMON YELLOW's own story beats, on top of the RED script modules (Pallet/Early/Mid/Late/Extra). Everything here is
## keyed by object ids that only exist in YELLOW's map overlay (data/versions.json "objects"), so it stays dormant in
## RED / BLUE. Dialogue comes from pokeyellow's text files (GameData.version_text); logic from pokeyellow's scripts:
##   - Oak's Lab: no starter choice. The one POKe BALL on the table (EEVEE) is the rival's; Oak gives you PIKACHU.
##   - MELANIE (Cerulean) gives BULBASAUR, OFFICER JENNY (Vermilion) SQUIRTLE, DAMIAN (Route 24) CHARMANDER, all Lv10;
##     the first two want a PIKACHU that is fond of you (PikachuBuddy.FRIENDLY).
##   - JESSIE & JAMES ambush you at Mt. Moon B2F, the Rocket Hideout B4F, the Pokemon Tower 7F and Silph Co. 11F.
##   - CHANSEY sits by every POKeMON CENTER counter.

const P := "PLAYER"
const JJ_MAPS := {
	"MtMoonB2F": ["MTMOONB2F_JESSIE", "MTMOONB2F_JAMES", "Mt. Moon", "MtMoonJessieJames"],
	"RocketHideoutB4F": ["ROCKETHIDEOUTB4F_JESSIE", "ROCKETHIDEOUTB4F_JAMES", "Hideout", "RocketHideoutJessieJames"],
	"PokemonTower7F": ["POKEMONTOWER7F_JESSIE", "POKEMONTOWER7F_JAMES", "Tower", "PokemonTowerJessieJames"],
	"SilphCo11F": ["SILPHCO11F_JESSIE", "SILPHCO11F_JAMES", "Silph", "SilphCoJessieJames"],
}
const CHANSEY_MAPS := ["ViridianPokecenter", "PewterPokecenter", "MtMoonPokecenter", "CeruleanPokecenter", "VermilionPokecenter",
	"LavenderPokecenter", "CeladonPokecenter", "RockTunnelPokecenter", "FuchsiaPokecenter", "SaffronPokecenter", "CinnabarPokecenter",
	"IndigoPlateauLobby"]

func register() -> void:
	Story.def_map("Route24", {"talk": {"ROUTE24_COOLTRAINER_M4": _damian}})
	Story.def_map("CeruleanTradeHouse", {"talk": {
		"CERULEANMELANIESHOUSE_MELANIE": _melanie,
		"CERULEANMELANIESHOUSE_BULBASAUR": _cry_text.bind("BULBASAUR", "MelanieBulbasaurText"),
		"CERULEANMELANIESHOUSE_ODDISH": _cry_text.bind("ODDISH", "MelanieOddishText"),
		"CERULEANMELANIESHOUSE_SANDSHREW": _cry_text.bind("SANDSHREW", "MelanieSandshrewText")}})
	Story.def_map("VermilionCity", {"talk": {"VERMILIONCITY_OFFICER_JENNY": _jenny}})
	Story.def_map("OaksLab", {"talk": {"OAKSLAB_EEVEE_POKE_BALL": _eevee_ball}})
	for m in CHANSEY_MAPS:
		var pre: String = str(m).to_upper()
		Story.def_map(m, {"talk": {pre + "_CHANSEY": _cry_text.bind("CHANSEY", "CHANSEY: Chaaan sey!")}})
	Story.def_map("CopycatsHouse1F", {"talk": {"COPYCATSHOUSE1F_CHANSEY": _cry_text.bind("CHANSEY", "CopycatsHouse1FChanseyText")}})
	Story.def_map("PokemonFanClub", {"talk": {"POKEMONFANCLUB_CLEFAIRY_FAN": _clefairy_fan,
		"POKEMONFANCLUB_CLEFAIRY": _cry_text.bind("CLEFAIRY", "PokemonFanClubClefairyText")}})
	Story.def_map("CeruleanCity", {"talk": {"CERULEANCITY_ELECTRODE": _electrode}})
	# RED's NPCs whose lines change with a PIKACHU in the party (pokeyellow scripts/Museum2F.asm, CeladonMansion1F.asm)
	Story.def_map("Museum2F", {"talk": {"MUSEUM2F_HIKER": _museum_hiker}})
	Story.def_map("CeladonMansion1F", {"talk": {"CELADONMANSION1F_GRANNY": _mansion_granny}})
	for m in JJ_MAPS.keys():
		var spec: Array = JJ_MAPS[m]
		Story.def_map(m, {"talk": {spec[0]: _jessie_james.bind(m), spec[1]: _jessie_james.bind(m)},
			"step": _jj_step.bind(m)})

# ---------------------------------------------------------------- Oak's Lab: the one ball is the rival's EEVEE, you get PIKACHU
## Interacting with the POKe BALL on the table: the rival snatches it (he wants EEVEE), Oak sighs and gives you PIKACHU.
func _eevee_ball(_o: Dictionary) -> void:
	if not Story.flag("EVENT_OAK_ASKED_TO_CHOOSE_MON"):
		await Story.say("OaksLabThatsAPokeball")
		return
	if Story.flag("EVENT_GOT_STARTER"):
		return
	var rival := "OAKSLAB_RIVAL"
	var ball := "OAKSLAB_EEVEE_POKE_BALL"
	await Story.emote(rival, "!", 30)
	Story.face(rival, "right")
	await Story.say("OaksLabRivalTakesText1")
	# he pushes you aside and stands where you were
	var bc := Story.cell(ball)
	var pc := Story.pcell()
	if pc.x == bc.x and pc.y == bc.y + 1:
		await Story.move_player("L")
	await Story.move(rival, Story.path_to(rival, bc.x, bc.y + 1))
	Story.face(rival, "up")
	await Story.say("OaksLabRivalTakesText2")
	Story.hide(ball)
	Story.sfx("get_mon")
	GameState.rival_eevee = "JOLTEON"   # the plan changes with how the first fights go (see Pallet._lab_rival_battle)
	Story.setvar("wNameBuffer", Story.species_name("EEVEE"))
	Story.setvar("wRivalStarter", Story.species_name("EEVEE"))
	await Story.say(Story.fmt(Story.t("OaksLabRivalReceivedMonText")))
	await Story.say("OaksLabRivalTakesText3")
	await Story.say("OaksLabRivalTakesText4")
	await Story.say("OaksLabRivalTakesText5")
	# Oak: this is the POKeMON I caught earlier
	await Story.say("OaksLabOakGivesText")
	give_pikachu()
	await Story.say(GameState.player_name + " received a PIKACHU!")

## The starter: a Lv5 PIKACHU that walks behind you, has a friendship value and never enters a POKe BALL.
static func give_pikachu() -> GameState.PartyMon:
	var m: GameState.PartyMon = Story.new_mon("PIKACHU", 5)
	m.buddy = true
	Story.sfx("get_mon")
	Story.cry("PIKACHU")
	GameState.starter = "PIKACHU"
	GameState.pikachu_happiness = 90
	GameState.party.append(m)
	GameState.party_changed.emit()
	Story.dex_caught("PIKACHU")
	Story.setf("EVENT_GOT_STARTER")
	return m

## After the Oak's Lab rival fight: which EEVEE evolution the rival is heading for (pokeyellow OaksLabRivalEndBattleScript):
## lost -> VAPOREON, won -> FLAREON; beating him on Route 22 later turns FLAREON into JOLTEON.
static func after_lab_battle(result: String) -> void:
	GameState.rival_eevee = "FLAREON" if result == "win" else "VAPOREON"

static func after_route22_first(result: String) -> void:
	if result != "lose" and GameState.rival_eevee == "FLAREON":
		GameState.rival_eevee = "JOLTEON"

## Prof. Oak notices that PIKACHU refuses to go into its POKe BALL.
static func pikachu_dislikes_balls() -> void:
	await Story.say("OaksLabPikachuDislikesPokeballsText1")
	Story.cry("PIKACHU")
	await Story.say("OaksLabPikachuDislikesPokeballsText2")

# ---------------------------------------------------------------- gifts
func _gift(sp: String, flag_name: String) -> bool:
	if GameState.party.size() >= 6 and GameState.box().size() >= 20:
		await Story.say("There's no more room for POKéMON!")
		return false
	var m: GameState.PartyMon = Story.new_mon(sp, 10)
	Story.sfx("get_mon")
	Story.dex_caught(sp)
	Story.setvar("wNameBuffer", Story.species_name(sp))
	await Story.say(GameState.player_name + " received " + Story.species_name(sp) + "!")
	await Story.receive_mon(m)
	Story.setf(flag_name)
	return true

func _damian(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_CHARMANDER_FROM_DAMIAN"):
		await Story.say("Route24DamianText4")
		return
	await Story.say("Route24DamianText1")
	if not await Story.ask("Take CHARMANDER?"):
		await Story.say("Route24DamianText3")
		return
	if await _gift("CHARMANDER", "EVENT_GOT_CHARMANDER_FROM_DAMIAN"):
		await Story.say("Route24DamianText2")

func _melanie(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_BULBASAUR_IN_CERULEAN"):
		await Story.say("MelanieText4")
		return
	await Story.say("MelanieText1")
	if not PikachuBuddy.is_friendly():
		return
	await Story.say("MelanieText2")
	if not await Story.ask("Take BULBASAUR?"):
		await Story.say("MelanieText5")
		return
	if await _gift("BULBASAUR", "EVENT_GOT_BULBASAUR_IN_CERULEAN"):
		Story.hide("CERULEANMELANIESHOUSE_BULBASAUR", "CeruleanTradeHouse")
		await Story.say("MelanieText3")

func _jenny(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_SQUIRTLE_FROM_OFFICER_JENNY"):
		await Story.say("OfficerJennyText5")
		return
	if not Story.has_badge("THUNDERBADGE") or not PikachuBuddy.is_friendly():
		await Story.say("OfficerJennyText1")
		return
	await Story.say("OfficerJennyText2")
	if not await Story.ask("Take SQUIRTLE?"):
		await Story.say("OfficerJennyText4")
		return
	if await _gift("SQUIRTLE", "EVENT_GOT_SQUIRTLE_FROM_OFFICER_JENNY"):
		await Story.say("OfficerJennyText3")

func _cry_text(_o: Dictionary, sp: String, text: String) -> void:
	Story.cry(sp)
	await Story.say(text)

# ---------------------------------------------------------------- PIKACHU-aware NPCs and Yellow-only scenery
## RED / BLUE: these handlers are registered too (they replace the plain-text default), so fall back to it there.
func _default(o: Dictionary) -> void:
	for line in DialogueText.for_obj(o):
		await Story.say(str(line))

func _clefairy_fan(_o: Dictionary) -> void:
	if Story.flag("EVENT_PIKACHU_FAN_BOAST"):
		await Story.say("PokemonFanClubClefairyFanBetterText")
		Story.clear("EVENT_PIKACHU_FAN_BOAST")
	else:
		await Story.say("PokemonFanClubClefairyFanNormalText")
		Story.setf("EVENT_SEEL_FAN_BOAST")

func _electrode(_o: Dictionary) -> void:
	Story.cry("ELECTRODE")
	var lines := ["CeruleanCityElectrodeTookASnoozeText", "CeruleanCityElectrodeIsLoafingAroundText", "CeruleanCityElectrodeTurnedAwayText",
		"CeruleanCityElectrodeIgnoredOrdersText"]
	await Story.say(lines[randi() % lines.size()])

## The Museum's hiker wants a PIKACHU: text 1 while yours isn't fond of you yet (<= 100), text 2 once it clings to you.
func _museum_hiker(o: Dictionary) -> void:
	if not GameState.is_yellow():
		await _default(o)
		return
	if PikachuBuddy.buddy() == null:
		await Story.say("Museum2FHikerText")
	elif GameState.pikachu_happiness > 100:
		await Story.say("Museum2FPikachuText2")
	else:
		await Story.say("Museum2FPikachuText1")

## Celadon Mansion's granny compliments your PIKACHU according to how tame it is.
func _mansion_granny(o: Dictionary) -> void:
	if not GameState.is_yellow():
		await _default(o)
		return
	if PikachuBuddy.buddy() == null:
		await Story.say("CeladonMansion1Text2")
		return
	await Story.say("CeladonMansion1Text6")
	var h := GameState.pikachu_happiness
	if h < 50:
		await Story.say("CeladonMansion1Text7")
		await Story.say("CeladonMansion1Text8")
	elif h < 100:
		await Story.say("CeladonMansion1Text9")
	elif h < 150:
		await Story.say("CeladonMansion1Text10")
	elif h < 200:
		await Story.say("CeladonMansion1Text11")
	else:
		await Story.say("CeladonMansion1Text12")
		if h >= 251:
			Story.cry("PIKACHU")

# ---------------------------------------------------------------- JESSIE & JAMES
func _jj_flag(map_name: String) -> String:
	return "EVENT_BEAT_JESSIE_JAMES_" + map_name.to_upper()

func _jj_step(x: int, y: int, map_name: String) -> Callable:
	if Story.flag(_jj_flag(map_name)):
		return Callable()
	var spec: Array = JJ_MAPS[map_name]
	if not Story.actor(spec[0]):
		return Callable()
	var c := Story.cell(spec[0])
	if absi(c.x - x) + absi(c.y - y) > 3:
		return Callable()
	return _jessie_james.bind({}, map_name)

func _jessie_james(_o: Dictionary, map_name: String) -> void:
	var spec: Array = JJ_MAPS[map_name]
	var flag_name := _jj_flag(map_name)
	if Story.flag(flag_name):
		return
	var stem: String = spec[3]
	Story.music("encounter_ROCKET")
	await Story.emote(spec[0], "!", 30)
	Story.face(spec[0], Story.dir_towards(Story.cell(spec[0]), Story.pcell()))
	Story.face(spec[1], Story.dir_towards(Story.cell(spec[1]), Story.pcell()))
	Story.face(P, Story.dir_towards(Story.pcell(), Story.cell(spec[0])))
	await Story.say(stem + "Text1")
	await Story.say(stem + "Text2")
	var n: int = int((GameData.versions_data.get("jessieJames", {}) as Dictionary).get(map_name, 1))
	var r := await Story.battle("ROCKET", n, {"display_name": "JESSIE & JAMES", "win_text": Story.fmt(Story.t(stem + "Text3"))})
	if r == "win":
		Story.setf(flag_name)
		await Story.say(stem + "Text4")
		Story.hide(spec[0])
		Story.hide(spec[1])
	Story.map_music()
