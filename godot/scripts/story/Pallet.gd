extends RefCounted
## Port of upstream src/scripts/pallet.js: Pallet Town, Oak's Lab, Route 1,
## Viridian City (+ Mart parcel) and the Route 22 rival.

const P := "PLAYER"
const STARTERS := {"OAKSLAB_CHARMANDER_POKE_BALL": "CHARMANDER", "OAKSLAB_SQUIRTLE_POKE_BALL": "SQUIRTLE", "OAKSLAB_BULBASAUR_POKE_BALL": "BULBASAUR"}
## rival picks the starter that beats yours: [rival ball object, rival species, party offset]
const RIVAL_PICK := {"CHARMANDER": ["OAKSLAB_SQUIRTLE_POKE_BALL", "SQUIRTLE", 1], "SQUIRTLE": ["OAKSLAB_BULBASAUR_POKE_BALL", "BULBASAUR", 2],
	"BULBASAUR": ["OAKSLAB_CHARMANDER_POKE_BALL", "CHARMANDER", 3]}

func register() -> void:
	Story.def_map("RedsHouse1F", {
		"talk": {"REDSHOUSE1F_MOM": _mom},
		"sign": {"TEXT_REDSHOUSE1F_TV": _tv},
	})
	Story.def_map("PalletTown", {"step": _pallet_step, "talk": {"PALLETTOWN_OAK": _pallet_oak}})
	Story.def_map("BluesHouse", {
		"enter": _blues_enter,
		"talk": {"BLUESHOUSE_DAISY1": _daisy1, "BLUESHOUSE_DAISY2": _say.bind("BluesHouseDaisyWalkingText"),
			"BLUESHOUSE_TOWN_MAP": _say.bind("BluesHouseTownMapText")},
	})
	Story.def_map("OaksLab", {
		"enter": _lab_enter, "step": _lab_step,
		"talk": {"OAKSLAB_CHARMANDER_POKE_BALL": _pick_ball, "OAKSLAB_SQUIRTLE_POKE_BALL": _pick_ball, "OAKSLAB_BULBASAUR_POKE_BALL": _pick_ball,
			"OAKSLAB_OAK1": _oak1, "OAKSLAB_RIVAL": _lab_rival,
			"OAKSLAB_POKEDEX1": _say.bind("OaksLabPokedexText"), "OAKSLAB_POKEDEX2": _say.bind("OaksLabPokedexText")},
	})
	Story.def_map("Route1", {"talk": {"ROUTE1_YOUNGSTER1": _route1_youngster}})
	Story.def_map("ViridianCity", {
		"enter": _viridian_enter, "step": _viridian_step,
		"talk": {
			"VIRIDIANCITY_GAMBLER1": _viridian_gambler, "VIRIDIANCITY_YOUNGSTER2": _viridian_youngster2,
			"VIRIDIANCITY_GIRL": _viridian_girl, "VIRIDIANCITY_OLD_MAN_SLEEPY": _say.bind("ViridianCityOldManSleepyPrivatePropertyText"),
			"VIRIDIANCITY_FISHER": _viridian_fisher, "VIRIDIANCITY_OLD_MAN": _viridian_old_man,
		},
		"sign": {"TEXT_VIRIDIANCITY_GYM_SIGN": _say.bind("ViridianCityGymSignText")},
	})
	Story.def_map("ViridianMart", {"enter": _mart_enter, "talk": {"VIRIDIANMART_CLERK": _mart_clerk}})
	Story.def_map("Route22", {"step": _route22_step})

## talk/sign handler that just says a label: _say.bind(label) (Callable.bind appends after the obj arg)
func _say(_o: Variant, label: String) -> void:
	await Story.say(label)

# ---------------------------------------------------------------- Red's house
func _mom(_o: Dictionary) -> void:
	if GameState.party.is_empty():
		await Story.say("RedsHouse1FMomWakeUpText")
		return
	await Story.say("RedsHouse1FMomYouShouldRestText")
	await Story.fade_out(12)
	Story.music("heal", true)
	Story.heal_all()
	await Story.wait(60)
	await Story.fade_in(12)
	Story.map_music()
	await Story.say("RedsHouse1FMomLookingGreatText")

