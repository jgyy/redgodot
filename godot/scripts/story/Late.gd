extends RefCounted
## Port of upstream src/scripts/late.js: Routes 12-16 (Snorlax + POKé FLUTE, gates,
## Super Rod house), Fuchsia City (Koga, Safari Zone, Warden, Good Rod), Seafoam
## Islands (boulders/currents, Articuno), Cinnabar Island (Mansion switches, Blaine's
## quiz gym, Lab fossils/trades), Power Plant (Zapdos), Viridian Gym (Giovanni),
## Route 22 gate, Route 23 badge guards, Victory Road (switches, Moltres), Indigo
## Plateau (Elite Four, Champion, Hall of Fame, credits) and Cerulean Cave (Mewtwo).

const P := "PLAYER"
const SNORLAX := {
	"Route12": {"id": "ROUTE12_SNORLAX", "beat": "EVENT_BEAT_ROUTE12_SNORLAX", "fight": "EVENT_FIGHT_ROUTE12_SNORLAX",
		"coords": [Vector2i(9, 62), Vector2i(10, 61), Vector2i(10, 63), Vector2i(11, 62)], "talk": "Route12SnorlaxText", "woke": "Route12SnorlaxWokeUpText", "calm": "Route12SnorlaxCalmedDownText"},
	"Route16": {"id": "ROUTE16_SNORLAX", "beat": "EVENT_BEAT_ROUTE16_SNORLAX", "fight": "EVENT_FIGHT_ROUTE16_SNORLAX",
		"coords": [Vector2i(27, 10), Vector2i(25, 10)], "talk": "Route16Text7", "woke": "Route16SnorlaxWokeUpText", "calm": "Route16SnorlaxReturnedToMountainsText"},
}
## holes: boulder pushed in -> event + boulder appears below; player steps in -> falls to `land`
const SEAFOAM := {
	"SeafoamIslands1F": {"below": "SeafoamIslandsB1F", "holes": [Vector2i(17, 6), Vector2i(24, 6)], "land": [Vector2i(18, 7), Vector2i(23, 7)],
		"ev": ["EVENT_SEAFOAM1_BOULDER1_DOWN_HOLE", "EVENT_SEAFOAM1_BOULDER2_DOWN_HOLE"], "show": ["SEAFOAMISLANDSB1F_BOULDER1", "SEAFOAMISLANDSB1F_BOULDER2"]},
	"SeafoamIslandsB1F": {"below": "SeafoamIslandsB2F", "holes": [Vector2i(18, 6), Vector2i(23, 6)], "land": [Vector2i(19, 7), Vector2i(22, 7)],
		"ev": ["EVENT_SEAFOAM2_BOULDER1_DOWN_HOLE", "EVENT_SEAFOAM2_BOULDER2_DOWN_HOLE"], "show": ["SEAFOAMISLANDSB2F_BOULDER1", "SEAFOAMISLANDSB2F_BOULDER2"]},
	"SeafoamIslandsB2F": {"below": "SeafoamIslandsB3F", "holes": [Vector2i(19, 6), Vector2i(22, 6)], "land": [Vector2i(18, 7), Vector2i(19, 7)],
		"ev": ["EVENT_SEAFOAM3_BOULDER1_DOWN_HOLE", "EVENT_SEAFOAM3_BOULDER2_DOWN_HOLE"], "show": ["SEAFOAMISLANDSB3F_BOULDER5", "SEAFOAMISLANDSB3F_BOULDER6"]},
	"SeafoamIslandsB3F": {"below": "SeafoamIslandsB4F", "holes": [Vector2i(3, 16), Vector2i(6, 16)], "land": [Vector2i(4, 14), Vector2i(5, 14)],
		"ev": ["EVENT_SEAFOAM4_BOULDER1_DOWN_HOLE", "EVENT_SEAFOAM4_BOULDER2_DOWN_HOLE"], "show": ["SEAFOAMISLANDSB4F_BOULDER1", "SEAFOAMISLANDSB4F_BOULDER2"]},
}
const VR_SWITCH := {
	"VictoryRoad1F": [{"at": Vector2i(17, 13), "ev": "EVENT_VICTORY_ROAD_1_BOULDER_ON_SWITCH", "cells": [[9, 12, "cave_high", true]]}],
	"VictoryRoad2F": [{"at": Vector2i(1, 16), "ev": "EVENT_VICTORY_ROAD_2_BOULDER_ON_SWITCH1", "cells": [[7, 8, "cave_high", true], [7, 9, "cave_high", true]]},
		{"at": Vector2i(9, 16), "ev": "EVENT_VICTORY_ROAD_2_BOULDER_ON_SWITCH2", "cells": [[23, 14, "cave_high", true]]}],
	"VictoryRoad3F": [{"at": Vector2i(3, 5), "ev": "EVENT_VICTORY_ROAD_3_BOULDER_ON_SWITCH1", "cells": [[7, 10, "cave_high", true]]}],
}
## A 32x32 block = 2x2 cells. mask = [tl, tr, bl, br] with 'X' = blocked.
const BLOCK := {"O": "PPPP", "H": "PPXX", "T": "XXPP", "V": "PXPX"}
const R23 := [[35, "EARTHBADGE", "ROUTE23_GUARD1"], [56, "VOLCANOBADGE", "ROUTE23_GUARD2"], [85, "MARSHBADGE", "ROUTE23_SWIMMER1"],
	[96, "SOULBADGE", "ROUTE23_SWIMMER2"], [105, "RAINBOWBADGE", "ROUTE23_GUARD3"], [119, "THUNDERBADGE", "ROUTE23_GUARD4"], [136, "CASCADEBADGE", "ROUTE23_GUARD5"]]
const MANSION := {
	"PokemonMansion1F": {"off": [[12, 6, "O"], [8, 3, "H"], [10, 8, "H"], [13, 13, "H"]], "on": [[12, 6, "H"], [8, 3, "O"], [10, 8, "O"], [13, 13, "O"]], "switches": ["2,5"], "text": "PokemonMansion1F"},
	"PokemonMansion2F": {"off": [[4, 2, "O"], [9, 4, "T"], [3, 11, "V"]], "on": [[4, 2, "V"], [9, 4, "O"], [3, 11, "O"]], "switches": ["2,11"], "text": "PokemonMansion2F"},
	"PokemonMansion3F": {"off": [[7, 2, "O"], [7, 5, "V"]], "on": [[7, 2, "V"], [7, 5, "O"]], "switches": ["10,5"], "text": "PokemonMansion2F"},
	"PokemonMansionB1F": {"off": [[13, 8, "O"], [6, 11, "O"], [4, 3, "V"], [8, 8, "T"]], "on": [[13, 8, "H"], [6, 11, "V"], [4, 3, "O"], [8, 8, "O"]], "switches": ["20,3", "18,25"], "text": "PokemonMansion2F"},
}
const CG_GATES := [null, [9, 3, "T"], [6, 3, "T"], [6, 6, "T"], [3, 8, "V"], [2, 6, "T"], [2, 3, "T"]]
const CG_QUIZ := {"15,7": [1, true], "10,1": [2, false], "9,7": [3, false], "9,13": [4, false], "1,13": [5, true], "1,7": [6, false]}
const CG_NERDS := ["CINNABARGYM_SUPER_NERD1", "CINNABARGYM_SUPER_NERD2", "CINNABARGYM_SUPER_NERD3", "CINNABARGYM_SUPER_NERD4",
	"CINNABARGYM_SUPER_NERD5", "CINNABARGYM_SUPER_NERD6", "CINNABARGYM_SUPER_NERD7"]
const FOSSILS := [["DOME_FOSSIL", "KABUTO"], ["HELIX_FOSSIL", "OMANYTE"], ["OLD_AMBER", "AERODACTYL"]]
const PP := {"POWERPLANT_VOLTORB1": 0, "POWERPLANT_VOLTORB2": 1, "POWERPLANT_VOLTORB3": 2, "POWERPLANT_ELECTRODE1": 3,
	"POWERPLANT_VOLTORB4": 4, "POWERPLANT_VOLTORB5": 5, "POWERPLANT_ELECTRODE2": 6, "POWERPLANT_VOLTORB6": 7}
const E4_EVENTS := ["EVENT_BEAT_LORELEIS_ROOM_TRAINER_0", "EVENT_AUTOWALKED_INTO_LORELEIS_ROOM", "EVENT_BEAT_BRUNOS_ROOM_TRAINER_0", "EVENT_AUTOWALKED_INTO_BRUNOS_ROOM",
	"EVENT_BEAT_AGATHAS_ROOM_TRAINER_0", "EVENT_AUTOWALKED_INTO_AGATHAS_ROOM", "EVENT_BEAT_LANCES_ROOM_TRAINER_0", "EVENT_BEAT_LANCE", "EVENT_LANCES_ROOM_LOCK_DOOR", "EVENT_BEAT_CHAMPION_RIVAL"]
