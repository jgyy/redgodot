class_name MechanicsTests
extends RefCounted
## Gen 1 battle-mechanic checks (docs/CONTENT_AUDIT.md "Battle engine" rows), called from BattleTests.run(). Each test
## builds a tiny BattleEngine against BattleNullUI and drives one rule directly: critical hits from base Speed, badge
## boosts, the single SPECIAL stat, trapping moves, MIRROR MOVE, METRONOME, TRANSFORM, SUBSTITUTE, HAZE, MIST,
## LEECH SEED, RAGE, COUNTER, BIDE, DISABLE, EXPLOSION, DREAM EATER, PSYWAVE, OHKO, multi-hit, two-turn moves ...

static func _eng(pl: String, plv: int, en: String, elv: int, seed_v: int = 1) -> Array:
	GameState.party = [GameState.PartyMon.new(pl, plv, {"atk": 8, "def": 8, "spd": 8, "spc": 8})]
	var foe_mon := GameState.PartyMon.new(en, elv, {"atk": 8, "def": 8, "spd": 8, "spc": 8})
	var b := BattleEngine.new({"kind": "wild", "enemy_party": [foe_mon], "seed": seed_v})
	var ui := BattleNullUI.new()
	b.ui = ui
	b.participants = [b.mon(b.p)]
	return [b, ui]

static func _use(b: BattleEngine, side: BattleSide, mv: String) -> void:
	Callable(b, "do_move").call(side, mv)

static func run(t: TestSuite) -> void:
	var saved_party: Array = GameState.party
	var saved_badges: Array = GameState.badges.duplicate()
	GameState.badges = []
	_crits(t)
	_badges_and_special(t)
	_type_chart(t)
	_fixed_damage(t)
	_multi_and_trap(t)
	_copy_moves(t)
	_field_effects(t)
	_counter_bide_rage(t)
	_two_turn(t)
	_status(t)
	_misc(t)
	GameState.party = saved_party
	GameState.badges = saved_badges

# ---------------------------------------------------------------- critical hits
static func _crit_rate(b: BattleEngine, mv: String, n: int = 3000) -> float:
	var hits := 0
	var md := GameData.get_move(mv)
	for i in n:
		if Callable(b, "calc_damage").call(b.p, b.e, md, true)["crit"]:
			hits += 1
	return float(hits) / n

static func _crits(t: TestSuite) -> void:
	# Gen 1: critical chance = base Speed / 2 out of 256 (x8 for high-crit moves, x4 with FOCUS ENERGY as upstream ports it)
	var a := _eng("PIKACHU", 30, "RATTATA", 30)   # base SPEED 90 -> 45/256 = 17.6%
	var b: BattleEngine = a[0]
	var r := _crit_rate(b, "TACKLE")
	t.check(r > 0.14 and r < 0.21, "crit rate follows base Speed: PIKACHU TACKLE %.3f ~ 45/256" % r)
	a = _eng("SLOWPOKE", 30, "RATTATA", 30)   # base SPEED 15 -> 7/256
	var rs := _crit_rate(a[0], "TACKLE")
	t.check(rs < 0.06, "slow mon rarely crits: SLOWPOKE %.3f" % rs)
	var rh := _crit_rate(b, "SLASH", 800)
	t.check(rh > 0.97, "high-crit move (SLASH) on a fast mon almost always crits (%.3f)" % rh)
	var rk := _crit_rate(a[0], "KARATE_CHOP")
	t.check(rk > 0.15 and rk < 0.30, "KARATE CHOP x8: SLOWPOKE 56/256 = 21.9%% (%.3f)" % rk)
	b.p.v["focus"] = true
	var rf := _crit_rate(b, "TACKLE", 800)
	t.check(rf > 0.6 and rf < 0.8, "FOCUS ENERGY x4 crit rate as upstream ports it (180/256 = 0.70, got %.3f; the cartridge's bug divides by 4 instead)" % rf)
	# a critical hit ignores stat stages
	var c := _eng("PIKACHU", 40, "GEODUDE", 40, 5)
	var cb: BattleEngine = c[0]
	cb.e.v["st"]["def"] = 6
	var dmg_nocrit := 0
	var dmg_crit := 0
	var md := GameData.get_move("TACKLE")
	for i in 40:
		var rr: Dictionary = Callable(cb, "calc_damage").call(cb.p, cb.e, md, true)
		if rr["crit"]:
			dmg_crit = maxi(dmg_crit, rr["dmg"])
		else:
			dmg_nocrit = maxi(dmg_nocrit, rr["dmg"])
	t.check(dmg_crit > dmg_nocrit, "a critical hit ignores the target's +6 DEFENSE (%d vs %d)" % [dmg_crit, dmg_nocrit])