func _tv(_s: Dictionary) -> void:
	if Story.pdir() == "up":
		await Story.say("RedsHouse1FTVStandByMeMovieText")
	else:
		await Story.say("RedsHouse1FTVWrongSideText")

# ---------------------------------------------------------------- Pallet Town
func _pallet_step(_x: int, y: int) -> Callable:
	if y != 1 or Story.flag("EVENT_FOLLOWED_OAK_INTO_LAB"):
		return Callable()
	return _oak_stops_you

func _oak_stops_you() -> void:
	Story.music("oak")
	Story.face(P, "down")
	await Story.say("PalletTownOakHeyWaitDontGoOutText")
	await Story.emote(P, "!", 30)
	var oak := Story.show("PALLETTOWN_OAK")
	# Oak walks to just below the player
	var p := Story.pcell()
	await Story.move(oak, Story.path_to(oak, p.x, p.y + 1))
	Story.face(oak, "up")
	Story.face(P, "down")
	await Story.say("PalletTownOakItsUnsafeText")
	# follow Oak to the lab: Oak walks round to the lab door, the player one step behind him
	var door := Vector2i(12, 11)
	var route := Story.path_to(oak, door.x, door.y + 1)
	var ppath := "D" + route.substr(0, route.length() - 1)
	for i in route.length():
		await Story.move_together([[oak, route[i]], [P, ppath[i]]])
	# Oak goes in first, then the player steps up to the door behind him
	await Story.move(oak, "U")
	Story.hide("PALLETTOWN_OAK")
	Story.setf("EVENT_FOLLOWED_OAK_INTO_LAB")
	await Story.move_player(Story.path_to(P, door.x, door.y + 1) + "U")
	Story.setf("EVENT_OAK_WALKING_INTO_LAB")
	await Story.warp("OaksLab", 5, 11, "up")

func _pallet_oak(_o: Dictionary) -> void:
	await Story.say("PalletTownOakItsUnsafeText")

# ---------------------------------------------------------------- Blue's house
func _blues_enter() -> Callable:
	if Story.flag("EVENT_GOT_TOWN_MAP"):
		Story.hide("BLUESHOUSE_TOWN_MAP")
	if Story.flag("EVENT_GOT_TOWN_MAP") and Story.flag("EVENT_GOT_POKEBALLS_FROM_OAK"):
		Story.hide("BLUESHOUSE_DAISY1")
		Story.show("BLUESHOUSE_DAISY2")
	return Callable()

func _daisy1(_o: Dictionary) -> void:
	if not Story.flag("EVENT_GOT_POKEDEX"):
		await Story.say("BluesHouseDaisyRivalAtLabText")
		return
	if not Story.flag("EVENT_GOT_TOWN_MAP"):
		await Story.say("BluesHouseDaisyOfferMapText")
		if await Story.give("TOWN_MAP", 1, "GotMapText" if Story.has_text("GotMapText") else ""):
			Story.setf("EVENT_GOT_TOWN_MAP")
			Story.hide("BLUESHOUSE_TOWN_MAP")
		return
	await Story.say("BluesHouseDaisyUseMapText")

# ---------------------------------------------------------------- Oak's Lab
func _rival_leaves(rival: String) -> void:
	var p := Story.pcell()
	var rc := Story.cell(rival)
	var path := ("R" if rc.x < 5 else "L") + "DDDDDD" if rc.x == p.x else "DDDDDD"
	await Story.move(rival, "DDDDDDD" if path.substr(0, 1) == "D" else path)
	Story.hide("OAKSLAB_RIVAL")

func _lab_enter() -> Callable:
	# a starter pick that crashed part-way: put the balls back so the player can choose again
	if Story.flag("EVENT_OAK_ASKED_TO_CHOOSE_MON") and not Story.flag("EVENT_GOT_STARTER") and GameState.party.is_empty():
		for id in STARTERS:
			Story.show(id)
	if Story.flag("EVENT_OAK_WALKING_INTO_LAB"):
		return _oak_walks_in
	if not Story.flag("EVENT_FOLLOWED_OAK_INTO_LAB_2"):
		return Callable()
	# Oak's position: at the desk once he's back in the lab
	if not Story.is_shown("OAKSLAB_OAK1") and Story.flag("EVENT_FOLLOWED_OAK_INTO_LAB_2"):
		Story.show("OAKSLAB_OAK1")
	if Story.flag("EVENT_GOT_POKEDEX"):
		Story.hide("OAKSLAB_POKEDEX1")
		Story.hide("OAKSLAB_POKEDEX2")
	return Callable()