const E4 := {
	"LoreleisRoom": {"id": "LORELEISROOM_LORELEI", "cls": "LORELEI", "beat": "EVENT_BEAT_LORELEIS_ROOM_TRAINER_0", "auto": "EVENT_AUTOWALKED_INTO_LORELEIS_ROOM", "run": "LoreleisRoomLoreleiDontRunAwayText", "floor": "floor_stone"},
	"BrunosRoom": {"id": "BRUNOSROOM_BRUNO", "cls": "BRUNO", "beat": "EVENT_BEAT_BRUNOS_ROOM_TRAINER_0", "auto": "EVENT_AUTOWALKED_INTO_BRUNOS_ROOM", "run": "BrunosRoomBrunoDontRunAwayText", "floor": "floor_stone"},
	"AgathasRoom": {"id": "AGATHASROOM_AGATHA", "cls": "AGATHA", "beat": "EVENT_BEAT_AGATHAS_ROOM_TRAINER_0", "auto": "EVENT_AUTOWALKED_INTO_AGATHAS_ROOM", "run": "AgathasRoomAgathaDontRunAwayText", "floor": "floor_tower"},
}
const SAFARI_MAPS := ["SafariZoneCenter", "SafariZoneEast", "SafariZoneNorth", "SafariZoneWest", "SafariZoneCenterRestHouse",
	"SafariZoneEastRestHouse", "SafariZoneNorthRestHouse", "SafariZoneWestRestHouse", "SafariZoneSecretHouse"]

var gate22_passed := false

