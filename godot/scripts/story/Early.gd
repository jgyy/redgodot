extends RefCounted
## Port of upstream src/scripts/early.js: Route 2, Pewter City (+ museum, gym),
## Mt. Moon, Cerulean City (+ gym, badge house, bike shop), Routes 24/25 + Bill,
## Routes 5/6 gates + Underground Path, Vermilion City (+ gym trash puzzle, dock,
## fan club), S.S. Anne, Route 11 gate, Pokécenter bench guys.

const P := "PLAYER"
const D4 := {"U": Vector2i(0, -1), "D": Vector2i(0, 1), "L": Vector2i(-1, 0), "R": Vector2i(1, 0)}
const TRADE_SET := {"TRADE_DIALOGSET_CASUAL": 1, "TRADE_DIALOGSET_EVOLUTION": 2, "TRADE_DIALOGSET_HAPPY": 3}
const BADGES := ["BOULDERBADGE", "CASCADEBADGE", "THUNDERBADGE", "RAINBOWBADGE", "SOULBADGE", "MARSHBADGE", "VOLCANOBADGE", "EARTHBADGE"]
const BILLS_FAVORITES := ["EEVEE", "FLAREON", "JOLTEON", "VAPOREON"]
const DRINK_FLAGS := ["EVENT_GAVE_SAFFRON_GUARDS_DRINK", "GAVE_SAFFRON_GUARDS_DRINK", "BIT_GAVE_SAFFRON_GUARDS_DRINK"]
const MOON_ROCKETS := ["MTMOONB2F_ROCKET1", "MTMOONB2F_ROCKET2", "MTMOONB2F_ROCKET3", "MTMOONB2F_ROCKET4"]
const NEAR_DOME := [Vector2i(12, 7), Vector2i(11, 6), Vector2i(12, 5)]
const NEAR_HELIX := [Vector2i(13, 7), Vector2i(14, 6), Vector2i(14, 5)]
const GYM_DOOR := [Vector2i(4, 4), Vector2i(5, 4), Vector2i(4, 5), Vector2i(5, 5)]

var GYM_GUY_PATH := "DD" + "L".repeat(15) + "UUUUU" + "L".repeat(11) + "DDDDD" + "RRR"
var MUSEUM_GUY_PATH := "UUUUUU" + "L".repeat(13) + "UUU" + "L"

var BROCK := {
	"cls": "BROCK", "flag": "EVENT_BEAT_BROCK", "tmFlag": "EVENT_GOT_TM34", "tm": "TM_BIDE", "badge": "BOULDERBADGE",
	"before": "PewterGymBrockPreBattleText", "win": ["PewterGymBrockReceivedBoulderBadgeText", "PewterGymBrockBoulderBadgeInfoText"],
	"info": "PewterGymBrockWaitTakeThisText", "tmText": ["PewterGymReceivedTM34Text", "TM34ExplanationText"], "noRoom": "PewterGymTM34NoRoomText",
	"after": "PewterGymBrockPostBattleAdviceText", "trainers": ["EVENT_BEAT_PEWTER_GYM_TRAINER_0"], "onWin": _brock_on_win,
}
var MISTY := {
	"cls": "MISTY", "flag": "EVENT_BEAT_MISTY", "tmFlag": "EVENT_GOT_TM11", "tm": "TM_BUBBLEBEAM", "badge": "CASCADEBADGE",
	"before": "CeruleanGymMistyPreBattleText", "win": ["CeruleanGymMistyReceivedCascadeBadgeText"],
	"info": "CeruleanGymMistyCascadeBadgeInfoText", "tmText": ["CeruleanGymMistyReceivedTM11Text"], "noRoom": "CeruleanGymMistyTM11NoRoomText",
	"after": "CeruleanGymMistyTM11ExplanationText", "trainers": ["EVENT_BEAT_CERULEAN_GYM_TRAINER_0", "EVENT_BEAT_CERULEAN_GYM_TRAINER_1"],
}
var SURGE := {
	"cls": "LT_SURGE", "flag": "EVENT_BEAT_LT_SURGE", "tmFlag": "EVENT_GOT_TM24", "tm": "TM_THUNDERBOLT", "badge": "THUNDERBADGE",
	"before": "VermilionGymLTSurgePreBattleText", "win": ["VermilionGymLTSurgeReceivedThunderBadgeText"],
	"info": "VermilionGymLTSurgeThunderBadgeInfoText", "tmText": ["VermilionGymLTSurgeReceivedTM24Text", "TM24ExplanationText"], "noRoom": "VermilionGymLTSurgeTM24NoRoomText",
	"after": "VermilionGymLTSurgePostBattleAdviceText", "trainers": ["EVENT_BEAT_VERMILION_GYM_TRAINER_0", "EVENT_BEAT_VERMILION_GYM_TRAINER_1", "EVENT_BEAT_VERMILION_GYM_TRAINER_2"],
}