func _oak_walks_in() -> void:
	Story.clear("EVENT_OAK_WALKING_INTO_LAB")
	# Oak walks from the door up to his desk, the player follows him in
	var oak := Story.show("OAKSLAB_OAK2", "", Vector2i(5, 10))
	await Story.move(oak, "UUUUUUUU")
	Story.hide("OAKSLAB_OAK2")
	Story.show("OAKSLAB_OAK1")
	await Story.move_player("UUUUUUU")
	Story.setf("EVENT_FOLLOWED_OAK_INTO_LAB_2")
	await Story.say("OaksLabRivalFedUpWithWaitingText")
	await Story.say("OaksLabOakChooseMonText")
	await Story.say("OaksLabRivalWhatAboutMeText")
	await Story.say("OaksLabOakBePatientText")
	Story.setf("EVENT_OAK_ASKED_TO_CHOOSE_MON")
	Story.music("oak_lab")

func _lab_step(_x: int, y: int) -> Callable:
	# Don't leave before choosing
	if Story.flag("EVENT_OAK_ASKED_TO_CHOOSE_MON") and not Story.flag("EVENT_GOT_STARTER") and y == 6:
		return _dont_go_away
	# Rival challenges after the starters are chosen
	if Story.flag("EVENT_GOT_STARTER") and not Story.flag("EVENT_BATTLED_RIVAL_IN_OAKS_LAB") and y == 6:
		return _lab_rival_battle
	return Callable()

func _dont_go_away() -> void:
	if Story.actor("OAKSLAB_OAK1"):
		Story.face("OAKSLAB_OAK1", "down")
	await Story.say("OaksLabOakDontGoAwayYetText")
	await Story.move_player("U")

func _lab_rival_battle() -> void:
	var rival := "OAKSLAB_RIVAL"
	var p := Story.pcell()
	Story.music("rival")
	await Story.say("OaksLabRivalIllTakeYouOnText")
	await Story.move(rival, Story.path_to(rival, p.x, p.y - 1))
	Story.face(rival, "down")
	Story.face(P, "up")
	var pick: Array = RIVAL_PICK.get(GameState.starter, RIVAL_PICK["CHARMANDER"])
	await Story.battle("RIVAL1", int(pick[2]), {"no_blackout": true,
		"win_text": Story.fmt(Story.t("OaksLabRivalIPickedTheWrongPokemonText")), "lose_text": Story.fmt(Story.t("OaksLabRivalAmIGreatOrWhatText"))})
	Story.heal_all()
	Story.setf("EVENT_BATTLED_RIVAL_IN_OAKS_LAB")
	Story.music("rival")
	await Story.say("OaksLabRivalSmellYouLaterText")
	await _rival_leaves(rival)
	Story.music("oak_lab")