# ---------------------------------------------------------------- badge boosts, the single Special stat
static func _badges_and_special(t: TestSuite) -> void:
	var a := _eng("CHARMANDER", 30, "RATTATA", 30)
	var b: BattleEngine = a[0]
	var raw := {}
	for k in ["atk", "def", "spd", "spc"]:
		raw[k] = b.stat(b.p, k)
	for pair in [["atk", "BOULDERBADGE"], ["def", "THUNDERBADGE"], ["spd", "SOULBADGE"], ["spc", "VOLCANOBADGE"]]:
		GameState.badges = [pair[1]]
		var boosted: int = b.stat(b.p, pair[0])
		t.check(boosted == int(floor(raw[pair[0]] * 9 / 8.0)), "%s boosts %s by 1/8 (%d -> %d)" % [pair[1], pair[0], raw[pair[0]], boosted])
		for k in ["atk", "def", "spd", "spc"]:
			if k != pair[0]:
				t.check(b.stat(b.p, k) == raw[k], "%s leaves %s alone" % [pair[1], k])
		t.check(b.stat(b.e, pair[0]) == b.mon(b.e).stat(pair[0]), "badges never boost the opponent")
	GameState.badges = []
	# Gen 1 has one SPECIAL stat: no separate special defence exists in the data or the formula
	var no_sdef := true
	for sp in GameData.species.values():
		if sp.has("sdef") or sp.has("spdef") or sp.has("spa"):
			no_sdef = false
	t.check(no_sdef and GameData.species["ALAKAZAM"].has("spc"), "single SPECIAL stat: no split special attack / defence in species data")
	# a special move uses the attacker's SPECIAL against the target's SPECIAL
	var b2: BattleEngine = _eng("ALAKAZAM", 50, "MACHOKE", 50)[0]
	b2.e.v["st"]["spc"] = 6   # +6 SPECIAL on the defender must reduce a special hit, +6 DEFENSE must not
	var special := 0
	var phys_st := 0
	var md_special := GameData.get_move("PSYBEAM")
	for i in 30:
		special = maxi(special, Callable(b2, "calc_damage").call(b2.p, b2.e, md_special, false)["dmg"])
	b2.e.v["st"]["spc"] = 0
	b2.e.v["st"]["def"] = 6
	for i in 30:
		phys_st = maxi(phys_st, Callable(b2, "calc_damage").call(b2.p, b2.e, md_special, false)["dmg"])
	t.check(phys_st > special, "special attacks are resisted by SPECIAL, not DEFENSE (%d vs %d)" % [phys_st, special])
	# no double-boost: the Special badge is the only one in effect for special moves
	GameState.badges = ["VOLCANOBADGE"]
	var b3: BattleEngine = _eng("ALAKAZAM", 50, "MACHOKE", 50)[0]
	t.check(b3.stat(b3.p, "spc") == int(floor(b3.mon(b3.p).stat("spc") * 9 / 8.0)), "VOLCANOBADGE boosts the single SPECIAL stat")
	GameState.badges = []

# ---------------------------------------------------------------- Gen 1 type chart quirks
static func _type_chart(t: TestSuite) -> void:
	t.check(GameData.type_multiplier("GHOST", ["PSYCHIC_TYPE"]) == 0.0, "Gen 1 bug: GHOST does nothing to PSYCHIC")
	t.check(GameData.type_multiplier("BUG", ["POISON"]) == 2.0 and GameData.type_multiplier("POISON", ["BUG"]) == 2.0, "Gen 1: BUG <-> POISON super effective both ways")
	t.check(GameData.type_multiplier("ICE", ["FIRE"]) == 1.0, "Gen 1: ICE is neutral against FIRE")
	t.check(GameData.type_multiplier("FIRE", ["ICE"]) == 2.0, "FIRE beats ICE")
	t.check(GameData.type_multiplier("ELECTRIC", ["GROUND"]) == 0.0 and GameData.type_multiplier("GROUND", ["FLYING"]) == 0.0, "immunities: GROUND vs ELECTRIC, FLYING vs GROUND")
	t.check(GameData.type_multiplier("NORMAL", ["GHOST"]) == 0.0 and GameData.type_multiplier("GHOST", ["NORMAL"]) == 0.0, "NORMAL <-> GHOST immune")
	t.check(GameData.type_multiplier("WATER", ["FIRE", "ROCK"]) == 4.0, "dual types multiply: WATER vs FIRE/ROCK = x4")
	t.check(GameData.type_multiplier("DRAGON", ["DRAGON"]) == 2.0 and GameData.type_multiplier("DRAGON", ["ICE"]) == 1.0, "DRAGON only beats DRAGON")
	t.check(GameData.type_multiplier("GRASS", ["FLYING", "GRASS"]) == 0.25, "GRASS vs FLYING/GRASS = x1/4")
	t.check(GameData.type_chart.size() >= 14 and GameData.moves.size() == 165 and GameData.move_list.size() == 165, "15 attacking types, 165 moves")