func register() -> void:
	# Mt. Moon B2F: no wild battles in the fossil area once the Super Nerd is beaten (BIT_NO_BATTLES)
	Story.encounter_guards.append(func(m: String, x: int, y: int) -> bool:
		return m == "MtMoonB2F" and Story.flag("EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD") and x >= 11 and x <= 14 and y >= 5 and y <= 8)

	# ---- Route 2
	Story.def_map("Route2Gate", {"talk": {"ROUTE2GATE_OAKS_AIDE": _aide.bind(10, "HM_FLASH", "EVENT_GOT_HM05", "Route2GateOaksAideFlashExplanationText")}})
	Story.def_map("Route2TradeHouse", {"talk": {"ROUTE2TRADEHOUSE_GAMEBOY_KID": _trade_h.bind(1)}})  # ABRA -> MR.MIME "MARCEL"
	Story.def_map("DiglettsCaveRoute2", {"enter": _set_last_outdoor.bind("Route2")})
	Story.def_map("DiglettsCaveRoute11", {"enter": _set_last_outdoor.bind("Route11")})
	# ---- Pewter
	Story.def_map("PewterCity", {
		"enter": _pewter_enter, "step": _pewter_step,
		"talk": {"PEWTERCITY_YOUNGSTER": _pewter_youngster, "PEWTERCITY_SUPER_NERD1": _pewter_nerd1, "PEWTERCITY_SUPER_NERD2": _pewter_nerd2},
	})
	Story.def_map("Museum1F", {
		"step": _museum_step,
		"talk": {"MUSEUM1F_SCIENTIST1": _museum_scientist1_talk, "MUSEUM1F_SCIENTIST2": _museum_scientist2},
		"hidden": {"2,3": _fossil_popup.bind("AERODACTYL", "AerodactylFossilText"), "2,6": _fossil_popup.bind("KABUTOPS", "KabutopsFossilText")},
	})
	Story.def_map("PewterGym", {"talk": {"PEWTERGYM_BROCK": _leader_h.bind("BROCK"), "PEWTERGYM_GYM_GUIDE": _pewter_guide}})
	Story.def_map("PewterPokecenter", {"talk": {"PEWTERPOKECENTER_JIGGLYPUFF": _jigglypuff}, "hidden": {"0,4": bench_guy("PewterCityPokecenterGuyText")}})
	Story.def_map("PewterNidoranHouse", {"talk": {"PEWTERNIDORANHOUSE_NIDORAN": _say_cry.bind("PewterNidoranHouseNidoranText", "NIDORAN_M")}})
	# ---- Mt. Moon
	Story.def_map("MtMoonPokecenter", {"talk": {"MTMOONPOKECENTER_MAGIKARP_SALESMAN": _magikarp_salesman}, "hidden": {"0,4": bench_guy("MtMoonPokecenterBenchGuyText")}})
	var moon_talk := {
		"MTMOONB2F_SUPER_NERD": _moon_nerd_h,
		"MTMOONB2F_DOME_FOSSIL": _moon_fossil.bind("DOME_FOSSIL", "MTMOONB2F_DOME_FOSSIL", "EVENT_GOT_DOME_FOSSIL", "MtMoonB2FDomeFossilYouWantText"),
		"MTMOONB2F_HELIX_FOSSIL": _moon_fossil.bind("HELIX_FOSSIL", "MTMOONB2F_HELIX_FOSSIL", "EVENT_GOT_HELIX_FOSSIL", "MtMoonB2FHelixFossilYouWantText"),
	}
	for r in MOON_ROCKETS:
		moon_talk[r] = Story.trainer_talk
	Story.def_map("MtMoonB2F", {"enter": _moon_enter, "step": _moon_step, "talk": moon_talk})
	# ---- Cerulean
	Story.def_map("CeruleanCity", {
		"enter": _cerulean_enter, "step": _cerulean_step,
		"talk": {"CERULEANCITY_RIVAL": _cerulean_rival_talk, "CERULEANCITY_ROCKET": _cerulean_rocket,
			"CERULEANCITY_COOLTRAINER_F1": _cerulean_cooltrainer, "CERULEANCITY_SLOWBRO": _cerulean_slowbro},
	})
	Story.def_map("CeruleanTrashedHouse", {"talk": {"CERULEANTRASHEDHOUSE_FISHING_GURU": _trashed_house_guru}})
	Story.def_map("CeruleanTradeHouse", {"talk": {"CERULEANTRADEHOUSE_GAMBLER": _trade_h.bind(6)}})  # POLIWHIRL -> JYNX "LOLA"
	Story.def_map("CeruleanBadgeHouse", {"talk": {"CERULEANBADGEHOUSE_MIDDLE_AGED_MAN": _badge_house}})
	var bike_hidden := {}
	for c in ["1,0", "2,1", "1,2", "3,2", "0,4", "1,5"]:
		bike_hidden[c] = _say.bind("NewBicycleText")
	Story.def_map("BikeShop", {"talk": {"BIKESHOP_CLERK": _bike_clerk, "BIKESHOP_YOUNGSTER": _bike_youngster}, "hidden": bike_hidden})
	Story.def_map("CeruleanGym", {"talk": {"CERULEANGYM_MISTY": _leader_h.bind("MISTY"), "CERULEANGYM_GYM_GUIDE": _flag_say.bind("EVENT_BEAT_MISTY", "CeruleanGymGymGuideChampInMakingText", "CeruleanGymGymGuideBeatMistyText")}})
	Story.def_map("CeruleanPokecenter", {"hidden": {"0,4": bench_guy("CeruleanPokecenterGuyText")}})
	# ---- Routes 24/25, Bill
	Story.def_map("Route24", {"step": _route24_step, "talk": {"ROUTE24_COOLTRAINER_M1": _nugget_talk}})
	Story.def_map("Route25", {"enter": _route25_enter})
	Story.def_map("BillsHouse", {
		"talk": {"BILLSHOUSE_BILL_POKEMON": _bill_pokemon, "BILLSHOUSE_BILL1": _bill1, "BILLSHOUSE_BILL2": _say.bind("BillsHouseBillCheckOutMyRarePokemonText")},
		"hidden": {"1,4": _bills_pc},
	})
	# ---- Routes 5/6 gates, Underground Path
	Story.def_map("Route5Gate", _saffron_gate("ROUTE5GATE_GUARD", "U", "left", 3))
	Story.def_map("Route6Gate", _saffron_gate("ROUTE6GATE_GUARD", "D", "right", 2))
	Story.def_map("UndergroundPathRoute5", {"enter": _set_last_outdoor.bind("Route5"), "talk": {"UNDERGROUNDPATHROUTE5_LITTLE_GIRL": _trade_h.bind(9)}})  # NIDORAN♂ -> NIDORAN♀
	Story.def_map("UndergroundPathRoute6", {"enter": _set_last_outdoor.bind("Route6")})
	# ---- Vermilion
	Story.def_map("VermilionCity", {
		"enter": _vermilion_enter, "step": _vermilion_step,
		"talk": {"VERMILIONCITY_SAILOR1": _vermilion_sailor_talk,
			"VERMILIONCITY_GAMBLER1": _flag_say.bind("EVENT_SS_ANNE_LEFT", "VermilionCityGambler1DidYouSeeText", "VermilionCityGambler1SSAnneDepartedText"),
			"VERMILIONCITY_MACHOP": _machop},
	})
	Story.def_map("VermilionGym", {
		"enter": _vermilion_gym_enter,
		"talk": {"VERMILIONGYM_LT_SURGE": _leader_h.bind("SURGE"), "VERMILIONGYM_GYM_GUIDE": _surge_guide},
		"hidden": {"6,1": _say.bind("VermilionGymTrashText")},
	})
	Story.def_map("VermilionOldRodHouse", {"talk": {"VERMILIONOLDRODHOUSE_FISHING_GURU": _old_rod}})
	Story.def_map("VermilionPidgeyHouse", {"talk": {"VERMILIONPIDGEYHOUSE_PIDGEY": _say_cry.bind("VermilionPidgeyHousePidgeyText", "PIDGEY")}})
	Story.def_map("VermilionTradeHouse", {"talk": {"VERMILIONTRADEHOUSE_LITTLE_GIRL": _trade_h.bind(4)}})  # SPEAROW -> FARFETCH'D "DUX"
	Story.def_map("VermilionPokecenter", {"hidden": {"0,4": bench_guy("VermilionPokecenterGuyText")}})
	Story.def_map("PokemonFanClub", {"talk": {
		"POKEMONFANCLUB_PIKACHU_FAN": _pikachu_fan, "POKEMONFANCLUB_SEEL_FAN": _seel_fan,
		"POKEMONFANCLUB_PIKACHU": _say_cry.bind("PokemonFanClubPikachuText", "PIKACHU"), "POKEMONFANCLUB_SEEL": _say_cry.bind("PokemonFanClubSeelText", "SEEL"),
		"POKEMONFANCLUB_CHAIRMAN": _fan_chairman}})
	Story.def_map("VermilionDock", {"enter": _dock_enter})
	# ---- S.S. Anne
	Story.def_map("SSAnne2F", {"step": _ssanne2f_step, "talk": {"SSANNE2F_RIVAL": _say.bind("SSAnne2FRivalText")}})
	Story.def_map("SSAnneCaptainsRoom", {"talk": {"SSANNECAPTAINSROOM_CAPTAIN": _captain}})
	Story.def_map("SSAnne1FRooms", {"talk": {"SSANNE1FROOMS_WIGGLYTUFF": _say_cry.bind("SSAnne1FRoomsWigglytuffText", "WIGGLYTUFF")}})
	Story.def_map("SSAnneB1FRooms", {"talk": {"SSANNEB1FROOMS_MACHOKE": _say_cry.bind("SSAnneB1FRoomsMachokeText", "MACHOKE")}})
	Story.def_map("SSAnne2FRooms", {"talk": {"SSANNE2FROOMS_GENTLEMAN3": _gentleman3}})
	Story.def_map("SSAnneKitchen", {"talk": {"SSANNEKITCHEN_COOK7": _cook7}, "hidden": {"13,5": _say.bind("VermilionGymTrashText"), "13,7": _say.bind("VermilionGymTrashText")}})
	# ---- Route 11 gate, Rock Tunnel Pokécenter
	Story.def_map("Route11Gate2F", {
		"talk": {"ROUTE11GATE2F_OAKS_AIDE": _aide.bind(30, "ITEMFINDER", "EVENT_GOT_ITEMFINDER", "Route11Gate2FOaksAideItemfinderDescriptionText"),
			"ROUTE11GATE2F_YOUNGSTER": _trade_h.bind(0)},  # NIDORINO -> NIDORINA "TERRY"
		"sign": {"TEXT_ROUTE11GATE2F_LEFT_BINOCULARS": _r11_left_binoculars, "TEXT_ROUTE11GATE2F_RIGHT_BINOCULARS": _r11_right_binoculars},
	})
	Story.def_map("RockTunnelPokecenter", {"hidden": {"0,4": bench_guy("RockTunnelPokecenterGuyText")}})

