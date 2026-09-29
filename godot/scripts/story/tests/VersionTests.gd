class_name VersionTests
extends RefCounted
## RED / BLUE / YELLOW checks for TestSuite: the three versions load, their wild tables, trainer teams, trades, prizes and
## NPC layouts differ the way pokered / pokeyellow say, every one of the 151 species can be obtained in some version,
## and the YELLOW opening (PIKACHU, EEVEE rival, friendship gifts, JESSIE & JAMES) runs against the fake Overworld.
## The expected values below come from the pret disassemblies (data/wild, data/trainers/parties.asm, scripts/*.asm);
## data/versions.json is re-generated from the same files by pipeline/scripts/extract_versions.py.

const FakeHost := preload("res://scripts/story/tests/StoryFakeHost.gd")
const FakeUI := preload("res://scripts/story/tests/StoryFakeUI.gd")

## Wild POKeMON that only one of RED / BLUE has (pokered data/wild, IF DEF(_RED) / IF DEF(_BLUE) blocks). Entries the
## games also hand out some other way (fossils, gifts) are not listed.
const RED_ONLY := ["ARBOK", "EKANS", "ELECTABUZZ", "GLOOM", "GROWLITHE", "MANKEY", "ODDISH", "SCYTHER"]
const BLUE_ONLY := ["BELLSPROUT", "MAGMAR", "MEOWTH", "PINSIR", "SANDSHREW", "SANDSLASH", "VULPIX", "WEEPINBELL"]

## Ways to get a POKeMON that are not random wild encounters (RED, BLUE and YELLOW combined).
const GIFTS := ["BULBASAUR", "CHARMANDER", "SQUIRTLE", "PIKACHU", "EEVEE", "LAPRAS", "HITMONLEE", "HITMONCHAN", "MAGIKARP",
	"KABUTO", "OMANYTE", "AERODACTYL", "DRATINI", "PORYGON", "ABRA", "CLEFAIRY", "NIDORINA", "NIDORINO", "PINSIR", "SCYTHER", "VULPIX",
	"WIGGLYTUFF", "MR_MIME", "SNORLAX", "ZAPDOS", "MOLTRES", "ARTICUNO", "MEWTWO"]

## JSON numbers load as floats: turn whole ones back into ints so `==` against literals works on nested arrays.
static func _i(v: Variant) -> Variant:
	if v is Array:
		return (v as Array).map(func(x): return _i(x))
	if v is float and floorf(v) == v:
		return int(v)
	return v

static func run(suite: TestSuite) -> void:
	_load(suite)
	_wild(suite)
	_species_obtainable(suite)
	_yellow_data(suite)
	_trades_prizes_marts(suite)
	_rival_and_buddy(suite)
	_trainer_objects(suite)
	_save(suite)
	_yellow_story(suite)
	GameState.set_version("RED")

# ---------------------------------------------------------------- loading
static func _load(t: TestSuite) -> void:
	t.check(GameData.VERSIONS == ["RED", "BLUE", "YELLOW"], "three versions: RED, BLUE, YELLOW")
	t.check(not GameData.versions_data.is_empty() and GameData.versions_data.has("wild"), "data/versions.json loaded")
	for v in GameData.VERSIONS:
		GameState.set_version(v)
		t.check(GameData.active_version == v and GameState.version == v, "%s: the version switch applies" % v)
		t.check(GameData.species.size() == 151 and GameData.maps.size() == 223, "%s: 151 species and 223 maps still loaded" % v)
		t.check(GameData.wild.size() == 248, "%s: a wild entry for every map id (%d)" % [v, GameData.wild.size()])
		t.check(GameData.parties.has("BROCK") and GameData.parties.has("RIVAL1"), "%s: trainer teams present" % v)
	GameState.set_version("RED")
	t.check(GameData.wild == (GameData._pristine["wild"] as Dictionary), "RED wild tables equal pokedata.json (the upstream Red data)")
	t.check(bool(GameData.versions_data.get("redPartiesMatchBase", false)), "pokered's trainer parties equal the base Red parties")
	# switching back and forth is lossless
	GameState.set_version("YELLOW")
	GameState.set_version("RED")
	t.check(GameData.get_species("KADABRA").get("moves1") == ["TELEPORT", "CONFUSION", "DISABLE"], "back to RED restores species data")
	t.check(_i(GameData.parties["BROCK"][0][0]) == [12, "GEODUDE"], "back to RED restores BROCK's team (Lv12 GEODUDE)")

static func _species_in(v: String, with_rods := true) -> Dictionary:
	var out := {}
	var wild: Dictionary = GameData.versions_data["wild"][v]
	for m in wild.keys():
		for kind in ["grass", "water"]:
			for e in wild[m][kind]["mons"]:
				out[str(e[1])] = true
	if with_rods:
		for e in GameData.versions_data["goodRod"][v]:
			out[str(e[1])] = true
		for m in GameData.versions_data["superRod"][v].keys():
			for e in GameData.versions_data["superRod"][v][m]:
				out[str(e[1])] = true
	return out

