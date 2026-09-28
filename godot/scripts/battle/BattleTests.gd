class_name BattleTests
extends RefCounted
## Battle-area tests, run from TestSuite.run_all(). The engine runs against
## BattleNullUI, which never suspends, so a whole battle completes
## synchronously inside Callable.call().

static func _run(b: BattleEngine, ui: BattleNullUI) -> String:
	var r: Variant = Callable(b, "run").call(ui)
	return r if r is String else "<suspended>"

static func _party(entries: Array) -> void:
	GameState.party = []
	for en in entries:
		GameState.party.append(GameState.PartyMon.new(en[0], en[1]))

static func run(t: TestSuite) -> void:
	var saved_party: Array = GameState.party
	var saved_bag: Dictionary = GameState.bag.duplicate()
	var saved_money: int = GameState.money
	_stats(t)
	_wild_battle(t)
	_trainer_battle(t)
	_catching(t)
	_status_and_stages(t)
	_losing_and_running(t)
	_items(t)
	_level_up(t)
	_save_fields(t)
	_special_battles(t)
	_env_and_vfx(t)
	_scene_smoke(t)
	GameState.party = saved_party
	GameState.bag = saved_bag
	GameState.money = saved_money

static func _stats(t: TestSuite) -> void:
	t.check(GameState.calc_stat(78, 2, 0, 50, true) == 140, "Gen1 HP formula: CHARIZARD L50 HP DV2 = 140")
	t.check(GameState.calc_stat(84, 0, 0, 50, false) == 89, "Gen1 stat formula: base 84 L50 = 89")
	t.check(GameState.exp_for_level("MEDIUM_SLOW", 5) == 135, "MEDIUM_SLOW exp at L5 = 135")
	t.check(GameState.exp_for_level("MEDIUM_FAST", 10) == 1000, "MEDIUM_FAST exp at L10 = 1000")
	var m := GameState.PartyMon.new("CHARIZARD", 50)
	t.check(m.moves.size() == 4 and m.moves.has("FLAMETHROWER"), "L50 CHARIZARD knows its last 4 level-up moves (%s)" % str(m.moves))
	var d := GameState.PartyMon.new("PIKACHU", 10, {"atk": 15, "def": 1, "spd": 0, "spc": 1})
	t.check(d.dvs["hp"] == 0b1101, "HP DV derives from the other DVs' low bits")

static func _wild_battle(t: TestSuite) -> void:
	_party([["CHARIZARD", 50]])
	var lead: GameState.PartyMon = GameState.party[0]
	var xp0 := lead.xp
	var b := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("PIDGEY", 5)], "seed": 1})
	var ui := BattleNullUI.new()
	var r := _run(b, ui)
	t.check(r == "win", "L50 CHARIZARD beats a wild L5 PIDGEY (got %s)" % r)
	t.check(lead.xp > xp0, "the winner gains EXP")
	t.check(ui.log.has("Wild PIDGEY appeared!"), "wild intro message")
	t.check(ui.log.any(func(s): return s.begins_with("CHARIZARD used ")), "'X used MOVE!' message")
	t.check(ui.log.has("Wild PIDGEY fainted!"), "wild faint message")

static func _trainer_battle(t: TestSuite) -> void:
	var brock := BattleEngine.make_trainer_party("BROCK", 1)
	t.check(brock.size() == 2 and brock[1].species_id == "ONIX" and brock[1].level == 14, "BROCK's party is GEODUDE/ONIX L14")
	t.check(brock[1].moves.has("BIDE"), "BROCK's ONIX knows his signature BIDE")
	_party([["BLASTOISE", 60]])
	GameState.money = 1000
	var opts := BattleEngine.trainer_opts("BROCK", 1)
	opts["seed"] = 3
	var b := BattleEngine.new(opts)
	var ui := BattleNullUI.new()
	var r := _run(b, ui)
	t.check(r == "win", "BLASTOISE beats BROCK (got %s)" % r)
	t.check(ui.log.has("BROCK wants to fight!"), "trainer intro message")
	t.check(ui.log.any(func(s): return s.contains("is about to use ONIX")), "trainer sends out the next mon")
	t.check(GameState.money == 1000 + 99 * 14, "prize money = 9900/100 x last level (%d)" % GameState.money)
	t.check(b.enemy_action()["type"] == "fight", "enemy AI picks a move")