func register() -> void:
	# ---- Routes 12/16: Snorlax + POKé FLUTE
	Story.def_map("Route12", {"talk": {"ROUTE12_SNORLAX": _say.bind(SNORLAX["Route12"]["talk"])}})
	Story.def_map("Route16", {"talk": {"ROUTE16_SNORLAX": _say.bind(SNORLAX["Route16"]["talk"])}})
	Story.def_map("Route12Gate2F", {
		"talk": {"ROUTE12GATE2F_BRUNETTE_GIRL": _gift.bind("EVENT_GOT_TM39", "Route12Gate2FBrunetteGirlTM39ExplanationText", "Route12Gate2FBrunetteGirlYouCanHaveThisText", "TM_SWIFT", "Route12Gate2FBrunetteGirlReceivedTM39Text", "Route12Gate2FBrunetteGirlTM39NoRoomText")},
		"sign": {"TEXT_ROUTE12GATE2F_LEFT_BINOCULARS": _facing_up.bind("Route12Gate2FLeftBinocularsText"), "TEXT_ROUTE12GATE2F_RIGHT_BINOCULARS": _facing_up.bind("Route12Gate2FRightBinocularsText")}})
	Story.def_map("Route12SuperRodHouse", {"talk": {"ROUTE12SUPERRODHOUSE_FISHING_GURU": _super_rod}})
	Story.def_map("Route15Gate2F", {
		"talk": {"ROUTE15GATE2F_OAKS_AIDE": _aide.bind(50, "EXP_ALL", "EVENT_GOT_EXP_ALL", "Route15Gate2FOaksAideExpAllText")},
		"sign": {"TEXT_ROUTE15GATE2F_BINOCULARS": _facing_up.bind("Route15Gate2FBinocularsText")},
		"hidden": {"1,2": _articuno_binoculars}})
	# ---- Fuchsia
	Story.def_map("FuchsiaCity", {"sign": {
		"TEXT_FUCHSIACITY_CHANSEY_SIGN": _dex_sign.bind("FuchsiaCityChanseySignText", "CHANSEY"),
		"TEXT_FUCHSIACITY_VOLTORB_SIGN": _dex_sign.bind("FuchsiaCityVoltorbSignText", "VOLTORB"),
		"TEXT_FUCHSIACITY_KANGASKHAN_SIGN": _dex_sign.bind("FuchsiaCityKangaskhanSignText", "KANGASKHAN"),
		"TEXT_FUCHSIACITY_SLOWPOKE_SIGN": _dex_sign.bind("FuchsiaCitySlowpokeSignText", "SLOWPOKE"),
		"TEXT_FUCHSIACITY_LAPRAS_SIGN": _dex_sign.bind("FuchsiaCityLaprasSignText", "LAPRAS"),
		"TEXT_FUCHSIACITY_FOSSIL_SIGN": _fossil_sign}})
	var fuchsia_trainers: Array = range(6).map(func(i): return "EVENT_BEAT_FUCHSIA_GYM_TRAINER_%d" % i)
	Story.def_map("FuchsiaGym", {"talk": {
		"FUCHSIAGYM_KOGA": _leader.bind({"cls": "KOGA", "beat": "EVENT_BEAT_KOGA", "gotTM": "EVENT_GOT_TM06", "tm": "TM_TOXIC", "badge": "SOULBADGE", "trainers": fuchsia_trainers,
			"before": "FuchsiaGymKogaBeforeBattleText", "win": "FuchsiaGymKogaReceivedSoulBadgeText", "info": "FuchsiaGymKogaSoulBadgeInfoText",
			"recv": "FuchsiaGymKogaReceivedTM06Text", "explain": "FuchsiaGymKogaTM06ExplanationText", "noRoom": "FuchsiaGymKogaTM06NoRoomText", "after": "FuchsiaGymKogaPostBattleAdviceText"}),
		"FUCHSIAGYM_GYM_GUIDE": _flag_say.bind("EVENT_BEAT_KOGA", "FuchsiaGymGymGuideChampInMakingText", "FuchsiaGymGymGuideBeatKogaText")}})
	Story.def_map("FuchsiaGoodRodHouse", {"talk": {"FUCHSIAGOODRODHOUSE_FISHING_GURU": _good_rod}})
	Story.def_map("WardensHouse", {
		"talk": {"WARDENSHOUSE_WARDEN": _warden},
		"sign": {"TEXT_WARDENSHOUSE_DISPLAY_LEFT": _say.bind("WardensHouseDisplayPhotosAndFossilsText"), "TEXT_WARDENSHOUSE_DISPLAY_RIGHT": _say.bind("WardensHouseDisplayMerchandiseText")}})
	Story.def_map("FuchsiaPokecenter", {"talk": {"FUCHSIAPOKECENTER_LINK_RECEPTIONIST": _cable_club}, "hidden": {"0,4": _bench.bind("FuchsiaCityPokecenterGuyText")}})
	# ---- Safari Zone
	Story.global_enter_hooks.append(func(m: String) -> void:
		# leaving the Safari by other means (ESCAPE ROPE, DIG, blackout) ends the game like Red
		if Story.flag("EVENT_IN_SAFARI_ZONE") and not m.begins_with("SafariZone"):
			end_safari_state())
	Story.def_map("SafariZoneGate", {
		"enter": _safari_gate_enter, "step": _safari_gate_step,
		"talk": {"SAFARIZONEGATE_SAFARI_ZONE_WORKER1": _say.bind("SafariZoneGateSafariZoneWorker1Text"), "SAFARIZONEGATE_SAFARI_ZONE_WORKER2": _safari_worker2}})
	for m in SAFARI_MAPS:
		Story.def_map(m, {"step": _safari_step})
	Story.def_map("SafariZoneSecretHouse", {"talk": {"SAFARIZONESECRETHOUSE_FISHING_GURU": _gift.bind("EVENT_GOT_HM03", "SafariZoneSecretHouseFishingGuruHM03ExplanationText", "SafariZoneSecretHouseFishingGuruYouHaveWonText", "HM_SURF", "SafariZoneSecretHouseFishingGuruReceivedHM03Text", "SafariZoneSecretHouseFishingGuruHM03NoRoomText")}})
	# ---- Seafoam Islands
	Story.def_map("SeafoamIslands1F", {"enter": _seafoam1_enter, "step": _seafoam_step.bind("SeafoamIslands1F")})
	Story.def_map("SeafoamIslandsB1F", {"step": _seafoam_step.bind("SeafoamIslandsB1F")})
	Story.def_map("SeafoamIslandsB2F", {"step": _seafoam_step.bind("SeafoamIslandsB2F")})
	Story.def_map("SeafoamIslandsB3F", {"enter": _seafoam_b3f_enter, "step": _seafoam_step.bind("SeafoamIslandsB3F")})
	Story.def_map("SeafoamIslandsB4F", {"enter": _seafoam_b4f_enter,
		"talk": {"SEAFOAMISLANDSB4F_ARTICUNO": _static_h.bind("ARTICUNO", 50, "EVENT_BEAT_ARTICUNO", "SeafoamIslandsB4FArticunoBattleText")}})
	Story.def_map("Route20", {"enter": _route20_enter})
	# ---- Victory Road
	Story.def_map("VictoryRoad1F", {"enter": _vr_enter.bind("VictoryRoad1F", false)})
	Story.def_map("VictoryRoad2F", {"enter": _vr_enter.bind("VictoryRoad2F", true),
		"talk": {"VICTORYROAD2F_MOLTRES": _static_h.bind("MOLTRES", 50, "EVENT_BEAT_MOLTRES", "VictoryRoad2FMoltresBattleText")}})
	Story.def_map("VictoryRoad3F", {"enter": _vr_enter.bind("VictoryRoad3F", false), "step": _vr3_step})
	Story.on_boulder_hooks.append(_on_boulder_moved)
	# ---- Route 22 gate / Route 23
	var other_22 := Story.maps.has("Route22Gate") and not (Story.maps["Route22Gate"]["talk"] as Dictionary).is_empty()
	Story.def_map("Route22Gate", {"enter": _gate22_enter, "step": _gate22_step.bind(other_22),
		"talk": {} if other_22 else {"ROUTE22GATE_GUARD": _gate22_talk}})
	var r23talk := {}
	for e in R23:
		r23talk[e[2]] = _r23_talk.bind(e[1])
	Story.def_map("Route23", {"enter": _route23_enter, "step": _route23_step, "talk": r23talk})
	# ---- Cinnabar
	Story.def_map("CinnabarIsland", {"enter": _cinnabar_enter, "step": _cinnabar_step})
	Story.def_map("CinnabarPokecenter", {"talk": {"CINNABARPOKECENTER_LINK_RECEPTIONIST": _cable_club}, "hidden": {"0,4": _bench.bind("CinnabarPokecenterGuyText")}})
	for name in MANSION:
		var hidden := {}
		for k in MANSION[name]["switches"]:
			hidden[k] = _mansion_switch.bind(name)
		Story.def_map(name, {"enter": _mansion_enter.bind(name), "hidden": hidden})
	Story.def_map("PokemonMansion3F", {"step": _mansion3_step})
	var cg_talk := {}
	for n in CG_NERDS.size():
		cg_talk[CG_NERDS[n]] = _cg_nerd_talk.bind(n)
	cg_talk["CINNABARGYM_BLAINE"] = _leader.bind({"cls": "BLAINE", "beat": "EVENT_BEAT_BLAINE", "gotTM": "EVENT_GOT_TM38", "tm": "TM_FIRE_BLAST", "badge": "VOLCANOBADGE",
		"trainers": range(7).map(func(i): return "EVENT_BEAT_CINNABAR_GYM_TRAINER_%d" % i),
		"before": "CinnabarGymBlainePreBattleText", "win": "CinnabarGymBlaineReceivedVolcanoBadgeText", "info": "CinnabarGymBlaineVolcanoBadgeInfoText",
		"recv": "CinnabarGymBlaineReceivedTM38Text", "explain": "CinnabarGymBlaineTM38ExplanationText", "noRoom": "CinnabarGymBlaineTM38NoRoomText", "after": "CinnabarGymBlainePostBattleAdviceText"})
	cg_talk["CINNABARGYM_GYM_GUIDE"] = _flag_say.bind("EVENT_BEAT_BLAINE", "CinnabarGymGymGuideChampInMakingText", "CinnabarGymGymGuideBeatBlaineText")
	Story.def_map("CinnabarGym", {"enter": _cinnabar_gym_enter, "talk": cg_talk})
	Story.def_map("CinnabarLabFossilRoom", {"talk": {"CINNABARLABFOSSILROOM_SCIENTIST1": _fossil_scientist, "CINNABARLABFOSSILROOM_SCIENTIST2": _trade.bind(3)}})  # PONYTA -> SEEL
	Story.def_map("CinnabarLabTradeRoom", {"talk": {"CINNABARLABTRADEROOM_GRAMPS": _trade.bind(7), "CINNABARLABTRADEROOM_BEAUTY": _trade.bind(8)}})
	Story.def_map("CinnabarLabMetronomeRoom", {"talk": {"CINNABARLABMETRONOMEROOM_SCIENTIST1": _gift.bind("EVENT_GOT_TM35", "CinnabarLabMetronomeRoomScientist1TM35ExplanationText", "CinnabarLabMetronomeRoomScientist1Text", "TM_METRONOME", "CinnabarLabMetronomeRoomScientist1ReceivedTM35Text", "CinnabarLabMetronomeRoomScientist1TM35NoRoomText")}})
	# ---- Power Plant / Cerulean Cave statics
	var pp_talk := {}
	for id in PP:
		pp_talk[id] = _pp_static.bind(int(PP[id]))
	pp_talk["POWERPLANT_ZAPDOS"] = _static_h.bind("ZAPDOS", 50, "EVENT_BEAT_ZAPDOS", "PowerPlantZapdosBattleText")
	Story.def_map("PowerPlant", {"talk": pp_talk})
	Story.def_map("CeruleanCaveB1F", {"talk": {"CERULEANCAVEB1F_MEWTWO": _static_h.bind("MEWTWO", 70, "EVENT_BEAT_MEWTWO", "MewtwoBattleText")}})
	# ---- Viridian Gym
	Story.def_map("ViridianGym", {"talk": {
		"VIRIDIANGYM_GIOVANNI": _leader.bind({"cls": "GIOVANNI", "n": 3, "beat": "EVENT_BEAT_VIRIDIAN_GYM_GIOVANNI", "gotTM": "EVENT_GOT_TM27", "tm": "TM_FISSURE", "badge": "EARTHBADGE",
			"trainers": range(8).map(func(i): return "EVENT_BEAT_VIRIDIAN_GYM_TRAINER_%d" % i),
			"before": "ViridianGymGiovanniPreBattleText", "win": "ViridianGymGiovanniReceivedEarthBadgeText", "info": "ViridianGymGiovanniEarthBadgeInfoText",
			"recv": "ViridianGymGiovanniReceivedTM27Text", "explain": "ViridianGymGiovanniTM27ExplanationText", "noRoom": "ViridianGymGiovanniTM27NoRoomText",
			"after": "ViridianGymGiovanniPostBattleAdviceText", "onVictory": _giovanni_victory, "afterTalk": _giovanni_leaves}),
		"VIRIDIANGYM_GYM_GUIDE": _flag_say.bind("EVENT_BEAT_VIRIDIAN_GYM_GIOVANNI", "ViridianGymGuidePreBattleText", "ViridianGymGuidePostBattleText")}})
	# ---- Indigo Plateau
	Story.def_map("IndigoPlateau", {"hidden": {"8,13": _facing_up.bind("IndigoPlateauHQText"), "11,13": _facing_up.bind("IndigoPlateauHQText")}})
	Story.def_map("IndigoPlateauLobby", {"enter": _lobby_enter, "talk": {"INDIGOPLATEAULOBBY_LINK_RECEPTIONIST": _cable_club}})
	for name in E4:
		var c: Dictionary = E4[name]
		Story.def_map(name, {"enter": _e4_enter.bind(name), "step": _e4_step.bind(name), "talk": {c["id"]: _e4_talk.bind(name)}})
	Story.def_map("LancesRoom", {"enter": _lance_enter, "step": _lance_step, "talk": {"LANCESROOM_LANCE": _lance_talk}})
	Story.def_map("ChampionsRoom", {"enter": _champion_enter, "talk": {"CHAMPIONSROOM_RIVAL": _champion_rival_talk}})
	Story.def_map("HallOfFame", {"enter": _hof_enter})

## Story.hidden_event hook: Cinnabar Gym quiz machines (PrintCinnabarQuiz)
func hidden_fn(fn: String, h: Dictionary, d: String) -> Callable:
	if fn != "PrintCinnabarQuiz" or d != "up":
		return Callable()
	var q: Array = CG_QUIZ.get("%d,%d" % [int(h["x"]), int(h["y"])], [])
	if q.is_empty():
		return Callable()
	return _guarded_h.bind(_cinnabar_quiz.bind(int(q[0]), bool(q[1])))

# ---------------------------------------------------------------- helpers
## tx(...ls): the first label that has text, else the last one
func tx(ls: Array) -> String:
	for l in ls:
		if l != "" and Story.has_text(l):
			return l
	return ls[ls.size() - 1]