static func _wild(t: TestSuite) -> void:
	var red := _species_in("RED")
	var blue := _species_in("BLUE")
	var yellow := _species_in("YELLOW")
	var red_only: Array = []
	var blue_only: Array = []
	for sp in red.keys():
		if not blue.has(sp):
			red_only.append(sp)
	for sp in blue.keys():
		if not red.has(sp):
			blue_only.append(sp)
	red_only.sort()
	blue_only.sort()
	t.check(red_only == RED_ONLY, "wild POKeMON only in RED == the known exclusives (%s)" % str(red_only))
	t.check(blue_only == BLUE_ONLY, "wild POKeMON only in BLUE == the known exclusives (%s)" % str(blue_only))
	for sp in ["EKANS", "ODDISH", "MANKEY", "GROWLITHE", "SCYTHER", "ELECTABUZZ"]:
		t.check(red.has(sp) and not blue.has(sp), "wild: %s only in RED, not BLUE" % sp)
	for sp in ["SANDSHREW", "VULPIX", "MEOWTH", "BELLSPROUT", "PINSIR", "MAGMAR"]:
		t.check(blue.has(sp) and not red.has(sp), "wild: %s only in BLUE, not RED" % sp)
	# Route 2: RED has WEEDLE, BLUE has CATERPIE in the slots that differ
	var r2r: Array = GameData.versions_data["wild"]["RED"]["ROUTE_2"]["grass"]["mons"]
	var r2b: Array = GameData.versions_data["wild"]["BLUE"]["ROUTE_2"]["grass"]["mons"]
	t.check(r2r.any(func(e): return e[1] == "WEEDLE") and not r2r.any(func(e): return e[1] == "CATERPIE"), "Route 2 (RED): WEEDLE slots")
	t.check(r2b.any(func(e): return e[1] == "CATERPIE") and not r2b.any(func(e): return e[1] == "WEEDLE"), "Route 2 (BLUE): CATERPIE slots")
	# YELLOW has its own tables: NIDORAN on Route 2, PIKACHU in Viridian Forest, no version exclusives beyond that
	var r2y: Array = GameData.versions_data["wild"]["YELLOW"]["ROUTE_2"]["grass"]["mons"]
	t.check(r2y.any(func(e): return e[1] == "NIDORAN_M") and r2y.any(func(e): return e[1] == "NIDORAN_F"), "Route 2 (YELLOW): NIDORAN_M / NIDORAN_F")
	var vfy: Array = GameData.versions_data["wild"]["YELLOW"]["VIRIDIAN_FOREST"]["grass"]["mons"]
	t.check(vfy.any(func(e): return e[1] == "PIDGEOTTO") and not vfy.any(func(e): return e[1] == "WEEDLE"), "Viridian Forest (YELLOW): PIDGEOTTO, no WEEDLE")
	t.check(not yellow.has("EKANS") and not yellow.has("ELECTABUZZ") and yellow.has("PINSIR"), "YELLOW: no EKANS / ELECTABUZZ in the wild, PINSIR yes")
	# every version: 10 slots per populated table, rates 1..255, levels 2..70
	for v in GameData.VERSIONS:
		var bad := 0
		var n := 0
		for m in GameData.versions_data["wild"][v].keys():
			for kind in ["grass", "water"]:
				var tb: Dictionary = GameData.versions_data["wild"][v][m][kind]
				if int(tb["rate"]) == 0:
					continue
				n += 1
				if tb["mons"].size() != 10 or int(tb["rate"]) > 255:
					bad += 1
				for e in tb["mons"]:
					if int(e[0]) < 2 or int(e[0]) > 70 or not GameData.species.has(str(e[1])):
						bad += 1
		t.check(n > 50 and bad == 0, "%s: %d wild tables well-formed (10 slots, valid species/levels)" % [v, n])
	# the EncounterSystem rolls from the active version's table
	GameState.set_version("YELLOW")
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	var got := {}
	for i in 400:
		var e := EncounterSystem.roll("Route2", false, rng)
		if not e.is_empty():
			got[e["species"]] = true
	t.check(got.has("NIDORAN_M") or got.has("NIDORAN_F"), "EncounterSystem (YELLOW Route 2) rolls NIDORAN")
	GameState.set_version("BLUE")
	got = {}
	for i in 400:
		var e2 := EncounterSystem.roll("Route2", false, rng)
		if not e2.is_empty():
			got[e2["species"]] = true
	t.check(got.has("CATERPIE") and not got.has("WEEDLE"), "EncounterSystem (BLUE Route 2) rolls CATERPIE, never WEEDLE")
	GameState.set_version("RED")