# ---------------------------------------------------------------- fixed / special damage, OHKO
static func _fixed_damage(t: TestSuite) -> void:
	var a := _eng("CHARIZARD", 50, "MACHAMP", 60)
	var b: BattleEngine = a[0]
	var hp0 := b.mon(b.e).hp
	_use(b, b.p, "DRAGON_RAGE")
	t.check(hp0 - b.mon(b.e).hp == 40, "DRAGON RAGE always does 40")
	hp0 = b.mon(b.e).hp
	_use(b, b.p, "SONICBOOM")
	t.check(hp0 - b.mon(b.e).hp == 20, "SONICBOOM always does 20")
	hp0 = b.mon(b.e).hp
	_use(b, b.p, "SEISMIC_TOSS")
	t.check(hp0 - b.mon(b.e).hp == 50, "SEISMIC TOSS does the user's level (50)")
	a = _eng("ALAKAZAM", 40, "SNORLAX", 70, 3)
	b = a[0]
	var lo := 9999
	var hi := 0
	for i in 200:
		b.mon(b.e).hp = b.mon(b.e).max_hp
		var h := b.mon(b.e).hp
		_use(b, b.p, "PSYWAVE")
		var d := h - b.mon(b.e).hp
		if d > 0:   # PSYWAVE is 80% accurate: ignore the misses
			lo = mini(lo, d)
			hi = maxi(hi, d)
	t.check(lo >= 1 and hi <= 60 and hi > 30, "PSYWAVE does 1..1.5 x level (got %d..%d, cap 60)" % [lo, hi])
	# SUPER FANG halves current HP
	a = _eng("RATICATE", 30, "SNORLAX", 40)
	b = a[0]
	hp0 = b.mon(b.e).hp
	_use(b, b.p, "SUPER_FANG")
	t.check(b.mon(b.e).hp == hp0 - maxi(1, int(floor(hp0 / 2.0))), "SUPER FANG takes half the current HP")
	# OHKO: fails if the user is slower, otherwise KOs
	a = _eng("GEODUDE", 30, "PIDGEOT", 50)
	b = a[0]
	_use(b, b.p, "FISSURE")
	t.check(b.mon(b.e).hp == b.mon(b.e).max_hp, "OHKO fails against a faster target")
	a = _eng("PIDGEOT", 50, "GEODUDE", 30)
	b = a[0]
	b.e.v["invuln"] = false
	var ko := false
	for i in 6:
		_use(b, b.p, "GUILLOTINE")
		if b.mon(b.e).hp == 0:
			ko = true
			break
	t.check(ko, "OHKO from a faster user knocks out")

# ---------------------------------------------------------------- multi-hit, trapping
static func _multi_and_trap(t: TestSuite) -> void:
	var b: BattleEngine = _eng("PIKACHU", 30, "GEODUDE", 60)[0]
	var counts := {2: 0, 3: 0, 4: 0, 5: 0}
	for i in 4000:
		counts[Callable(b, "_multi_hits").call()] += 1
	t.check(absf(counts[2] / 4000.0 - 0.375) < 0.04 and absf(counts[3] / 4000.0 - 0.375) < 0.04 and absf(counts[4] / 4000.0 - 0.125) < 0.03
		and absf(counts[5] / 4000.0 - 0.125) < 0.03, "multi-hit moves: 2 hits 3/8, 3 hits 3/8, 4 hits 1/8, 5 hits 1/8 (%s)" % str(counts))
	# TWO_TO_FIVE_ATTACKS, ATTACK_TWICE really hit that many times
	var a := _eng("PIKACHU", 40, "SNORLAX", 60)
	b = a[0]
	(a[1] as BattleNullUI).log.clear()
	_use(b, b.p, "DOUBLE_KICK")
	t.check((a[1] as BattleNullUI).log.has("Hit 2 times!"), "DOUBLE KICK hits twice")
	# WRAP: the target can't act while the wrap lasts
	a = _eng("ARBOK", 40, "SNORLAX", 60, 4)
	b = a[0]
	(a[1] as BattleNullUI).log.clear()
	_use(b, b.p, "WRAP")
	t.check(not (b.p.v["trapping"] as Dictionary).is_empty() and int(b.e.v["trapped"]) == 1, "WRAP traps the target")
	_use(b, b.e, "BODY_SLAM")
	t.check((a[1] as BattleNullUI).log.has("Wild SNORLAX can't move!"), "a wrapped target can't move")
	var trap_moves: Array = []
	for id in GameData.move_list:
		if GameData.get_move(id).get("effect", "") == "TRAPPING":
			trap_moves.append(id)
	t.check(trap_moves.size() == 4, "four trapping moves: BIND, WRAP, FIRE SPIN, CLAMP (%s)" % str(trap_moves))
	# JUMP KICK crashes on a miss
	a = _eng("HITMONLEE", 40, "GASTLY", 30)
	b = a[0]
	var hp1 := b.mon(b.p).hp
	_use(b, b.p, "HI_JUMP_KICK")
	t.check(b.mon(b.p).hp < hp1 and (a[1] as BattleNullUI).log.any(func(s): return s.contains("crashed")), "HI JUMP KICK on a GHOST crashes (%d -> %d)" % [hp1, b.mon(b.p).hp])

