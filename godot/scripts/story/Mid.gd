extends RefCounted
## Port of upstream src/scripts/mid.js: Rock Tunnel headers, Lavender Town +
## Pokémon Tower (ghosts, Marowak, Mr. Fuji), Routes 7/8 gates, Celadon City (Dept.
## Store, Mansion, Game Corner + slots/prizes, Rocket Hideout, Erika), Saffron City
## (Silph Co. card keys, Sabrina, Fighting Dojo, houses) and Routes 16-18.

const P := "PLAYER"
const DRINK_FLAG := "EVENT_GAVE_SAFFRON_GUARDS_DRINK"
const PURIFIED := [Vector2i(10, 8), Vector2i(11, 8), Vector2i(10, 9), Vector2i(11, 9)]
const FORCE_BIKE := {"Route16": [Vector2i(17, 10), Vector2i(17, 11)], "Route18": [Vector2i(33, 8), Vector2i(33, 9)]}
const CYCLING := ["Route16", "Route17", "Route18"]
## Silph Co. card-key doors: [event, blockX, blockY, kind] (h = top row, v = right column, b = bottom row)
const CARD_DOORS := {
	"SilphCo2F": [["EVENT_SILPH_CO_2_UNLOCKED_DOOR1", 2, 2, "h"], ["EVENT_SILPH_CO_2_UNLOCKED_DOOR2", 2, 5, "h"]],
	"SilphCo3F": [["EVENT_SILPH_CO_3_UNLOCKED_DOOR1", 4, 4, "v"], ["EVENT_SILPH_CO_3_UNLOCKED_DOOR2", 8, 4, "v"]],
	"SilphCo4F": [["EVENT_SILPH_CO_4_UNLOCKED_DOOR1", 2, 6, "h"], ["EVENT_SILPH_CO_4_UNLOCKED_DOOR2", 6, 4, "h"]],
	"SilphCo5F": [["EVENT_SILPH_CO_5_UNLOCKED_DOOR1", 3, 2, "v"], ["EVENT_SILPH_CO_5_UNLOCKED_DOOR2", 3, 6, "v"], ["EVENT_SILPH_CO_5_UNLOCKED_DOOR3", 7, 5, "v"]],
	"SilphCo6F": [["EVENT_SILPH_CO_6_UNLOCKED_DOOR", 2, 6, "v"]],
	"SilphCo7F": [["EVENT_SILPH_CO_7_UNLOCKED_DOOR1", 5, 3, "h"], ["EVENT_SILPH_CO_7_UNLOCKED_DOOR2", 10, 2, "h"], ["EVENT_SILPH_CO_7_UNLOCKED_DOOR3", 10, 6, "h"]],
	"SilphCo8F": [["EVENT_SILPH_CO_8_UNLOCKED_DOOR", 3, 4, "v"]],
	"SilphCo9F": [["EVENT_SILPH_CO_9_UNLOCKED_DOOR1", 1, 4, "v"], ["EVENT_SILPH_CO_9_UNLOCKED_DOOR2", 9, 2, "h"], ["EVENT_SILPH_CO_9_UNLOCKED_DOOR3", 9, 5, "h"], ["EVENT_SILPH_CO_9_UNLOCKED_DOOR4", 5, 6, "v"]],
	"SilphCo10F": [["EVENT_SILPH_CO_10_UNLOCKED_DOOR", 5, 4, "h"]],
	"SilphCo11F": [["EVENT_SILPH_CO_11_UNLOCKED_DOOR", 3, 6, "b"]],
}
const T7_EXIT := {
	"POKEMONTOWER7F_ROCKET1": {"9,12": "RDDDDDL", "10,11": "DRDDDD", "11,11": "DDDDD", "12,11": "DDDDD"},
	"POKEMONTOWER7F_ROCKET2": {"12,10": "LDDDDDD", "11,9": "DDDLDD", "10,9": "DDDDD", "9,9": "DDDDD"},
	"POKEMONTOWER7F_ROCKET3": {"9,8": "RDDDDDD", "10,7": "DDDDD", "11,7": "DDDDD", "12,7": "DDDDD"},
}
## hidden coins (data/events/hidden_events.asm; COIN+40 pays 20 due to the original typo)
const GC_COINS := {"0,8": 10, "1,16": 10, "3,11": 20, "3,14": 10, "4,12": 10, "9,12": 20, "9,15": 10, "16,14": 10, "10,16": 10, "11,7": 20, "15,8": 100, "12,15": 10}
const PRIZES := [
	[["ABRA", 180, 9], ["CLEFAIRY", 500, 8], ["NIDORINA", 1200, 17]],
	[["DRATINI", 2800, 18], ["SCYTHER", 5500, 25], ["PORYGON", 9999, 26]],
	[["TM_DRAGON_RAGE", 3300], ["TM_HYPER_BEAM", 5500], ["TM_SUBSTITUTE", 7700]],
]
const ROCKETS_LEAVE_HIDE := [["SaffronCity", ["ROCKET1", "ROCKET2", "ROCKET3", "ROCKET4", "ROCKET5", "ROCKET6", "ROCKET7", "ROCKET8", "ROCKET9"]],
	["SilphCo2F", ["SCIENTIST1", "SCIENTIST2", "ROCKET1", "ROCKET2"]], ["SilphCo3F", ["ROCKET", "SCIENTIST"]],
	["SilphCo4F", ["ROCKET1", "SCIENTIST", "ROCKET2"]], ["SilphCo5F", ["ROCKET1", "SCIENTIST", "ROCKER", "ROCKET2"]],
	["SilphCo6F", ["ROCKET1", "SCIENTIST", "ROCKET2"]], ["SilphCo7F", ["ROCKET1", "SCIENTIST", "ROCKET2", "ROCKET3"]],
	["SilphCo8F", ["ROCKET1", "SCIENTIST", "ROCKET2"]], ["SilphCo9F", ["ROCKET1", "SCIENTIST", "ROCKET2"]],
	["SilphCo10F", ["ROCKET", "SCIENTIST"]], ["SilphCo11F", ["GIOVANNI", "ROCKET1", "ROCKET2"]]]
const ROCKETS_LEAVE_SHOW := [["SaffronCity", ["SCIENTIST", "SILPH_WORKER_M", "SILPH_WORKER_F", "GENTLEMAN", "PIDGEOT", "ROCKER"]]]
const MART_FLOORS := [{"label": "1F", "map": "CeladonMart1F", "warp": 5}, {"label": "2F", "map": "CeladonMart2F", "warp": 2},
	{"label": "3F", "map": "CeladonMart3F", "warp": 2}, {"label": "4F", "map": "CeladonMart4F", "warp": 2}, {"label": "5F", "map": "CeladonMart5F", "warp": 2}]
const HIDEOUT_FLOORS := [{"label": "B1F", "map": "RocketHideoutB1F", "warp": 4}, {"label": "B2F", "map": "RocketHideoutB2F", "warp": 4},
	{"label": "B4F", "map": "RocketHideoutB4F", "warp": 2}]

var slots: SlotMachine = null