## Story.hidden_event hook for fn = GymTrashScript (G.vermilionTrash)
func hidden_fn(fn: String, _h: Dictionary, _d: String) -> Callable:
	if fn == "GymTrashScript":
		return _vermilion_trash
	return Callable()

# ======================================================================
# helpers
# ======================================================================
func _say(_o: Variant, label: String) -> void:
	await Story.say(label)

func _flag_say(_o: Variant, f: String, before: String, after: String) -> void:
	await Story.say(after if Story.flag(f) else before)

func _say_cry(_o: Variant, label: String, sp: String) -> void:
	Story.cry(sp)
	await Story.say(label)

func _set_last_outdoor(route: String) -> Callable:
	GameState.last_outdoor = route
	return Callable()

func _is_warp(c: Vector2i) -> bool:
	for w in Story.map_data().get("warps", []):
		if int(w["x"]) == c.x and int(w["y"]) == c.y:
			return true
	return false

## freeCell: passable, no actors, no warps
func _free_cell(c: Vector2i) -> bool:
	return bool(Story.hq("is_passable", [c], true)) and not _is_warp(c) and not Story._occupied(c, P)

## An NPC walks `path` and the player follows one step behind (Pewter City guides)
func lead(guy: String, path: String) -> void:
	var t: Array = [Story.cell(guy)]
	for ch in path:
		t.append(t[t.size() - 1] + D4[ch])
	var p := Story.pcell()
	if t.slice(0, 3).has(p):
		for d in "LRDU":
			var n: Vector2i = p + D4[d]
			if _free_cell(n) and not t.slice(0, 3).has(n):
				await Story.move_player(d)
				break
	await Story.move(guy, path[0])
	var pre := Story.path_to(P, t[0].x, t[0].y)
	if pre != "":
		await Story.move_player(pre)
	else:
		Story.hq("show_actor", [P, t[0]])
	for i in range(1, path.length()):
		await Story.move_together([[guy, path[i]], [P, path[i - 1]]])
	var last := path[path.length() - 2] if path.length() >= 2 else path[0]
	Story.face(P, Story.DIRC[last])
	GameState.player_cell = Story.pcell()

## wait for a door/warp transition to finish before a scripted sequence starts
func wait_warp() -> void:
	await Story.wait(1)
	var n := 0
	while Story._has_host("is_warping") and bool(Story.hq("is_warping", [], false)) and n < 600:
		await Story.wait(1)
		n += 1

func bench_guy(label: String) -> Callable:
	return _bench.bind(label)

func _bench(_h: Dictionary, label: String) -> void:
	if Story.pdir() == "left":
		await Story.say(label)

## Prof. Oak's aides (engine/events/oaks_aide.asm)
func _aide(_o: Dictionary, req: int, item: String, f: String, explain: String) -> void:
	await oaks_aide(req, item, f, explain)

func oaks_aide(req: int, item: String, f: String, explain: String) -> void:
	if not Story.flag(f):
		Story.setvar("wOaksAideRewardItemName", Story.item_name(item))
		Story.setvar("hOaksAideRequirement", req)
		if not await Story.ask("OaksAideHiText"):
			await Story.say("OaksAideComeBackText")
			return
		var own := Story.caught_count()
		Story.setvar("hOaksAideNumMonsOwned", own)
		if own < req:
			await Story.say("OaksAideUhOhText")
			return
		await Story.say("OaksAideHereYouGoText")
		if not Story.bag_add(item, 1):
			await Story.say("OaksAideNoRoomText")
			return
		Story.sfx("get_tm" if item.begins_with("HM_") else "get_item")
		await Story.say("OaksAideGotItemText")
		Story.setf(f)
	await Story.say(explain)

## In-game trades (engine/events/in_game_trades.asm)
func _trade_h(_o: Dictionary, idx: int) -> void:
	await trade(idx)

func trade(idx: int) -> void:
	var tr: Dictionary = Story.pokedata["trades"][idx]
	var set_n: int = TRADE_SET.get(tr.get("dialog", ""), 1)
	var k := "TRADED_%d" % idx
	Story.setvar("wInGameTradeGiveMonName", Story.species_name(tr["give"]))
	Story.setvar("wInGameTradeReceiveMonName", Story.species_name(tr["get"]))
	if Story.flag(k):
		await Story.say("AfterTrade%dText" % set_n)
		return
	if not await Story.ask("WannaTrade%dText" % set_n):
		await Story.say("NoTrade%dText" % set_n)
		return
	var i := await Story.party_screen("Trade which POKéMON?")
	if i < 0:
		await Story.say("NoTrade%dText" % set_n)
		return
	var m: Object = GameState.party[i]
	if m.get("species_id") != tr["give"]:
		await Story.say("WrongMon%dText" % set_n)
		return
	Story.setf(k)
	await Story.say("ConnectCableText")
	var nm := Story.new_mon(tr["get"], int(m.get("level")))
	nm.set("nickname", tr["nick"])
	nm.set_meta("ot", "TRAINER")
	await Story.trade_animation(m, nm)
	# the traded mon leaves the party; the new one is appended at the end
	GameState.party.remove_at(i)
	GameState.party.append(nm)
	GameState.party_changed.emit()
	Story.dex_caught(tr["get"])
	Story.sfx("get_key")
	await Story.say("TradedForText")
	await Story.say("Thanks%dText" % set_n)

## Gym leaders: {cls, flag, tmFlag, tm, badge, before, win:[labels], info, tmText:[labels], noRoom, after, trainers:[flags], onWin}
func _leader_h(_o: Dictionary, which: String) -> void:
	await leader_talk(get(which))

func leader_reward(o: Dictionary) -> void:
	await Story.say(o["info"])
	Story.setf(o["flag"])
	if await Story.got(o["tm"], 1):
		await Story.say(Story.join(o["tmText"]))
		Story.setf(o["tmFlag"])
	else:
		await Story.say(o["noRoom"])
	if not Story.has_badge(o["badge"]):
		GameState.badges.append(o["badge"])
		GameState.badge_earned.emit(o["badge"])
	for f in o["trainers"]:
		Story.setf(f)
	if o.has("onWin"):
		(o["onWin"] as Callable).call()

func leader_talk(o: Dictionary) -> void:
	if Story.flag(o["flag"]):
		if not Story.flag(o["tmFlag"]):
			await leader_reward(o)
			return
		await Story.say(o["after"])
		return
	await Story.say(o["before"])
	var r := await Story.battle(o["cls"], 1, {"win_text": Story.fmt(Story.join(o["win"]))})
	if r != "win":
		return
	Story.sfx("get_badge")
	await leader_reward(o)