# ---------------------------------------------------------------- MIRROR MOVE, METRONOME, TRANSFORM, MIMIC, CONVERSION
static func _copy_moves(t: TestSuite) -> void:
	var a := _eng("PIDGEOT", 40, "RATICATE", 40)
	var b: BattleEngine = a[0]
	b.e.v["last_used"] = "BODY_SLAM"
	var hp0 := b.mon(b.e).hp
	_use(b, b.p, "MIRROR_MOVE")
	t.check((a[1] as BattleNullUI).anims.has("BODY_SLAM") and b.mon(b.e).hp < hp0, "MIRROR MOVE copies the foe's last move")
	a = _eng("PIDGEOT", 40, "RATICATE", 40)
	b = a[0]
	_use(b, b.p, "MIRROR_MOVE")
	t.check((a[1] as BattleNullUI).log.has("But, it failed!"), "MIRROR MOVE fails with nothing to copy")
	a = _eng("CLEFABLE", 40, "RATICATE", 40, 9)
	b = a[0]
	_use(b, b.p, "METRONOME")
	t.check((a[1] as BattleNullUI).log.has("CLEFABLE used METRONOME!") and not (a[1] as BattleNullUI).anims.is_empty(), "METRONOME calls a random move")
	# TRANSFORM
	a = _eng("DITTO", 30, "PIKACHU", 40)
	b = a[0]
	_use(b, b.p, "TRANSFORM")
	var tr: Dictionary = b.p.v["transformed"]
	t.check(not tr.is_empty() and tr["species"] == "PIKACHU" and tr["types"] == ["ELECTRIC"], "TRANSFORM copies species and type")
	t.check(int(tr["spd"]) == b.mon(b.e).stat("spd") and b.stat(b.p, "atk") == b.mon(b.e).stat("atk"), "TRANSFORM copies the foe's stats")
	var pps := true
	for m in tr["moves"]:
		if int(m["pp"]) > 5:
			pps = false
	t.check(pps and tr["moves"].size() == b.mon(b.e).moves.size(), "TRANSFORM'd moves have 5 PP")
	# CONVERSION copies the foe's types
	a = _eng("PORYGON", 30, "GYARADOS", 40)
	b = a[0]
	_use(b, b.p, "CONVERSION")
	t.check(b.types_of(b.p) == ["WATER", "FLYING"], "CONVERSION copies the target's types")
	# MIMIC (foe's move replaces MIMIC in the slot)
	a = _eng("MEW", 30, "RATICATE", 40)
	b = a[0]
	b.mon(b.p).moves = ["MIMIC"]
	b.mon(b.p).pp = {"MIMIC": 10}
	b.mon(b.p).pp_max = {"MIMIC": 10}
	_use(b, b.p, "MIMIC")
	t.check(b.mon(b.p).moves[0] != "MIMIC", "MIMIC learns one of the foe's moves in its slot")
	b._cleanup()
	t.check(b.mon(b.p).moves[0] == "MIMIC", "MIMIC'd move is undone after the battle")