func _oak1(_o: Dictionary) -> void:
	if Story.bag_has("OAKS_PARCEL"):
		await Story.say("OaksLabOak1DeliverParcelText")
		Story.bag_remove("OAKS_PARCEL", 1)
		await Story.say("OaksLabOak1ParcelThanksText")
		Story.setf("EVENT_OAK_GOT_PARCEL")
		# rival arrives
		var rival := Story.show("OAKSLAB_RIVAL", "", Vector2i(4, 11))
		Story.music("rival")
		await Story.say("OaksLabRivalGrampsText")
		await Story.move(rival, "UUUUUUUU")
		Story.face(rival, "up")
		await Story.say("OaksLabRivalWhatDidYouCallMeForText")
		await Story.say("OaksLabOakIHaveARequestText")
		await Story.say("OaksLabOakMyInventionPokedexText")
		Story.hide("OAKSLAB_POKEDEX1")
		Story.hide("OAKSLAB_POKEDEX2")
		Story.sfx("get_key")
		await Story.say("OaksLabOakGotPokedexText")
		Story.setf("EVENT_GOT_POKEDEX")
		await Story.say("OaksLabOakThatWasMyDreamText")
		await Story.say("OaksLabRivalLeaveItAllToMeText")
		await Story.move(rival, "DDDDDDDD")
		Story.hide("OAKSLAB_RIVAL")
		Story.setf("EVENT_1ST_ROUTE22_RIVAL_BATTLE")
		Story.setf("EVENT_ROUTE22_RIVAL_WANTS_BATTLE")
		Story.show("ROUTE22_RIVAL1", "Route22")
		Story.music("oak_lab")
		return
	if Story.flag("EVENT_GOT_POKEDEX"):
		if not Story.flag("EVENT_GOT_POKEBALLS_FROM_OAK") and not Story.bag_has("POKE_BALL") and Story.flag("EVENT_BEAT_ROUTE22_RIVAL_1ST_BATTLE"):
			await Story.say("OaksLabOak1PokemonAroundTheWorldText")
			Story.setf("EVENT_GOT_POKEBALLS_FROM_OAK")
			await Story.give("POKE_BALL", 5, Story.t("OaksLabOak1ReceivedPokeballsText"))
			await Story.say("OaksLabGivePokeballsExplanationText")
			return
		await Story.say("OaksLabOak1ComeSeeMeSometimesText" if randf() < 0.5 else "OaksLabOak1HowIsYourPokedexComingText")
		await oak_rating(false)
		return
	if not Story.flag("EVENT_GOT_STARTER"):
		await Story.say("OaksLabOak1WhichPokemonDoYouWantText")
		return
	await Story.say("OaksLabOak1RaiseYourYoungPokemonText" if Story.flag("EVENT_BATTLED_RIVAL_IN_OAKS_LAB") else "OaksLabOak1YourPokemonCanFightText")

## pc.js G.oakRating
static func oak_rating(_via_pc: bool) -> void:
	var seen := GameState.seen_species.size()
	var own := GameState.caught_species.size()
	await Story.say("POKéDEX completion is:\f" + str(seen) + " POKéMON seen\f" + str(own) + " POKéMON owned\fPROF.OAK's rating:")
	var tiers := [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 999]
	var fallback := ["You still have lots to do. Look for POKéMON in grassy areas!", "You're on the right track! Get a FLASH HM from my AIDE!",
		"You still need more POKéMON! Try to catch other species!", "Good, you're trying hard! Get an ITEMFINDER from my AIDE!",
		"Looking good! Go find my AIDE when you get 50!", "You finally got at least 50 species! Be sure to get EXP.ALL from my AIDE!",
		"Ho! This is getting even better!", "Very good! Go fish for some marine POKéMON!", "Wonderful! Do you like to collect things?",
		"I'm impressed! It must have been difficult to do!", "You finally got at least 100 species! I can't believe how good you are!",
		"You even have the evolved forms of POKéMON! Super!", "Excellent! Trade with friends to get some more!",
		"Outstanding! You've become a real pro at this!", "I have nothing left to say! You're the authority now!",
		"Your POKéDEX is entirely complete! Congratulations!"]
	var i := 15
	for k in tiers.size():
		if own < tiers[k]:
			i = k
			break
	await Story.say(Story.tf("OakRating%d" % i, fallback[i]))

func _lab_rival(_o: Dictionary) -> void:
	if not Story.flag("EVENT_FOLLOWED_OAK_INTO_LAB_2"):
		await Story.say("OaksLabRivalGrampsIsntAroundText")
		return
	if not Story.flag("EVENT_GOT_STARTER"):
		await Story.say("OaksLabRivalGoAheadAndChooseText")
		return
	await Story.say("OaksLabRivalMyPokemonLooksStrongerText")