static func _catching(t: TestSuite) -> void:
	_party([["PIKACHU", 30]])
	GameState.bag = {"MASTER_BALL": 1}
	var b := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("ZUBAT", 10)], "seed": 5})
	var ui := BattleNullUI.new()
	ui.actions = [{"type": "item", "item": "MASTER_BALL"}]
	var r := _run(b, ui)
	t.check(r == "caught", "MASTER BALL always catches (got %s)" % r)
	t.check(GameState.party.size() == 2 and GameState.party[1].species_id == "ZUBAT", "caught mon joins the party")
	t.check(not GameState.bag.has("MASTER_BALL"), "the thrown ball is used up")
	var b2 := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("MEWTWO", 70)], "seed": 9})
	var rolls := 0
	for i in 200:
		if b2.catch_roll("POKE_BALL", b2.mon(b2.e))["caught"]:
			rolls += 1
	t.check(rolls < 20, "full-HP MEWTWO rarely falls for a POKE BALL (%d/200)" % rolls)
	var tb := BattleEngine.new(BattleEngine.trainer_opts("YOUNGSTER", 1))
	GameState.bag = {"POKE_BALL": 2}
	tb.ui = BattleNullUI.new()
	var used: Variant = Callable(tb, "use_item").call("POKE_BALL", -1)
	t.check(used == "used" and (tb.ui as BattleNullUI).log.has("The trainer blocked the BALL!"), "can't catch a trainer's mon")

static func _status_and_stages(t: TestSuite) -> void:
	_party([["VENUSAUR", 50]])
	var b := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("RATTATA", 20)], "seed": 2})
	var ui := BattleNullUI.new()
	b.ui = ui
	Callable(b, "inflict").call(b.e, "SLP", false, "")
	t.check(b.mon(b.e).status == "SLP" and b.mon(b.e).sleep >= 1, "SLEEP sets status and a sleep counter")
	t.check(ui.log.has("Wild RATTATA fell asleep!"), "sleep message")
	var spd0 := b.stat(b.e, "spd")
	Callable(b, "stat_change").call(b.e, "spd", -2, true, false)
	t.check(b.stat(b.e, "spd") == int(floor(b.mon(b.e).stat("spd") * 50 / 100.0)) and b.stat(b.e, "spd") < spd0, "-2 SPEED stage halves speed")
	t.check(ui.log.has("Wild RATTATA's SPEED greatly fell!"), "stat stage message")
	b.mon(b.p).status = "PAR"
	t.check(b.stat(b.p, "spd") == maxi(1, int(floor(b.mon(b.p).stat("spd") / 4.0))), "paralysis quarters speed")
	var acc_ok := 0
	for i in 100:
		if b.accuracy_check(b.p, GameData.get_move("HYPNOSIS")):
			acc_ok += 1
	t.check(acc_ok > 40 and acc_ok < 80, "60%% accuracy move hits ~60/100 (%d)" % acc_ok)

static func _losing_and_running(t: TestSuite) -> void:
	_party([["MAGIKARP", 5]])
	var b := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("MEWTWO", 70)], "seed": 4})
	var ui := BattleNullUI.new()
	var r := _run(b, ui)
	t.check(r == "lose", "L5 MAGIKARP loses to L70 MEWTWO (got %s)" % r)
	t.check(ui.log.has(GameState.player_name + " blacked out!"), "blackout message")
	_party([["JOLTEON", 50]])
	var b2 := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("SLOWPOKE", 5)], "seed": 4})
	var ui2 := BattleNullUI.new()
	ui2.actions = [{"type": "run"}]
	t.check(_run(b2, ui2) == "run" and ui2.log.has("Got away safely!"), "fast mon runs from a slow one")
	var b3 := BattleEngine.new(BattleEngine.trainer_opts("YOUNGSTER", 1))
	b3.ui = BattleNullUI.new()
	var ran: Variant = Callable(b3, "try_run").call(false)
	t.check(ran == false, "no running from trainer battles")

static func _items(t: TestSuite) -> void:
	_party([["SQUIRTLE", 20]])
	var m: GameState.PartyMon = GameState.party[0]
	m.hp = 5
	GameState.bag = {"POTION": 1}
	var b := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("RATTATA", 3)], "seed": 6})
	var ui := BattleNullUI.new()
	b.ui = ui
	var r: Variant = Callable(b, "use_item").call("POTION", 0)
	t.check(r == "used" and m.hp == 25, "POTION restores 20 HP (hp=%d)" % m.hp)
	t.check(not GameState.bag.has("POTION"), "POTION consumed")
	t.check(BattleEngine.usable_in_battle("SUPER_POTION") and not BattleEngine.usable_in_battle("TOWN_MAP"), "battle bag filter")

static func _level_up(t: TestSuite) -> void:
	_party([["CHARMANDER", 15]])
	var m: GameState.PartyMon = GameState.party[0]
	m.xp = m.exp_to_next() - 1
	var b := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("PIDGEY", 3)], "seed": 8})
	var ui := BattleNullUI.new()
	var r := _run(b, ui)
	t.check(r == "win" and m.level >= 16, "CHARMANDER levels to 16 (L%d)" % m.level)
	t.check(m.leveled_in_battle and m.evo_by_level() == "CHARMELEON", "L16 CHARMANDER is due to evolve")
	t.check(ui.log.has("CHARMANDER grew to level 16!"), "level-up message")