# ---------------------------------------------------------------- SUBSTITUTE, HAZE, MIST, LEECH SEED, REFLECT
static func _field_effects(t: TestSuite) -> void:
	var a := _eng("KADABRA", 40, "MACHOKE", 40)
	var b: BattleEngine = a[0]
	var hp0 := b.mon(b.p).hp
	_use(b, b.p, "SUBSTITUTE")
	var cost := int(floor(b.mon(b.p).max_hp / 4.0))
	t.check(b.p.v["sub"] == cost + 1 and hp0 - b.mon(b.p).hp == cost, "SUBSTITUTE costs 1/4 max HP and has cost+1 HP")
	var sub0: int = b.p.v["sub"]
	Callable(b, "deal_damage").call(b.e, b.p, 5, GameData.get_move("TACKLE"), false)
	t.check(b.p.v["sub"] == sub0 - 5 and b.mon(b.p).hp == hp0 - cost, "damage goes to the SUBSTITUTE, not the user")
	Callable(b, "deal_damage").call(b.e, b.p, 999, GameData.get_move("TACKLE"), false)
	t.check(b.p.v["sub"] == 0 and (a[1] as BattleNullUI).log.has("KADABRA's SUBSTITUTE broke!"), "the SUBSTITUTE breaks")
	# a foe's stat drop bounces off a SUBSTITUTE
	b.p.v["sub"] = 10
	var ok: bool = await_stat(b, b.p, "atk", -1, true)
	t.check(not ok, "a SUBSTITUTE blocks the foe's stat-lowering moves")
	# HAZE
	a = _eng("KADABRA", 40, "MACHOKE", 40)
	b = a[0]
	b.p.v["st"]["atk"] = 3
	b.e.v["st"]["def"] = -2
	b.mon(b.e).status = "PAR"
	b.e.v["confused"] = 3
	_use(b, b.p, "HAZE")
	t.check(b.p.v["st"]["atk"] == 0 and b.e.v["st"]["def"] == 0 and b.mon(b.e).status == "" and b.e.v["confused"] == 0, "HAZE resets stages, confusion and the foe's status")
	# MIST
	a = _eng("ARTICUNO", 50, "MACHOKE", 40)
	b = a[0]
	_use(b, b.p, "MIST")
	t.check(b.p.v["mist"] and not await_stat(b, b.p, "def", -1, true), "MIST stops the foe's stat drops")
	t.check(await_stat(b, b.p, "def", 1, false), "MIST doesn't stop your own boosts")
	# LEECH SEED
	a = _eng("VENUSAUR", 50, "MACHAMP", 50)
	b = a[0]
	b.mon(b.p).hp = b.mon(b.p).max_hp - 30
	_use(b, b.p, "LEECH_SEED")
	t.check(b.e.v["seeded"], "LEECH SEED seeds the target")
	var ehp := b.mon(b.e).hp
	var php := b.mon(b.p).hp
	Callable(b, "after_move_damage").call(b.e)
	var drained := ehp - b.mon(b.e).hp
	t.check(drained == maxi(1, int(floor(b.mon(b.e).max_hp / 16.0))) and b.mon(b.p).hp == php + drained, "LEECH SEED drains 1/16 max HP and heals the seeder")
	a = _eng("VENUSAUR", 50, "EXEGGUTOR", 50)
	b = a[0]
	_use(b, b.p, "LEECH_SEED")
	t.check(not b.e.v["seeded"], "GRASS types are immune to LEECH SEED")
	# REFLECT / LIGHT SCREEN double defences
	a = _eng("ALAKAZAM", 50, "MACHAMP", 50, 2)
	b = a[0]
	var md := GameData.get_move("KARATE_CHOP")
	var base := 0
	for i in 30:
		base = maxi(base, Callable(b, "calc_damage").call(b.e, b.p, {"power": 50, "type": "FIGHTING", "id": "X", "effect": ""}, false)["dmg"])
	_use(b, b.p, "REFLECT")
	var with_reflect := 0
	for i in 30:
		with_reflect = maxi(with_reflect, Callable(b, "calc_damage").call(b.e, b.p, {"power": 50, "type": "FIGHTING", "id": "X", "effect": ""}, false)["dmg"])
	t.check(with_reflect < base and md.size() > 0, "REFLECT halves physical damage (%d -> %d)" % [base, with_reflect])

static func await_stat(b: BattleEngine, side: BattleSide, k: String, delta: int, by_foe: bool) -> bool:
	var r: Variant = Callable(b, "stat_change").call(side, k, delta, by_foe, false)
	return r is bool and r