func register() -> void:
	slots = SlotMachine.new()
	# Underground Path entrances set wLastMap so LAST_MAP exits return to the right route
	Story.def_map("UndergroundPathRoute7", {"enter": _set_last_outdoor.bind("Route7")})
	Story.def_map("UndergroundPathRoute8", {"enter": _set_last_outdoor.bind("Route8")})
	# Cycling Road: force the BICYCLE next to the gates; Route 17 slopes downhill
	Story.global_step_hooks.append(func(_m: String, _x: int, _y: int) -> Callable:
		check_force_bike()
		return Callable())
	Story.global_enter_hooks.append(func(_m: String) -> void: check_force_bike())
	# Pokémon Tower 5F purified zone: no wild battles there
	Story.encounter_guards.append(func(m: String, x: int, y: int) -> bool:
		return m == "PokemonTower5F" and PURIFIED.has(Vector2i(x, y)))

	Story.def_map("Route7Gate", {"step": _gate_step.bind(3, "up", "L"), "talk": {"ROUTE7GATE_GUARD": _saffron_guard_talk}})
	Story.def_map("Route8Gate", {"step": _gate_step.bind(2, "left", "R"), "talk": {"ROUTE8GATE_GUARD": _saffron_guard_talk}})

	# Pokémon Center extras (link receptionists, bench guys) in this region
	var bench := {"LavenderPokecenter": "LavenderPokecenterGuyText", "CeladonPokecenter": "CeladonCityPokecenterGuyText",
		"CeladonHotel": "CeladonCityHotelText", "RockTunnelPokecenter": "RockTunnelPokecenterGuyText", "SaffronPokecenter": ""}
	for map_name in bench:
		var md := Story.map_data(map_name)
		if md.is_empty():
			continue
		var hidden := {}
		for h in md.get("hidden", []):
			if h.get("fn", "") == "PrintBenchGuyText":
				hidden["%d,%d" % [int(h["x"]), int(h["y"])]] = _bench.bind(bench[map_name])
		var talk := {}
		for o in md.get("objs", []):
			if o.get("sprite", "") == "link_receptionist":
				talk[o["id"]] = _cable_club
		Story.def_map(map_name, {"hidden": hidden, "talk": talk})

	# ---- Lavender Town
	Story.def_map("LavenderTown", {"talk": {"LAVENDERTOWN_LITTLE_GIRL": _lavender_girl}})
	Story.def_map("LavenderCuboneHouse", {"talk": {
		"LAVENDERCUBONEHOUSE_CUBONE": _cry_talk.bind("LavenderCuboneHouseCuboneText", "CUBONE"),
		"LAVENDERCUBONEHOUSE_BRUNETTE_GIRL": _flag_talk.bind("EVENT_RESCUED_MR_FUJI", "LavenderCuboneHouseBrunetteGirlPoorCubonesMotherText", "LavenderCuboneHouseBrunetteGirlGhostIsGoneText")}})
	Story.def_map("LavenderMart", {"talk": {"LAVENDERMART_COOLTRAINER_M": _flag_talk.bind("EVENT_RESCUED_MR_FUJI", "LavenderMartCooltrainerMReviveText", "LavenderMartCooltrainerMNuggetText")}})
	Story.def_map("MrFujisHouse", {"talk": {
		"MRFUJISHOUSE_SUPER_NERD": _flag_talk.bind("EVENT_RESCUED_MR_FUJI", "MrFujisHouseSuperNerdMrFujiIsntHereText", "MrFujisHouseSuperNerdMrFujiHadBeenPrayingText"),
		"MRFUJISHOUSE_LITTLE_GIRL": _flag_talk.bind("EVENT_RESCUED_MR_FUJI", "MrFujisHouseLittleGirlThisIsMrFujisHouseText", "MrFujisHouseLittleGirlPokemonAreNiceToHugText"),
		"MRFUJISHOUSE_PSYDUCK": _cry_talk.bind("MrFujisHousePsyduckText", "PSYDUCK"),
		"MRFUJISHOUSE_NIDORINO": _cry_talk.bind("MrFujisHouseNidorinoText", "NIDORINO"),
		"MRFUJISHOUSE_MR_FUJI": _mr_fuji}})
	Story.def_map("NameRatersHouse", {"talk": {"NAMERATERSHOUSE_NAME_RATER": _name_rater}})
	# ---- Pokémon Tower
	Story.def_map("PokemonTower2F", {"step": _tower2_step, "talk": {"POKEMONTOWER2F_RIVAL": _tower2_rival_talk}})
	Story.def_map("PokemonTower5F", {"enter": _tower5_enter, "step": _tower5_step})
	Story.def_map("PokemonTower6F", {"step": _tower6_step})
	Story.after_trainer["PokemonTower7F"] = _tower7_rocket_leaves
	Story.def_map("PokemonTower7F", {"talk": {"POKEMONTOWER7F_MR_FUJI": _tower7_fuji}})
	# ---- Celadon
	Story.def_map("CeladonCity", {"talk": {"CELADONCITY_GRAMPS3": _celadon_gramps3, "CELADONCITY_POLIWRATH": _cry_talk.bind("CeladonCityPoliwrathText", "POLIWRATH")}})
	Story.def_map("CeladonDiner", {"talk": {"CELADONDINER_GYM_GUIDE": _diner_guide}})
	Story.def_map("CeladonMansion1F", {"talk": {
		"CELADONMANSION1F_MEOWTH": _cry_talk.bind("CeladonMansion1FMeowthText", "MEOWTH"),
		"CELADONMANSION1F_CLEFAIRY": _cry_talk.bind("CeladonMansion1FClefairyText", "CLEFAIRY"),
		"CELADONMANSION1F_NIDORANF": _cry_talk.bind("CeladonMansion1FNidoranFText", "NIDORAN_F")}})
	Story.def_map("CeladonMansion3F", {"talk": {"CELADONMANSION3F_GAME_DESIGNER": _game_designer}})
	Story.def_map("CeladonMansionRoofHouse", {
		"hidden": {"3,0": _link_cable_help, "4,0": _link_cable_help, "3,4": _say.bind("TMNotebookText")},
		"talk": {"CELADONMANSION_ROOF_HOUSE_EEVEE_POKEBALL": _eevee}})
	Story.def_map("CeladonMart3F", {"talk": {"CELADONMART3F_CLERK": _mart3f_clerk}})
	Story.def_map("CeladonMartElevator", {"enter": _elevator_enter.bind(MART_FLOORS),
		"sign": {"TEXT_CELADONMARTELEVATOR": _elevator.bind(MART_FLOORS, false)}})
	Story.def_map("CeladonMartRoof", {
		"sign": {"TEXT_CELADONMARTROOF_VENDING_MACHINE1": _vending_h, "TEXT_CELADONMARTROOF_VENDING_MACHINE2": _vending_h,
			"TEXT_CELADONMARTROOF_VENDING_MACHINE3": _vending_h},
		"talk": {"CELADONMARTROOF_LITTLE_GIRL": _roof_girl}})
	Story.def_map("CeladonGym", {"talk": {"CELADONGYM_ERIKA": _erika}})
	# ---- Game Corner
	var gc_hidden := {}
	for k in GC_COINS:
		gc_hidden[k] = _gc_coins.bind(int(GC_COINS[k]))
	var gcm := Story.map_data("GameCorner")
	var gci := 0
	for h in gcm.get("hidden", []):
		gci += 1
		if h.get("fn", "") == "StartSlotMachine":
			gc_hidden["%d,%d" % [int(h["x"]), int(h["y"])]] = _slot_hidden.bind(gci)
	Story.def_map("GameCorner", {
		"enter": _gc_enter, "hidden": gc_hidden,
		"sign": {"TEXT_GAMECORNER_POSTER": _gc_poster},
		"talk": {"GAMECORNER_CLERK1": _gc_clerk1,
			"GAMECORNER_FISHING_GURU": _coins_npc.bind("EVENT_GOT_10_COINS", "GameCornerFishingGuruWantToPlayText", "GameCornerFishingGuruReceived10CoinsText", "GameCornerFishingGuruDontNeedMyCoinsText", "GameCornerFishingGuruWinsComeAndGoText", 10, 9990),
			"GAMECORNER_CLERK2": _coins_npc.bind("EVENT_GOT_20_COINS_2", "GameCornerClerk2WantSomeCoinsText", "GameCornerClerk2Received20CoinsText", "GameCornerClerk2YouHaveLotsOfCoinsText", "GameCornerClerk2INeedMoreCoinsText", 20, 9990),
			"GAMECORNER_GENTLEMAN": _coins_npc.bind("EVENT_GOT_20_COINS", "GameCornerGentlemanThrowingMeOffText", "GameCornerGentlemanReceived20CoinsText", "GameCornerGentlemanYouGotYourOwnCoinsText", "GameCornerGentlemanCloselyWatchTheReelsText", 20, 9990),
			"GAMECORNER_GYM_GUIDE": _flag_talk.bind("EVENT_BEAT_ERIKA", "GameCornerGymGuideChampInMakingText", "GameCornerGymGuideTheyOfferRarePokemonText"),
			"GAMECORNER_ROCKET": _gc_rocket}})
	Story.def_map("GameCornerPrizeRoom", {"sign": {
		"TEXT_GAMECORNERPRIZEROOM_PRIZE_VENDOR_1": _prize_h.bind(0), "TEXT_GAMECORNERPRIZEROOM_PRIZE_VENDOR_2": _prize_h.bind(1),
		"TEXT_GAMECORNERPRIZEROOM_PRIZE_VENDOR_3": _prize_h.bind(2)}})
	# ---- Rocket Hideout
	Story.def_map("RocketHideoutB1F", {"enter": _hideout_b1f_enter})
	Story.after_trainer["RocketHideoutB1F"] = _hideout_b1f_after
	Story.after_trainer["RocketHideoutB4F"] = _hideout_b4f_after
	Story.def_map("RocketHideoutB4F", {"enter": _hideout_b4f_enter, "talk": {"ROCKETHIDEOUTB4F_GIOVANNI": _hideout_giovanni, "ROCKETHIDEOUTB4F_ROCKET3": _hideout_rocket3}})
	Story.def_map("RocketHideoutElevator", {"enter": _elevator_enter.bind(HIDEOUT_FLOORS),
		"sign": {"TEXT_ROCKETHIDEOUTELEVATOR": _elevator.bind(HIDEOUT_FLOORS, true)}})
	# ---- Saffron
	Story.def_map("SaffronGym", {"talk": {"SAFFRONGYM_SABRINA": _sabrina,
		"SAFFRONGYM_GYM_GUIDE": _flag_talk.bind("EVENT_BEAT_SABRINA", "SaffronGymGuideChampInMakingText", "SaffronGymGuideBeatSabrinaText")}})
	Story.def_map("SaffronPidgeyHouse", {"talk": {"SAFFRONPIDGEYHOUSE_PIDGEY": _cry_talk.bind("SaffronPidgeyHousePidgeyText", "PIDGEY")}})
	Story.def_map("MrPsychicsHouse", {"talk": {"MRPSYCHICSHOUSE_MR_PSYCHIC": _gift_tm.bind("EVENT_GOT_TM29", "MrPsychicsHouseMrPsychicTM29ExplanationText", "MrPsychicsHouseMrPsychicYouWantedThisText", "TM_PSYCHIC_M", "MrPsychicsHouseMrPsychicReceivedTM29Text", "MrPsychicsHouseMrPsychicTM29NoRoomText")}})
	Story.def_map("CopycatsHouse1F", {"talk": {"COPYCATSHOUSE1F_CHANSEY": _cry_talk.bind("CopycatsHouse1FChanseyText", "CHANSEY")}})
	Story.def_map("CopycatsHouse2F", {"talk": {"COPYCATSHOUSE2F_COPYCAT": _copycat}, "sign": {"TEXT_COPYCATSHOUSE2F_PC": _copycat_pc}})
	Story.def_map("FightingDojo", {
		"step": _dojo_step,
		"hidden": {"3,9": _facing_up_say.bind("FightingDojoText"), "6,9": _facing_up_say.bind("FightingDojoText"),
			"4,0": _facing_up_say.bind("EnemiesOnEverySideText"), "5,0": _facing_up_say.bind("WhatGoesAroundComesAroundText")},
		"talk": {"FIGHTINGDOJO_KARATE_MASTER": _karate_master_talk,
			"FIGHTINGDOJO_HITMONLEE_POKE_BALL": _dojo_ball.bind("HITMONLEE", "FIGHTINGDOJO_HITMONLEE_POKE_BALL", "EVENT_GOT_HITMONLEE", "FightingDojoHitmonleePokeBallText"),
			"FIGHTINGDOJO_HITMONCHAN_POKE_BALL": _dojo_ball.bind("HITMONCHAN", "FIGHTINGDOJO_HITMONCHAN_POKE_BALL", "EVENT_GOT_HITMONCHAN", "FightingDojoHitmonchanPokeBallText")}})
	# ---- Silph Co.
	_silph_floor(1, {"enter": _silph1_enter})
	_silph_floor(2, {"talk": {"SILPHCO2F_SILPH_WORKER_F": _gift_tm.bind("EVENT_GOT_TM36", "SilphCo2FSilphWorkerFTM36ExplanationText", "SilphCo2FSilphWorkerFPleaseTakeThisText", "TM_SELFDESTRUCT", "SilphCo2FSilphWorkerFReceivedTM36Text", "SilphCo2FSilphWorkerFTM36NoRoomText")}})
	_silph_floor(3, {"talk": {"SILPHCO3F_SILPH_WORKER_M": _silph_talk.bind("SilphCo3FSilphWorkerMWhatShouldIDoText", "SilphCo3FSilphWorkerMYouSavedUsText")}})
	_silph_floor(4, {"talk": {"SILPHCO4F_SILPH_WORKER_M": _silph_talk.bind("SilphCo4FSilphWorkerMImHidingText", "SilphCo4FSilphWorkerMTeamRocketIsGoneText")}})
	_silph_floor(5, {"talk": {"SILPHCO5F_SILPH_WORKER_M": _silph_talk.bind("SilphCo5FSilphWorkerMThatsYouRightText", "SilphCo5FSilphWorkerMYoureOurHeroText")}})
	_silph_floor(6, {"talk": {
		"SILPHCO6F_SILPH_WORKER_M1": _silph_talk.bind("SilphCo6FSilphWorkerM1TookOverTheBuildingText", "SilphCo6FSilphWorkerM1BackToWorkText"),
		"SILPHCO6F_SILPH_WORKER_M2": _silph_talk.bind("SilphCo6FSilphWorkerMHelpMePleaseText", "SilphCo6FSilphWorkerMWeGotEngagedText"),
		"SILPHCO6F_SILPH_WORKER_F1": _silph_talk.bind("SilphCo6FSilphWorkerF1SuchACowardText", "SilphCo6FSilphWorkerF1HaveToMarryHimText"),
		"SILPHCO6F_SILPH_WORKER_F2": _silph_talk.bind("SilphCo6FSilphWorkerF2TeamRocketConquerWorldText", "SilphCo6FSilphWorkerF2TeamRocketRanText"),
		"SILPHCO6F_SILPH_WORKER_M3": _silph_talk.bind("SilphCo6FSilphWorkerM3TargetedSilphText", "SilphCo6FSilphWorkerM3WorkForSilphText")}})
	_silph_floor(7, {"step": _silph7_step, "talk": {
		"SILPHCO7F_SILPH_WORKER_M1": _silph7_lapras,
		"SILPHCO7F_SILPH_WORKER_M2": _silph_talk.bind("SilphCo7FSilphWorkerM2AfterTheMasterBallText", "SilphCo7FSilphWorkerM2CancelledMasterBallText"),
		"SILPHCO7F_SILPH_WORKER_M3": _silph_talk.bind("SilphCo7FSilphWorkerM3ItWouldBeBadText", "SilphCo7FSilphWorkerM3YouChasedOffTeamRocketText"),
		"SILPHCO7F_SILPH_WORKER_M4": _silph_talk.bind("SilphCo7FSilphWorkerM4ItsReallyDangerousHereText", "SilphCo7FSilphWorkerM4SafeAtLastText"),
		"SILPHCO7F_RIVAL": _say.bind("SilphCo7FRivalText")}})
	_silph_floor(8, {"talk": {"SILPHCO8F_SILPH_WORKER_M": _silph_talk.bind("SilphCo8FSilphWorkerMSilphIsFinishedText", "SilphCo8FSilphWorkerMThanksForSavingUsText")}})
	_silph_floor(9, {"talk": {"SILPHCO9F_NURSE": _silph9_nurse}})
	_silph_floor(10, {"talk": {"SILPHCO10F_SILPH_WORKER_F": _silph_talk.bind("SilphCo10FSilphWorkerFImScaredText", "SilphCo10FSilphWorkerFQuietAboutMyCryingText")}})
	_silph_floor(11, {"step": _silph11_step, "talk": {"SILPHCO11F_SILPH_PRESIDENT": _silph_president, "SILPHCO11F_GIOVANNI": _say.bind("SilphCo11FGiovanniText")}})
	var silph_floors: Array = []
	for n in range(1, 12):
		silph_floors.append({"label": "%dF" % n, "map": "SilphCo%dF" % n, "warp": 3 if n == 1 else (1 if n == 11 else 2)})
	Story.def_map("SilphCoElevator", {"enter": _elevator_enter.bind(silph_floors), "sign": {"TEXT_SILPHCOELEVATOR_ELEVATOR": _elevator.bind(silph_floors, false)}})
	# ---- Routes 16-18
	_bike_gate("Route16Gate1F", "ROUTE16GATE1F_GUARD", [7, 8, 9, 10], "Route16Gate1FGuardWaitUpText", "Route16Gate1FGuardNoPedestriansAllowedText", "Route16Gate1FGuardCyclingRoadExplanationText")
	_bike_gate("Route18Gate1F", "ROUTE18GATE1F_GUARD", [3, 4, 5, 6], "Route18Gate1FGuardExcuseMeText", "Route18Gate1FGuardYouNeedABicycleText", "Route18Gate1FGuardCyclingRoadUphillText")
	Story.def_map("Route16Gate2F", {"sign": {"TEXT_ROUTE16GATE2F_LEFT_BINOCULARS": _facing_up_say.bind("Route16Gate2FLeftBinocularsText"),
		"TEXT_ROUTE16GATE2F_RIGHT_BINOCULARS": _facing_up_say.bind("Route16Gate2FRightBinocularsText")}})
	Story.def_map("Route18Gate2F", {
		"sign": {"TEXT_ROUTE18GATE2F_LEFT_BINOCULARS": _facing_up_say.bind("Route18Gate2FLeftBinocularsText"),
			"TEXT_ROUTE18GATE2F_RIGHT_BINOCULARS": _facing_up_say.bind("Route18Gate2FRightBinocularsText")},
		"talk": {"ROUTE18GATE2F_YOUNGSTER": _route18_trade}})
	Story.def_map("Route16FlyHouse", {"talk": {"ROUTE16FLYHOUSE_BRUNETTE_GIRL": _fly_house_girl, "ROUTE16FLYHOUSE_FEAROW": _cry_talk.bind("Route16FlyHouseFearowText", "FEAROW")}})