# ---------------------------------------------------------------- all 151 obtainable
static func _species_obtainable(t: TestSuite) -> void:
	var have := {}
	for v in GameData.VERSIONS:
		for sp in _species_in(v).keys():
			have[sp] = true
		for tr in GameData.versions_data["trades"][v]:
			if tr["get"] != "MEW":   # Yellow's unused 'BART' trade entry is never offered by an NPC
				have[str(tr["get"])] = true
		for grp in GameData.versions_data["prizes"][v]:
			for e in grp:
				if GameData.species.has(str(e[0])):
					have[str(e[0])] = true
	for sp in GIFTS:
		have[sp] = true
	# static map encounters (Snorlax, the legendary birds, MEWTWO, Voltorb / Electrode items ...)
	for m in GameData.maps.keys():
		for o in GameData.maps[m].get("objs", []):
			if o.has("mon"):
				have[str(o["mon"].get("species", ""))] = true
	# evolution closure over every version's evolution lines
	var changed := true
	while changed:
		changed = false
		for sp in have.keys().duplicate():
			for e in GameData.species[sp].get("evos", []):
				if not have.has(str(e["to"])):
					have[str(e["to"])] = true
					changed = true
	var missing: Array = []
	for sp in GameData.species.keys():
		if not have.has(sp):
			missing.append(sp)
	# MEW is the one POKeMON no cartridge hands out (Nintendo events / glitches only): documented in docs/CONTENT_AUDIT.md
	t.check(missing == ["MEW"], "all 151 species but event-only MEW are obtainable in at least one version (missing: %s)" % str(missing))
	# and per version: nothing exclusive to another version's wild tables is required to finish that version's dex,
	# because the 3 ways to complete it are trades + the other version's exclusives via trade
	t.check(have.size() >= 150, "obtainable set covers the Pokedex (%d, MEW aside)" % have.size())

# ---------------------------------------------------------------- YELLOW data
static func _team(cls: String, n: int = 1) -> Array:
	var out: Array = []
	for e in GameData.versions_data["parties"]["YELLOW"][cls][n - 1]:
		out.append(e[1])
	return out