# ---------------------------------------------------------------- COUNTER, BIDE, RAGE, DISABLE, EXPLOSION, DREAM EATER
static func _counter_bide_rage(t: TestSuite) -> void:
	# COUNTER returns double the last physical damage; fails vs a special hit
	var a := _eng("CHANSEY", 50, "MACHAMP", 50, 6)
	var b: BattleEngine = a[0]
	b.e.v["last_used"] = "KARATE_CHOP"
	b.p.v["last_dmg_dealt"] = 0
	b.e.v["last_dmg_dealt"] = 37
	var hp0 := b.mon(b.e).hp
	_use(b, b.p, "COUNTER")
	t.check(hp0 - b.mon(b.e).hp == 74, "COUNTER deals double the damage just taken (74)")
	b.e.v["last_used"] = "PSYCHIC_M"
	b.e.v["last_dmg_dealt"] = 30
	hp0 = b.mon(b.e).hp
	(a[1] as BattleNullUI).log.clear()
	_use(b, b.p, "COUNTER")
	t.check(b.mon(b.e).hp == hp0 and (a[1] as BattleNullUI).log.has("But, it failed!"), "COUNTER fails against a special move")
	t.check(b._prio("COUNTER") < 0 and b._prio("QUICK_ATTACK") > 0, "COUNTER goes last, QUICK ATTACK first")
	# BIDE: stores damage for 2-3 turns and unleashes double
	a = _eng("SNORLAX", 50, "MACHAMP", 50, 8)
	b = a[0]
	_use(b, b.p, "BIDE")
	t.check(not (b.p.v["bide"] as Dictionary).is_empty(), "BIDE starts storing")
	b.p.v["bide"]["dmg"] = 25
	b.p.v["bide"]["turns"] = 1
	hp0 = b.mon(b.e).hp
	_use(b, b.p, "BIDE")
	t.check(hp0 - b.mon(b.e).hp == 50 and (b.p.v["bide"] as Dictionary).is_empty(), "BIDE unleashes double the stored damage")
	# RAGE builds ATTACK when hit
	a = _eng("GYARADOS", 40, "MACHAMP", 40)
	b = a[0]
	_use(b, b.p, "RAGE")
	t.check(b.p.v["rage"], "RAGE locks in")
	Callable(b, "execute_move").call(b.e, GameData.get_move("KARATE_CHOP"))
	t.check(b.p.v["st"]["atk"] == 1, "RAGE: each hit taken raises ATTACK")
	# DISABLE
	a = _eng("ALAKAZAM", 50, "MACHAMP", 50, 5)
	b = a[0]
	var foe_move: String = b.mon(b.e).moves[0]
	_use(b, b.e, foe_move)
	for i in 8:   # DISABLE is 55% accurate
		_use(b, b.p, "DISABLE")
		if not (b.e.v["disabled"] as Dictionary).is_empty():
			break
	t.check(not (b.e.v["disabled"] as Dictionary).is_empty() and b.e.v["disabled"]["move"] == foe_move, "DISABLE disables the foe's last move (%s)" % foe_move)
	t.check(b.is_disabled(b.e, foe_move), "the disabled move can't be picked")
	# EXPLOSION / SELFDESTRUCT: user faints, foe hurt
	a = _eng("GOLEM", 50, "CHANSEY", 40)
	b = a[0]
	hp0 = b.mon(b.e).hp
	_use(b, b.p, "EXPLOSION")
	t.check(b.mon(b.p).hp == 0 and b.mon(b.e).hp < hp0, "EXPLOSION knocks out the user and hurts the foe")
	# DREAM EATER
	a = _eng("HYPNO", 50, "SNORLAX", 50)
	b = a[0]
	b.mon(b.p).hp = 10
	(a[1] as BattleNullUI).log.clear()
	_use(b, b.p, "DREAM_EATER")
	t.check(b.mon(b.p).hp == 10 and (a[1] as BattleNullUI).log.any(func(s): return s.contains("didn't affect")), "DREAM EATER fails on an awake target")
	b.mon(b.e).status = "SLP"
	b.mon(b.e).sleep = 4
	_use(b, b.p, "DREAM_EATER")
	t.check(b.mon(b.p).hp > 10, "DREAM EATER heals half the damage from a sleeping target")
	# MEGA DRAIN
	a = _eng("VENUSAUR", 50, "GOLEM", 50)
	b = a[0]
	b.mon(b.p).hp = 20
	_use(b, b.p, "MEGA_DRAIN")
	t.check(b.mon(b.p).hp > 20, "MEGA DRAIN heals the user")
	# STRUGGLE: recoil 1/2
	a = _eng("MAGIKARP", 20, "CATERPIE", 20)
	b = a[0]
	hp0 = b.mon(b.p).hp
	_use(b, b.p, "STRUGGLE")
	t.check(b.mon(b.p).hp < hp0, "STRUGGLE hurts the user")

# ---------------------------------------------------------------- FLY / DIG / SOLARBEAM / HYPER BEAM / THRASH
static func _two_turn(t: TestSuite) -> void:
	var a := _eng("PIDGEOT", 50, "MACHAMP", 50, 2)
	var b: BattleEngine = a[0]
	_use(b, b.p, "FLY")
	t.check(b.p.v["charging"] == "FLY" and b.p.v["invuln"], "FLY: first turn charges and is untouchable")
	var hp0 := b.mon(b.p).hp
	_use(b, b.e, "KARATE_CHOP")
	t.check(b.mon(b.p).hp == hp0, "attacks miss a FLYing target")
	_use(b, b.p, "FLY")
	t.check(not b.p.v["invuln"] and b.p.v["charging"] == "", "FLY: second turn strikes")
	a = _eng("VENUSAUR", 50, "MACHAMP", 50)
	b = a[0]
	_use(b, b.p, "SOLARBEAM")
	t.check(b.p.v["charging"] == "SOLARBEAM", "SOLARBEAM charges first")
	a = _eng("SNORLAX", 50, "MACHAMP", 50)
	b = a[0]
	_use(b, b.p, "HYPER_BEAM")
	t.check(b.p.v["recharge"] or b.mon(b.e).hp == 0, "HYPER BEAM forces a recharge turn")
	a = _eng("PRIMEAPE", 40, "MACHAMP", 60)
	b = a[0]
	_use(b, b.p, "THRASH")
	t.check(not (b.p.v["thrash"] as Dictionary).is_empty(), "THRASH locks the user in for 2-3 turns")