## Story.field_interact hook: closed Silph Co. card-key doors.
func field_interact(c: Vector2i) -> Callable:
	var d := _card_door_at(c)
	if d.is_empty():
		return Callable()
	return _card_key.bind(d)

# ======================================================================
# small shared helpers
# ======================================================================
func _say(_o: Variant, label: String) -> void:
	await Story.say(label)

func _cry_talk(_o: Variant, label: String, sp: String) -> void:
	await Story.say(label)
	Story.cry(sp)

func _flag_talk(_o: Variant, f: String, before: String, after: String) -> void:
	await Story.say(after if Story.flag(f) else before)

func _facing_up_say(_o: Variant, label: String) -> void:
	if Story.pdir() == "up":
		await Story.say(label)

func _set_last_outdoor(route: String) -> Callable:
	GameState.last_outdoor = route
	return Callable()

func _bench(_h: Dictionary, label: String) -> void:
	if Story.pdir() != "left":
		return
	if label == "":
		label = "SaffronCityPokecenterGuyText2" if Story.flag("EVENT_BEAT_SILPH_CO_GIOVANNI") else "SaffronCityPokecenterGuyText1"
	await Story.say(label)

## cable club receptionist (engine/link/cable_club_npc.asm, no link partner)
func _cable_club(_o: Dictionary) -> void:
	await Story.say("CableClubNPCWelcomeText")
	await Story.wait(60)
	await Story.say("CableClubNPCAreaReservedFor2FriendsLinkedByCableText" if Story.flag("EVENT_GOT_POKEDEX") else "CableClubNPCMakingPreparationsText")