## Fossil / Pokédex pop-ups
func mon_popup(sp: String, label: String, fossil: bool) -> void:
	var pic := Story.mon_popup(sp, Rect2i(104, 16, 112, 100), fossil)
	if not fossil:
		Story.cry(sp)
	await Story.say(label)
	Story.close_box(pic)

func _fossil_popup(_h: Dictionary, sp: String, label: String) -> void:
	await mon_popup(sp, label, true)

# ======================================================================
# Pewter City
# ======================================================================
func _pewter_enter() -> Callable:
	Story.clear("EVENT_BOUGHT_MUSEUM_TICKET")
	return Callable()

func _pewter_step(x: int, y: int) -> Callable:
	if Story.running > 0 or Story.flag("EVENT_BEAT_BROCK") or not Story.actor("PEWTERCITY_YOUNGSTER"):
		return Callable()
	if (y == 17 and (x == 35 or x == 36)) or (x == 37 and (y == 18 or y == 19)):
		return pewter_gym_guy
	return Callable()

func pewter_gym_guy() -> void:
	var g := "PEWTERCITY_YOUNGSTER"
	if not Story.actor(g):
		return
	await Story.say("PewterCityYoungsterYoureATrainerFollowMeText")
	await lead(g, GYM_GUY_PATH)
	Story.face(g, "left")
	await Story.say("PewterCityYoungsterGoTakeOnBrockText")
	await Story.move(g, "RRRRR")
	Story.hide(g)
	Story.show(g)  # back at his post

func pewter_museum_guy() -> void:
	var g := "PEWTERCITY_SUPER_NERD1"
	if not Story.actor(g):
		return
	await lead(g, MUSEUM_GUY_PATH)
	Story.face(g, "up")
	await Story.say("PewterCitySuperNerd1ItsRightHereText")
	await Story.move(g, "DDDD")
	Story.hide(g)
	Story.show(g)

func _pewter_youngster(_o: Dictionary) -> void:
	await pewter_gym_guy()

func _pewter_nerd1(_o: Dictionary) -> void:
	if await Story.ask("PewterCitySuperNerd1DidYouCheckOutMuseumText"):
		await Story.say("PewterCitySuperNerd1WerentThoseFossilsAmazingText")
		return
	await Story.say("PewterCitySuperNerd1YouHaveToGoText")
	await pewter_museum_guy()

func _pewter_nerd2(_o: Dictionary) -> void:
	if await Story.ask("PewterCitySuperNerd2DoYouKnowWhatImDoingText"):
		await Story.say("PewterCitySuperNerd2ThatsRightText")
	else:
		await Story.say("PewterCitySuperNerd2ImSprayingRepelText")

# ---------------- Pewter Museum
func museum_scientist(_from_step: bool) -> void:
	var p := Story.pcell()
	if (p.y == 4 and p.x == 13) or (p.y == 3 and p.x == 12):  # behind the counter
		if await Story.ask("Museum1FScientist1DoYouKnowWhatAmberIsText"):
			await Story.say("Museum1FScientist1TheresALabSomewhereText")
		else:
			await Story.say("Museum1FScientist1AmberIsFossilizedTreeSapText")
		return
	if Story.flag("EVENT_BOUGHT_MUSEUM_TICKET"):
		await Story.say("Museum1FScientist1TakePlentyOfTimeText")
		return
	if p.y != 4:
		await Story.say("Museum1FScientist1GoToOtherSideText")
		return
	var box := Story.money_box()
	if await Story.ask("Museum1FScientist1WouldYouLikeToComeInText"):
		if GameState.money >= 50:
			await Story.say("Museum1FScientist1ThankYouText")
			Story.setf("EVENT_BOUGHT_MUSEUM_TICKET")
			GameState.money -= 50
			Story.sfx("buy")
			await Story.wait(20)
			Story.close_box(box)
			return
		await Story.say("Museum1FScientist1DontHaveEnoughMoneyText")
	await Story.say("Museum1FScientist1ComeAgainText")
	Story.close_box(box)
	await Story.move_player("D")

func _museum_step(x: int, y: int) -> Callable:
	if Story.running > 0 or Story.flag("EVENT_BOUGHT_MUSEUM_TICKET") or y != 4 or (x != 9 and x != 10):
		return Callable()
	return museum_scientist.bind(true)

func _museum_scientist1_talk(_o: Dictionary) -> void:
	await museum_scientist(false)