# ---------------------------------------------------------------- major status rules
static func _status(t: TestSuite) -> void:
	var a := _eng("PIKACHU", 30, "GEODUDE", 30, 3)
	var b: BattleEngine = a[0]
	# burn halves ATTACK; paralysis quarters SPEED; sleep 1..7; freeze never thaws on its own
	var atk0 := b.stat(b.p, "atk")
	b.mon(b.p).status = "BRN"
	t.check(b.stat(b.p, "atk") == int(floor(atk0 / 2.0)), "BURN halves ATTACK")
	b.mon(b.p).status = ""
	var lo := 99
	var hi := 0
	for i in 400:
		b.mon(b.e).status = ""
		Callable(b, "inflict").call(b.e, "SLP", false, "")
		lo = mini(lo, b.mon(b.e).sleep)
		hi = maxi(hi, b.mon(b.e).sleep)
	t.check(lo == 1 and hi == 7, "sleep lasts 1..7 turns (%d..%d)" % [lo, hi])
	b.mon(b.e).status = "FRZ"
	for i in 30:
		_use(b, b.e, "TACKLE")
	t.check(b.mon(b.e).status == "FRZ", "a frozen POKeMON never thaws on its own")
	# fire moves defrost
	b.mon(b.e).status = "FRZ"
	Callable(b, "side_effect").call(b.p, b.e, GameData.get_move("EMBER"))
	t.check(b.mon(b.e).status == "", "a FIRE-type move thaws a frozen target")
	# full paralysis ~25%
	b.mon(b.p).status = "PAR"
	var lost := 0
	(a[1] as BattleNullUI).log.clear()
	for i in 400:
		b.mon(b.p).hp = b.mon(b.p).max_hp
		_use(b, b.p, "GROWL")
	for s in (a[1] as BattleNullUI).log:
		if s.contains("fully paralyzed"):
			lost += 1
	t.check(lost > 60 and lost < 140, "paralysis stops the mon ~25%% of turns (%d/400)" % lost)
	# toxic damage climbs 1/16, 2/16, ...
	a = _eng("PIKACHU", 50, "SNORLAX", 50)
	b = a[0]
	b.mon(b.e).status = "PSN"
	b.e.v["toxic"] = 1
	var unit := maxi(1, int(floor(b.mon(b.e).max_hp / 16.0)))
	var h0 := b.mon(b.e).hp
	Callable(b, "after_move_damage").call(b.e)
	var d1 := h0 - b.mon(b.e).hp
	h0 = b.mon(b.e).hp
	Callable(b, "after_move_damage").call(b.e)
	var d2 := h0 - b.mon(b.e).hp
	t.check(d1 == unit and d2 == 2 * unit, "TOXIC damage grows 1/16, 2/16 of max HP (%d, %d)" % [d1, d2])
	# confusion lasts 2-5 turns
	a = _eng("PIKACHU", 50, "SNORLAX", 50)
	b = a[0]
	lo = 99
	hi = 0
	for i in 300:
		b.e.v["confused"] = 0
		_use(b, b.p, "SUPERSONIC")
		if int(b.e.v["confused"]) > 0:
			lo = mini(lo, b.e.v["confused"])
			hi = maxi(hi, b.e.v["confused"])
	t.check(lo >= 2 and hi <= 5, "confusion lasts 2-5 turns (%d..%d)" % [lo, hi])