static func _yellow_data(t: TestSuite) -> void:
	t.check(_team("BROCK") == ["GEODUDE", "ONIX"], "YELLOW BROCK: GEODUDE, ONIX")
	t.check(_i(GameData.versions_data["parties"]["YELLOW"]["BROCK"][0]) == [[10, "GEODUDE"], [12, "ONIX"]], "YELLOW BROCK levels 10 / 12")
	t.check(_team("MISTY") == ["STARYU", "STARMIE"], "YELLOW MISTY: STARYU, STARMIE")
	t.check(_team("LT_SURGE") == ["RAICHU"], "YELLOW LT.SURGE: RAICHU")
	t.check(_team("ERIKA") == ["TANGELA", "WEEPINBELL", "GLOOM"], "YELLOW ERIKA: TANGELA, WEEPINBELL, GLOOM")
	t.check(_team("KOGA") == ["VENONAT", "VENONAT", "VENONAT", "VENOMOTH"], "YELLOW KOGA: VENONAT x3, VENOMOTH")
	t.check(_team("SABRINA") == ["ABRA", "KADABRA", "ALAKAZAM"], "YELLOW SABRINA: ABRA, KADABRA, ALAKAZAM")
	t.check(_team("BLAINE") == ["NINETALES", "RAPIDASH", "ARCANINE"], "YELLOW BLAINE: NINETALES, RAPIDASH, ARCANINE")
	t.check(_team("GIOVANNI", 3) == ["DUGTRIO", "PERSIAN", "NIDOQUEEN", "NIDOKING", "RHYDON"], "YELLOW GIOVANNI (gym): DUGTRIO, PERSIAN, NIDOQUEEN, NIDOKING, RHYDON")
	t.check(_team("LORELEI") == ["DEWGONG", "CLOYSTER", "SLOWBRO", "JYNX", "LAPRAS"], "YELLOW LORELEI's team")
	t.check(_team("BRUNO") == ["ONIX", "HITMONCHAN", "HITMONLEE", "ONIX", "MACHAMP"], "YELLOW BRUNO's team")
	t.check(_team("AGATHA") == ["GENGAR", "GOLBAT", "HAUNTER", "ARBOK", "GENGAR"], "YELLOW AGATHA's team")
	t.check(_team("LANCE") == ["GYARADOS", "DRAGONAIR", "DRAGONAIR", "AERODACTYL", "DRAGONITE"], "YELLOW LANCE's team")
	# the rival: EEVEE plus its evolution by branch
	t.check(_team("RIVAL1", 1) == ["EEVEE"] and _team("RIVAL1", 2) == ["SPEAROW", "EEVEE"], "YELLOW rival Lv5 EEVEE, then SPEAROW + EEVEE")
	t.check(_team("RIVAL3", 1).back() == "JOLTEON" and _team("RIVAL3", 2).back() == "FLAREON" and _team("RIVAL3", 3).back() == "VAPOREON",
		"YELLOW champion rival ends with JOLTEON / FLAREON / VAPOREON")
	# JESSIE & JAMES are four extra ROCKET teams
	var jj: Dictionary = GameData.versions_data["jessieJames"]
	t.check(jj.size() == 4, "JESSIE & JAMES: four battles")
	t.check(_i(GameData.versions_data["parties"]["YELLOW"]["ROCKET"][int(jj["MtMoonB2F"]) - 1]) == [[14, "EKANS"], [14, "MEOWTH"], [14, "KOFFING"]], "J&J at Mt. Moon: EKANS, MEOWTH, KOFFING (Lv14)")
	t.check(_i(GameData.versions_data["parties"]["YELLOW"]["ROCKET"][int(jj["SilphCo11F"]) - 1]) == [[31, "WEEZING"], [31, "ARBOK"], [31, "MEOWTH"]], "J&J at Silph Co.: WEEZING, ARBOK, MEOWTH (Lv31)")
	# custom movesets (special_moves.asm): BROCK's ONIX knows BIND + BIDE, MISTY's STARMIE BUBBLEBEAM
	GameState.set_version("YELLOW")
	var brock := BattleEngine.make_trainer_party("BROCK", 1)
	t.check(brock.size() == 2 and brock[1].moves.has("BIND") and brock[1].moves.has("BIDE"), "YELLOW BROCK's ONIX knows BIND and BIDE")
	var misty := BattleEngine.make_trainer_party("MISTY", 1)
	t.check(misty[1].moves.has("BUBBLEBEAM"), "YELLOW MISTY's STARMIE knows BUBBLEBEAM")
	GameState.set_version("RED")
	var brock_r := BattleEngine.make_trainer_party("BROCK", 1)
	t.check(brock_r[0].level == 12 and brock_r[1].level == 14, "RED BROCK is Lv12 / Lv14")
	# species data: YELLOW's PIKACHU learnset and start moves
	GameState.set_version("YELLOW")
	var pk: Dictionary = GameData.get_species("PIKACHU")
	t.check(_i(pk["learn"][0]) == [6, "TAIL_WHIP"] and _i(pk["learn"]).has([26, "THUNDERBOLT"]), "YELLOW PIKACHU learnset (TAIL WHIP Lv6 ... THUNDERBOLT Lv26)")
	t.check(GameData.get_species("KADABRA")["moves1"] == ["TELEPORT", "KINESIS"], "YELLOW KADABRA starts with KINESIS")
	var counts := 0
	for sid in GameData.versions_data["species"]["YELLOW"].keys():
		counts += 1
	t.check(counts >= 20, "YELLOW changes %d species' stats / moves / evolutions" % counts)
	# NPC layout: Oak's Lab has one ball, MELANIE's house replaces the Cerulean trade house, JENNY stands in Vermilion
	var lab_ids := []
	for o in GameData.get_map("OaksLab")["objs"]:
		if o.get("sprite", "") == "poke_ball" and o.get("shown", true):
			lab_ids.append(o["id"])
	t.check(lab_ids == ["OAKSLAB_EEVEE_POKE_BALL"], "YELLOW Oak's Lab: only the EEVEE ball is left (%s)" % str(lab_ids))
	t.check(_has_obj("CeruleanTradeHouse", "CERULEANMELANIESHOUSE_MELANIE"), "YELLOW Cerulean: Melanie's house objects")
	t.check(_has_obj("VermilionCity", "VERMILIONCITY_OFFICER_JENNY"), "YELLOW Vermilion: Officer Jenny")
	t.check(_has_obj("Route24", "ROUTE24_COOLTRAINER_M4"), "YELLOW Route 24: Damian")
	t.check(_has_obj("MtMoonB2F", "MTMOONB2F_JESSIE") and _has_obj("SilphCo11F", "SILPHCO11F_JAMES"), "YELLOW: Jessie and James are placed")
	t.check(Story.raw("OaksLabOakChooseMonText").contains("that ball"), "YELLOW dialogue replaces RED's ('see that ball on the table')")
	# an NPC YELLOW's map doesn't have stays gone even when a RED script "shows" it
	GameState.toggles["SaffronCity:SAFFRONCITY_ROCKET9"] = true
	t.check(Story.obj("SAFFRONCITY_ROCKET9", "SaffronCity").get("removed", false) and not Story.is_shown("SAFFRONCITY_ROCKET9", "SaffronCity"),
		"YELLOW: SAFFRONCITY_ROCKET9 is removed and can't be shown again")
	GameState.toggles.erase("SaffronCity:SAFFRONCITY_ROCKET9")
	GameState.set_version("RED")
	t.check(not _has_obj("MtMoonB2F", "MTMOONB2F_JESSIE"), "RED has no Jessie")
	var red_lab: int = 0
	for o in GameData.get_map("OaksLab")["objs"]:
		if o.get("sprite", "") == "poke_ball":
			red_lab += 1
	t.check(red_lab == 3, "RED Oak's Lab still has the three starter balls")
	t.check(Story.raw("OaksLabOakChooseMonText").contains("3 POKéMON"), "RED dialogue unchanged")

static func _has_obj(map_name: String, id: String) -> bool:
	for o in GameData.get_map(map_name).get("objs", []):
		if o.get("id", "") == id and o.get("shown", true):
			return true
	return false