func _gift_tm(_o: Dictionary, f: String, explain: String, intro: String, tm: String, recv: String, no_room: String) -> void:
	if Story.flag(f):
		await Story.say(explain)
		return
	await Story.say(intro)
	if await Story.give_item(tm, recv, no_room):
		Story.setf(f)

# ======================================================================
# Cycling Road
# ======================================================================
func check_force_bike() -> void:
	var n := Story.mapname()
	if GameState.always_on_bike and not CYCLING.has(n):
		GameState.always_on_bike = false
	if not GameState.always_on_bike and FORCE_BIKE.has(n) and (FORCE_BIKE[n] as Array).has(Story.pcell()):
		GameState.always_on_bike = true
		if not Story.biking:
			Story.set_biking(true)
			Story.music("bike")

func _bike_gate(map_name: String, guard_id: String, rows: Array, wait_label: String, no_bike_label: String, bike_label: String) -> void:
	Story.def_map(map_name, {
		"enter": func() -> Callable:
			GameState.always_on_bike = false
			return Callable(),
		"step": func(x: int, y: int) -> Callable:
			if Story.bag_has("BICYCLE") or x != 4 or not rows.has(y):
				return Callable()
			return _bike_gate_stop.bind(y, rows[0], wait_label, no_bike_label),
		"talk": {guard_id: _bike_guard_talk.bind(no_bike_label, bike_label)},
	})

func _bike_gate_stop(y: int, row0: int, wait_label: String, no_bike_label: String) -> void:
	await Story.say(wait_label)
	var ups := y - row0
	if ups > 0:
		await Story.move_player("U".repeat(ups))
	Story.face(P, "up")
	await Story.say(no_bike_label)
	await Story.move_player("R")

func _bike_guard_talk(_o: Dictionary, no_bike_label: String, bike_label: String) -> void:
	await Story.say(bike_label if Story.bag_has("BICYCLE") else no_bike_label)

# ======================================================================
# Saffron gate guards (Routes 7/8; one flag shared with Routes 5/6)
# ======================================================================
static func remove_guard_drink() -> String:
	for d in ["FRESH_WATER", "SODA_POP", "LEMONADE"]:
		if Story.bag_has(d):
			Story.bag_remove(d, 1)
			return d
	return ""

func _guard_give_drink() -> void:
	await Story.say("SaffronGateGuardImParchedText")
	Story.sfx("get_key")
	await Story.say("SaffronGateGuardYouCanGoOnThroughText")
	Story.setf(DRINK_FLAG)

func _saffron_guard_talk(_o: Dictionary) -> void:
	if Story.flag(DRINK_FLAG):
		await Story.say("SaffronGateGuardThanksForTheDrinkText")
		return
	if remove_guard_drink() != "":
		await _guard_give_drink()
		return
	await Story.say("SaffronGateGuardGeeImThirstyText")

func _gate_step(x: int, y: int, gx: int, facing_dir: String, push: String) -> Callable:
	if x != gx or (y != 3 and y != 4) or Story.flag(DRINK_FLAG):
		return Callable()
	return _guard_step.bind(facing_dir, push)

func _guard_step(facing_dir: String, push: String) -> void:
	Story.face(P, facing_dir)
	if remove_guard_drink() != "":
		await _guard_give_drink()
		return
	await Story.say("SaffronGateGuardGeeImThirstyText")
	await Story.move_player(push)

# ======================================================================
# Lavender Town
# ======================================================================
func _lavender_girl(_o: Dictionary) -> void:
	var yes := await Story.ask("LavenderTownLittleGirlDoYouBelieveInGhostsText")
	await Story.say("LavenderTownLittleGirlSoThereAreBelieversText" if yes else "LavenderTownLittleGirlHaHaGuessNotText")