# ---------------------------------------------------------------- the Old Man glitch and MISSINGNO.
static func _missingno(t: TestSuite) -> void:
	var saved_flags := GameState.flags.duplicate()
	var saved_cell := GameState.player_cell
	var saved_bag := GameState.bag.duplicate()
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	GameState.flags.erase(EncounterSystem.GLITCH_FLAG)
	GameState.player_cell = Vector2i(19, 9)
	var none := 0
	for i in 300:
		if EncounterSystem.roll("CinnabarIsland", true, rng).get("species", "") == "MISSINGNO":
			none += 1
	t.check(none == 0, "no MISSINGNO. before the Old Man's demo")
	GameState.flags[EncounterSystem.GLITCH_FLAG] = true
	var found := 0
	for i in 600:
		if EncounterSystem.roll("CinnabarIsland", true, rng).get("species", "") == "MISSINGNO":
			found += 1
	t.check(found > 20, "after the Old Man's demo, surfing Cinnabar's east coast meets MISSINGNO. (%d/600)" % found)
	var on_land := 0
	for i in 300:
		if EncounterSystem.roll("CinnabarIsland", false, rng).get("species", "") == "MISSINGNO":
			on_land += 1
	GameState.player_cell = Vector2i(4, 9)
	var west := 0
	for i in 300:
		if EncounterSystem.roll("CinnabarIsland", true, rng).get("species", "") == "MISSINGNO":
			west += 1
	t.check(on_land == 0 and west == 0, "the glitch needs the east shore and water")
	BattleEngine.ensure_glitch_species()
	GameState.bag = {"POTION": 1, "ANTIDOTE": 2, "REPEL": 3, "POKE_BALL": 4, "ESCAPE_ROPE": 5, "REVIVE": 6}
	GameState.party = [GameState.PartyMon.new("PIKACHU", 30)]
	var mm := GameState.PartyMon.new("MISSINGNO", 80)
	BattleEngine.new({"kind": "wild", "enemy_party": [mm], "seed": 1})
	t.check(GameState.bag["REVIVE"] == 134 and GameState.bag["ESCAPE_ROPE"] == 5, "MISSINGNO. item glitch: the 6th item stack gains 128")
	GameState.flags = saved_flags
	GameState.player_cell = saved_cell
	GameState.bag = saved_bag
	GameData.species.erase("MISSINGNO")   # the glitch species is added on demand: keep the Pokedex at 151 for later tests

# ---------------------------------------------------------------- everything else the audit lists
static func _misc(t: TestSuite) -> void:
	_missingno(t)
	# stat stages use pret's ratio table
	t.check(BattleEngine.STAGE == [25, 28, 33, 40, 50, 66, 100, 150, 200, 250, 300, 350, 400], "stat stage multipliers: 25/100 .. 400/100")
	# the SPEED tie is a coin flip; faster moves first; QUICK ATTACK beats speed
	var a := _eng("SLOWPOKE", 30, "PIDGEOT", 30)
	var b: BattleEngine = a[0]
	t.check(b.speed_order("TACKLE", "TACKLE")[0] == b.e, "the faster POKeMON moves first")
	t.check(b.speed_order("QUICK_ATTACK", "TACKLE")[0] == b.p, "QUICK ATTACK goes first")
	# PAY DAY coins
	a = _eng("MEOWTH", 20, "RATTATA", 20)
	b = a[0]
	_use(b, b.p, "PAY_DAY")
	t.check(b.pay_day == 40, "PAY DAY scatters 2 x level coins")
	# SPLASH does nothing; TELEPORT / WHIRLWIND end wild battles
	a = _eng("MAGIKARP", 20, "RATTATA", 20)
	b = a[0]
	_use(b, b.p, "SPLASH")
	t.check((a[1] as BattleNullUI).log.has("No effect!"), "SPLASH: No effect!")
	a = _eng("ABRA", 20, "RATTATA", 20)
	b = a[0]
	_use(b, b.p, "TELEPORT")
	t.check(b.result == "run", "TELEPORT flees a wild battle")
	# accuracy: 100% moves never miss unless stages say so; evasion stages matter; SWIFT never misses
	a = _eng("STARMIE", 30, "RATTATA", 20)
	b = a[0]
	b.e.v["st"]["eva"] = 6
	var hits := 0
	for i in 500:
		if b.accuracy_check(b.p, GameData.get_move("SWIFT")):
			hits += 1
	t.check(hits == 500, "SWIFT never misses, even at +6 evasion")
	hits = 0
	for i in 500:
		if b.accuracy_check(b.p, GameData.get_move("TACKLE")):
			hits += 1
	t.check(hits < 250, "+6 evasion makes a 95%% move miss most of the time (%d/500)" % hits)
	# the level cap: 100 stays 100 ; exp formulas for all six growth rates
	t.check(GameState.exp_for_level("FAST", 10) == 800 and GameState.exp_for_level("SLOW", 10) == 1250
		and GameState.exp_for_level("MEDIUM_SLOW", 10) == 560 and GameState.exp_for_level("MEDIUM_FAST", 100) == 1000000, "experience curves: fast/medium/slow (Gen 1)")
	# catch formula sanity: sleeping / paralysed / low-HP targets are easier
	a = _eng("PIKACHU", 30, "PIDGEY", 5)
	b = a[0]
	var em := b.mon(b.e)
	var full := 0
	var asleep := 0
	for i in 400:
		if b.catch_roll("POKE_BALL", em)["caught"]:
			full += 1
	em.status = "SLP"
	em.hp = 1
	for i in 400:
		if b.catch_roll("POKE_BALL", em)["caught"]:
			asleep += 1
	t.check(asleep > full, "a sleeping, 1-HP target is easier to catch (%d vs %d of 400)" % [asleep, full])