# ---------------------------------------------------------------- trades, prizes, marts
static func _trades_prizes_marts(t: TestSuite) -> void:
	var trades: Dictionary = GameData.versions_data["trades"]
	t.check(trades["RED"] == trades["BLUE"] and trades["RED"].size() == 10, "RED and BLUE share the ten in-game trades")
	t.check(trades["RED"][0]["give"] == "NIDORINO" and trades["RED"][0]["get"] == "NIDORINA", "RED/BLUE trade 1: NIDORINO -> NIDORINA")
	t.check(trades["YELLOW"][0]["give"] == "LICKITUNG" and trades["YELLOW"][0]["get"] == "DUGTRIO", "YELLOW trade 1: LICKITUNG -> DUGTRIO")
	t.check(trades["YELLOW"][1]["give"] == "CLEFAIRY" and trades["YELLOW"][1]["get"] == "MR_MIME", "YELLOW trade 2: CLEFAIRY -> MR. MIME")
	GameState.set_version("YELLOW")
	t.check(Story.pokedata["trades"][0]["get"] == "DUGTRIO", "Story reads YELLOW's trades")
	GameState.set_version("RED")
	t.check(Story.pokedata["trades"][0]["get"] == "NIDORINA", "Story reads RED's trades after switching back")
	# Game Corner prizes
	var pz: Dictionary = GameData.versions_data["prizes"]
	t.check(_i(pz["RED"][0]) == [["ABRA", 180, 9], ["CLEFAIRY", 500, 8], ["NIDORINA", 1200, 17]], "RED prizes: ABRA 180, CLEFAIRY 500, NIDORINA 1200")
	t.check(_i(pz["RED"][1]) == [["DRATINI", 2800, 18], ["SCYTHER", 5500, 25], ["PORYGON", 9999, 26]], "RED prizes: DRATINI, SCYTHER, PORYGON")
	t.check(_i(pz["BLUE"][0]) == [["ABRA", 120, 6], ["CLEFAIRY", 750, 12], ["NIDORINO", 1200, 17]], "BLUE prizes: ABRA 120, CLEFAIRY 750, NIDORINO 1200")
	t.check(_i(pz["BLUE"][1]) == [["PINSIR", 2500, 20], ["DRATINI", 4600, 24], ["PORYGON", 6500, 18]], "BLUE prizes: PINSIR, DRATINI, PORYGON")
	t.check(_i(pz["YELLOW"][0]) == [["ABRA", 230, 15], ["VULPIX", 1000, 18], ["WIGGLYTUFF", 2680, 22]], "YELLOW prizes: ABRA, VULPIX, WIGGLYTUFF")
	t.check(str(pz["YELLOW"][1][0][0]) == "SCYTHER" and str(pz["YELLOW"][1][1][0]) == "PINSIR" and str(pz["YELLOW"][1][2][0]) == "PORYGON",
		"YELLOW prizes: SCYTHER, PINSIR, PORYGON")
	t.check(Mid_prizes_active("BLUE")[0][2][0] == "NIDORINO", "Game Corner uses BLUE's prize list")
	t.check(Mid_prizes_active("RED")[0][2][0] == "NIDORINA", "Game Corner uses RED's prize list")
	# Marts
	GameState.set_version("YELLOW")
	t.check(Story.pokedata["marts"]["ViridianMartClerkText"].has("POTION"), "YELLOW Viridian Mart sells POTION")
	t.check(Story.pokedata["marts"]["CeruleanMartClerkText"] == ["POKE_BALL", "POTION", "ESCAPE_ROPE", "REPEL", "ANTIDOTE", "BURN_HEAL", "AWAKENING", "PARLYZ_HEAL"], "YELLOW Cerulean Mart also sells ESCAPE ROPE")
	t.check(Story.pokedata["marts"]["CeladonMart4FClerkText"].size() >= 0 and not Story.pokedata["marts"]["PewterMartClerkText"].is_empty(), "YELLOW marts present")
	GameState.set_version("RED")
	t.check(not Story.pokedata["marts"]["ViridianMartClerkText"].has("POTION"), "RED Viridian Mart has no POTION")
	# fishing
	t.check(_i(GameData.versions_data["superRod"]["YELLOW"]["PALLET_TOWN"][0]) == [10, "STARYU"], "YELLOW super rod Pallet Town: STARYU first")
	t.check(GameData.versions_data["superRod"]["RED"] == GameData.versions_data["superRod"]["BLUE"], "RED and BLUE fish alike")

static func Mid_prizes_active(v: String) -> Array:
	GameState.set_version(v)
	var arr: Array = Story.pokedata.get("prizes", [])
	GameState.set_version("RED")
	return arr