func _say(_o: Variant, label: String) -> void:
	await Story.say(label)

func _flag_say(_o: Variant, f: String, before: String, after: String) -> void:
	await Story.say(after if Story.flag(f) else before)

func _facing_up(_o: Variant, label: String) -> void:
	if Story.pdir() == "up":
		await Story.say(label)

func _bench(_h: Dictionary, label: String) -> void:
	if Story.pdir() == "left":
		await Story.say(label)

## Cable Club receptionist without a link partner (late.js version)
func _cable_club(_o: Dictionary) -> void:
	if not Story.flag("EVENT_GOT_POKEDEX"):
		await Story.say("CableClubNPCAreaReservedFor2FriendsLinkedByCableText")
		return
	await Story.say("CableClubNPCWelcomeText")
	await Story.say("CableClubNPCLinkClosedBecauseOfInactivityText")

func _show_dex(sp: String) -> void:
	Story.dex_seen(sp)
	await Story.dex_page(sp)

func _dex_sign(_s: Dictionary, label: String, sp: String) -> void:
	await Story.say(label)
	await _show_dex(sp)

## run as one of our "busy" sequences (suppresses our own step triggers)
func _guarded(c: Callable) -> void:
	Story.busy += 1
	await c.call()
	Story.busy -= 1

func _guarded_h(_h: Variant, c: Callable) -> void:
	await _guarded(c)

func guarded(c: Callable) -> Callable:
	return _guarded.bind(c)

## wait until a warp/fade that brought us into the map has finished
func settle_in() -> void:
	await Story.wait(1)
	var n := 0
	while Story._has_host("is_warping") and bool(Story.hq("is_warping", [], false)) and n < 120:
		await Story.wait(1)
		n += 1

## walk the player along a path; false if a warp fired on the way (the script should stop)
func walk(path: String) -> bool:
	var m := Story.mapname()
	for ch in path:
		await Story.move_player(ch)
		if Story.mapname() != m:
			return false
	return true

func _gift(_o: Dictionary, f: String, explain: String, intro: String, item: String, recv: String, no_room: String) -> void:
	if Story.flag(f):
		await Story.say(explain)
		return
	await Story.say(intro)
	if await Story.give_item(item, recv, no_room):
		Story.setf(f)

## A 32x32 block = 2x2 cells
func block_cells(bx: int, by: int, shape: String, x_label: String = "barrier") -> Array:
	var mask: String = BLOCK.get(shape, shape)
	var out: Array = []
	var offs := [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1), Vector2i(1, 1)]
	for k in 4:
		var blocked := mask[k] == "X"
		out.append([bx * 2 + offs[k].x, by * 2 + offs[k].y, x_label if blocked else null, not blocked])
	return out

## Static Pokémon handled the Red way: any finished battle removes it, a loss keeps it.
func static_mon(o: Dictionary, sp: String, lv: int, f: String, text: String, song: String = "legendary") -> String:
	var map_name := Story.mapname()
	var id: String = o.get("id", "")
	await Story.say(text)
	Story.cry(sp)
	var r := await Story.wild_battle(sp, lv, {"music": song})
	if r == "lose":
		return r
	Story.setf(f)
	Story.hide(id, map_name)
	return r

func _static_h(o: Dictionary, sp: String, lv: int, f: String, text: String) -> void:
	await static_mon(o, sp, lv, f, text)

func _pp_static(o: Dictionary, idx: int) -> void:
	var mon: Dictionary = o.get("mon", {"species": "VOLTORB", "level": 40})
	await static_mon(o, mon["species"], int(mon["level"]), "EVENT_BEAT_POWER_PLANT_VOLTORB_%d" % idx, "PowerPlantVoltorbBattleText", "wild")

## Gym leader in Red's order: before text -> battle -> badge info -> TM.
func _leader(a: Dictionary, o: Dictionary) -> void:
	if Story.flag(o["beat"]):
		if not Story.flag(o["gotTM"]):
			await _leader_reward(o)
			return
		await Story.say(o["after"])
		if o.has("afterTalk"):
			await (o["afterTalk"] as Callable).call(a)
		return
	await Story.say(o["before"])
	var r := await Story.battle(o["cls"], int(o.get("n", 1)), {"win_text": Story.fmt(Story.t(o["win"]))})
	if r != "win":
		return
	Story.sfx("get_badge")
	await _leader_reward(o)

func _leader_reward(o: Dictionary) -> void:
	await Story.say(o["info"])
	Story.setf(o["beat"])
	if await Story.give_item(o["tm"], o["recv"], o["noRoom"]):
		if o.has("explain"):
			await Story.say(o["explain"])
		Story.setf(o["gotTM"])
	if not Story.has_badge(o["badge"]):
		GameState.badges.append(o["badge"])
		GameState.badge_earned.emit(o["badge"])
	for f in o.get("trainers", []):
		Story.setf(f)
	if o.has("onVictory"):
		(o["onVictory"] as Callable).call()

## Oak's aides (OaksAideScript, late.js version)
func _aide(_o: Dictionary, need: int, item: String, f: String, explain: String) -> void:
	if not Story.flag(f):
		var own := Story.caught_count()
		Story.setvar("wOaksAideRewardItemName", Story.item_name(item))
		Story.setvar("hOaksAideRequirement", need)
		Story.setvar("hOaksAideNumMonsOwned", own)
		if not await Story.ask("OaksAideHiText"):
			await Story.say("OaksAideComeBackText")
			return
		if own < need:
			await Story.say("OaksAideUhOhText")
			return
		await Story.say("OaksAideHereYouGoText")
		if not Story.bag_add(item, 1):
			await Story.say("OaksAideNoRoomText")
			return
		Story.sfx("get_key")
		await Story.say("OaksAideGotItemText")
		Story.setf(f)
	await Story.say(explain)

## In-game trades using the original dialogue sets
func _trade(_o: Dictionary, idx: int) -> void:
	var set_n: int = {"TRADE_DIALOGSET_CASUAL": 1, "TRADE_DIALOGSET_EVOLUTION": 2, "TRADE_DIALOGSET_HAPPY": 3}.get(Story.pokedata["trades"][idx].get("dialog", ""), 1)
	var texts := {}
	for pair in [["ask", "WannaTrade%dText"], ["no", "NoTrade%dText"], ["wrong", "WrongMon%dText"], ["done", "Thanks%dText"], ["after", "AfterTrade%dText"]]:
		var l: String = pair[1] % set_n
		if Story.has_text(l):
			texts[pair[0]] = Story.raw(l)
	await Story.in_game_trade(idx, texts)

# ================================================================= ROUTE 12 / 16: SNORLAX
func _snorlax_battle(cfg: Dictionary) -> void:
	Story.clear(cfg["fight"])
	await Story.say(cfg["woke"])
	Story.hide(cfg["id"])  # Red hides Snorlax before the battle (it is gone even if you lose)
	var r := await Story.wild_battle("SNORLAX", 30)
	if r == "lose":
		return
	if r != "caught":
		await Story.say(cfg["calm"])
	Story.setf(cfg["beat"])

## Using the POKé FLUTE from the bag (ItemUsePokeFlute): wakes Snorlax when standing next to it.
func poke_flute_field() -> bool:
	var cfg: Dictionary = SNORLAX.get(Story.mapname(), {})
	if not cfg.is_empty() and not Story.flag(cfg["beat"]) and Story.is_shown(cfg["id"]) and (cfg["coords"] as Array).has(Story.pcell()):
		await Story.say("PlayedFluteHadEffectText")
		Story.setf(cfg["fight"])
		await _snorlax_battle(cfg)
		return true
	await Story.say("PlayedFluteNoEffectText")
	return true