static func _save_fields(t: TestSuite) -> void:
	var m := GameState.PartyMon.new("GENGAR", 40, {"atk": 3, "def": 7, "spd": 11, "spc": 13})
	m.status = "PSN"
	m.pp[m.moves[0]] = 1
	var back := GameState.PartyMon.from_dict(JSON.parse_string(JSON.stringify(m.to_dict())))
	t.check(back.dvs["spc"] == 13 and back.max_hp == m.max_hp and back.stat("spd") == m.stat("spd"), "DVs survive save/load")
	t.check(back.status == "PSN" and int(back.pp[m.moves[0]]) == 1 and back.xp == m.xp, "status/pp/exp survive save/load")

static func _env_and_vfx(t: TestSuite) -> void:
	t.check(BattleStage.env_for_map("Route1", false) == "grass", "Route1 battles on grass")
	t.check(BattleStage.env_for_map("ViridianForest", false) == "forest", "ViridianForest battles in the forest")
	t.check(BattleStage.env_for_map("MtMoon1F", false) == "cave", "Mt Moon battles in a cave")
	t.check(BattleStage.env_for_map("SeafoamIslands1F", false) == "ice", "Seafoam battles on ice")
	t.check(BattleStage.env_for_map("Route21", true) == "water", "surfing battles on water")
	t.check(BattleStage.env_for_map("CinnabarIsland", false) == "beach", "Cinnabar battles on the beach")
	var missing := 0
	for id in GameData.move_list:
		if not BattleVfx.MOVES.has(id):
			missing += 1
	t.check(missing == 0, "every move has a VFX recipe (%d missing)" % missing)

## Builds a real BattleScene (no rendering needed), poses it and runs every
## move's animation recipe to completion, then checks the framing.
static func _scene_smoke(t: TestSuite) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	_party([["CHARIZARD", 50]])
	var sc: Node = load("res://scenes/Battle.tscn").instantiate()
	tree.root.add_child(sc)
	sc.setup({"kind": "wild", "species": "BLASTOISE", "level": 50, "env": "grass", "screenshot": true, "seed": 3})
	Callable(sc, "pose").call("idle", {})
	t.check(sc.hud.boxes["e"] and sc.hud.boxes["p"], "posed battle shows both HP boxes")
	t.check(sc.center_px("e").x > sc.center_px("p").x and sc.center_px("e").y < sc.center_px("p").y,
		"enemy is framed upper-right of the player's mon")
	var bad: Array = []
	for id in GameData.move_list:
		if int(sc.vfx_frames(id, "p")) < 0:
			bad.append(id)
	for id in ["CHARGE", "DRAIN", "LEECH_SEED_DRAIN", "HEAL_ITEM", "FLY_CHARGE", "DIG_CHARGE", "BIDE_HIT"]:
		if int(sc.vfx_frames(id, "e")) < 0:
			bad.append(id)
	t.check(bad.is_empty(), "every move animation runs to completion (failed: %s)" % str(bad))
	for env in BattleStage.ENVS.keys():
		t.check(ResourceLoader.exists("res://assets/models/battle/bg_%s.glb" % env), "battle stage generated for %s" % env)
	sc.queue_free()

static func _special_battles(t: TestSuite) -> void:
	# Pokemon Tower ghost: the player's mon is too scared, the GHOST only moans, RUN always works
	_party([["CHARIZARD", 40]])
	var g := GameState.PartyMon.new("GASTLY", 20)
	g.nickname = "GHOST"
	var b := BattleEngine.new({"kind": "wild", "enemy_party": [g], "ghost": true, "no_catch": true, "seed": 2})
	var ui := BattleNullUI.new()
	ui.actions = [{"type": "fight", "slot": 0}, {"type": "run"}]
	var r := _run(b, ui)
	t.check(r == "run", "a GHOST battle ends by running (got %s)" % r)
	t.check(ui.log.has("CHARIZARD is too frightened to move!"), "ghost: the player's mon is too scared")
	t.check(ui.log.has("GHOST: Leave... Leave now..."), "ghost: the GHOST's moan")
	# Safari Zone: BALL/BAIT/ROCK, balls counted down, no FIGHT
	_party([["PIKACHU", 30]])
	BattleEngine.set_safari_balls(30)
	var sb := BattleEngine.new({"kind": "wild", "enemy_party": [GameState.PartyMon.new("RHYHORN", 25)], "safari": true, "seed": 12})
	var sui := BattleNullUI.new()
	sui.actions = [{"type": "safari", "what": "bait"}, {"type": "safari", "what": "rock"}]
	var sr := _run(sb, sui)
	t.check(sr == "caught" or sr == "fled" or sr == "run", "safari battle ends by catch or flight (got %s)" % sr)
	t.check(BattleEngine.safari_balls() < 30 or sui.log.any(func(x): return x.contains("ran away")), "safari balls are spent")
	t.check(sui.log.has(GameState.player_name + " threw some BAIT."), "safari BAIT message")
	# trainer prize money override (Story's `money` field)
	var o := BattleEngine.trainer_opts("YOUNGSTER", 1, {"money": 5000})
	t.check(int(o["trainer"]["money"]) == 5000, "trainer money override")