# ---------------------------------------------------------------- rival branch + buddy friendship
static func _rival_and_buddy(t: TestSuite) -> void:
	GameState.set_version("YELLOW")
	GameState.rival_eevee = "JOLTEON"
	t.check(Story.yellow_rival_party("RIVAL1", 4) == 2 and Story.yellow_rival_party("RIVAL1", 7) == 3, "YELLOW: rival Route 22 / Cerulean are parties 2 and 3")
	var expect := {"JOLTEON": 0, "FLAREON": 1, "VAPOREON": 2}
	for ev in expect.keys():
		GameState.rival_eevee = ev
		var v: int = expect[ev]
		t.check(Story.yellow_rival_party("RIVAL2", 4) == 2 + v and Story.yellow_rival_party("RIVAL2", 7) == 5 + v and Story.yellow_rival_party("RIVAL2", 10) == 8 + v,
			"YELLOW rival %s branch: Tower / Silph / Route 22 party numbers" % ev)
		var champ := BattleEngine.make_trainer_party("RIVAL3", Story.yellow_rival_party("RIVAL3", 1))
		t.check(champ.back().species_id == ev, "YELLOW champion's last POKeMON is %s" % ev)
		var silph := BattleEngine.make_trainer_party("RIVAL2", Story.yellow_rival_party("RIVAL2", 7))
		t.check(silph.back().species_id == ev, "YELLOW Silph Co. rival ends with %s" % ev)
	# friendship: pokeyellow's HappinessChangeTable
	GameState.party = [GameState.PartyMon.new("PIKACHU", 5), GameState.PartyMon.new("PIDGEY", 5)]
	GameState.party[0].buddy = true
	GameState.pikachu_happiness = 90
	PikachuBuddy.event(PikachuBuddy.LEVEL_UP, GameState.party[0])
	t.check(GameState.pikachu_happiness == 95, "level-up: +5 while under 100 (got %d)" % GameState.pikachu_happiness)
	PikachuBuddy.event(PikachuBuddy.LEVEL_UP, GameState.party[1])
	t.check(GameState.pikachu_happiness == 95, "another mon levelling up doesn't count")
	PikachuBuddy.event(PikachuBuddy.WALKING)
	t.check(GameState.pikachu_happiness == 97, "walking: +2 under 100")
	GameState.pikachu_happiness = 150
	PikachuBuddy.event(PikachuBuddy.LEVEL_UP, GameState.party[0])
	t.check(GameState.pikachu_happiness == 153, "level-up: +3 between 100 and 199")
	GameState.pikachu_happiness = 220
	PikachuBuddy.event(PikachuBuddy.TRADED_AWAY, GameState.party[0])
	t.check(GameState.pikachu_happiness == 200, "traded away above 200: -20")
	GameState.pikachu_happiness = 2
	PikachuBuddy.event(PikachuBuddy.POISON_FAINT, GameState.party[0])
	t.check(GameState.pikachu_happiness == 0, "friendship never goes below 0")
	GameState.pikachu_happiness = 254
	PikachuBuddy.event(PikachuBuddy.LEVEL_UP, GameState.party[0])
	t.check(GameState.pikachu_happiness == 255, "friendship never goes above 255")
	GameState.party[0].hp = 0
	GameState.pikachu_happiness = 100
	PikachuBuddy.event(PikachuBuddy.WALKING)
	t.check(GameState.pikachu_happiness == 100, "a fainted PIKACHU gets nothing from walking")
	GameState.set_version("RED")
	GameState.pikachu_happiness = 90
	PikachuBuddy.event(PikachuBuddy.LEVEL_UP, GameState.party[0])
	t.check(GameState.pikachu_happiness == 90, "RED / BLUE: no friendship system")
	t.check(PikachuBuddy.tier() == 1 and PikachuBuddy.mood_word() == "wary", "tiers: 90 is 'wary'")
	GameState.pikachu_happiness = 200
	t.check(PikachuBuddy.tier() == 4 and PikachuBuddy.is_friendly(), "200 is devoted, friendly (>= 147)")
	GameState.pikachu_happiness = 90

# ---------------------------------------------------------------- every trainer on every map, per version
static func _trainer_objects(t: TestSuite) -> void:
	for v in GameData.VERSIONS:
		GameState.set_version(v)
		var n := 0
		var bad: Array = []
		for m in GameData.maps.keys():
			for o in GameData.maps[m].get("objs", []):
				if not o.has("trainer") or o.get("removed", false):
					continue
				n += 1
				var tr: Dictionary = o["trainer"]
				var parties: Array = GameData.parties.get(str(tr["cls"]), [])
				if int(tr["n"]) < 1 or int(tr["n"]) > parties.size():
					bad.append("%s:%s has no party %s/%d" % [m, o["id"], tr["cls"], int(tr["n"])])
					continue
				var th: Dictionary = o.get("th", {})
				# a trainer needs its three battle lines (a few are handled by map scripts instead: gym leaders, the rival ...)
				if not th.is_empty():
					for k in ["battle", "end", "after"]:
						if not GameText.has(str(th.get(k, ""))):
							bad.append("%s:%s lacks text %s" % [m, o["id"], th.get(k, "")])
		t.check(bad.is_empty(), "%s: all %d trainers have a party and battle text (%s)" % [v, n, str(bad.slice(0, 4))])
		t.check(n >= 320, "%s: %d trainers placed on the maps" % [v, n])
	GameState.set_version("RED")