func _mr_fuji(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_POKE_FLUTE"):
		await Story.say("MrFujisHouseMrFujiHasMyFluteHelpedYouText")
		return
	await Story.say("MrFujisHouseMrFujiIThinkThisMayHelpYourQuestText")
	if not Story.bag_add("POKE_FLUTE", 1):
		await Story.say("MrFujisHouseMrFujiPokeFluteNoRoomText")
		return
	Story.setvar("wStringBuffer", Story.item_name("POKE_FLUTE"))
	Story.setvar("wNameBuffer", Story.item_name("POKE_FLUTE"))
	Story.sfx("get_key")
	await Story.say("MrFujisHouseMrFujiReceivedPokeFluteText")
	await Story.say("MrFujisHouseMrFujiPokeFluteExplanationText")
	Story.setf("EVENT_GOT_POKE_FLUTE")

## Name Rater (scripts/NameRatersHouse.asm)
func _name_rater(_o: Dictionary) -> void:
	if not await Story.ask("NameRatersHouseNameRaterWantMeToRateText"):
		await Story.say("NameRatersHouseNameRaterComeAnyTimeYouLikeText")
		return
	await Story.say("NameRatersHouseNameRaterWhichPokemonText")
	var i := await Story.party_screen("Choose a POKéMON.")
	if i < 0:
		await Story.say("NameRatersHouseNameRaterComeAnyTimeYouLikeText")
		return
	var m: Object = GameState.party[i]
	Story.setvar("wNameBuffer", Story.mon_name(m))
	# traded POKéMON (different OT) can't be renamed
	if str(m.get("ot")) != "" and str(m.get("ot")) != GameState.player_name:
		await Story.say("NameRatersHouseNameRaterATrulyImpeccableNameText")
		return
	if not await Story.ask("NameRatersHouseNameRaterGiveItANiceNameText"):
		await Story.say("NameRatersHouseNameRaterComeAnyTimeYouLikeText")
		return
	await Story.say("NameRatersHouseNameRaterWhatShouldWeNameItText")
	var spn := Story.species_name(str(m.get("species_id")))
	var n := await Story.name_entry(spn + "'s nickname?", "", 10)
	if n == "":
		await Story.say("NameRatersHouseNameRaterComeAnyTimeYouLikeText")
		return
	m.set("nickname", n)
	Story.setvar("wBuffer", n)
	await Story.say("NameRatersHouseNameRaterPokemonHasBeenRenamedText")

# ======================================================================
# Pokémon Tower
# ======================================================================
func _tower2_step(x: int, y: int) -> Callable:
	if Story.flag("EVENT_BEAT_POKEMON_TOWER_RIVAL"):
		return Callable()
	var on_left := x == 15 and y == 5
	var below := x == 14 and y == 6
	if not on_left and not below:
		return Callable()
	return _tower2_ambush.bind(on_left)

func _tower2_ambush(on_left: bool) -> void:
	var rival := "POKEMONTOWER2F_RIVAL"
	Story.music("rival")
	Story.face(P, "left" if on_left else "up")
	if Story.actor(rival):
		Story.face(rival, "right" if on_left else "down")
	await Story.wait(4)
	await tower_rival_talk(rival, on_left)

func _tower2_rival_talk(o: Dictionary) -> void:
	var id: String = o.get("id", "")
	await tower_rival_talk(id, Story.pcell().x > Story.cell(id).x)

func tower_rival_talk(rival: String, on_left: bool) -> void:
	if Story.flag("EVENT_BEAT_POKEMON_TOWER_RIVAL"):
		await Story.say("PokemonTower2FRivalHowsYourDexText")
		return
	await Story.say("PokemonTower2FRivalWhatBringsYouHereText")
	var r := await Story.battle("RIVAL2", Story.rival_party(4), {"win_text": Story.fmt(Story.t("PokemonTower2FRivalDefeatedText")), "lose_text": Story.fmt(Story.t("PokemonTower2FRivalVictoryText"))})
	if r != "win":
		return
	Story.setf("EVENT_BEAT_POKEMON_TOWER_RIVAL")
	await Story.say("PokemonTower2FRivalHowsYourDexText")
	Story.music("rival")
	await Story.move(rival, "DDRRRRDD" if on_left else "RDDRDDRR")
	Story.hide("POKEMONTOWER2F_RIVAL")
	Story.map_music()

## 5F: the purified zone glows and heals the party once per entry into it
func _tower5_enter() -> Callable:
	Story.hq("fx", ["purified_zone", Vector2i(10, 8)])
	return Callable()

func _tower5_step(x: int, y: int) -> Callable:
	if not PURIFIED.has(Vector2i(x, y)):
		Story.clear("EVENT_IN_PURIFIED_ZONE")
		return Callable()
	# inside the zone: always consume the step (no trainers, no encounters)
	if Story.flag("EVENT_IN_PURIFIED_ZONE"):
		return _noop
	return _purify

func _noop() -> void:
	await Story.wait(0)

func _purify() -> void:
	Story.setf("EVENT_IN_PURIFIED_ZONE")
	Story.heal_all()
	Story.sfx("heal")
	if Story._has_host("flash_white"):
		await Story.ha("flash_white", [8])
	else:
		await Story.wait(22)
	await Story.say("PokemonTower5FPurifiedZoneText")

## 6F: the restless soul of CUBONE's mother blocks the stairs
func _tower6_step(x: int, y: int) -> Callable:
	if Story.flag("EVENT_BEAT_GHOST_MAROWAK") or x != 10 or y != 16:
		return Callable()
	return _marowak

func _marowak() -> void:
	await Story.say("PokemonTower6FBeGoneText")
	var r := await Story.wild_battle("MAROWAK", 30, {"restless_soul": true})
	if r == "lose":
		return
	# a POKé DOLL escape counts as defeating it, like the original
	if r == "win" or r == "fled" or r == "run":
		Story.setf("EVENT_BEAT_GHOST_MAROWAK")
		await Story.say("PokemonTower6FGhostWasCubonesMotherText")
		Story.cry("MAROWAK")
		await Story.wait(30)
		await Story.say("PokemonTower6FSoulWasCalmedText")
		return
	await Story.move_player("R")

## 7F: Team Rocket grunts leave after losing (AFTER_TRAINER), then Mr. Fuji is rescued
func _tower7_rocket_leaves(o: Dictionary) -> void:
	var id: String = o.get("id", "")
	if not T7_EXIT.has(id):
		return
	var p := Story.pcell()
	await Story.say(o["th"]["after"])
	await Story.move(id, T7_EXIT[id].get("%d,%d" % [p.x, p.y], "DDDDD"))
	Story.hide(id)

func _tower7_fuji(_o: Dictionary) -> void:
	await Story.say("PokemonTower7FMrFujiRescueText")
	Story.setf("EVENT_RESCUED_MR_FUJI")
	Story.setf("EVENT_RESCUED_MR_FUJI_2")
	Story.show("MRFUJISHOUSE_MR_FUJI", "MrFujisHouse")
	Story.hide("SAFFRONCITY_ROCKET8", "SaffronCity")
	Story.show("SAFFRONCITY_ROCKET9", "SaffronCity")
	Story.hide("POKEMONTOWER7F_MR_FUJI")
	GameState.last_outdoor = "LavenderTown"
	var w: Dictionary = Story.map_data("MrFujisHouse")["warps"][1]
	await Story.warp("MrFujisHouse", int(w["x"]), int(w["y"]), "up")
	Story.map_music()

# ======================================================================
# Celadon City
# ======================================================================
func _celadon_gramps3(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_TM41"):
		await Story.say("CeladonCityGramps3TM41ExplanationText")
		return
	await Story.say("CeladonCityGramps3Text")
	if await Story.give_item("TM_SOFTBOILED", "CeladonCityGramps3ReceivedTM41Text", "CeladonCityGramps3TM41NoRoomText"):
		Story.setf("EVENT_GOT_TM41")

func _diner_guide(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_COIN_CASE"):
		await Story.say("CeladonDinerGymGuideWinItBackText")
		return
	await Story.say("CeladonDinerGymGuideImFlatOutBustedText")
	if await Story.give_item("COIN_CASE", "CeladonDinerGymGuideReceivedCoinCaseText", "CeladonDinerGymGuideCoinCaseNoRoomText"):
		Story.setf("EVENT_GOT_COIN_CASE")

## game designer: diploma once every POKéMON but MEW is owned
static func diploma() -> void:
	Story.sfx("get_key")
	var u := Story.get_ui()
	if u and u.has_method("diploma"):
		await u.call("diploma")
		return
	await Story.say("~ DIPLOMA ~\fPLAYER  " + GameState.player_name + "\fCongrats! This diploma certifies that you have completed your POKéDEX.\fGAME FREAK")

func _game_designer(_o: Dictionary) -> void:
	var owned := 0
	for sp in GameState.caught_species:
		if sp != "MEW":
			owned += 1
	if owned < 150:
		await Story.say("CeladonMansion3FGameDesignerText")
		return
	await Story.say("CeladonMansion3FGameDesignerCompletedDexText")
	await diploma()

func _eevee(_o: Dictionary) -> void:
	if await Story.gift_mon("EEVEE", 25):
		Story.hide("CELADONMANSION_ROOF_HOUSE_EEVEE_POKEBALL")

## blackboard: TRAINER TIPS on the link cable
func _link_cable_help(_h: Dictionary) -> void:
	await Story.say("LinkCableHelpText1")
	while true:
		var r := await Story.menu_with_text("LinkCableHelpText2", ["HOW TO LINK", "COLOSSEUM", "TRADE CENTER", "STOP READING"], {"x": 6, "y": 6})
		if r < 0 or r == 3:
			return
		await Story.say("LinkCableInfoText%d" % (r + 1))

func _mart3f_clerk(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_TM18"):
		await Story.say("CeladonMart3FClerkTM18ExplanationText")
		return
	await Story.say("CeladonMart3FClerkTM18PreReceiveText")
	if await Story.give_item("TM_COUNTER", "CeladonMart3FClerkReceivedTM18Text", "CeladonMart3FClerkTM18NoRoomText"):
		Story.setf("EVENT_GOT_TM18")

## elevators: exits lead back to the floor the player came from until a floor is chosen
func _elevator_enter(floors: Array) -> Callable:
	for f in floors:
		if f["map"] == Story.prev_map:
			Story.set_exit_warps(f["map"], int(f["warp"]))
			return Callable()
	var ws: Array = Story.map_data().get("warps", [])
	if not ws.is_empty() and ws[0].get("to", "") == "UNUSED_MAP_ED":
		Story.set_exit_warps(floors[0]["map"], int(floors[0]["warp"]))
	return Callable()

func _elevator(_s: Dictionary, floors: Array, needs_key: bool) -> void:
	if needs_key and not Story.bag_has("LIFT_KEY"):
		await Story.say("RocketHideoutElevatorAppearsToNeedKeyText")
		return
	await Story.elevator(floors)

## rooftop vending machines (engine/events/vending_machine.asm)
static func vending_machine() -> void:
	await Story.say("VendingMachineText1")
	var box := Story.info_box(func() -> Array: return [Story.money_str()])
	var drinks := [["FRESH_WATER", 200], ["SODA_POP", 300], ["LEMONADE", 350]]
	var items: Array = drinks.map(func(d): return Story.item_name(d[0]) + "  $" + str(d[1]))
	items.append("CANCEL")
	var r := await Story.choose(items, {"x": 6, "y": 40})
	Story.close_box(box)
	if r < 0 or r == 3:
		await Story.say("VendingMachineText7")
		return
	var item: String = drinks[r][0]
	var price: int = drinks[r][1]
	if GameState.money < price:
		await Story.say("VendingMachineText4")
		return
	if not Story.bag_add(item, 1):
		await Story.say("VendingMachineText6")
		return
	for i in 30:
		if i % 4 == 0:
			Story.sfx("boulder")
		await Story.wait(2)
	Story.setvar("wStringBuffer", Story.item_name(item))
	Story.setvar("wNameBuffer", Story.item_name(item))
	await Story.say("VendingMachineText5")
	GameState.money -= price

func _vending_h(_s: Dictionary) -> void:
	await vending_machine()

## the thirsty girl trades TMs for drinks
func _roof_girl(_o: Dictionary) -> void:
	var drinks: Array = ["FRESH_WATER", "SODA_POP", "LEMONADE"].filter(func(d): return Story.bag_has(d))
	if drinks.is_empty():
		await Story.say("CeladonMartRoofLittleGirlImThirstyText")
		return
	if not await Story.ask("CeladonMartRoofLittleGirlGiveHerADrinkText"):
		return
	var r := await Story.menu_with_text("CeladonMartRoofLittleGirlGiveHerWhichDrinkText", drinks.map(func(d): return Story.item_name(d)), {"x": 6, "y": 6})
	if r < 0:
		return
	var reward := {"FRESH_WATER": ["EVENT_GOT_TM13", "TM_ICE_BEAM", "FreshWater", "TM13"], "SODA_POP": ["EVENT_GOT_TM48", "TM_ROCK_SLIDE", "SodaPop", "TM48"],
		"LEMONADE": ["EVENT_GOT_TM49", "TM_TRI_ATTACK", "Lemonade", "TM49"]}
	var rw: Array = reward[drinks[r]]
	if Story.flag(rw[0]):
		await Story.say("CeladonMartRoofLittleGirlImNotThirstyText")
		return
	await Story.say("CeladonMartRoofLittleGirlYay" + str(rw[2]) + "Text")
	Story.bag_remove(drinks[r], 1)
	if not await Story.give_item(rw[1], "CeladonMartRoofLittleGirlReceived" + str(rw[3]) + "Text", "CeladonMartRoofLittleGirlNoRoomText"):
		return
	await Story.say("CeladonMartRoofLittleGirl" + str(rw[3]) + "ExplanationText")
	Story.setf(rw[0])

## Celadon Gym (Erika)
func _erika_reward() -> void:
	await Story.say("CeladonGymRainbowBadgeInfoText")
	Story.setf("EVENT_BEAT_ERIKA")
	if await Story.give_item("TM_MEGA_DRAIN", "CeladonGymReceivedTM21Text", "CeladonGymTM21NoRoomText"):
		await Story.say("TM21ExplanationText")
		Story.setf("EVENT_GOT_TM21")

func _erika(_o: Dictionary) -> void:
	if Story.flag("EVENT_BEAT_ERIKA"):
		if not Story.flag("EVENT_GOT_TM21"):
			await _erika_reward()
			return
		await Story.say("CeladonGymErikaPostBattleAdviceText")
		return
	await Story.say("CeladonGymErikaPreBattleText")
	var r := await Story.battle("ERIKA", 1, {"win_text": Story.fmt(Story.t("CeladonGymErikaReceivedRainbowBadgeText"))})
	if r != "win":
		return
	await Story.award_badge("RAINBOWBADGE")
	await _erika_reward()
	for i in 7:
		Story.setf("EVENT_BEAT_CELADON_GYM_TRAINER_%d" % i)

# ======================================================================
# Rocket Game Corner
# ======================================================================
func _gc_coins(h: Dictionary, n: int) -> void:
	if not Story.bag_has("COIN_CASE"):
		return
	var k := "HIDDENCOIN_GameCorner_%d_%d" % [int(h["x"]), int(h["y"])]
	if Story.flag(k):
		return
	if GameState.coins >= 9999:
		await Story.say("DroppedHiddenCoinsText")
		return
	Story.setf(k)
	Story.add_coins(n)
	Story.setvar("hCoins", n)
	Story.sfx("get_item")
	await Story.say("FoundHiddenCoinsText")

## slot machines: facing left/right at a machine (AbleToPlaySlotsCheck)
func _slot_hidden(h: Dictionary, idx: int) -> void:
	var arg := str(h.get("arg", ""))
	if arg == "SLOTS_OUTOFORDER":
		await Story.say("GameCornerOutOfOrderText")
		return
	if arg == "SLOTS_OUTTOLUNCH":
		await Story.say("GameCornerOutToLunchText")
		return
	if arg == "SLOTS_SOMEONESKEYS":
		await Story.say("GameCornerSomeonesKeysText")
		return
	if Story.pdir() != "left" and Story.pdir() != "right":
		return
	await slots.play(GameState.lucky_slot == idx)

func _coins_npc(_o: Dictionary, f: String, intro: String, recv: String, full: String, after: String, n: int, full_at: int) -> void:
	if Story.flag(f):
		await Story.say(after)
		return
	await Story.say(intro)
	if not Story.bag_has("COIN_CASE"):
		await Story.say("GameCornerOopsForgotCoinCaseText")
		return
	if GameState.coins >= full_at:
		await Story.say(full)
		return
	Story.add_coins(n)
	Story.setf(f)
	Story.sfx("get_item")
	await Story.say(recv)

func _gc_enter() -> Callable:
	# GameCornerSelectLuckySlotMachine
	var r := randi() % 256
	if r < 7:
		r = 8
	GameState.lucky_slot = r >> 3
	# the hideout stairs stay hidden behind a wall until the poster switch is found
	if not Story.flag("EVENT_FOUND_ROCKET_HIDEOUT"):
		Story.set_cell(17, 4, "wall", false)
	return Callable()

func _gc_poster(_s: Dictionary) -> void:
	await Story.say("GameCornerPosterSwitchBehindPosterText")
	Story.sfx("door")
	Story.setf("EVENT_FOUND_ROCKET_HIDEOUT")
	Story.restore_cell(17, 4)

func _gc_clerk1(_o: Dictionary) -> void:
	var box := Story.info_box(func() -> Array: return [Story.money_str(), Story.coin_str()])
	if not await Story.ask("GameCornerClerk1DoYouNeedSomeGameCoinsText"):
		await Story.say("GameCornerClerk1PleaseComePlaySometimeText")
	elif not Story.bag_has("COIN_CASE"):
		await Story.say("GameCornerClerk1DontHaveCoinCaseText")
	elif GameState.coins >= 9990:
		await Story.say("GameCornerClerk1CoinCaseIsFullText")
	elif GameState.money < 1000:
		await Story.say("GameCornerClerk1CantAffordTheCoinsText")
	else:
		GameState.money -= 1000
		Story.add_coins(50)
		Story.sfx("buy")
		await Story.say("GameCornerClerk1ThanksHereAre50CoinsText")
	Story.close_box(box)

func _gc_rocket(o: Dictionary) -> void:
	await Story.say("GameCornerRocketImGuardingThisPosterText")
	var r := await Story.battle("ROCKET", 7, {"win_text": Story.fmt(Story.t("GameCornerRocketBattleEndText"))})
	if r != "win":
		return
	await Story.say("GameCornerRocketAfterBattleText")
	var p := Story.pcell()
	await Story.move(o.get("id", ""), "RRRRR" if (p.y == 6 or p.x == 8) else "DRRURRRR")
	Story.hide("GAMECORNER_ROCKET")

## prize exchange (engine/events/prize_menu.asm, Red prices/levels)
static func prize_menu(which: int) -> void:
	if not Story.bag_has("COIN_CASE"):
		await Story.say("RequireCoinCaseText")
		return
	await Story.say("ExchangeCoinsForPrizesText")
	var list: Array = (Story.pokedata.get("prizes", PRIZES) as Array)[which]   # the active version's window (RED / BLUE / YELLOW)
	var is_tm := which == 2
	var box := Story.info_box(func() -> Array: return [Story.coin_str()])
	var items: Array = []
	for e in list:
		var nm := Story.item_name(e[0]) if is_tm else Story.species_name(e[0])
		items.append(nm.rpad(10) + str(e[1]).lpad(5))
	items.append("NO THANKS")
	var r := await Story.menu_with_text("WhichPrizeText", items, {"x": 6, "y": 30, "w": 200})
	if r < 0 or r == 3:
		Story.close_box(box)
		return
	var id: String = list[r][0]
	var cost: int = list[r][1]
	Story.setvar("wNameBuffer", Story.item_name(id) if is_tm else Story.species_name(id))
	if not await Story.ask("SoYouWantPrizeText"):
		await Story.say("OhFineThenText")
	elif GameState.coins < cost:
		await Story.say("SorryNeedMoreCoinsText")
	elif is_tm:
		if not Story.bag_add(id, 1):
			await Story.say("OopsYouDontHaveEnoughRoomText")
		else:
			Story.sfx("get_tm")
			Story.add_coins(-cost)
	elif await Story.gift_mon(id, int(list[r][2])):
		Story.add_coins(-cost)
	Story.close_box(box)

func _prize_h(_s: Dictionary, which: int) -> void:
	await prize_menu(which)

# ======================================================================
# Rocket Hideout
# ======================================================================
func _hideout_b1f_enter() -> Callable:
	if not Story.flag("EVENT_BEAT_ROCKET_HIDEOUT_1_TRAINER_4"):
		Story.set_cell(24, 16, "card_door", false)
		Story.set_cell(25, 16, "card_door", false)
	else:
		Story.setf("EVENT_ENTERED_ROCKET_HIDEOUT")
	return Callable()

func _hideout_b1f_after(o: Dictionary) -> void:
	if o.get("id", "") != "ROCKETHIDEOUTB1F_ROCKET5":
		return
	Story.sfx("door")
	Story.restore_cell(24, 16)
	Story.restore_cell(25, 16)
	await Story.wait(0)

func _b4f_door_open() -> bool:
	return Story.flag("EVENT_BEAT_ROCKET_HIDEOUT_4_TRAINER_0") and Story.flag("EVENT_BEAT_ROCKET_HIDEOUT_4_TRAINER_1")

func _hideout_b4f_after(o: Dictionary) -> void:
	var id: String = o.get("id", "")
	if not (id.ends_with("ROCKET1") or id.ends_with("ROCKET2")) or Story.flag("EVENT_ROCKET_HIDEOUT_4_DOOR_UNLOCKED") or not _b4f_door_open():
		return
	Story.setf("EVENT_ROCKET_HIDEOUT_4_DOOR_UNLOCKED")
	Story.sfx("door")
	Story.restore_cell(24, 11)
	Story.restore_cell(25, 11)
	await Story.wait(0)

func _hideout_b4f_enter() -> Callable:
	if not Story.flag("EVENT_ROCKET_HIDEOUT_4_DOOR_UNLOCKED"):
		if _b4f_door_open():
			Story.setf("EVENT_ROCKET_HIDEOUT_4_DOOR_UNLOCKED")
		else:
			Story.set_cell(24, 11, "card_door", false)
			Story.set_cell(25, 11, "card_door", false)
	return Callable()

func _hideout_giovanni(_o: Dictionary) -> void:
	if Story.flag("EVENT_BEAT_ROCKET_HIDEOUT_GIOVANNI"):
		await Story.say("RocketHideoutB4FGiovanniHopeWeMeetAgainText")
		return
	await Story.say("RocketHideoutB4FGiovanniImpressedYouGotHereText")
	var r := await Story.battle("GIOVANNI", 1, {"win_text": Story.fmt(Story.t("RocketHideoutB4FGiovanniWhatCannotBeText"))})
	if r != "win":
		return
	Story.setf("EVENT_BEAT_ROCKET_HIDEOUT_GIOVANNI")
	await Story.say("RocketHideoutB4FGiovanniHopeWeMeetAgainText")
	await Story.fade_out(12)
	Story.hide("ROCKETHIDEOUTB4F_GIOVANNI")
	Story.show("ROCKETHIDEOUTB4F_SILPH_SCOPE")
	await Story.wait(10)
	await Story.fade_in(12)

## the grunt drops the LIFT KEY when talked to after his defeat
func _hideout_rocket3(o: Dictionary) -> void:
	if not Story.flag(o["th"]["flag"]):
		await Story.trainer_battle_flow(o)
		return
	await Story.say("RocketHideoutB4FRocket3AfterBattleText")
	if not Story.flag("EVENT_ROCKET_DROPPED_LIFT_KEY"):
		Story.setf("EVENT_ROCKET_DROPPED_LIFT_KEY")
		Story.show("ROCKETHIDEOUTB4F_LIFT_KEY")

# ======================================================================
# Saffron City
# ======================================================================
func _sabrina_reward() -> void:
	await Story.say("SaffronGymSabrinaMarshBadgeInfoText")
	Story.setf("EVENT_BEAT_SABRINA")
	if Story.bag_add("TM_PSYWAVE", 1):
		Story.setvar("wStringBuffer", Story.item_name("TM_PSYWAVE"))
		Story.setvar("wNameBuffer", Story.item_name("TM_PSYWAVE"))
		Story.sfx("get_tm")
		await Story.say("SaffronGymSabrinaReceivedTM46Text")
		await Story.say("TM46ExplanationText")
		Story.setf("EVENT_GOT_TM46")
	else:
		await Story.say("SaffronGymSabrinaTM46NoRoomText")

func _sabrina(_o: Dictionary) -> void:
	if Story.flag("EVENT_BEAT_SABRINA"):
		if not Story.flag("EVENT_GOT_TM46"):
			await _sabrina_reward()
			return
		await Story.say("SaffronGymSabrinaPostBattleAdviceText")
		return
	await Story.say("SaffronGymSabrinaText")
	var r := await Story.battle("SABRINA", 1, {"win_text": Story.fmt(Story.t("SaffronGymSabrinaReceivedMarshBadgeText"))})
	if r != "win":
		return
	await Story.award_badge("MARSHBADGE")
	await _sabrina_reward()
	for i in 7:
		Story.setf("EVENT_BEAT_SAFFRON_GYM_TRAINER_%d" % i)

func _copycat(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_TM31"):
		await Story.say("CopycatsHouse2FCopycatTM31Explanation2Text")
		return
	await Story.say("CopycatsHouse2FCopycatDoYouLikePokemonText")
	if not Story.bag_has("POKE_DOLL"):
		return
	await Story.say("CopycatsHouse2FCopycatTM31PreReceiveText")
	if not await Story.give_item("TM_MIMIC", "CopycatsHouse2FCopycatReceivedTM31Text", "CopycatsHouse2FCopycatTM31NoRoomText"):
		return
	await Story.say("CopycatsHouse2FCopycatTM31Explanation1Text")
	Story.bag_remove("POKE_DOLL", 1)
	Story.setf("EVENT_GOT_TM31")

func _copycat_pc(_s: Dictionary) -> void:
	await Story.say("CopycatsHouse2FPCMySecretsText" if Story.pdir() == "up" else "CopycatsHouse2FPCCantSeeText")

## Fighting Dojo: beat the Karate Master, then pick HITMONLEE or HITMONCHAN
func karate_master(master: String) -> void:
	if Story.flag("EVENT_DEFEATED_FIGHTING_DOJO"):
		await Story.say("FightingDojoKarateMasterStayAndTrainWithUsText")
		return
	if Story.flag("EVENT_BEAT_KARATE_MASTER"):
		await Story.say("FightingDojoKarateMasterIWillGiveYouAPokemonText")
		return
	await Story.say("FightingDojoKarateMasterText")
	var r := await Story.battle("BLACKBELT", 1, {"win_text": Story.fmt(Story.t("FightingDojoKarateMasterDefeatedText"))})
	if r != "win":
		return
	if master != "":
		Story.face_to(master, P)
	Story.setf("EVENT_BEAT_KARATE_MASTER")
	for i in 4:
		Story.setf("EVENT_BEAT_FIGHTING_DOJO_TRAINER_%d" % i)
	await Story.say("FightingDojoKarateMasterIWillGiveYouAPokemonText")

func _karate_master_talk(o: Dictionary) -> void:
	await karate_master(o.get("id", ""))

func _dojo_ball(_o: Dictionary, sp: String, id: String, ev: String, label: String) -> void:
	if Story.flag("EVENT_GOT_HITMONLEE") or Story.flag("EVENT_GOT_HITMONCHAN"):
		await Story.say("FightingDojoBetterNotGetGreedyText")
		return
	Story.dex_seen(sp)
	await Story.dex_page(sp)
	if not await Story.ask(label):
		return
	if not await Story.gift_mon(sp, 30):
		return
	Story.hide(id)
	Story.setf(ev)
	Story.setf("EVENT_DEFEATED_FIGHTING_DOJO")

func _dojo_step(x: int, y: int) -> Callable:
	if x != 4 or y != 3 or Story.flag("EVENT_DEFEATED_FIGHTING_DOJO") or Story.flag("EVENT_BEAT_KARATE_MASTER") or not Story.trainer_in_sight().is_empty():
		return Callable()
	return _dojo_master_step

func _dojo_master_step() -> void:
	var m := "FIGHTINGDOJO_KARATE_MASTER"
	Story.face(P, "right")
	if Story.actor(m):
		Story.face(m, "left")
	await karate_master(m if Story.actor(m) else "")

# ======================================================================
# Silph Co.
# ======================================================================
func _beat_gio() -> bool:
	return Story.flag("EVENT_BEAT_SILPH_CO_GIOVANNI")

func _silph_talk(_o: Dictionary, before: String, after: String) -> void:
	await Story.say(after if _beat_gio() else before)

static func door_cells(d: Array) -> Array:
	var x := int(d[1]) * 2
	var y := int(d[2]) * 2
	match str(d[3]):
		"h":
			return [Vector2i(x, y), Vector2i(x + 1, y)]
		"v":
			return [Vector2i(x + 1, y), Vector2i(x + 1, y + 1)]
	return [Vector2i(x, y + 1), Vector2i(x + 1, y + 1)]

func apply_card_doors(map_name: String) -> void:
	for d in CARD_DOORS.get(map_name, []):
		if Story.flag(d[0]):
			continue
		for c in door_cells(d):
			Story.set_cell(c.x, c.y, "card_door", false)

func _card_door_at(c: Vector2i) -> Array:
	for d in CARD_DOORS.get(Story.mapname(), []):
		if not Story.flag(d[0]) and door_cells(d).has(c):
			return d
	return []

func _card_key(d: Array) -> void:
	if not Story.bag_has("CARD_KEY"):
		await Story.say("CardKeyFailText")
		return
	Story.sfx("get_item")
	await Story.say(Story.fmt(Story.t("CardKeySuccessText1")) + "\f" + Story.fmt(Story.t("CardKeySuccessText2")))
	Story.setf(d[0])
	for c in door_cells(d):
		Story.restore_cell(c.x, c.y)
	Story.sfx("door")

func _silph_floor(n: int, spec: Dictionary) -> void:
	var map_name := "SilphCo%dF" % n
	var prev: Callable = spec.get("enter", Callable())
	spec["enter"] = func() -> Callable:
		apply_card_doors(map_name)
		return prev.call() if prev.is_valid() else Callable()
	Story.def_map(map_name, spec)

func _silph1_enter() -> Callable:
	if _beat_gio() and not Story.flag("EVENT_SILPH_CO_RECEPTIONIST_AT_DESK"):
		Story.setf("EVENT_SILPH_CO_RECEPTIONIST_AT_DESK")
		Story.show("SILPHCO1F_LINK_RECEPTIONIST")
	return Callable()

## 7F: LAPRAS gift and the rival ambush next to the 11F teleporter
func silph7_rival(lower: bool) -> void:
	var rival := "SILPHCO7F_RIVAL"
	Story.music("rival")
	Story.face(P, "down")
	await Story.say("SilphCo7FRivalText")
	await Story.move(rival, "UUU" if lower else "UUUU")
	await Story.say("SilphCo7FRivalWaitedHereText")
	var r := await Story.battle("RIVAL2", Story.rival_party(7), {"win_text": Story.fmt(Story.t("SilphCo7FRivalDefeatedText")), "lose_text": Story.fmt(Story.t("SilphCo7FRivalVictoryText"))})
	if r != "win":
		return
	Story.setf("EVENT_BEAT_SILPH_CO_RIVAL")
	Story.face(P, "down")
	Story.face(rival, "up")
	await Story.say("SilphCo7FRivalGoodLuckToYouText")
	Story.music("rival")
	await Story.move(rival, "LUURRRD" if lower else "RR")
	Story.hide("SILPHCO7F_RIVAL")
	Story.map_music()

func _silph7_step(x: int, y: int) -> Callable:
	if Story.flag("EVENT_BEAT_SILPH_CO_RIVAL") or x != 3 or (y != 2 and y != 3):
		return Callable()
	return silph7_rival.bind(y == 3)

func _silph7_lapras(_o: Dictionary) -> void:
	if not Story.flag("EVENT_GOT_LAPRAS"):
		await Story.say("SilphCo7FSilphWorkerM1HaveThisPokemonText")
		if not await Story.gift_mon("LAPRAS", 15):
			return
		await Story.say("SilphCo7FSilphWorkerM1LaprasDescriptionText")
		Story.setf("EVENT_GOT_LAPRAS")
		return
	await Story.say("SilphCo7FSilphWorkerM1SavedText" if _beat_gio() else "SilphCo7FSilphWorkerM1IsOurPresidentOkText")

func _silph9_nurse(_o: Dictionary) -> void:
	if _beat_gio():
		await Story.say("SilphCo9FNurseThankYouText")
		return
	await Story.say("SilphCo9FNurseYouLookTiredText")
	Story.heal_all()
	Story.sfx("heal")
	if Story._has_host("flash_white"):
		await Story.ha("flash_white", [8])
	else:
		await Story.wait(22)
	await Story.say("SilphCo9FNurseDontGiveUpText")

static func team_rocket_leaves_saffron() -> void:
	for e in ROCKETS_LEAVE_HIDE:
		for id in e[1]:
			Story.hide(str(e[0]).to_upper() + "_" + id, e[0])
	for e in ROCKETS_LEAVE_SHOW:
		for id in e[1]:
			Story.show(str(e[0]).to_upper() + "_" + id, e[0])

func silph11_giovanni(upper: bool) -> void:
	var gio := "SILPHCO11F_GIOVANNI"
	await Story.say("SilphCo11FGiovanniText")
	await Story.move(gio, "DDD")
	# player at (7,12) stands right of Giovanni, at (6,13) right below him
	if upper:
		Story.face(P, "left")
		Story.face(gio, "right")
	else:
		Story.face(P, "up")
		Story.face(gio, "down")
	await Story.wait(4)
	var r := await Story.battle("GIOVANNI", 2, {"win_text": Story.fmt(Story.t("SilphCo11FGiovanniILostAgainText"))})
	if r != "win":
		return
	await Story.say("SilphCo11FGiovanniYouRuinedOurPlansText")
	await Story.fade_out(16)
	team_rocket_leaves_saffron()
	Story.setf("EVENT_BEAT_SILPH_CO_GIOVANNI")
	await Story.wait(10)
	await Story.fade_in(16)

func _silph11_step(x: int, y: int) -> Callable:
	if _beat_gio():
		return Callable()
	if x == 6 and y == 13:
		return silph11_giovanni.bind(false)
	if x == 7 and y == 12:
		return silph11_giovanni.bind(true)
	return Callable()

func _silph_president(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_MASTER_BALL"):
		await Story.say("SilphCo11FSilphPresidentMasterBallDescriptionText")
		return
	await Story.say("SilphCo11FSilphPresidentText")
	if await Story.give_item("MASTER_BALL", "SilphCo11FSilphPresidentReceivedMasterBallText", "SilphCo11FSilphPresidentNoRoomText"):
		Story.setf("EVENT_GOT_MASTER_BALL")

# ======================================================================
# Routes 16-18
# ======================================================================
func _route18_trade(_o: Dictionary) -> void:
	await Story.in_game_trade(5, {"ask": Story.txt("WannaTrade1Text"), "no": Story.txt("NoTrade1Text"), "wrong": Story.txt("WrongMon1Text"),
		"done": Story.txt("Thanks1Text"), "after": Story.txt("AfterTrade1Text")})

func _fly_house_girl(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_HM02"):
		await Story.say("Route16FlyHouseBrunetteGirlHM02ExplanationText")
		return
	await Story.say("Route16FlyHouseBrunetteGirlText")
	if not await Story.give_item("HM_FLY", "Route16FlyHouseBrunetteGirlReceivedHM02Text", "Route16FlyHouseBrunetteGirlHM02NoRoomText"):
		return
	Story.setf("EVENT_GOT_HM02")
	await Story.say("Route16FlyHouseBrunetteGirlHM02ExplanationText")

# ======================================================================
# Slot machine (engine/slots/slot_machine.asm), game logic.
# The reel scene itself is drawn by UI.slot_machine_scene(state) when the UI
# provides one; otherwise reels stop at once and results are told in text.
# ======================================================================
class SlotMachine extends RefCounted:
	const SEVEN := 0
	const BAR := 1
	const CHERRY := 2
	const SYM_NAME := ["7", "BAR", "CHERRY", "FISH", "BIRD", "MOUSE"]
	const SYM_PAY := [300, 100, 8, 15, 15, 15]
	const F_WIN := 1
	const F_WIN7 := 2
	const LINES := {"mid": [1, 1, 1], "top": [2, 2, 2], "bot": [0, 0, 0], "d1": [0, 1, 2], "d2": [2, 1, 0]}
	var wheels: Array = []
	var pos: Array = [0, 0, 0]
	var bet := 0
	var st := {"flags": 0, "counter": 0, "reroll": 256, "chance": 253}

	func _init() -> void:
		var names := {"SEVEN": 0, "BAR": 1, "CHERRY": 2, "FISH": 3, "BIRD": 4, "MOUSE": 5}
		for w in ["SEVEN MOUSE FISH BAR CHERRY SEVEN FISH BIRD BAR CHERRY SEVEN MOUSE BIRD BAR CHERRY SEVEN MOUSE FISH",
				"SEVEN FISH CHERRY BIRD MOUSE BAR CHERRY FISH BIRD CHERRY BAR FISH BIRD CHERRY MOUSE SEVEN FISH CHERRY",
				"SEVEN BIRD FISH CHERRY MOUSE BIRD FISH CHERRY MOUSE BIRD FISH CHERRY MOUSE BIRD BAR SEVEN BIRD FISH"]:
			wheels.append(Array(w.split(" ")).map(func(n): return names[n]))

	func sym(r: int, row: int) -> int:
		return wheels[r][(int(pos[r]) + row) % 18]

	func find_match() -> int:
		var order := ["mid"]
		if bet == 3:
			order = ["d1", "d2", "top", "bot", "mid"]
		elif bet == 2:
			order = ["top", "bot", "mid"]
		for k in order:
			var rows: Array = LINES[k]
			var a := sym(0, rows[0])
			if a == sym(1, rows[1]) and a == sym(2, rows[2]):
				return a
		return -1

	func wheel12_match() -> int:
		for xy in [[0, 0], [0, 1], [1, 1], [2, 1], [2, 2]]:
			if sym(0, xy[0]) == sym(1, xy[1]):
				return sym(0, xy[0])
		return -1

	func set_flags() -> void:
		if st["flags"] & F_WIN7:
			return
		if st["counter"] > 0:
			st["flags"] |= F_WIN
			return
		var b := randi() % 256
		if b == 0:
			st["counter"] = 60
			return
		if st["chance"] < b:
			st["flags"] |= F_WIN7
			return
		if 210 < b:
			st["flags"] |= F_WIN
			return
		st["flags"] = 0

	## the reels stop where the player stops them (random here), with the machine's slip rules
	func spin() -> void:
		for i in 3:
			pos[i] = randi() % 18
			var slip := 4
			while slip > 0:
				var keep := false
				if i == 0:
					keep = true if st["flags"] & F_WIN7 else sym(0, 1) == CHERRY
				elif i == 1:
					var m := wheel12_match()
					keep = not (m == SEVEN or m == BAR) if st["flags"] & F_WIN7 else m < 0
				if not keep:
					break
				slip -= 1
				pos[i] = (pos[i] + 1) % 18

	func check_matches() -> int:
		for guard in 300:
			var m := find_match()
			var allowed: int = st["flags"] & (F_WIN | F_WIN7)
			if m < 0:
				st["reroll"] -= 1
				if not allowed or st["reroll"] <= 0:
					return -1
				pos[2] = (pos[2] + 1) % 18
				continue
			if not allowed:
				pos[2] = (pos[2] + 1) % 18
				continue
			if not (st["flags"] & F_WIN7) and (m == SEVEN or m == BAR):
				pos[2] = (pos[2] + 1) % 18
				continue
			return m
		return -1

	func play(lucky: bool) -> void:
		if not Story.bag_has("COIN_CASE"):
			await Story.say("GameCornerCoinCaseText")
			return
		if GameState.coins <= 0:
			await Story.say("GameCornerNoCoinsText")
			return
		if not await Story.ask("PlaySlotMachineText"):
			return
		st = {"flags": 0, "counter": 0, "reroll": 256, "chance": 250 if lucky else 253}
		var ui := Story.get_ui()
		if ui and ui.has_method("slot_machine_open"):
			ui.call("slot_machine_open", self)
		while true:
			bet = 0
			var b := 0
			while true:
				var r := await Story.menu_with_text("BetHowManySlotMachineText", ["×3", "×2", "×1"], {"x": 250, "y": 60, "w": 64})
				if r < 0:
					_close(ui)
					return
				b = 3 - r
				if GameState.coins < b:
					await Story.say("NotEnoughCoinsSlotMachineText")
					continue
				break
			Story.add_coins(-b)
			bet = b
			set_flags()
			st["reroll"] = 256
			Story.sfx("select")
			spin()
			if ui and ui.has_method("slot_machine_spin"):
				await ui.call("slot_machine_spin", self)
			var m := check_matches()
			if m < 0:
				await Story.say("NotThisTimeText")
			else:
				var pay: int = SYM_PAY[m]
				if pay == 300:
					await Story.say("YeahText")
					if randi() % 256 >= 0x80:
						st["flags"] = 0
					st["counter"] = 0
				elif pay == 100:
					st["flags"] = 0
				elif st["counter"] > 0:
					st["counter"] -= 1
				Story.sfx("get_key" if pay >= 100 else "get_item")
				Story.setvar("wStringBuffer", str(pay))
				await Story.say(SYM_NAME[m] + " " + Story.fmt(Story.t("LinedUpText")))
				Story.add_coins(pay)
			if GameState.coins <= 0:
				await Story.say("OutOfCoinsSlotMachineText")
				await Story.wait(60)
				_close(ui)
				return
			if not await Story.ask("OneMoreGoSlotMachineText"):
				_close(ui)
				return

	func _close(ui: Node) -> void:
		if ui and ui.has_method("slot_machine_close"):
			ui.call("slot_machine_close")