func _museum_scientist2(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_OLD_AMBER"):
		await Story.say("Museum1FScientist2GetTheOldAmberCheckText")
		return
	await Story.say("Museum1FScientist2TakeThisToAPokemonLabText")
	if not Story.bag_add("OLD_AMBER", 1):
		await Story.say("Museum1FScientist2YouDontHaveSpaceText")
		return
	Story.setf("EVENT_GOT_OLD_AMBER")
	Story.hide("MUSEUM1F_OLD_AMBER")
	Story.sfx("get_item")
	await Story.say("Museum1FScientist2ReceivedOldAmberText")

# ---------------- Pewter Gym
func _brock_on_win() -> void:
	Story.hide("PEWTERCITY_YOUNGSTER", "PewterCity")  # TOGGLE_GYM_GUY
	Story.hide("ROUTE22_RIVAL1", "Route22")
	Story.clear("EVENT_1ST_ROUTE22_RIVAL_BATTLE")
	Story.clear("EVENT_ROUTE22_RIVAL_WANTS_BATTLE")

func _pewter_guide(_o: Dictionary) -> void:
	if Story.has_badge("BOULDERBADGE"):
		await Story.say("PewterGymGuidePostBattleText")
		return
	if await Story.ask("PewterGymGuidePreAdviceText"):
		await Story.say("PewterGymGuideBeginAdviceText")
	else:
		await Story.say("PewterGymGuideFreeServiceText")
	await Story.say("PewterGymGuideAdviceText")

func _jigglypuff(o: Dictionary) -> void:
	var id: String = o.get("id", "")
	var t := Story.fmt(Story.txt("PewterPokecenterJigglypuffText"))
	await Story.say(t, {"no_wait": true})
	if Story._audio():
		Story.music("jigglypuff", true)
	else:
		Story.cry("JIGGLYPUFF")
	var dirs := ["down", "left", "up", "right"]
	var k := maxi(0, dirs.find(Story.dir_of(id)))
	for i in 16:
		Story.face(id, dirs[k % 4])
		k += 1
		await Story.wait(24)
	await Story.wait(48)
	Story.map_music()

# ======================================================================
# Mt. Moon
# ======================================================================
func _magikarp_salesman(_o: Dictionary) -> void:
	if Story.flag("EVENT_BOUGHT_MAGIKARP"):
		await Story.say("MtMoonPokecenterMagikarpSalesmanNoRefundsText")
		return
	var box := Story.money_box()
	if not await Story.ask("MtMoonPokecenterMagikarpSalesmanIGotADealText"):
		await Story.say("MtMoonPokecenterMagikarpSalesmanNoText")
	elif GameState.money < 500:
		await Story.say("MtMoonPokecenterMagikarpSalesmanNoMoneyText")
	elif await Story.gift_mon("MAGIKARP", 5):
		GameState.money -= 500
		Story.setf("EVENT_BOUGHT_MAGIKARP")
	Story.close_box(box)

func _got_fossil() -> bool:
	return Story.flag("EVENT_GOT_DOME_FOSSIL") or Story.flag("EVENT_GOT_HELIX_FOSSIL")

## once a fossil is taken the rockets no longer spot you
func _moon_rockets_sight() -> void:
	if not _got_fossil():
		return
	for id in MOON_ROCKETS:
		Story.sight_off[Story.key("MtMoonB2F", id)] = true

func _moon_nerd_takes_other() -> void:
	var p := Story.pcell()
	var n := "MTMOONB2F_SUPER_NERD"
	var path := ""
	if NEAR_DOME.has(p):
		path = "RU"
	elif NEAR_HELIX.has(p):
		path = "U"
	if path == "":
		Story.setf("MTMOONB2F_NERD_WAITING")
		return
	Story.clear("MTMOONB2F_NERD_WAITING")
	if Story.actor(n):
		await Story.move(n, path)
	Story.sfx("get_key")
	await Story.say("MtMoonB2FSuperNerdThenThisIsMineText")
	Story.hide("MTMOONB2F_HELIX_FOSSIL" if Story.flag("EVENT_GOT_DOME_FOSSIL") else "MTMOONB2F_DOME_FOSSIL")

func _moon_fossil(_o: Dictionary, item: String, obj: String, f: String, ask: String) -> void:
	if not await Story.ask(ask):
		return
	if not await Story.got(item, 1):
		await Story.say("MtMoonB2FYouHaveNoRoomText")
		return
	await Story.say("MtMoonB2FReceivedFossilText")
	Story.hide(obj)
	Story.setf(f)
	_moon_rockets_sight()
	await _moon_nerd_takes_other()

func moon_nerd() -> void:
	if Story.flag("EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD"):
		await Story.say("MtMoonB2FSuperNerdTheresAPokemonLabText" if _got_fossil() else "MtMoonB2fSuperNerdEachTakeOneText")
		return
	var n := "MTMOONB2F_SUPER_NERD"
	if Story.actor(n):
		Story.face_player(n)
	await Story.say("MtMoonB2FSuperNerdTheyreBothMineText")
	var t := Story.fmt(Story.join(["MtMoonB2FSuperNerdOkIllShareText"]))
	var r := await Story.battle("SUPER_NERD", 2, {"win_text": t, "lose_text": t})
	if r == "win":
		Story.setf("EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD")

func _moon_nerd_h(_o: Dictionary) -> void:
	await moon_nerd()

func _moon_enter() -> Callable:
	_moon_rockets_sight()
	return Callable()

func _moon_step(x: int, y: int) -> Callable:
	if Story.running > 0:
		return Callable()
	if not Story.flag("EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD") and x == 13 and y == 8:
		return moon_nerd
	var c := Vector2i(x, y)
	if Story.flag("MTMOONB2F_NERD_WAITING") and (NEAR_DOME.has(c) or NEAR_HELIX.has(c)):
		return _moon_nerd_takes_other
	return Callable()

# ======================================================================
# Cerulean City
# ======================================================================
func cerulean_rocket(r: Dictionary) -> void:
	if not Story.flag("EVENT_BEAT_CERULEAN_ROCKET_THIEF"):
		await Story.say("CeruleanCityRocketText")
		var t := Story.fmt(Story.join(["CeruleanCityRocketIGiveUpText"]))
		var res := await Story.battle("ROCKET", int(r.get("trainer", {}).get("n", 5)), {"win_text": t, "lose_text": t})
		if res != "win":
			return
		Story.setf("EVENT_BEAT_CERULEAN_ROCKET_THIEF")
	await Story.say("CeruleanCityRocketIllReturnTheTMText")
	if not await Story.got("TM_DIG", 1):
		await Story.say("CeruleanCityRocketTM28NoRoomText")
		return
	await Story.say(Story.join(["CeruleanCityRocketReceivedTM28Text", "CeruleanCityRocketIBetterGetMovingText"]))
	# CeruleanHideRocket
	await Story.fade_out(12)
	Story.show("CERULEANCITY_GUARD1")
	Story.hide("CERULEANCITY_GUARD2")
	Story.hide("CERULEANCITY_ROCKET")
	await Story.fade_in(12)

func cerulean_rival(x: int) -> void:
	Story.music("rival")
	var rival := Story.show("CERULEANCITY_RIVAL", "", Vector2i(x, 2))
	Story.place(rival, x, 2, "down")
	await Story.move(rival, "DDD")
	Story.face(P, "up")
	Story.face(rival, "down")
	await Story.say("CeruleanCityRivalPreBattleText")
	var r := await Story.battle("RIVAL1", Story.rival_party(7), {"win_text": Story.fmt(Story.join(["CeruleanCityRivalDefeatedText"])), "lose_text": Story.fmt(Story.join(["CeruleanCityRivalVictoryText"]))})
	if r != "win":
		Story.hide("CERULEANCITY_RIVAL", "CeruleanCity")
		return
	Story.setf("EVENT_BEAT_CERULEAN_RIVAL")
	Story.face(rival, "down")
	await Story.say("CeruleanCityRivalIWentToBillsText")
	Story.music("rival")
	await Story.move(rival, ("R" if x == 20 else "L") + "DDDDDD")
	Story.hide("CERULEANCITY_RIVAL")
	Story.map_music()

func _cerulean_enter() -> Callable:
	# TOGGLE_CERULEAN_CAVE_GUY is hidden by the Hall of Fame script
	if Story.flag("EVENT_BEAT_CHAMPION_RIVAL") or Story.flag("EVENT_BEAT_CHAMPION") or Story.flag("EVENT_HALL_OF_FAME_DEX_RATING"):
		Story.hide("CERULEANCITY_SUPER_NERD3")
	return Callable()

func _cerulean_step(x: int, y: int) -> Callable:
	if Story.running > 0:
		return Callable()
	if not Story.flag("EVENT_BEAT_CERULEAN_ROCKET_THIEF") and x == 30 and (y == 7 or y == 9) and Story.actor("CERULEANCITY_ROCKET"):
		return _cerulean_rocket_step.bind(y)
	if not Story.flag("EVENT_BEAT_CERULEAN_RIVAL") and y == 6 and (x == 20 or x == 21):
		return cerulean_rival.bind(x)
	return Callable()

func _cerulean_rocket_step(y: int) -> void:
	var r := "CERULEANCITY_ROCKET"
	if y == 9:
		Story.face(P, "up")
		Story.face(r, "down")
	else:
		Story.face(P, "down")
		Story.face(r, "up")
	await Story.wait(3)
	await cerulean_rocket(Story.obj(r))

func _cerulean_rival_talk(_o: Dictionary) -> void:
	await Story.say("CeruleanCityRivalIWentToBillsText" if Story.flag("EVENT_BEAT_CERULEAN_RIVAL") else "CeruleanCityRivalPreBattleText")

func _cerulean_rocket(o: Dictionary) -> void:
	await cerulean_rocket(o)

func _cerulean_cooltrainer(_o: Dictionary) -> void:
	var r := randi() % 256
	await Story.say("CeruleanCityCooltrainerF1SlowbroUseSonicboomText" if r >= 180 else ("CeruleanCityCooltrainerF1SlowbroPunchText" if r >= 100 else "CeruleanCityCooltrainerF1SlowbroWithdrawText"))

func _cerulean_slowbro(_o: Dictionary) -> void:
	var r := randi() % 256
	var l := "CeruleanCitySlowbroIgnoredOrdersText"
	if r >= 180:
		l = "CeruleanCitySlowbroTookASnoozeText"
	elif r >= 120:
		l = "CeruleanCitySlowbroIsLoafingAroundText"
	elif r >= 60:
		l = "CeruleanCitySlowbroTurnedAwayText"
	await Story.say(l)

func _trashed_house_guru(_o: Dictionary) -> void:
	await Story.say("CeruleanTrashedHouseFishingGuruWhatsLostIsLostText" if Story.bag_has("TM_DIG") else "CeruleanTrashedHouseFishingGuruTheyStoleATMText")

func _badge_house(_o: Dictionary) -> void:
	await Story.say("CeruleanBadgeHouseMiddleAgedManText")
	while true:
		var r := await Story.menu_with_text("CeruleanBadgeHouseMiddleAgedManWhichBadgeText", BADGES, {"x": 184, "y": -4, "w": 130})
		if r < 0 or r >= BADGES.size():
			break
		var n: String = BADGES[r].replace("BADGE", "")
		await Story.say("CeruleanBadgeHouse" + n.substr(0, 1) + n.substr(1).to_lower() + "BadgeText")
	await Story.say("CeruleanBadgeHouseMiddleAgedManVisitAnyTimeText")

func _bike_clerk(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_BICYCLE"):
		await Story.say("BikeShopClerkHowDoYouLikeYourBicycleText")
		return
	if Story.bag_has("BIKE_VOUCHER"):
		await Story.say("BikeShopClerkOhThatsAVoucherText")
		if not Story.bag_add("BICYCLE", 1):
			await Story.say("BikeShopBagFullText")
			return
		Story.bag_remove("BIKE_VOUCHER", 1)
		Story.setf("EVENT_GOT_BICYCLE")
		Story.sfx("get_key")
		await Story.say("BikeShopExchangedVoucherText")
		return
	await Story.say("BikeShopClerkWelcomeText")
	var box := Story.money_box()
	var r := await Story.menu_with_text("BikeShopClerkDoYouLikeItText", ["BICYCLE  $1000000", "CANCEL"], {"x": 6, "y": 6})
	Story.close_box(box)
	if r == 0:
		await Story.say("BikeShopCantAffordText")
	await Story.say("BikeShopComeAgainText")

func _bike_youngster(_o: Dictionary) -> void:
	await Story.say("BikeShopYoungsterCoolBikeText" if Story.flag("EVENT_GOT_BICYCLE") else "BikeShopYoungsterTheseBikesAreExpensiveText")

# ======================================================================
# Route 24 (Nugget Bridge) / Route 25 / Bill's house
# ======================================================================
func nugget_rocket(a: Dictionary, from_step: bool) -> void:
	Story.clear("EVENT_NUGGET_REWARD_AVAILABLE")
	if Story.flag("EVENT_GOT_NUGGET"):
		await Story.say("Route24CooltrainerM1YouCouldBecomeATopLeaderText")
		return
	await Story.say(Story.join(["Route24CooltrainerM1YouBeatOurContestText", "Route24CooltrainerM1YouJustEarnedAPrizeText"]))
	if not await Story.got("NUGGET", 1, "Route24CooltrainerM1ReceivedNuggetText"):
		await Story.say("Route24CooltrainerM1NoRoomText")
		Story.setf("EVENT_NUGGET_REWARD_AVAILABLE")
		if from_step:
			Story.clear("EVENT_NUGGET_REWARD_AVAILABLE")
			await Story.move_player("D")
		return
	Story.setf("EVENT_GOT_NUGGET")
	await Story.say("Route24CooltrainerM1JoinTeamRocketText")
	var t := Story.fmt(Story.join(["Route24CooltrainerM1DefeatedText"]))
	var r := await Story.battle("ROCKET", int(a.get("trainer", {}).get("n", 6)), {"win_text": t, "lose_text": t})
	if r != "win":
		return
	Story.setf("EVENT_BEAT_ROUTE24_ROCKET")
	await Story.say("Route24CooltrainerM1YouCouldBecomeATopLeaderText")

func _route24_step(x: int, y: int) -> Callable:
	if Story.running > 0 or Story.flag("EVENT_GOT_NUGGET") or x != 10 or y != 15:
		return Callable()
	if not Story.actor("ROUTE24_COOLTRAINER_M1"):
		return Callable()
	return _nugget_step

func _nugget_step() -> void:
	Story.face("ROUTE24_COOLTRAINER_M1", "left")
	await nugget_rocket(Story.obj("ROUTE24_COOLTRAINER_M1"), true)

func _nugget_talk(o: Dictionary) -> void:
	await nugget_rocket(o, false)

func _route25_enter() -> Callable:  # Route25ToggleBillsScript
	if Story.flag("EVENT_LEFT_BILLS_HOUSE_AFTER_HELPING"):
		return Callable()
	if not Story.flag("EVENT_MET_BILL_2"):
		Story.clear("EVENT_BILL_SAID_USE_CELL_SEPARATOR")
		Story.show("BILLSHOUSE_BILL_POKEMON", "BillsHouse")
		return Callable()
	if not Story.flag("EVENT_GOT_SS_TICKET"):
		return Callable()
	Story.setf("EVENT_LEFT_BILLS_HOUSE_AFTER_HELPING")
	Story.hide("ROUTE24_COOLTRAINER_M1", "Route24")  # TOGGLE_NUGGET_BRIDGE_GUY
	Story.hide("BILLSHOUSE_BILL1", "BillsHouse")
	Story.show("BILLSHOUSE_BILL2", "BillsHouse")
	return Callable()

func bills_cell_separator() -> void:
	await Story.say("BillsHouseInitiatedText")
	await Story.wait(16)
	Story.sfx("select")
	await Story.wait(60)
	await Story.wait(32)
	Story.sfx("blip")
	await Story.wait(80)
	Story.sfx("shrink")
	await Story.wait(48)
	Story.sfx("blip")
	await Story.wait(32)
	Story.sfx("get_item")
	await Story.wait(40)
	Story.map_music()
	Story.setf("EVENT_USED_CELL_SEPARATOR_ON_BILL")
	# BillsHouseBillExitsMachineScript
	var bill := Story.show("BILLSHOUSE_BILL1", "", Vector2i(1, 2))
	Story.place(bill, 1, 2, "down")
	await Story.wait(8)
	await Story.move(bill, "DRRRD")
	Story.setf("EVENT_MET_BILL_2")
	Story.setf("EVENT_MET_BILL")

func _bill_pokemon(a: Dictionary) -> void:
	if not await Story.ask("BillsHouseBillImNotAPokemonText"):
		await Story.say("BillsHouseBillNoYouGottaHelpText")
	await Story.say("BillsHouseBillUseSeparationSystemText")
	await Story.move(a.get("id", ""), "RUULU" if Story.pdir() == "down" else "UUU")
	Story.hide("BILLSHOUSE_BILL_POKEMON")
	Story.setf("EVENT_BILL_SAID_USE_CELL_SEPARATOR")

func _bill1(_o: Dictionary) -> void:
	if not Story.flag("EVENT_GOT_SS_TICKET"):
		await Story.say("BillsHouseBillThankYouText")
		if not await Story.got("S_S_TICKET", 1, "SSTicketReceivedText"):
			await Story.say("SSTicketNoRoomText")
			return
		Story.setf("EVENT_GOT_SS_TICKET")
		Story.show("CERULEANCITY_GUARD1", "CeruleanCity")
		Story.hide("CERULEANCITY_GUARD2", "CeruleanCity")
	await Story.say("BillsHouseBillWhyDontYouGoInsteadOfMeText")

func _bills_pc(_h: Dictionary) -> void:
	if Story.pdir() != "up":
		return
	if Story.flag("EVENT_LEFT_BILLS_HOUSE_AFTER_HELPING"):
		await Story.say("BillsHousePokemonListText1")
		while true:
			var items: Array = BILLS_FAVORITES.map(func(s): return Story.species_name(s))
			items.append("CANCEL")
			var r := await Story.menu_with_text("BillsHousePokemonListText2", items, {"x": 6, "y": 4, "w": 120})
			if r < 0 or r >= BILLS_FAVORITES.size():
				return
			await Story.dex_page(BILLS_FAVORITES[r])
			Story.dex_seen(BILLS_FAVORITES[r])
	if Story.flag("EVENT_USED_CELL_SEPARATOR_ON_BILL") or not Story.flag("EVENT_BILL_SAID_USE_CELL_SEPARATOR"):
		await Story.say("BillsHouseMonitorText")
		return
	await bills_cell_separator()

# ======================================================================
# Routes 5 / 6: Saffron gate guards and the Underground Path entrances
# ======================================================================
func _drink_given() -> bool:
	for f in DRINK_FLAGS:
		if Story.flag(f):
			return true
	return false

func _take_guard_drink() -> String:
	for d in ["FRESH_WATER", "SODA_POP", "LEMONADE"]:
		if Story.bag_has(d):
			Story.bag_remove(d, 1)
			return d
	return ""

func saffron_guard(push: String, face_dir: String) -> void:
	if face_dir != "":
		Story.face(P, face_dir)
	if _take_guard_drink() != "":
		for f in DRINK_FLAGS:
			Story.setf(f)
		await Story.say("SaffronGateGuardImParchedText")
		Story.sfx("get_key")
		await Story.say("SaffronGateGuardYouCanGoOnThroughText")
		return
	await Story.say("SaffronGateGuardGeeImThirstyText")
	await Story.move_player(push)

func _saffron_gate(guard_id: String, push: String, face_dir: String, ys: int) -> Dictionary:
	return {
		"step": func(x: int, y: int) -> Callable:
			if Story.running > 0 or _drink_given() or y != ys or (x != 3 and x != 4):
				return Callable()
			return saffron_guard.bind(push, face_dir),
		"talk": {guard_id: _saffron_guard_talk.bind(push)},
	}

func _saffron_guard_talk(_o: Dictionary, push: String) -> void:
	if _drink_given():
		await Story.say("SaffronGateGuardThanksForTheDrinkText")
	else:
		await saffron_guard(push, "")

# ======================================================================
# Vermilion City
# ======================================================================
func vermilion_sailor(from_step: bool) -> void:
	if Story.flag("EVENT_SS_ANNE_LEFT"):
		await Story.say("VermilionCitySailor1ShipSetSailText")
		if from_step:
			await Story.move_player("U")
		return
	var p := Story.pcell()
	if not from_step and (Story.pdir() == "right" or (p.x == 19 and (p.y == 29 or p.y == 31))):
		await Story.say("VermilionCitySailor1WelcomeToSSAnneText")
		return
	await Story.say("VermilionCitySailor1DoYouHaveATicketText")
	if Story.bag_has("S_S_TICKET"):
		await Story.say("VermilionCitySailor1FlashedTicketText")
		return
	await Story.say("VermilionCitySailor1YouNeedATicketText")
	if from_step:
		await Story.move_player("U")

func _vermilion_enter() -> Callable:
	# new first trash-can lock every time the city loads (wFirstLockTrashCanIndex)
	if GameState.vermilion_trash.is_empty():
		GameState.vermilion_trash = {"first": 0, "second": 0}
	GameState.vermilion_trash["first"] = (randi() % 256) & 0xe
	if Story.flag("EVENT_SS_ANNE_LEFT") and not Story.flag("EVENT_WALKED_PAST_GUARD_AFTER_SS_ANNE_LEFT"):
		Story.setf("EVENT_WALKED_PAST_GUARD_AFTER_SS_ANNE_LEFT")
		return _walk_past_guard
	return Callable()

func _walk_past_guard() -> void:
	await wait_warp()
	await Story.move_player("UU")

func _vermilion_step(x: int, y: int) -> Callable:
	if Story.running > 0 or x != 18 or y != 30 or Story.pdir() != "down":
		return Callable()
	return vermilion_sailor.bind(true)

func _vermilion_sailor_talk(_o: Dictionary) -> void:
	await vermilion_sailor(false)

func _machop(_o: Dictionary) -> void:
	Story.cry("MACHOP")
	await Story.say("VermilionCityMachopText")
	await Story.say("VermilionCityMachopStompingTheLandFlatText")

# ---------------- Vermilion Gym: trash-can switch puzzle
## the 15 cans are numbered down each column (5 columns of 3); the second switch is next to the first
static func trash_neighbours(i: int) -> Array:
	var c := int(i / 3.0)
	var r := i % 3
	var out: Array = []
	if r > 0:
		out.append(i - 1)
	if r < 2:
		out.append(i + 1)
	if c > 0:
		out.append(i - 3)
	if c < 4:
		out.append(i + 3)
	return out

func vermilion_gym_door(open: bool) -> void:
	if Story.mapname() != "VermilionGym":
		return
	for c in GYM_DOOR:
		if open:
			Story.restore_cell(c.x, c.y)
		else:
			Story.set_cell(c.x, c.y, "barrier", false)

func _vermilion_trash(h: Dictionary) -> void:
	var idx := int(h.get("arg", 0))
	if GameState.vermilion_trash.is_empty():
		GameState.vermilion_trash = {"first": (randi() % 256) & 0xe, "second": 0}
	var st: Dictionary = GameState.vermilion_trash
	if Story.flag("EVENT_2ND_LOCK_OPENED"):
		await Story.say("VermilionGymTrashText")
		return
	if not Story.flag("EVENT_1ST_LOCK_OPENED"):
		if idx != int(st["first"]):
			await Story.say("VermilionGymTrashText")
			return
		Story.setf("EVENT_1ST_LOCK_OPENED")
		var near := trash_neighbours(idx)
		st["second"] = near[randi() % near.size()]
		await Story.say("VermilionGymTrashSuccessText1")
		Story.sfx("select")
		return
	if idx == int(st["second"]):
		Story.setf("EVENT_2ND_LOCK_OPENED")
		await Story.say("VermilionGymTrashSuccessText3")
		Story.sfx("door")
		vermilion_gym_door(true)
		return
	Story.clear("EVENT_1ST_LOCK_OPENED")
	st["first"] = (randi() % 256) & 0xe
	await Story.say("VermilionGymTrashFailText")
	Story.sfx("bump")

func _vermilion_gym_enter() -> Callable:
	if not Story.flag("EVENT_2ND_LOCK_OPENED"):
		vermilion_gym_door(false)
	return Callable()

func _surge_guide(_o: Dictionary) -> void:
	await Story.say("VermilionGymGymGuideBeatLTSurgeText" if Story.has_badge("THUNDERBADGE") else "VermilionGymGymGuideChampInMakingText")

func _old_rod(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_OLD_ROD"):
		await Story.say("VermilionOldRodHouseFishingGuruHowAreTheFishBitingText")
		return
	if not await Story.ask("VermilionOldRodHouseFishingGuruDoYouLikeToFishText"):
		await Story.say("VermilionOldRodHouseFishingGuruThatsSoDisappointingText")
		return
	if not await Story.got("OLD_ROD", 1):
		await Story.say("VermilionOldRodHouseFishingGuruNoRoomText")
		return
	Story.setf("EVENT_GOT_OLD_ROD")
	await Story.say(Story.join(["VermilionOldRodHouseFishingGuruTakeThisText", "VermilionOldRodHouseFishingGuruFishingIsAWayOfLifeText"]))

func _pikachu_fan(_o: Dictionary) -> void:
	if Story.flag("EVENT_PIKACHU_FAN_BOAST"):
		await Story.say("PokemonFanClubPikachuFanBetterText")
		Story.clear("EVENT_PIKACHU_FAN_BOAST")
	else:
		await Story.say("PokemonFanClubPikachuFanNormalText")
		Story.setf("EVENT_SEEL_FAN_BOAST")

func _seel_fan(_o: Dictionary) -> void:
	if Story.flag("EVENT_SEEL_FAN_BOAST"):
		await Story.say("PokemonFanClubSeelFanBetterText")
		Story.clear("EVENT_SEEL_FAN_BOAST")
	else:
		await Story.say("PokemonFanClubSeelFanNormalText")
		Story.setf("EVENT_PIKACHU_FAN_BOAST")

func _fan_chairman(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_BIKE_VOUCHER") or Story.bag_has("BICYCLE") or Story.bag_has("BIKE_VOUCHER"):
		await Story.say("PokemonFanClubChairFinalText")
		return
	if not await Story.ask("PokemonFanClubChairmanIntroText"):
		await Story.say("PokemonFanClubNoStoryText")
		return
	await Story.say("PokemonFanClubChairmanStoryText")
	if not await Story.got("BIKE_VOUCHER", 1):
		await Story.say("PokemonFanClubBagFullText")
		return
	await Story.say(Story.join(["PokemonFanClubReceivedBikeVoucherText", "PokemonFanClubExplainBikeVoucherText"]))
	Story.setf("EVENT_GOT_BIKE_VOUCHER")

# ---------------- Vermilion Dock: the S.S. Anne departs
func _ship_cells() -> Array:
	var out: Array = []
	var md := Story.map_data("VermilionDock")
	for y in int(md.get("h", 0)):
		for x in int(md.get("w", 0)):
			var l := Story.cell_label(Vector2i(x, y))
			if l == "deck" or l == "ship_wall":
				out.append(Vector2i(x, y))
	return out

func remove_ship() -> void:
	for c in _ship_cells():
		Story.set_cell(c.x, c.y, "water", false)
	for w in Story.map_data().get("warps", []):
		if w.get("to", "") == "SSAnne1F":  # the gangway no longer leads anywhere
			Story.set_cells([[int(w["x"]), int(w["y"]), null, false]])

func ship_leaves() -> void:
	await wait_warp()
	Story.setf("EVENT_SS_ANNE_LEFT")
	Story.music("surf")
	await Story.wait(60)
	if Story._has_host("ship_departs"):
		await Story.ha("ship_departs")
	else:
		await Story.wait(320)
	remove_ship()
	await Story.wait(60)
	Story.map_music()
	Story.setf("EVENT_STARTED_WALKING_OUT_OF_DOCK")
	await Story.move_player("UU")  # onto the exit mat, then out of the dock
	Story.setf("EVENT_WALKED_OUT_OF_DOCK")
	Story.face(P, "up")
	await Story.take_warp()

func _dock_enter() -> Callable:
	if Story.flag("EVENT_SS_ANNE_LEFT"):
		remove_ship()
		return Callable()
	var p := Story.pcell()
	for w in Story.map_data().get("warps", []):
		if w.get("to", "") == "SSAnne1F" and Story.flag("EVENT_GOT_HM01") and p == Vector2i(int(w["x"]), int(w["y"])):
			return ship_leaves
	return Callable()

# ======================================================================
# S.S. Anne
# ======================================================================
func _ssanne_face(x: int, rival: String) -> void:
	if x == 37:
		Story.face(P, "left")
		Story.face(rival, "right")
	else:
		Story.face(P, "up")
		Story.face(rival, "down")

func ss_anne_rival(x: int) -> void:
	Story.music("rival")
	var rival := Story.show("SSANNE2F_RIVAL", "", Vector2i(36, 4))
	Story.place(rival, 36, 4, "down")
	await Story.move(rival, "DDDD" if x == 37 else "DDD")
	_ssanne_face(x, rival)
	await Story.say("SSAnne2FRivalText")
	var r := await Story.battle("RIVAL2", Story.rival_party(1), {"win_text": Story.fmt(Story.join(["SSAnne2FRivalDefeatedText"])), "lose_text": Story.fmt(Story.join(["SSAnne2FRivalVictoryText"]))})
	if r != "win":
		Story.hide("SSANNE2F_RIVAL", "SSAnne2F")
		return
	_ssanne_face(x, rival)
	await Story.say("SSAnne2FRivalCutMasterText")
	Story.music("rival")
	await Story.move(rival, "DDDD" if x == 37 else "RDDDDD")
	Story.hide("SSANNE2F_RIVAL")
	Story.setf("EVENT_BEAT_SS_ANNE_RIVAL")
	Story.map_music()

func _ssanne2f_step(x: int, y: int) -> Callable:
	if Story.running > 0 or Story.flag("EVENT_BEAT_SS_ANNE_RIVAL") or y != 8 or (x != 36 and x != 37):
		return Callable()
	return ss_anne_rival.bind(x)

func _captain(a: Dictionary) -> void:
	var id: String = a.get("id", "")
	if not Story.flag("EVENT_RUBBED_CAPTAINS_BACK"):
		Story.face(id, "up")  # too seasick to turn around
	if Story.flag("EVENT_GOT_HM01"):
		await Story.say("SSAnneCaptainsRoomCaptainNotSickAnymoreText")
		return
	await Story.say("SSAnneCaptainsRoomRubCaptainsBackText")
	Story.music("heal", true)
	await Story.wait(150)
	Story.map_music()
	Story.setf("EVENT_RUBBED_CAPTAINS_BACK")
	await Story.say("SSAnneCaptainsRoomCaptainIFeelMuchBetterText")
	if await Story.got("HM_CUT", 1, "SSAnneCaptainsRoomCaptainReceivedHM01Text"):
		Story.setf("EVENT_GOT_HM01")
	else:
		await Story.say("SSAnneCaptainsRoomCaptainHM01NoRoomText")
		Story.face(id, "up")

func _gentleman3(_o: Dictionary) -> void:
	await Story.say("SSAnne2FRoomsGentleman3Text")
	await Story.dex_page("SNORLAX")
	Story.dex_seen("SNORLAX")

func _cook7(_o: Dictionary) -> void:
	await Story.say("SSAnneKitchenCook7MainCourseIsText")
	var r := randi() % 256
	await Story.say("SSAnneKitchenCook7SalmonDuSaladText" if r & 0x80 else ("SSAnneKitchenCook7EelsAuBarbecueText" if r & 0x10 else "SSAnneKitchenCook7PrimeBeefSteakText"))

# ======================================================================
# Route 11 gate
# ======================================================================
func _r11_left_binoculars(_s: Dictionary) -> void:
	if Story.pdir() != "up":
		return
	await Story.say("Route11Gate2FLeftBinocularsNoSnorlaxText" if Story.flag("EVENT_BEAT_ROUTE12_SNORLAX") else "Route11Gate2FLeftBinocularsSnorlaxText")

func _r11_right_binoculars(_s: Dictionary) -> void:
	if Story.pdir() == "up":
		await Story.say("Route11Gate2FRightBinocularsText")