# ---------------------------------------------------------------- saves
static func _save(t: TestSuite) -> void:
	var saved_party := GameState.party
	GameState.set_version("YELLOW")
	GameState.party = [GameState.PartyMon.new("PIKACHU", 7)]
	GameState.party[0].buddy = true
	GameState.pikachu_happiness = 123
	GameState.rival_eevee = "VAPOREON"
	t.check(GameState.save(), "YELLOW: save succeeds")
	GameState.set_version("RED")
	t.check(GameState.load_save(), "YELLOW: load succeeds")
	t.check(GameState.version == "YELLOW" and GameData.active_version == "YELLOW", "the save remembers the version (YELLOW)")
	t.check(GameState.party[0].buddy and GameState.pikachu_happiness == 123 and GameState.rival_eevee == "VAPOREON", "buddy flag, friendship and rival plan survive a save")
	t.check(GameData.get_species("KADABRA")["moves1"] == ["TELEPORT", "KINESIS"], "loading a YELLOW save applies YELLOW's species data")
	# a save written before versions existed has no "version" key: it must load as RED
	var f := FileAccess.open(GameState.SAVE_PATH, FileAccess.READ)
	var d: Dictionary = JSON.parse_string(f.get_as_text())
	f.close()
	d.erase("version")
	f = FileAccess.open(GameState.SAVE_PATH, FileAccess.WRITE)
	f.store_string(JSON.stringify(d))
	f.close()
	GameState.set_version("YELLOW")
	t.check(GameState.load_save() and GameState.version == "RED", "an old save (no version key) loads as RED")
	t.check(GameData.get_species("KADABRA")["moves1"] == ["TELEPORT", "CONFUSION", "DISABLE"], "old save: RED species data")
	for v in ["BLUE", "RED"]:
		GameState.set_version(v)
		GameState.save()
		GameState.set_version("YELLOW")
		GameState.load_save()
		t.check(GameState.version == v, "the save remembers %s" % v)
	GameState.party = saved_party
	GameState.set_version("RED")
	GameState.pikachu_happiness = 90
	GameState.rival_eevee = "JOLTEON"

# ---------------------------------------------------------------- the YELLOW opening, gifts and J&J
static var battles: Array = []
static var results: Array = []

static func _battle(enc: Dictionary) -> String:
	battles.append(enc)
	return str(results.pop_front()) if not results.is_empty() else "win"