func _pick_ball(ball: Dictionary) -> void:
	var id: String = ball.get("id", "")
	var sp: String = STARTERS[id]
	if not Story.flag("EVENT_OAK_ASKED_TO_CHOOSE_MON"):
		await Story.say("OaksLabThoseArePokeBallsText")
		return
	if Story.flag("EVENT_GOT_STARTER"):
		await Story.say("OaksLabLastMonText")
		return
	# show the Pokémon inside
	var pic := Story.mon_popup(sp, Rect2i(110, 20, 100, 90))
	Story.cry(sp)
	var q: String = {"CHARMANDER": "OaksLabYouWantCharmanderText", "SQUIRTLE": "OaksLabYouWantSquirtleText", "BULBASAUR": "OaksLabYouWantBulbasaurText"}[sp]
	var yes := await Story.ask(q)
	Story.close_box(pic)
	if not yes:
		return
	Story.hide(id)
	GameState.starter = sp
	await Story.say("OaksLabMonEnergeticText")
	var m := Story.new_mon(sp, 5)
	Story.sfx("get_mon")
	Story.setvar("wcd6d", sp)
	Story.setvar("wStringBuffer", Story.species_name(sp))
	await Story.say(GameState.player_name + " received a " + Story.species_name(sp) + "!")
	Story.dex_caught(sp)
	await Story.receive_mon(m)
	Story.setf("EVENT_GOT_STARTER")
	# rival takes his
	var pick: Array = RIVAL_PICK[sp]
	var rb: String = pick[0]
	var rsp: String = pick[1]
	var rival := "OAKSLAB_RIVAL"
	var bc := Story.cell(rb)
	await Story.move(rival, Story.path_to(rival, bc.x, bc.y + 1))
	Story.face(rival, "up")
	await Story.say("OaksLabRivalIllTakeThisOneText")
	Story.hide(rb)
	Story.setvar("wRivalStarter", Story.species_name(rsp))
	Story.sfx("get_mon")
	var re := RegEx.create_from_string("\\{\\w+\\}")
	var line := re.sub(Story.fmt(Story.t("OaksLabRivalReceivedMonText")), Story.species_name(rsp), true)
	await Story.say(line if line != "" else GameState.rival_name + " received a " + Story.species_name(rsp) + "!")