func _super_rod(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_SUPER_ROD"):
		await Story.say("Route12SuperRodHouseFishingGuruTryFishingText")
		return
	if not await Story.ask("Route12SuperRodHouseFishingGuruDoYouLikeToFishText"):
		await Story.say("Route12SuperRodHouseFishingGuruThatsDisappointingText")
		return
	if await Story.give_item("SUPER_ROD", "Route12SuperRodHouseFishingGuruReceivedSuperRodText", "Route12SuperRodHouseFishingGuruNoRoomText"):
		Story.setf("EVENT_GOT_SUPER_ROD")
		await Story.say("Route12SuperRodHouseFishingGuruFishingWayOfLifeText")

## Route15GateLeftBinoculars: shows ARTICUNO (DisplayMonFrontSpriteInBox)
func _articuno_binoculars(_h: Dictionary) -> void:
	if Story.pdir() != "up":
		return
	await Story.say("Route15UpstairsBinocularsText")
	Story.cry("ARTICUNO")
	var box := Story.mon_popup("ARTICUNO", Rect2i(110, 24, 100, 96))
	await Story.wait_button(90)
	Story.close_box(box)

# ================================================================= FUCHSIA CITY
func _fossil_sign(_s: Dictionary) -> void:
	# the display shows the fossil Pokémon you did NOT pick at Mt.Moon
	if Story.flag("EVENT_GOT_DOME_FOSSIL"):
		await Story.say("FuchsiaCityFossilSignOmanyteText")
		await _show_dex("OMANYTE")
	elif Story.flag("EVENT_GOT_HELIX_FOSSIL"):
		await Story.say("FuchsiaCityFossilSignKabutoText")
		await _show_dex("KABUTO")
	else:
		await Story.say("FuchsiaCityFossilSignUndeterminedText")

func _good_rod(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_GOOD_ROD"):
		await Story.say("FuchsiaGoodRodHouseFishingGuruHowAreTheFishText")
		return
	if not await Story.ask("FuchsiaGoodRodHouseFishingGuruText"):
		await Story.say("FuchsiaGoodRodHouseFishingGuruThatsSoDisappointingText")
		return
	if await Story.give_item("GOOD_ROD", "FuchsiaGoodRodHouseFishingGuruReceivedGoodRodText", "FuchsiaGoodRodHouseFishingGuruNoRoomText"):
		Story.setf("EVENT_GOT_GOOD_ROD")

func _warden(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_HM04"):
		await Story.say("WardensHouseWardenHM04ExplanationText")
		return
	if Story.bag_has("GOLD_TEETH"):
		Story.sfx("get_item")
		await Story.say("WardensHouseWardenGaveTheGoldTeethText")
		Story.bag_remove("GOLD_TEETH", 1)
		Story.setf("EVENT_GAVE_GOLD_TEETH")
	elif not Story.flag("EVENT_GAVE_GOLD_TEETH"):
		var yes := await Story.ask("WardensHouseWardenGibberish1Text")
		await Story.say("WardensHouseWardenGibberish2Text" if yes else "WardensHouseWardenGibberish3Text")
		return
	await Story.say("WardensHouseWardenThanksText")
	if await Story.give_item("HM_STRENGTH", "WardensHouseWardenReceivedHM04Text", "WardensHouseWardenHM04NoRoomText"):
		Story.setf("EVENT_GOT_HM04")

# ================================================================= SAFARI ZONE
func end_safari_state() -> void:
	Story.clear("EVENT_IN_SAFARI_ZONE")
	Story.clear("EVENT_SAFARI_GAME_OVER")
	GameState.safari_balls = -1
	GameState.safari_steps = -1

## PA announcement, then back to the gate (SafariZoneGameOver). Also called by Story.wild_battle when out of balls.
func safari_game_over() -> void:
	Story.busy += 1
	if GameState.safari_balls > 0:
		await Story.say("TimesUpText")
	await Story.say("GameOverText")
	Story.setf("EVENT_SAFARI_GAME_OVER")
	Story.surfing = false
	Story.biking = false
	Story.hq("set_ride", ["walk"])
	await Story.warp("SafariZoneGate", 4, 0, "down")
	Story.busy -= 1

## Counts a step inside the Safari Zone (SafariZoneCheckSteps)
func _safari_step(_x: int, _y: int) -> Callable:
	if not Story.in_safari() or Story.flag("EVENT_SAFARI_GAME_OVER"):
		return Callable()
	if GameState.safari_steps <= 0:
		return safari_game_over
	GameState.safari_steps -= 1
	return Callable()

func _safari_entry(x: int) -> void:
	await Story.say("SafariZoneGateSafariZoneWorker1Text")
	Story.face(P, "right")
	if x == 3:
		await walk("R")
		Story.face(P, "right")
	var box := Story.money_box("late")
	var yes := await Story.ask("SafariZoneGateSafariZoneWorker1WouldYouLikeToJoinText")
	Story.close_box(box)
	if not yes:
		await Story.say("SafariZoneGateSafariZoneWorker1PleaseComeAgainText")
		await walk("D")
		return
	if GameState.money < 500:
		await Story.say("SafariZoneGateSafariZoneWorker1NotEnoughMoneyText")
		await walk("D")
		return
	GameState.money -= 500
	Story.sfx("get_item")
	box = Story.money_box("late")
	await Story.say("SafariZoneGateSafariZoneWorker1ThatllBe500PleaseText")
	Story.close_box(box)
	await Story.say("SafariZoneGateSafariZoneWorker1CallYouOnThePAText")
	GameState.safari_balls = 30
	GameState.safari_steps = 502
	Story.setf("EVENT_IN_SAFARI_ZONE")
	Story.clear("EVENT_SAFARI_GAME_OVER")
	if await walk("UU"):
		GameState.safari_steps -= 2
		await Story.take_warp()
	else:
		GameState.safari_steps -= 2

## Coming back into the gate from the Safari (SafariZoneGateLeavingSafariScript)
func _safari_leaving() -> void:
	await settle_in()
	Story.face(P, "down")
	if Story.flag("EVENT_SAFARI_GAME_OVER"):
		await Story.say("SafariZoneGateSafariZoneWorker1GoodHaulComeAgainText")
		end_safari_state()
		await walk("DDD")
		return
	if await Story.ask("SafariZoneGateSafariZoneWorker1LeavingEarlyText"):
		await Story.say("SafariZoneGateSafariZoneWorker1ReturnSafariBallsText")
		end_safari_state()
		await walk("DDD")
	else:
		await Story.say("SafariZoneGateSafariZoneWorker1GoodLuckText")
		Story.face(P, "up")
		await Story.take_warp()  # back into the Safari

func _safari_gate_enter() -> Callable:
	if Story.flag("EVENT_IN_SAFARI_ZONE") and Story.pcell().y <= 1:
		return guarded(_safari_leaving)
	return Callable()

func _safari_gate_step(x: int, y: int) -> Callable:
	if Story.busy > 0:
		return Callable()
	if not Story.flag("EVENT_IN_SAFARI_ZONE") and y == 2 and (x == 3 or x == 4):
		return guarded(_safari_entry.bind(x))
	return Callable()

func _safari_worker2(_o: Dictionary) -> void:
	var first := await Story.ask("SafariZoneGateSafariZoneWorker2FirstTimeHereText")
	await Story.say("SafariZoneGateSafariZoneWorker2SafariZoneExplanationText" if first else "SafariZoneGateSafariZoneWorker2YoureARegularHereText")

# ================================================================= SEAFOAM ISLANDS
func _both(a: String, b: String) -> bool:
	return Story.flag(a) and Story.flag(b)

func _currents_b3f() -> bool:
	return not _both("EVENT_SEAFOAM3_BOULDER1_DOWN_HOLE", "EVENT_SEAFOAM3_BOULDER2_DOWN_HOLE")

func _currents_b4f() -> bool:
	return not _both("EVENT_SEAFOAM4_BOULDER1_DOWN_HOLE", "EVENT_SEAFOAM4_BOULDER2_DOWN_HOLE")

## Forced surfing along a strong current; drops off the water when it reaches land.
func current(path: String) -> void:
	Story.set_surfing(true)
	var m := Story.mapname()
	for ch in path:
		await Story.move_player(ch, 2)
		if Story.mapname() != m:
			return
		var p := Story.pcell()
		if not Story.is_water(p) and bool(Story.hq("is_passable", [p], true)):
			Story.set_surfing(false)
	await Story.take_warp()

## Fall through a hole to the floor below (dungeon warp).
func fall_through(map_name: String, x: int, y: int) -> void:
	Story.sfx("jump")
	await Story.warp(map_name, x, y, "down")
	if Story.is_water(Vector2i(x, y)):
		Story.set_surfing(true)

func _seafoam_step(x: int, y: int, name: String) -> Callable:
	if Story.busy > 0:
		return Callable()
	var cfg: Dictionary = SEAFOAM[name]
	var i: int = (cfg["holes"] as Array).find(Vector2i(x, y))
	if i >= 0:
		return guarded(fall_through.bind(cfg["below"], cfg["land"][i].x, cfg["land"][i].y))
	if name == "SeafoamIslandsB3F" and x == 15 and y == 8 and _currents_b3f():
		return guarded(current.bind("DDDRRRRRDDDDDD"))
	return Callable()

func _seafoam1_enter() -> Callable:
	Story.setf("EVENT_IN_SEAFOAM_ISLANDS")
	return Callable()

func _settle_current(path: String, off_after: bool = false) -> void:
	await settle_in()
	await current(path)
	if off_after:
		Story.set_surfing(false)

func _seafoam_b3f_enter() -> Callable:
	# landed from the B2F holes: the current sweeps the player down to B4F unless the boulders block it
	var i := [Vector2i(18, 7), Vector2i(19, 7)].find(Story.pcell())
	if i < 0:
		return Callable()
	Story.set_surfing(true)
	if not _currents_b3f():
		return Callable()
	return guarded(_settle_current.bind("DDDDRRDDDDDD" if i == 0 else "LDDDDRRDDDDDD"))

func _seafoam_b4f_enter() -> Callable:
	var p := Story.pcell()
	# arriving on the waterfall from B3F: pushed up by the current
	var w := [Vector2i(20, 17), Vector2i(21, 17), Vector2i(20, 16), Vector2i(21, 16)].find(p)
	if w >= 0 and _currents_b3f():
		return guarded(_settle_current.bind("UU" if w < 2 else "U"))
	# landed from the B3F holes
	var i := [Vector2i(4, 14), Vector2i(5, 14)].find(p)
	if i >= 0:
		Story.set_surfing(true)
		if not _currents_b4f():
			return Callable()
		return guarded(_settle_current.bind("URRRUUU" if i == 0 else "URRUUU", true))
	if Story.is_water(p):
		Story.set_surfing(true)
	return Callable()

## Leaving Seafoam resets unfinished boulder puzzles (Route20BoulderScript)
func _route20_enter() -> Callable:
	if not Story.flag("EVENT_IN_SEAFOAM_ISLANDS"):
		return Callable()
	Story.clear("EVENT_IN_SEAFOAM_ISLANDS")
	if not _both("EVENT_SEAFOAM3_BOULDER1_DOWN_HOLE", "EVENT_SEAFOAM3_BOULDER2_DOWN_HOLE"):
		Story.show("SEAFOAMISLANDS1F_BOULDER1", "SeafoamIslands1F")
		Story.show("SEAFOAMISLANDS1F_BOULDER2", "SeafoamIslands1F")
		for e in [["SeafoamIslandsB1F", "SEAFOAMISLANDSB1F_BOULDER1"], ["SeafoamIslandsB1F", "SEAFOAMISLANDSB1F_BOULDER2"], ["SeafoamIslandsB2F", "SEAFOAMISLANDSB2F_BOULDER1"],
				["SeafoamIslandsB2F", "SEAFOAMISLANDSB2F_BOULDER2"], ["SeafoamIslandsB3F", "SEAFOAMISLANDSB3F_BOULDER5"], ["SeafoamIslandsB3F", "SEAFOAMISLANDSB3F_BOULDER6"]]:
			Story.hide(e[1], e[0])
	if not _both("EVENT_SEAFOAM4_BOULDER1_DOWN_HOLE", "EVENT_SEAFOAM4_BOULDER2_DOWN_HOLE"):
		Story.show("SEAFOAMISLANDSB3F_BOULDER2", "SeafoamIslandsB3F")
		Story.show("SEAFOAMISLANDSB3F_BOULDER3", "SeafoamIslandsB3F")
		Story.hide("SEAFOAMISLANDSB4F_BOULDER1", "SeafoamIslandsB4F")
		Story.hide("SEAFOAMISLANDSB4F_BOULDER2", "SeafoamIslandsB4F")
	return Callable()

# ================================================================= VICTORY ROAD
func vr_apply(name: String) -> void:
	var cells: Array = []
	for sw in VR_SWITCH[name]:
		if Story.flag(sw["ev"]):
			cells.append_array(sw["cells"])
	if not cells.is_empty():
		Story.set_cells(cells)

func _vr_enter(name: String, clear_1f: bool) -> Callable:
	if clear_1f:
		Story.clear("EVENT_VICTORY_ROAD_1_BOULDER_ON_SWITCH")
	vr_apply(name)
	return Callable()

func _vr3_step(x: int, y: int) -> Callable:
	if Story.busy == 0 and x == 23 and y == 15:
		return guarded(fall_through.bind("VictoryRoad2F", 22, 16))
	return Callable()

## Boulders: switches (Victory Road) and holes (Seafoam, Victory Road 3F)
func _on_boulder_moved(map_name: String, id: String, c: Vector2i) -> Callable:
	if SEAFOAM.has(map_name):
		var sf: Dictionary = SEAFOAM[map_name]
		var i: int = (sf["holes"] as Array).find(c)
		if i >= 0:
			return _boulder_down_hole.bind(sf, i, id)
		return Callable()
	if map_name == "VictoryRoad3F" and c == Vector2i(23, 15):
		return _vr3_boulder_hole.bind(id)
	if VR_SWITCH.has(map_name):
		for sw in VR_SWITCH[map_name]:
			if sw["at"] == c and not Story.flag(sw["ev"]):
				return _vr_switch.bind(map_name, sw["ev"])
	return Callable()

func _boulder_down_hole(sf: Dictionary, i: int, id: String) -> void:
	Story.setf(sf["ev"][i])
	await Story.wait(6)
	Story.sfx("boulder")
	if id != "":
		Story.hide(id)
	Story.show(sf["show"][i], sf["below"])

func _vr3_boulder_hole(id: String) -> void:
	if Story.flag("EVENT_VICTORY_ROAD_3_BOULDER_ON_SWITCH2"):
		return
	Story.setf("EVENT_VICTORY_ROAD_3_BOULDER_ON_SWITCH2")
	await Story.wait(6)
	if id != "":
		Story.hide(id)
	Story.show("VICTORYROAD2F_BOULDER3", "VictoryRoad2F")

func _vr_switch(map_name: String, ev: String) -> void:
	Story.setf(ev)
	Story.sfx("door")
	vr_apply(map_name)
	await Story.wait(4)

# ================================================================= ROUTE 22 GATE / ROUTE 23
func _fix_last_map() -> void:
	GameState.last_outdoor = "Route23" if Story.pcell().y < 4 else "Route22"

func _gate22_guard() -> void:
	if Story.has_badge("BOULDERBADGE"):
		Story.sfx("get_item")
		await Story.say("Route22GateGuardGoRightAheadText")
		gate22_passed = true
		return
	await Story.say("Route22GateGuardNoBoulderbadgeText")
	await Story.say("Route22GateGuardICantLetYouPassText")
	Story.face(P, "down")
	await walk("D")

func _gate22_enter() -> Callable:
	gate22_passed = false
	_fix_last_map()
	return Callable()

func _gate22_step(x: int, y: int, other: bool) -> Callable:
	_fix_last_map()
	if other or Story.busy > 0 or gate22_passed:
		return Callable()
	if y == 2 and (x == 4 or x == 5):
		return guarded(_gate22_guard)
	return Callable()

func _gate22_talk(_o: Dictionary) -> void:
	await _guarded(_gate22_guard)

func route23_check(badge: String) -> void:
	Story.setvar("wNameBuffer", badge)
	if Story.has_badge(badge):
		Story.sfx("get_item")
		await Story.say("Route23OhThatIsTheBadgeText")
		await Story.say("Route23GoRightAheadText")
		Story.setf("EVENT_PASSED_" + badge + "_CHECK")
		return
	await Story.say("Route23YouDontHaveTheBadgeYetText")
	Story.face(P, "down")
	await walk("D")

func _r23_talk(_o: Dictionary, badge: String) -> void:
	await _guarded(route23_check.bind(badge))

func _route23_enter() -> Callable:
	# Route23SetVictoryRoadBoulders
	for f in ["EVENT_VICTORY_ROAD_2_BOULDER_ON_SWITCH1", "EVENT_VICTORY_ROAD_2_BOULDER_ON_SWITCH2", "EVENT_VICTORY_ROAD_3_BOULDER_ON_SWITCH1", "EVENT_VICTORY_ROAD_3_BOULDER_ON_SWITCH2"]:
		Story.clear(f)
	Story.show("VICTORYROAD3F_BOULDER4", "VictoryRoad3F")
	Story.hide("VICTORYROAD2F_BOULDER3", "VictoryRoad2F")
	return Callable()

func _route23_step(x: int, y: int) -> Callable:
	if Story.busy > 0:
		return Callable()
	for g in R23:
		if g[0] == y:
			if y == 35 and x >= 14:
				return Callable()
			if Story.flag("EVENT_PASSED_" + str(g[1]) + "_CHECK"):
				return Callable()
			return guarded(route23_check.bind(g[1]))
	return Callable()

# ================================================================= CINNABAR ISLAND
func _cinnabar_enter() -> Callable:
	Story.clear("EVENT_MANSION_SWITCH_ON")
	Story.clear("EVENT_LAB_STILL_REVIVING_FOSSIL")
	return Callable()

func _cinnabar_step(x: int, y: int) -> Callable:
	if Story.busy > 0 or x != 18 or y != 4 or Story.bag_has("SECRET_KEY"):
		return Callable()
	return guarded(_door_locked)

func _door_locked() -> void:
	Story.face(P, "up")
	await Story.say("CinnabarIslandDoorIsLockedText")
	await walk("D")

## Pokémon Mansion: statue switches swap the gates on every floor
func mansion_gates(name: String) -> void:
	var cfg: Dictionary = MANSION[name]
	var cells: Array = []
	for b in (cfg["on"] if Story.flag("EVENT_MANSION_SWITCH_ON") else cfg["off"]):
		cells.append_array(block_cells(b[0], b[1], b[2]))
	Story.set_cells(cells)

func _mansion_enter(name: String) -> Callable:
	mansion_gates(name)
	return Callable()

func _mansion_switch(_h: Dictionary, name: String) -> void:
	if Story.pdir() != "up":
		return
	var t: String = MANSION[name]["text"]
	if await Story.ask(t + "SwitchText"):
		await Story.say(t + "SwitchPressedText")
		Story.sfx("door")
		if Story.flag("EVENT_MANSION_SWITCH_ON"):
			Story.clear("EVENT_MANSION_SWITCH_ON")
		else:
			Story.setf("EVENT_MANSION_SWITCH_ON")
		mansion_gates(name)
	else:
		await Story.say(t + "SwitchNotPressedText")

## 3F floor holes drop you to 1F/2F
func _mansion3_step(x: int, y: int) -> Callable:
	if Story.busy > 0 or y != 14:
		return Callable()
	if x == 16 or x == 17:
		return guarded(fall_through.bind("PokemonMansion1F", 16, 14))
	if x == 19:
		return guarded(fall_through.bind("PokemonMansion2F", 18, 14))
	return Callable()

## Cinnabar Gym: quiz machines, gates, trainers and BLAINE
func _cg_beat(i: int) -> String:
	return "EVENT_BEAT_CINNABAR_GYM_TRAINER_%d" % i

func _cg_gate(i: int) -> String:
	return "EVENT_CINNABAR_GYM_GATE%d_UNLOCKED" % i

func cinnabar_gates() -> void:
	var cells: Array = []
	for i in range(1, 7):
		var g: Array = CG_GATES[i]
		cells.append_array(block_cells(g[0], g[1], "O" if Story.flag(_cg_gate(i)) else g[2]))
	Story.set_cells(cells)

func _unlock_gate(i: int) -> void:
	if not Story.flag(_cg_gate(i)):
		Story.sfx("door")
	Story.setf(_cg_gate(i))
	cinnabar_gates()
	await Story.wait(4)

## Talking to (or being challenged by) super nerd N (0-based): battle, then its gate (N) opens.
func cinnabar_trainer(n: int) -> void:
	var id: String = CG_NERDS[n]
	if not Story.actor(id):
		return
	var lbl := "CinnabarGymSuperNerd%d" % (n + 1)
	if Story.flag(_cg_beat(n)):
		await Story.say(lbl + "AfterBattleText")
		return
	await Story.say(lbl + "BattleText")
	var tr: Dictionary = Story.obj(id).get("trainer", {})
	var r := await Story.battle(tr.get("cls", "SUPER_NERD"), int(tr.get("n", 1)), {"win_text": Story.fmt(Story.t(lbl + "EndBattleText"))})
	if r != "win":
		return
	Story.setf(_cg_beat(n))
	if n >= 1:
		await _unlock_gate(n)

func _cg_nerd_talk(_o: Dictionary, n: int) -> void:
	await cinnabar_trainer(n)

func _cinnabar_quiz(gate: int, yes_is_right: bool) -> void:
	await Story.say("CinnabarGymQuizIntroText")
	var yes := await Story.ask("CinnabarQuizQuestionsText%d" % gate)
	if yes == yes_is_right:
		Story.sfx("get_item")
		await Story.say("CinnabarGymQuizCorrectText")
		await _unlock_gate(gate)
		return
	Story.sfx("bump")
	await Story.say("CinnabarGymQuizIncorrectText")
	var n := gate  # trainer index for this gate (super nerd n+1)
	if Story.flag(_cg_beat(n)):
		return
	var id: String = CG_NERDS[n]
	if not Story.actor(id):
		return
	await Story.move(id, "LU" if n == 2 else "L")
	Story.face_to(id, P)
	Story.face_to(P, id)
	await cinnabar_trainer(n)

func _cinnabar_gym_enter() -> Callable:
	cinnabar_gates()
	return Callable()

## Cinnabar Lab: fossil revival
func _fossil_names() -> void:
	var item = GameState.flags.get("LAB_FOSSIL_ITEM")
	var mon = GameState.flags.get("LAB_FOSSIL_MON")
	if mon is String:
		Story.setvar("wStringBuffer", Story.species_name(mon))
	if item is String:
		Story.setvar("wNameBuffer", Story.item_name(item))

func _fossil_scientist(_o: Dictionary) -> void:
	if not Story.flag("EVENT_GAVE_FOSSIL_TO_LAB"):
		await Story.say("CinnabarLabFossilRoomScientist1Text")
		var have: Array = FOSSILS.filter(func(f): return Story.bag_has(f[0]))
		if have.is_empty():
			await Story.say("CinnabarLabFossilRoomScientist1NoFossilsText")
			return
		var r := await Story.choose(have.map(func(f): return Story.item_name(f[0])), {"x": 6, "y": 6})
		if r < 0:
			await Story.say("CinnabarLabFossilRoomScientist1ComeAgainText")
			return
		GameState.flags["LAB_FOSSIL_ITEM"] = have[r][0]
		GameState.flags["LAB_FOSSIL_MON"] = have[r][1]
		_fossil_names()
		if not await Story.ask("CinnabarLabFossilRoomScientist1SeesFossilText"):
			await Story.say("CinnabarLabFossilRoomScientist1ComeAgainText")
			return
		await Story.say("CinnabarLabFossilRoomScientist1TakesFossilText")
		Story.bag_remove(have[r][0], 1)
		await Story.say("CinnabarLabFossilRoomScientist1GoForAWalkText2")
		Story.setf("EVENT_GAVE_FOSSIL_TO_LAB")
		Story.setf("EVENT_LAB_STILL_REVIVING_FOSSIL")
		return
	if Story.flag("EVENT_LAB_STILL_REVIVING_FOSSIL"):
		await Story.say("CinnabarLabFossilRoomScientist1GoForAWalkText")
		return
	_fossil_names()
	await Story.say("CinnabarLabFossilRoomScientist1FossilIsBackToLifeText")
	Story.setf("EVENT_LAB_HANDING_OVER_FOSSIL_MON")
	if await Story.gift_mon(str(GameState.flags.get("LAB_FOSSIL_MON", "KABUTO")), 30):
		for f in ["EVENT_GAVE_FOSSIL_TO_LAB", "EVENT_LAB_STILL_REVIVING_FOSSIL", "EVENT_LAB_HANDING_OVER_FOSSIL_MON", "LAB_FOSSIL_ITEM", "LAB_FOSSIL_MON"]:
			Story.clear(f)

# ================================================================= VIRIDIAN GYM (GIOVANNI)
func _giovanni_victory() -> void:
	# the rival now waits on Route 22 (second battle, scripted in Pallet.gd)
	Story.show("ROUTE22_RIVAL2", "Route22")
	Story.setf("EVENT_2ND_ROUTE22_RIVAL_BATTLE")
	Story.setf("EVENT_ROUTE22_RIVAL_WANTS_BATTLE")

func _giovanni_leaves(_a: Dictionary) -> void:
	await Story.fade_out(12)
	Story.hide("VIRIDIANGYM_GIOVANNI")
	await Story.wait(4)
	await Story.fade_in(12)

# ================================================================= INDIGO PLATEAU / ELITE FOUR
func reset_e4() -> void:
	for f in E4_EVENTS:
		Story.clear(f)
	Story.clear("E4_STARTED")

func _lobby_enter() -> Callable:
	Story.clear("EVENT_VICTORY_ROAD_1_BOULDER_ON_SWITCH")
	if Story.flag("E4_STARTED"):
		reset_e4()  # lost (or left) during the Elite Four: start over
	return Callable()

func _e4_door(name: String) -> void:
	var c: Dictionary = E4[name]
	var open := Story.flag(c["beat"])
	Story.set_cells([[4, 0, c["floor"] if open else "door", open], [5, 0, c["floor"] if open else "door", open]])

func _dont_run_away(c: Dictionary) -> void:
	await Story.say(c["run"])
	Story.face(P, "up")
	await walk("U")

func _e4_enter(name: String) -> Callable:
	var c: Dictionary = E4[name]
	Story.setf("E4_STARTED")
	_e4_door(name)
	if Story.pcell().y < 11:
		return Callable()
	return guarded(_e4_autowalk.bind(c))

func _e4_autowalk(c: Dictionary) -> void:
	await settle_in()
	if not Story.flag(c["auto"]):
		Story.setf(c["auto"])
		Story.face(P, "up")
		await walk("UUUUUU")
	else:
		await _dont_run_away(c)

func _e4_step(x: int, y: int, name: String) -> Callable:
	if Story.busy > 0 or y != 10 or (x != 4 and x != 5):
		return Callable()
	return guarded(_dont_run_away.bind(E4[name]))

func _e4_talk(a: Dictionary, name: String) -> void:
	var c: Dictionary = E4[name]
	var th: Dictionary = a.get("th", {})
	if Story.flag(c["beat"]):
		await Story.say(th.get("after", ""))
		return
	await Story.say(th.get("battle", ""))
	var r := await Story.battle(c["cls"], 1, {"win_text": Story.fmt(Story.t(th.get("end", "")))})
	if r != "win":
		return
	Story.setf(c["beat"])
	await Story.say(th.get("after", ""))
	Story.sfx("door")
	_e4_door(name)

## Lance
func _lance_door() -> void:
	var locked := Story.flag("EVENT_LANCES_ROOM_LOCK_DOOR")
	Story.set_cells([[5, 12, "door" if locked else "floor_stone", not locked], [6, 12, "door" if locked else "floor_stone", not locked]])

func _lance_battle(a: Dictionary = {}) -> void:
	if a.is_empty():
		a = Story.obj("LANCESROOM_LANCE")
	var th: Dictionary = a.get("th", {})
	if Story.flag("EVENT_BEAT_LANCES_ROOM_TRAINER_0"):
		await Story.say(th.get("after", ""))
		Story.setf("EVENT_BEAT_LANCE")
		return
	Story.face_to("LANCESROOM_LANCE", P)
	Story.face_to(P, "LANCESROOM_LANCE")
	await Story.say(th.get("battle", ""))
	var r := await Story.battle("LANCE", 1, {"win_text": Story.fmt(Story.t(th.get("end", "")))})
	if r != "win":
		return
	Story.setf("EVENT_BEAT_LANCES_ROOM_TRAINER_0")
	await Story.say(th.get("after", ""))
	Story.setf("EVENT_BEAT_LANCE")

func _lock_lance() -> void:
	if Story.flag("EVENT_LANCES_ROOM_LOCK_DOOR"):
		return
	Story.setf("EVENT_LANCES_ROOM_LOCK_DOOR")
	Story.sfx("door")
	_lance_door()
	await Story.wait(4)

func _lance_enter() -> Callable:
	Story.setf("E4_STARTED")
	_lance_door()
	if Story.flag("EVENT_BEAT_LANCE") or Story.pcell() != Vector2i(24, 16):
		return Callable()
	return guarded(_lance_autowalk)

func _lance_autowalk() -> void:
	await settle_in()
	await walk("LLLLLLDDDDDDDLLLLLLLLLLLLUUUUUUUUUUUU")
	await _lock_lance()

func _lance_step(_x: int, _y: int) -> Callable:
	if Story.busy > 0 or Story.flag("EVENT_BEAT_LANCE"):
		return Callable()
	var i := [Vector2i(5, 1), Vector2i(6, 2), Vector2i(5, 11), Vector2i(6, 11)].find(Story.pcell())
	if i < 0:
		return Callable()
	if i < 2:
		return guarded(_lance_battle)
	if not Story.flag("EVENT_LANCES_ROOM_LOCK_DOOR"):
		return guarded(_lock_lance)
	return Callable()

func _lance_talk(a: Dictionary) -> void:
	await _guarded(_lance_battle.bind(a))

## Champion (RIVAL3) and PROF.OAK
func _champion_enter() -> Callable:
	if Story.flag("EVENT_BEAT_CHAMPION_RIVAL"):
		return Callable()
	return guarded(_champion)

func _champion() -> void:
	await settle_in()
	await walk("UUURU")
	var rival := "CHAMPIONSROOM_RIVAL"
	Story.face(P, "up")
	if Story.actor(rival):
		Story.face(rival, "down")
	Story.music("rival")
	await Story.say("ChampionsRoomRivalIntroText")
	var r := await Story.battle("RIVAL3", Story.rival_party(1), {"win_text": Story.fmt(Story.t("RivalDefeatedText")), "lose_text": Story.fmt(Story.t("RivalVictoryText"))})
	if r != "win":
		return
	Story.setf("EVENT_BEAT_CHAMPION_RIVAL")
	await Story.say("ChampionsRoomRivalAfterBattleText")
	# PROF.OAK arrives to a slowed-down CITIES1 (Music_Cities1AlternateTempo)
	Story.stop_music()
	await Story.wait(60)
	Story.music("Cities1@232")
	await Story.say("ChampionsRoomOakText")
	var oak := Story.show("CHAMPIONSROOM_OAK", "", Vector2i(3, 7))
	await Story.move(oak, "UUUUU")
	Story.face(P, "left")
	if Story.actor(rival):
		Story.face(rival, "left")
	Story.face(oak, "down")
	await Story.wait(6)
	Story.setvar("wNameBuffer", Story.species_name(GameState.starter if GameState.starter != "" else "CHARMANDER"))
	await Story.say("ChampionsRoomOakCongratulatesPlayerText")
	Story.face(oak, "right")
	await Story.wait(6)
	await Story.say("ChampionsRoomOakDisappointedWithRivalText")
	Story.face(oak, "down")
	await Story.wait(6)
	await Story.say("ChampionsRoomOakComeWithMeText")
	await Story.move(oak, "UU")
	Story.hide("CHAMPIONSROOM_OAK")
	if await walk("LUUU"):
		Story.face(P, "up")
		await Story.take_warp()

func _champion_rival_talk(_o: Dictionary) -> void:
	await Story.say("ChampionsRoomRivalAfterBattleText" if Story.flag("EVENT_BEAT_CHAMPION_RIVAL") else "ChampionsRoomRivalIntroText")

## Hall of Fame
func _hof_enter() -> Callable:
	if not Story.flag("EVENT_BEAT_CHAMPION_RIVAL"):
		return Callable()
	return guarded(_hof)

func _hof() -> void:
	await settle_in()
	await walk("UUUUU")
	var oak := "HALLOFFAME_OAK"
	Story.face(P, "right")
	if Story.actor(oak):
		Story.face(oak, "left")
	await Story.wait(6)
	await Story.say("HallOfFameOakText")
	Story.hide("CERULEANCITY_SUPER_NERD3", "CeruleanCity")  # the guard at CERULEAN CAVE steps aside
	await hall_of_fame()

## Hall of Fame + credits (AnimateHallOfFame, Credits), then save and restart at PALLET TOWN.
func hall_of_fame() -> void:
	var team: Array = []
	for m in GameState.party:
		team.append({"species": m.species_id, "level": m.level, "name": m.nickname})
	await Story.fade_out(20)
	Story.music("hall_of_fame")
	var ui := Story.get_ui()
	if ui and ui.has_method("hall_of_fame"):
		await ui.call("hall_of_fame", team)
	else:
		for t in team:
			Story.cry(t["species"])
			await Story.say("%s   Lv%d\f%s" % [t["name"], t["level"], Story.species_name(t["species"])])
		Story.music("credits")
		await Story.say("THE END")
	GameState.hall_of_fame.append({"team": team, "time": GameState.play_seconds})
	if GameState.hall_of_fame.size() > 50:
		GameState.hall_of_fame = GameState.hall_of_fame.slice(-50)
	# HallOfFameResetEventsAndSaveScript
	reset_e4()
	Story.setf("EVENT_BEAT_CHAMPION")
	GameState.current_map = "PalletTown"
	GameState.player_cell = Vector2i(5, 6)
	GameState.player_facing = "down"
	GameState.last_outdoor = "PalletTown"
	GameState.last_heal = {}
	GameState.last_heal_town = {"map": "PalletTown", "x": 5, "y": 6}
	Story.surfing = false
	Story.biking = false
	GameState.save()
	# restart (jp Init): back to the title screen
	var sr := Story.get_node_or_null("/root/SceneRouter")
	if Story.host_override == null and sr and sr.has_method("goto_title"):
		sr.call("goto_title")