static func _yellow_story(t: TestSuite) -> void:
	var saved := {"party": GameState.party, "bag": GameState.bag.duplicate(), "badges": GameState.badges.duplicate(),
		"money": GameState.money, "story": GameState.story_to_dict().duplicate(true), "map": GameState.current_map,
		"seen": GameState.seen_species.duplicate(), "caught": GameState.caught_species.duplicate()}
	var host: Node = FakeHost.new()
	var ui: Node = FakeUI.new()
	var prev_override := Story.battle_override
	Story.fast = true
	Story.host_override = host
	Story.ui_override = ui
	Story.battle_override = _battle
	battles = []
	results = []
	GameState.set_version("YELLOW")
	GameState.reset_story_state()
	GameState.party = []
	GameState.bag = {}
	GameState.badges = []
	GameState.seen_species = {}
	GameState.caught_species = {}
	GameState.player_name = "RED"

	# --- Pallet Town: Oak stops you, leads you to the lab
	host.load_map("PalletTown", Vector2i(10, 2), "up")
	host.walk("U")
	t.check(host.map == "OaksLab", "YELLOW: Oak takes you to the lab")
	t.check(Story.flag("EVENT_OAK_ASKED_TO_CHOOSE_MON"), "YELLOW: Oak asks you to take the ball")
	t.check(host.is_actor_shown("OAKSLAB_EEVEE_POKE_BALL") and not host.is_actor_shown("OAKSLAB_CHARMANDER_POKE_BALL")
		and not host.is_actor_shown("OAKSLAB_SQUIRTLE_POKE_BALL") and not host.is_actor_shown("OAKSLAB_BULBASAUR_POKE_BALL"),
		"YELLOW lab: only the EEVEE ball is on the table")
	t.check(ui.said_has("that ball"), "YELLOW lab dialogue: 'see that ball on the table'")
	# --- take it: the rival snatches EEVEE, Oak gives you PIKACHU (no nickname prompt, no starter choice)
	host.talk("OAKSLAB_EEVEE_POKE_BALL")
	t.check(GameState.party.size() == 1 and GameState.party[0].species_id == "PIKACHU" and GameState.party[0].level == 5, "YELLOW: you receive a Lv5 PIKACHU")
	t.check(GameState.party[0].buddy and GameState.starter == "PIKACHU" and Story.flag("EVENT_GOT_STARTER"), "YELLOW: PIKACHU is the buddy / starter")
	t.check(GameState.party[0].moves == ["THUNDERSHOCK", "GROWL"], "YELLOW: PIKACHU knows THUNDERSHOCK and GROWL")
	t.check(GameState.pikachu_happiness == 90, "YELLOW: PIKACHU's friendship starts at 90")
	t.check(not Story.is_shown("OAKSLAB_EEVEE_POKE_BALL", "OaksLab") and ui.said_has("snatched"), "YELLOW: the rival took the EEVEE ball")
	t.check(GameState.caught_species.has("PIKACHU") and GameState.seen_species.has("PIKACHU"), "YELLOW: PIKACHU registered in the POKeDEX")
	t.check(GameState.rival_eevee == "JOLTEON", "YELLOW: the rival's plan starts as JOLTEON")
	# --- rival battle with EEVEE on the way out
	results = ["lose"]
	host.walk("DD")
	t.check(battles.size() == 1 and battles[0].get("trainer_class") == "RIVAL1" and int(battles[0].get("party_index")) == 1, "YELLOW: RIVAL1 party 1 (EEVEE)")
	t.check(BattleEngine.make_trainer_party("RIVAL1", 1)[0].species_id == "EEVEE", "YELLOW: the lab rival fights with EEVEE")
	t.check(GameState.rival_eevee == "VAPOREON", "YELLOW: lose the lab fight -> the rival's EEVEE becomes VAPOREON")
	t.check(ui.said_has("dislikes"), "YELLOW: Oak notices that PIKACHU dislikes POKe BALLs")
	Yellow_after_win(t, "win", "FLAREON")
	# Route 22: win turns FLAREON into JOLTEON
	GameState.rival_eevee = "FLAREON"
	load("res://scripts/story/Yellow.gd").after_route22_first("win")
	t.check(GameState.rival_eevee == "JOLTEON", "YELLOW: beating the rival on Route 22 turns FLAREON into JOLTEON")
	GameState.rival_eevee = "FLAREON"
	load("res://scripts/story/Yellow.gd").after_route22_first("lose")
	t.check(GameState.rival_eevee == "FLAREON", "YELLOW: losing on Route 22 keeps FLAREON")

	# --- Damian (Route 24): CHARMANDER Lv10
	host.load_map("Route24", Vector2i(6, 6), "up")
	ui.answers = [true, false]
	host.talk("ROUTE24_COOLTRAINER_M4")
	t.check(_has_mon("CHARMANDER", 10) and Story.flag("EVENT_GOT_CHARMANDER_FROM_DAMIAN"), "YELLOW: Damian gives CHARMANDER Lv10")
	# --- Melanie (Cerulean): BULBASAUR only for a fond PIKACHU
	GameState.pikachu_happiness = 100
	host.load_map("CeruleanTradeHouse", Vector2i(3, 3), "up")
	ui.answers = [true]
	host.talk("CERULEANMELANIESHOUSE_MELANIE")
	t.check(not _has_mon("BULBASAUR", 10), "YELLOW: Melanie won't give BULBASAUR while PIKACHU's friendship < 147")
	GameState.pikachu_happiness = 200
	ui.answers = [true, false]
	host.talk("CERULEANMELANIESHOUSE_MELANIE")
	t.check(_has_mon("BULBASAUR", 10) and Story.flag("EVENT_GOT_BULBASAUR_IN_CERULEAN"), "YELLOW: Melanie gives BULBASAUR Lv10 to a fond PIKACHU")
	# --- Officer Jenny (Vermilion): SQUIRTLE needs the THUNDERBADGE
	GameState.pikachu_happiness = 200
	host.load_map("VermilionCity", Vector2i(19, 16), "up")
	ui.answers = [true, false]
	host.talk("VERMILIONCITY_OFFICER_JENNY")
	t.check(not _has_mon("SQUIRTLE", 10), "YELLOW: Officer Jenny wants the THUNDERBADGE first")
	GameState.badges.append("THUNDERBADGE")
	host.talk("VERMILIONCITY_OFFICER_JENNY")
	t.check(_has_mon("SQUIRTLE", 10) and Story.flag("EVENT_GOT_SQUIRTLE_FROM_OFFICER_JENNY"), "YELLOW: Officer Jenny gives SQUIRTLE Lv10")
	# --- Jessie & James at Mt. Moon: a ROCKET battle with their own team
	battles.clear()
	results = ["win"]
	host.load_map("MtMoonB2F", Vector2i(12, 3), "up")
	host.talk("MTMOONB2F_JESSIE")
	t.check(battles.size() == 1 and battles[0].get("trainer_class") == "ROCKET" and int(battles[0].get("party_index")) == int(GameData.versions_data["jessieJames"]["MtMoonB2F"]),
		"YELLOW: JESSIE & JAMES battle (ROCKET party %s)" % str(GameData.versions_data["jessieJames"]["MtMoonB2F"]))
	t.check(not host.is_actor_shown("MTMOONB2F_JESSIE") and Story.flag("EVENT_BEAT_JESSIE_JAMES_MTMOONB2F"), "YELLOW: J&J blast off after losing")
	# --- Chansey by the Pokemon Center counter
	host.load_map("ViridianPokecenter", Vector2i(4, 4), "up")
	t.check(host.is_actor_shown("VIRIDIANPOKECENTER_CHANSEY"), "YELLOW: CHANSEY in the Viridian POKeMON CENTER")

	Story.fast = false
	Story.host_override = null
	Story.ui_override = null
	Story.battle_override = prev_override
	GameState.party = saved["party"]
	GameState.bag = saved["bag"]
	GameState.badges = saved["badges"]
	GameState.money = saved["money"]
	GameState.story_from_dict(saved["story"])
	GameState.current_map = saved["map"]
	GameState.seen_species = saved["seen"]
	GameState.caught_species = saved["caught"]
	GameState.starter = ""
	GameState.pikachu_happiness = 90
	GameState.rival_eevee = "JOLTEON"
	host.free()
	ui.free()

static func Yellow_after_win(t: TestSuite, result: String, expect: String) -> void:
	load("res://scripts/story/Yellow.gd").after_lab_battle(result)
	t.check(GameState.rival_eevee == expect, "YELLOW: win the lab fight -> the rival's EEVEE becomes %s" % expect)

static func _has_mon(sp: String, lv: int) -> bool:
	for m in GameState.party:
		if m.species_id == sp and m.level == lv:
			return true
	for m in GameState.box():
		if m.species_id == sp and m.level == lv:
			return true
	return false