# ---------------------------------------------------------------- Route 1
func _route1_youngster(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_POTION_SAMPLE"):
		await Story.say("Route1Youngster1AlsoGotPokeballsText")
		return
	await Story.say("Route1Youngster1MartSampleText")
	if await Story.give("POTION", 1, Story.t("Route1Youngster1GotPotionText")):
		Story.setf("EVENT_GOT_POTION_SAMPLE")
		await Story.say("Route1Youngster1AlsoGotPokeballsText")
	else:
		await Story.say("Route1Youngster1NoRoomText")

# ---------------------------------------------------------------- Viridian City
func _viridian_enter() -> Callable:
	if Story.flag("EVENT_GOT_POKEDEX"):
		Story.hide("VIRIDIANCITY_OLD_MAN_SLEEPY")
		Story.show("VIRIDIANCITY_OLD_MAN")
	return Callable()

func _viridian_step(x: int, y: int) -> Callable:
	if not Story.flag("EVENT_GOT_POKEDEX") and x == 19 and y == 9:
		return _say_push.bind("ViridianCityOldManSleepyPrivatePropertyText", "D")
	if Story.badge_count() < 7 and x == 32 and y == 8:
		return _say_push.bind("ViridianCityGymLockedText", "D")
	return Callable()

func _say_push(label: String, push: String) -> void:
	await Story.say(label)
	await Story.move_player(push)

func _viridian_gambler(_o: Dictionary) -> void:
	await Story.say("ViridianCityGambler1GymLeaderReturnedText" if Story.badge_count() >= 7 else "ViridianCityGambler1GymAlwaysClosedText")

func _viridian_youngster2(_o: Dictionary) -> void:
	if await Story.ask("ViridianCityYoungster2YouWantToKnowAboutText"):
		await Story.say("ViridianCityYoungster2CaterpieAndWeedleDescriptionText")
	else:
		await Story.say("ViridianCityYoungster2OkThenText")

func _viridian_girl(_o: Dictionary) -> void:
	await Story.say("ViridianCityGirlWhenIGoShopText" if Story.flag("EVENT_GOT_POKEDEX") else "ViridianCityGirlHasntHadHisCoffeeYetText")

func _viridian_fisher(_o: Dictionary) -> void:
	if Story.flag("EVENT_GOT_TM42"):
		await Story.say("ViridianCityFisherTM42ExplanationText")
		return
	await Story.say("ViridianCityFisherYouCanHaveThisText")
	if await Story.give("TM_DREAM_EATER", 1, Story.t("ViridianCityFisherReceivedTM42Text")):
		Story.setf("EVENT_GOT_TM42")
	else:
		await Story.say("ViridianCityFisherTM42NoRoomText")

func _viridian_old_man(_o: Dictionary) -> void:
	await Story.say("ViridianCityOldManHadMyCoffeeNowText")
	var hurry := await Story.ask("ViridianCityOldManKnowHowToCatchPokemonText")
	if hurry:
		await Story.say("ViridianCityOldManTimeIsMoneyText")
		return
	# catching demonstration (a scripted battle)
	await catch_demo()
	await Story.say("ViridianCityOldManYouNeedToWeakenTheTargetText")

## G.catchDemo: the old man's scripted WEEDLE catch. Runs as a battle with
## enc.demo = true (the battle scene shows the old man throwing a POKé BALL).
static func catch_demo() -> void:
	var saved_name := GameState.player_name
	GameState.player_name = "OLD MAN"
	await Story.wild_battle("WEEDLE", 5, {"demo": true, "no_blackout": true, "trainer_name": "OLD MAN"})
	GameState.player_name = saved_name

func _mart_enter() -> Callable:
	if Story.flag("EVENT_OAK_GOT_PARCEL") or Story.bag_has("OAKS_PARCEL"):
		return Callable()
	return _parcel_quest

func _parcel_quest() -> void:
	await Story.wait(10)
	await Story.say("ViridianMartClerkYouCameFromPalletTownText")
	await Story.move_player("UUL")
	Story.face(P, "left")
	await Story.say("ViridianMartClerkParcelQuestText")
	Story.bag_add("OAKS_PARCEL", 1)
	Story.setf("EVENT_GOT_OAKS_PARCEL")

func _mart_clerk(_o: Dictionary) -> void:
	if not Story.flag("EVENT_OAK_GOT_PARCEL"):
		await Story.say("ViridianMartClerkSayHiToOakText")
		return
	await Story.mart(Story.pokedata.get("marts", {}).get("ViridianMartClerkText", []))

# ---------------------------------------------------------------- Route 22 rival
func _route22_step(x: int, y: int) -> Callable:
	if x != 29 or (y != 4 and y != 5):
		return Callable()
	# the first battle only while EVENT_1ST_ROUTE22_RIVAL_BATTLE is set (the BOULDERBADGE clears it)
	var first := Story.flag("EVENT_1ST_ROUTE22_RIVAL_BATTLE") and Story.flag("EVENT_ROUTE22_RIVAL_WANTS_BATTLE") and not Story.flag("EVENT_BEAT_ROUTE22_RIVAL_1ST_BATTLE")
	var second := Story.flag("EVENT_2ND_ROUTE22_RIVAL_BATTLE") and not Story.flag("EVENT_BEAT_ROUTE22_RIVAL_2ND_BATTLE")
	if not first and not second:
		return Callable()
	return _route22_rival.bind(first)

func _route22_rival(first: bool) -> void:
	var id := "ROUTE22_RIVAL1" if first else "ROUTE22_RIVAL2"
	var rival := Story.show(id)
	var p := Story.pcell()
	Story.music("rival")
	await Story.emote(P, "!", 30)
	await Story.move(rival, Story.path_to(rival, p.x - 1, p.y))
	Story.face(rival, "right")
	Story.face(P, "left")
	await Story.say("Route22RivalBeforeBattleText1" if first else "Route22RivalBeforeBattleText2")
	# only the Oak's Lab battle spares the player a blackout; losing here blacks out and the rival waits again
	var r := await Story.battle("RIVAL1" if first else "RIVAL2", Story.rival_party(4) if first else Story.rival_party(10), {
		"win_text": Story.fmt(Story.t("Route22Rival1DefeatedText" if first else "Route22Rival2DefeatedText")),
		"lose_text": Story.fmt(Story.t("Route22Rival1VictoryText" if first else "Route22Rival2VictoryText"))})
	if r == "lose":
		Story.hide(id, "Route22")
		return
	await Story.say("Route22RivalAfterBattleText1" if first else "Route22RivalAfterBattleText2")
	# RIVAL1 heads past the player into the open ground to the south-east; RIVAL2 walks back west
	await Story.move(rival, Story.path_to(rival, 30, 10) if first else "LLLLLLLL")
	Story.hide(id)
	Story.setf("EVENT_BEAT_ROUTE22_RIVAL_1ST_BATTLE" if first else "EVENT_BEAT_ROUTE22_RIVAL_2ND_BATTLE")
	Story.map_music()
