class_name BattleEngine
extends RefCounted
## Generation I battle engine, ported from upstream src/game/battle.js (+ the
## battle parts of battleflow.js / bag.js). Runs as an async coroutine and
## drives a UI object through the same protocol upstream's BattleScene
## implements (msg, anim, sync_hp, hit_flash, faint, ...). BattleScene.gd is
## the 3D UI; BattleNullUI.gd is a scripted, instant UI used by the tests.
##
## Options (`o`):
##   kind: "wild" | "trainer"
##   enemy_party: Array[GameState.PartyMon]
##   trainer: {cls, n, display_name, money, win_text, lose_text}  (trainer battles)
##   trainer_items: Array[String]  (enemy trainer's healing / X items)
##   no_run, no_catch, no_exp, no_items: bool
##   seed: int  (deterministic RNG for tests / screenshots)
## Results: "win", "lose", "run", "caught", "fled".

const STAGE := [25, 28, 33, 40, 50, 66, 100, 150, 200, 250, 300, 350, 400]
const PHYSICAL := ["NORMAL", "FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "BIRD"]
const HIGH_CRIT := ["KARATE_CHOP", "RAZOR_LEAF", "CRABHAMMER", "SLASH"]
const STAT_NAME := {"atk": "ATTACK", "def": "DEFENSE", "spd": "SPEED", "spc": "SPECIAL", "acc": "accuracy", "eva": "evade"}
const BADGE_BOOST := {"atk": "BOULDERBADGE", "def": "THUNDERBADGE", "spd": "SOULBADGE", "spc": "VOLCANOBADGE"}

## Items (upstream src/game/bag.js)
const HEAL := {"POTION": 20, "SUPER_POTION": 50, "HYPER_POTION": 200, "MAX_POTION": 9999, "FULL_RESTORE": 9999,
	"FRESH_WATER": 50, "SODA_POP": 60, "LEMONADE": 80}
const CURE := {"ANTIDOTE": ["PSN"], "BURN_HEAL": ["BRN"], "ICE_HEAL": ["FRZ"], "AWAKENING": ["SLP"], "PARLYZ_HEAL": ["PAR"],
	"FULL_HEAL": ["PSN", "BRN", "FRZ", "SLP", "PAR"], "FULL_RESTORE": ["PSN", "BRN", "FRZ", "SLP", "PAR"]}
const KEY_ITEMS := ["TOWN_MAP", "BICYCLE", "SURFBOARD", "POKEDEX", "OLD_AMBER", "DOME_FOSSIL", "HELIX_FOSSIL", "SECRET_KEY",
	"BIKE_VOUCHER", "CARD_KEY", "S_S_TICKET", "GOLD_TEETH", "COIN_CASE", "OAKS_PARCEL", "ITEMFINDER", "SILPH_SCOPE", "LIFT_KEY",
	"EXP_ALL", "OLD_ROD", "GOOD_ROD", "SUPER_ROD"]
const X_ITEM := {"X_ATTACK": "atk", "X_DEFEND": "def", "X_SPEED": "spd", "X_SPECIAL": "spc", "X_ACCURACY": "acc"}

## Trainer data (upstream battleflow.js)
const LEADERS := {"BROCK": "BROCK", "MISTY": "MISTY", "LT_SURGE": "LT.SURGE", "ERIKA": "ERIKA", "KOGA": "KOGA",
	"SABRINA": "SABRINA", "BLAINE": "BLAINE", "GIOVANNI": "GIOVANNI", "LORELEI": "LORELEI", "BRUNO": "BRUNO",
	"AGATHA": "AGATHA", "LANCE": "LANCE"}
const TRAINER_ITEMS := {"MISTY": ["X_DEFEND"], "LT_SURGE": ["X_SPEED"], "ERIKA": ["SUPER_POTION"], "KOGA": ["X_ATTACK"],
	"SABRINA": ["HYPER_POTION"], "BLAINE": ["SUPER_POTION"], "GIOVANNI": ["GUARD_SPEC"], "LORELEI": ["SUPER_POTION"],
	"BRUNO": ["X_DEFEND"], "AGATHA": ["SUPER_POTION"], "LANCE": ["HYPER_POTION"], "RIVAL2": ["POTION"], "RIVAL3": ["FULL_RESTORE"]}
const LONE_MOVES := {"BROCK": "BIDE", "MISTY": "BUBBLEBEAM", "LT_SURGE": "THUNDERBOLT", "ERIKA": "MEGA_DRAIN",
	"KOGA": "TOXIC", "SABRINA": "PSYWAVE", "BLAINE": "FIRE_BLAST", "GIOVANNI": "FISSURE"}

var o: Dictionary
var wild := true
var trainer: Dictionary = {}
var p := BattleSide.new()
var e := BattleSide.new()
var participants: Array = []
var run_attempts := 0
var pay_day := 0
var result := ""
var turn := 0
var trainer_items: Array = []
var safari := false
var safari_bait := 0
var safari_rock := 0
var ui: Object
var rng := RandomNumberGenerator.new()

func _init(opts: Dictionary) -> void:
	o = opts
	wild = str(o.get("kind", "wild")) == "wild"
	trainer = o.get("trainer", {})
	p.party = GameState.party
	p.is_player = true
	p.v = new_vol()
	e.party = o.get("enemy_party", [])
	e.v = new_vol()
	for i in p.party.size():
		if not p.party[i].is_fainted():
			p.idx = i
			break
	trainer_items = (o.get("trainer_items", []) as Array).duplicate()
	safari = o.get("safari", false)
	if o.has("seed"):
		rng.seed = int(o["seed"])
	else:
		rng.randomize()

static func new_vol() -> Dictionary:
	return {"st": {"atk": 0, "def": 0, "spd": 0, "spc": 0, "acc": 0, "eva": 0}, "confused": 0, "flinch": false,
		"recharge": false, "charging": "", "invuln": false, "trapping": {}, "trapped": 0, "thrash": {}, "bide": {},
		"rage": false, "rage_started": false, "disabled": {}, "seeded": false, "toxic": 0, "sub": 0, "focus": false,
		"mist": false, "reflect": false, "light_screen": false, "transformed": {}, "mimic": {}, "last_move": "",
		"last_used": "", "last_dmg_dealt": 0, "types": [], "moved": false, "xacc": false}

# ------------------------------------------------------------------ helpers
func rnd(n: int) -> int:
	return rng.randi_range(0, n - 1) if n > 0 else 0

func chance(pr: float) -> bool:
	return rng.randf() < pr

func mon(side: BattleSide) -> GameState.PartyMon:
	return side.party[side.idx]

func foe(side: BattleSide) -> BattleSide:
	return e if side == p else p

func mdata(id: String) -> Dictionary:
	var md := GameData.get_move(id)
	return md if not md.is_empty() else GameData.get_move("STRUGGLE")

static func move_name(id: String) -> String:
	return str(GameData.get_move(id).get("name", id))

func label(side: BattleSide) -> String:
	var m := mon(side)
	if side.is_player:
		return m.display_name()
	return ("Wild " if wild else "Enemy ") + m.display_name()

func trainer_name() -> String:
	return str(trainer.get("display_name", "The trainer"))

## Effective stat including stage, badge boost and status penalties.
func stat(side: BattleSide, k: String) -> int:
	var m := mon(side)
	var v := side.v
	var tr: Dictionary = v["transformed"]
	var base: int = int(tr[k]) if not tr.is_empty() else m.stat(k)
	var val: int = int(floor(base * STAGE[int(v["st"][k]) + 6] / 100.0))
	if side.is_player and not o.get("no_badge_boost", false):
		var b: String = BADGE_BOOST.get(k, "")
		if b != "" and GameState.badges.has(b):
			val = int(floor(val * 9 / 8.0))
	if k == "spd" and m.status == "PAR":
		val = int(floor(val / 4.0))
	if k == "atk" and m.status == "BRN":
		val = int(floor(val / 2.0))
	return clampi(val, 1, 999)

## Unmodified stat of a side's mon, honouring an earlier TRANSFORM (upstream copies `T.atk` etc.).
func _raw_stat(side: BattleSide, k: String) -> int:
	var tr: Dictionary = side.v["transformed"]
	return int(tr[k]) if not tr.is_empty() else mon(side).stat(k)

## Species whose *base* stats drive the crit roll (a transformed mon uses the copied species).
func atr_species(side: BattleSide) -> String:
	var tr: Dictionary = side.v["transformed"]
	if not tr.is_empty():
		return str(tr.get("species", mon(side).species_id))
	return mon(side).species_id

func types_of(side: BattleSide) -> Array:
	if not (side.v["types"] as Array).is_empty():
		return side.v["types"]
	var tr: Dictionary = side.v["transformed"]
	if not tr.is_empty():
		return tr["types"]
	return mon(side).types()

func type_mult(t: String, def_types: Array) -> float:
	return GameData.type_multiplier(t, def_types)

## Move list as [{id, pp, max}] (a transformed mon uses its copied list).
func move_list(side: BattleSide) -> Array:
	var tr: Dictionary = side.v["transformed"]
	if not tr.is_empty():
		return tr["moves"]
	var m := mon(side)
	var out: Array = []
	for id in m.moves:
		out.append({"id": id, "pp": int(m.pp.get(id, 0)), "max": m.max_pp(id)})
	return out

func use_pp(side: BattleSide, id: String) -> void:
	var tr: Dictionary = side.v["transformed"]
	if not tr.is_empty():
		for x in tr["moves"]:
			if x["id"] == id:
				x["pp"] = maxi(0, int(x["pp"]) - 1)
				return
		return
	var m := mon(side)
	if m.moves.has(id):
		m.pp[id] = maxi(0, int(m.pp.get(id, 0)) - 1)

func is_disabled(side: BattleSide, id: String) -> bool:
	var d: Dictionary = side.v["disabled"]
	return not d.is_empty() and d["move"] == id

func _add_participant(m: GameState.PartyMon) -> void:
	if not participants.has(m):
		participants.append(m)

# ------------------------------------------------------------------ main loop
func run(the_ui: Object) -> String:
	ui = the_ui
	if not wild and LEADERS.has(str(trainer.get("cls", ""))):
		PikachuBuddy.event(PikachuBuddy.GYM_LEADER)   # YELLOW: challenging a gym leader (or the league) pleases PIKACHU
	await ui.intro(self)
	_add_participant(mon(p))
	while true:
		turn += 1
		for s0: BattleSide in [p, e]:
			s0.v["moved"] = false
			s0.v["flinch"] = false
		var p_act: Dictionary = await player_action()
		if p_act["type"] == "run":
			var r: bool = await try_run(false)
			if r:
				return _finish("run")
			var e_act0 := enemy_action()
			if e_act0["type"] == "fight":
				await do_move(e, e_act0["move"])
				if result != "":
					return _finish(result)
			if await check_faints():
				if result != "":
					return result
			continue
		if p_act["type"] == "caught":
			return _finish("caught")
		if p_act["type"] == "fled":
			return _finish("fled")
		if p_act["type"] == "safari":
			if result != "":
				return _finish(result)
			continue
		var e_act := enemy_action()
		if p_act["type"] == "switch":
			await switch_in(p, int(p_act["index"]), true)
		if e_act["type"] == "item":
			await enemy_use_item(e_act["item"])
		var p_move: String = p_act["move"] if p_act["type"] == "fight" else ""
		var e_move: String = e_act["move"] if e_act["type"] == "fight" else ""
		var order: Array = []
		if p_move != "" and e_move != "":
			order = speed_order(p_move, e_move)
		elif p_move != "":
			order = [p]
		elif e_move != "":
			order = [e]
		for side: BattleSide in order:
			var mv: String = p_move if side == p else e_move
			if mon(side).is_fainted() or mon(foe(side)).is_fainted():
				continue
			await do_move(side, mv)
			if result != "":
				return _finish(result)
			if not mon(foe(side)).is_fainted():
				await after_move_damage(side)
			if await check_faints():
				if result != "":
					return result
				break
	return result

func _finish(r: String) -> String:
	result = r
	_cleanup()
	return r

## Restores MIMIC'd moves (upstream resets battle-only move state after a battle).
func _cleanup() -> void:
	for s: BattleSide in [p, e]:
		_undo_mimic(s)

func _undo_mimic(side: BattleSide) -> void:
	var mm: Dictionary = side.v["mimic"]
	if mm.is_empty():
		return
	var m := mon(side)
	var slot: int = mm["slot"]
	if slot < m.moves.size():
		var cur: String = m.moves[slot]
		var left: int = int(m.pp.get(cur, 0))
		m.pp.erase(cur)
		m.pp_max.erase(cur)
		m.moves[slot] = mm["old"]
		m.pp[mm["old"]] = mini(left, int(mm["old_max"]))
		m.pp_max[mm["old"]] = mm["old_max"]
	side.v["mimic"] = {}

func speed_order(pm: String, em: String) -> Array:
	var a := _prio(pm)
	var b := _prio(em)
	if a != b:
		return [p, e] if a > b else [e, p]
	var sp := stat(p, "spd")
	var se := stat(e, "spd")
	if sp != se:
		return [p, e] if sp > se else [e, p]
	return [p, e] if chance(0.5) else [e, p]

func _prio(m: String) -> int:
	if m == "QUICK_ATTACK":
		return 1
	if m == "COUNTER":
		return -1
	return 0

func player_action() -> Dictionary:
	var v := p.v
	var m := mon(p)
	var locked: bool = v["recharge"] or v["charging"] != "" or not (v["thrash"] as Dictionary).is_empty() \
		or not (v["bide"] as Dictionary).is_empty() or (not (v["trapping"] as Dictionary).is_empty() and int(v["trapping"]["turns"]) > 0) or v["rage"]
	if locked:
		var mv := "STRUGGLE"
		if v["charging"] != "":
			mv = v["charging"]
		elif not (v["thrash"] as Dictionary).is_empty():
			mv = v["thrash"]["move"]
		elif not (v["bide"] as Dictionary).is_empty():
			mv = "BIDE"
		elif not (v["trapping"] as Dictionary).is_empty() and int(v["trapping"]["turns"]) > 0:
			mv = v["trapping"]["move"]
		elif v["rage"]:
			mv = "RAGE"
		return {"type": "fight", "move": "_RECHARGE" if v["recharge"] else mv}
	if int(v["trapped"]) > 0:
		return {"type": "fight", "move": "_TRAPPED"}
	while true:
		var act: Dictionary = await ui.choose_action(self)
		match str(act.get("type", "")):
			"fight":
				var moves := move_list(p)
				var all_out := true
				for x in moves:
					if int(x["pp"]) > 0 and not is_disabled(p, x["id"]):
						all_out = false
				if all_out:
					return {"type": "fight", "move": "STRUGGLE"}
				var slot: int = int(act.get("slot", 0))
				if slot < 0 or slot >= moves.size():
					continue
				var mvd: Dictionary = moves[slot]
				var immobile: bool = m.status == "SLP" or m.status == "FRZ"   # the UI auto-picks slot 0 for these
				if int(mvd["pp"]) <= 0 and not immobile:
					await ui.msg("No PP left for this move!")
					continue
				if is_disabled(p, mvd["id"]) and not immobile:
					await ui.msg(move_name(mvd["id"]) + " is disabled!")
					continue
				return {"type": "fight", "move": mvd["id"], "slot": slot}
			"switch":
				if int(act["index"]) == p.idx:
					await ui.msg(m.display_name() + " is already out!")
					continue
				return act
			"item":
				var r: String = await use_item(str(act["item"]), int(act.get("target", -1)))
				if r == "cancel":
					continue
				if r == "caught" or r == "fled":
					return {"type": r}
				return {"type": "item"}
			"run":
				return act
			"safari":
				var sr: String = await safari_action(str(act["what"]))
				if sr != "":
					return {"type": sr}
				return {"type": "safari"}
	return {"type": "run"}

## Weighted move-picking AI (upstream enemyAction).
func enemy_action() -> Dictionary:
	var side := e
	var v := side.v
	if v["recharge"]:
		return {"type": "fight", "move": "_RECHARGE"}
	if v["charging"] != "":
		return {"type": "fight", "move": v["charging"]}
	if not (v["thrash"] as Dictionary).is_empty():
		return {"type": "fight", "move": v["thrash"]["move"]}
	if not (v["bide"] as Dictionary).is_empty():
		return {"type": "fight", "move": "BIDE"}
	if not (v["trapping"] as Dictionary).is_empty() and int(v["trapping"]["turns"]) > 0:
		return {"type": "fight", "move": v["trapping"]["move"]}
	if v["rage"]:
		return {"type": "fight", "move": "RAGE"}
	if int(v["trapped"]) > 0:
		return {"type": "fight", "move": "_TRAPPED"}
	var m := mon(side)
	if not wild and not trainer_items.is_empty() and m.hp < m.max_hp / 4.0 and chance(0.5):
		return {"type": "item", "item": trainer_items.pop_front()}
	var moves: Array = []
	for x in move_list(side):
		if int(x["pp"]) > 0 and not is_disabled(side, x["id"]):
			moves.append(x)
	if moves.is_empty():
		return {"type": "fight", "move": "STRUGGLE"}
	var fm := mon(p)
	var fv := p.v
	var smart := not wild
	var scored: Array = []
	var tot := 0
	for x in moves:
		var md := mdata(x["id"])
		var s := 10
		var eff_s: String = md.get("effect", "")
		if int(md.get("power", 0)) == 0:
			if ["SLEEP", "POISON", "PARALYZE", "CONFUSION"].has(eff_s) and (fm.status != "" or (eff_s == "CONFUSION" and int(fv["confused"]) > 0)):
				s -= 8
			if eff_s == "LEECH_SEED" and (fv["seeded"] or fm.types().has("GRASS")):
				s -= 8
			if eff_s == "HEAL" and m.hp == m.max_hp:
				s -= 8
			if smart and eff_s.contains("_UP") and int(v["st"]["atk"]) > 2:
				s -= 3
		else:
			var tm := type_mult(md.get("type", "NORMAL"), types_of(p))
			if tm == 0.0:
				s -= 9
			elif smart and tm > 1.0:
				s += 6
			elif smart and tm < 1.0:
				s -= 3
			if eff_s == "DREAM_EATER" and fm.status != "SLP":
				s -= 9
			if eff_s == "OHKO" and stat(side, "spd") < stat(p, "spd"):
				s -= 9
		s = maxi(1, s)
		scored.append([x["id"], s])
		tot += s
	var r := rng.randf() * tot
	for c in scored:
		r -= c[1]
		if r <= 0:
			return {"type": "fight", "move": c[0]}
	return {"type": "fight", "move": scored[0][0]}

# ------------------------------------------------------------------ move execution
func do_move(side: BattleSide, move_id: String) -> void:
	var a := mon(side)
	var v := side.v
	var fs := foe(side)
	var nm := label(side)
	v["moved"] = true
	v["last_dmg_dealt"] = 0
	if o.get("ghost", false):
		if side.is_player:
			if a.status != "SLP" and a.status != "FRZ":
				await ui.msg(a.display_name() + " is too frightened to move!")
				return
		else:
			await ui.msg("GHOST: Leave... Leave now...")
			return
	if move_id == "_RECHARGE":
		v["recharge"] = false
		await ui.msg(nm + " must recharge!")
		return
	if a.status == "SLP":
		a.sleep -= 1
		if a.sleep > 0:
			await ui.status_anim(side, "SLP")
			await ui.msg(nm + " is fast asleep!")
			return
		a.status = ""
		await ui.refresh()
		await ui.msg(nm + " woke up!")
		return
	if a.status == "FRZ":
		await ui.status_anim(side, "FRZ")
		await ui.msg(nm + " is frozen solid!")
		return
	if move_id == "_TRAPPED" or int(v["trapped"]) > 0:
		var ft: Dictionary = fs.v["trapping"]
		if not ft.is_empty() and int(ft["turns"]) > 0 and not mon(fs).is_fainted():
			v["trapped"] = 0
			await ui.msg(nm + " can't move!")
			return
		v["trapped"] = 0
		if move_id == "_TRAPPED":
			await ui.msg(nm + " can't move!")
			return
	if v["flinch"]:
		v["flinch"] = false
		await ui.msg(nm + " flinched!")
		return
	var dis: Dictionary = v["disabled"]
	if not dis.is_empty():
		dis["turns"] = int(dis["turns"]) - 1
		if int(dis["turns"]) <= 0:
			v["disabled"] = {}
			await ui.msg(nm + "'s disabled no more!")
	if int(v["confused"]) > 0:
		v["confused"] = int(v["confused"]) - 1
		if int(v["confused"]) <= 0:
			await ui.msg(nm + "'s confused no more!")
		else:
			await ui.status_anim(side, "CONF")
			await ui.msg(nm + " is confused!")
			if chance(0.5):
				var dmg := calc_damage(side, side, {"power": 40, "type": "NORMAL_CONF", "id": "", "effect": ""}, false)["dmg"] as int
				if v["invuln"]:
					await ui.hide_side(side, false)
				_break_lock(v)
				await ui.msg("It hurt itself in its confusion!")
				await apply_damage(side, dmg)
				return
	if a.status == "PAR" and chance(0.25):
		if v["invuln"]:
			await ui.hide_side(side, false)
		_break_lock(v)
		await ui.status_anim(side, "PAR")
		await ui.msg(nm + "'s fully paralyzed!")
		return
	var md := mdata(move_id)
	var continuing: bool = v["charging"] == move_id \
		or (not (v["thrash"] as Dictionary).is_empty() and v["thrash"].get("started", false)) \
		or (not (v["bide"] as Dictionary).is_empty() and v["bide"].get("started", false)) \
		or (not (v["trapping"] as Dictionary).is_empty() and int(v["trapping"].get("turns", 0)) > 0 and v["trapping"].get("started", false)) \
		or (v["rage"] and move_id == "RAGE" and v["rage_started"])
	if not continuing and move_id != "STRUGGLE":
		use_pp(side, move_id)
	fs.v["last_move"] = ""
	v["last_move"] = move_id
	if md.get("effect", "") == "METRONOME":
		await ui.msg(nm + " used METRONOME!", {"auto": 18})
		await ui.anim("METRONOME", side, 0)
		var pool: Array = GameData.move_list.filter(func(x): return x != "METRONOME" and x != "STRUGGLE")
		md = mdata(pool[rnd(pool.size())])
		move_id = md["id"]
	elif md.get("effect", "") == "MIRROR_MOVE":
		await ui.msg(nm + " used MIRROR MOVE!", {"auto": 18})
		var last: String = fs.v["last_used"]
		if last == "" or last == "MIRROR_MOVE":
			await ui.msg("But, it failed!")
			return
		md = mdata(last)
		move_id = md["id"]
	v["last_used"] = move_id
	await execute_move(side, md)

func _break_lock(v: Dictionary) -> void:
	v["charging"] = ""
	v["invuln"] = false
	v["thrash"] = {}
	v["bide"] = {}

func execute_move(side: BattleSide, md: Dictionary) -> void:
	var a := mon(side)
	var v := side.v
	var fs := foe(side)
	var t := mon(fs)
	var tv := fs.v
	var nm := label(side)
	var tname := label(fs)
	var eff: String = md.get("effect", "")
	var mid: String = md["id"]
	if (eff == "CHARGE" or eff == "FLY") and v["charging"] != mid:
		v["charging"] = mid
		await ui.msg(nm + " used " + str(md["name"]) + "!", {"auto": 18})
		var charge_msg: String = {"RAZOR_WIND": " made a whirlwind!", "SOLARBEAM": " took in sunlight!",
			"SKULL_BASH": " lowered its head!", "SKY_ATTACK": " is glowing!", "FLY": " flew up high!", "DIG": " dug a hole!"}.get(mid, " is charging!")
		if mid == "FLY" or mid == "DIG":
			v["invuln"] = true
			await ui.anim(mid + "_CHARGE", side, 0)
			await ui.hide_side(side, true)
		else:
			await ui.anim("CHARGE", side, 0)
		await ui.msg(nm + charge_msg)
		return
	if v["charging"] == mid:
		v["charging"] = ""
		if v["invuln"]:
			v["invuln"] = false
			await ui.hide_side(side, false)
	var thrash_started: bool = not (v["thrash"] as Dictionary).is_empty() and v["thrash"].get("started", false)
	var bide_started: bool = not (v["bide"] as Dictionary).is_empty() and v["bide"].get("started", false)
	if not thrash_started and not bide_started:
		await ui.msg(nm + " used " + str(md["name"]) + "!", {"auto": 18})
	# BIDE
	if eff == "BIDE":
		if (v["bide"] as Dictionary).is_empty():
			v["bide"] = {"turns": 2 + rnd(2), "dmg": 0, "started": true}
			await ui.anim("BIDE", side, 0)
			return
		v["bide"]["turns"] = int(v["bide"]["turns"]) - 1
		if int(v["bide"]["turns"]) > 0:
			await ui.msg(nm + " is storing energy!")
			return
		var bdmg: int = int(v["bide"]["dmg"]) * 2
		v["bide"] = {}
		await ui.msg(nm + " unleashed energy!")
		if bdmg == 0 or t.is_fainted():
			await ui.msg(nm + "'s attack missed!")
			return
		await ui.anim("BIDE_HIT", side, 0)
		await deal_damage(side, fs, bdmg, md, false)
		return
	# status / non-damaging moves
	if int(md.get("power", 0)) == 0 and not ["SPECIAL_DAMAGE", "OHKO", "SUPER_FANG", "BIDE", "COUNTER", "TRAPPING"].has(eff) and mid != "COUNTER":
		await status_move(side, md)
		return
	if not accuracy_check(side, md):
		await ui.dodge(fs)
		await ui.msg(nm + "'s attack missed!")
		if eff == "JUMP_KICK":
			await ui.msg(nm + " kept going and crashed!")
			await apply_damage(side, 1)
		if eff == "EXPLODE":
			a.hp = 0
			await ui.sync_hp(side)
		v["thrash"] = {}
		return
	if mid == "COUNTER":
		var last := mdata(str(tv["last_used"]) if tv["last_used"] != "" else "SPLASH")
		if int(tv["last_dmg_dealt"]) <= 0 or not ["NORMAL", "FIGHTING"].has(last.get("type", "")) or int(last.get("power", 0)) == 0:
			await ui.msg("But, it failed!")
			return
		await ui.anim("COUNTER", side, 0)
		await deal_damage(side, fs, int(tv["last_dmg_dealt"]) * 2, md, false)
		return
	var tm := type_mult(md.get("type", "NORMAL"), types_of(fs))
	if tm == 0.0 and eff != "SPECIAL_DAMAGE" and eff != "SUPER_FANG":
		await ui.msg("It doesn't affect " + tname + "!")
		v["thrash"] = {}
		if eff == "EXPLODE":
			a.hp = 0
			await ui.sync_hp(side)
		return
	if eff == "DREAM_EATER" and t.status != "SLP":
		await ui.msg("It didn't affect " + tname + "!")
		return
	if eff == "OHKO":
		if stat(side, "spd") < stat(fs, "spd"):
			await ui.msg(nm + "'s attack missed!")
			return
		await ui.anim(mid, side, 0)
		await deal_damage(side, fs, t.hp, md, true)
		await ui.msg("One-hit KO!")
		return
	var fixed := -1
	if eff == "SPECIAL_DAMAGE":
		match mid:
			"SONICBOOM": fixed = 20
			"DRAGON_RAGE": fixed = 40
			"PSYWAVE": fixed = 1 + rnd(int(floor(a.level * 1.5)))
			_: fixed = a.level
	if eff == "SUPER_FANG":
		fixed = maxi(1, int(floor(t.hp / 2.0)))
	var hits := 1
	if eff == "TWO_TO_FIVE_ATTACKS":
		hits = _multi_hits()
	if eff == "ATTACK_TWICE" or eff == "TWINEEDLE":
		hits = 2
	if eff == "THRASH_PETAL_DANCE" and (v["thrash"] as Dictionary).is_empty():
		v["thrash"] = {"move": mid, "turns": 2 + rnd(2), "started": true}
	if eff == "TRAPPING":
		var trp: Dictionary = v["trapping"]
		if trp.is_empty() or int(trp["turns"]) <= 0:
			v["trapping"] = {"move": mid, "turns": _multi_hits() - 1, "started": true}
		else:
			trp["turns"] = int(trp["turns"]) - 1
	if eff == "RAGE":
		v["rage"] = true
		v["rage_started"] = true
	var total := 0
	var n := 0
	for h in hits:
		if t.is_fainted():
			break
		await ui.anim(mid, side, h)
		var dmg := 0
		var crit := false
		if fixed >= 0:
			dmg = fixed
		else:
			var r := calc_damage(side, fs, md, true)
			dmg = r["dmg"]
			crit = r["crit"]
		if dmg <= 0 and fixed < 0:
			dmg = 1
		n += 1
		await deal_damage(side, fs, dmg, md, false)
		total += dmg
		if crit:
			await ui.msg("Critical hit!")
		if eff == "TWINEEDLE" and not t.is_fainted() and chance(0.2):
			await inflict(fs, "PSN", true, "")
	if hits > 1:
		await ui.msg("Hit %d times!" % n)
	if fixed < 0 and tm != 1.0 and total > 0:
		await ui.msg("It's super effective!" if tm > 1.0 else "It's not very effective...")
	if eff == "TRAPPING" and not t.is_fainted():
		tv["trapped"] = 1
	if eff == "THRASH_PETAL_DANCE" and not (v["thrash"] as Dictionary).is_empty():
		v["thrash"]["turns"] = int(v["thrash"]["turns"]) - 1
		if int(v["thrash"]["turns"]) <= 0:
			v["thrash"] = {}
			v["confused"] = 2 + rnd(4)
			await ui.msg(nm + " became confused!")
	if eff == "RECOIL" and total > 0:
		var rec := maxi(1, int(floor(total / (2.0 if mid == "STRUGGLE" else 4.0))))
		await ui.msg(nm + "'s hit with recoil!")
		await apply_damage(side, rec)
	if eff == "DRAIN_HP" or eff == "DREAM_EATER":
		var heal := maxi(1, int(floor(total / 2.0)))
		if not a.is_fainted():
			a.hp = mini(a.max_hp, a.hp + heal)
			await ui.anim("DRAIN", side, 0)
			await ui.sync_hp(side)
			await ui.msg("Sucked health from " + tname + "!")
	if eff == "EXPLODE":
		a.hp = 0
		await ui.sync_hp(side)
	if eff == "HYPER_BEAM" and not t.is_fainted():
		v["recharge"] = true
	if eff == "PAY_DAY" and side.is_player:
		pay_day += 2 * a.level
		await ui.msg("Coins scattered everywhere!")
	if not t.is_fainted() and total > 0:
		await side_effect(side, fs, md)
	if tv["rage"] and not t.is_fainted() and total > 0:
		await stat_change(fs, "atk", 1, false, true)
		await ui.msg(label(fs) + "'s RAGE is building!")

func _multi_hits() -> int:
	var r := rnd(8)
	if r < 3:
		return 2
	if r < 6:
		return 3
	if r < 7:
		return 4
	return 5

func accuracy_check(side: BattleSide, md: Dictionary) -> bool:
	var fs := foe(side)
	var tv := fs.v
	if tv["invuln"] and md.get("effect", "") != "SWIFT":
		return false
	if md.get("effect", "") == "SWIFT" or side.v.get("xacc", false):
		return true
	var acc: int = int(floor(int(md.get("acc", 100)) * 255 / 100.0))
	acc = int(floor(acc * STAGE[int(side.v["st"]["acc"]) + 6] / 100.0))
	acc = int(floor(acc * STAGE[6 - int(tv["st"]["eva"])] / 100.0))
	return rnd(256) < mini(255, acc) or (int(md.get("acc", 100)) >= 100 and int(side.v["st"]["acc"]) >= 0 and int(tv["st"]["eva"]) <= 0)

## upstream calcDamage: returns {dmg, crit}. The core formula is BattleMath's.
func calc_damage(side: BattleSide, fs: BattleSide, md: Dictionary, use_crit: bool) -> Dictionary:
	var a := mon(side)
	var t := mon(fs)
	var mtype: String = md.get("type", "NORMAL")
	var typ := "NORMAL" if mtype == "NORMAL_CONF" else mtype
	var physical := PHYSICAL.has(typ)
	var crit := false
	if use_crit and mtype != "NORMAL_CONF":
		var crit_sp: String = str(atr_species(side))
		var base := int(floor(int(GameData.get_species(crit_sp).get("spd", 0)) / 2.0))
		if HIGH_CRIT.has(md.get("id", "")):
			base *= 8
		if side.v["focus"]:
			base *= 4
		crit = rnd(256) < mini(255, base)
	var atk := 0
	var def := 0
	var atr: Dictionary = side.v["transformed"]
	var dtr: Dictionary = fs.v["transformed"]
	if crit:
		atk = (int(atr["atk"]) if not atr.is_empty() else a.stat("atk")) if physical else (int(atr["spc"]) if not atr.is_empty() else a.stat("spc"))
		def = (int(dtr["def"]) if not dtr.is_empty() else t.stat("def")) if physical else (int(dtr["spc"]) if not dtr.is_empty() else t.stat("spc"))
		if physical and a.status == "BRN":
			atk = int(floor(atk / 2.0))
	else:
		atk = stat(side, "atk" if physical else "spc")
		def = stat(fs, "def" if physical else "spc")
		if physical and fs.v["reflect"]:
			def *= 2
		if not physical and fs.v["light_screen"]:
			def *= 2
	if mtype == "NORMAL_CONF":
		atk = stat(side, "atk")
		def = stat(side, "def")
	if md.get("effect", "") == "EXPLODE":
		def = maxi(1, int(floor(def / 2.0)))
	if atk > 255 or def > 255:
		atk = maxi(1, int(floor(atk / 4.0)))
		def = maxi(1, int(floor(def / 4.0)))
	def = maxi(1, def)
	var dmg := 0
	if mtype == "NORMAL_CONF":
		var l: int = a.level
		dmg = int(floor(floor(floor(2.0 * l / 5.0 + 2.0) * 40 * atk / def) / 50.0))
		dmg = mini(997, dmg) + 2
	else:
		dmg = BattleMath.calc_damage(a.level, int(md.get("power", 0)), atk, def, typ, types_of(side), types_of(fs), crit, rng)
	return {"dmg": dmg, "crit": crit}

func deal_damage(side: BattleSide, fs: BattleSide, dmg: int, md: Dictionary, ohko: bool) -> void:
	var t := mon(fs)
	var tv := fs.v
	if int(tv["sub"]) > 0 and not ohko:
		tv["sub"] = int(tv["sub"]) - dmg
		await ui.hit_flash(fs, 1.0)
		if int(tv["sub"]) <= 0:
			tv["sub"] = 0
			await ui.substitute(fs, false)
			await ui.msg(label(fs) + "'s SUBSTITUTE broke!")
		else:
			await ui.msg("The SUBSTITUTE took damage for " + label(fs) + "!")
		return
	dmg = mini(dmg, t.hp)
	side.v["last_dmg_dealt"] = dmg
	if not (tv["bide"] as Dictionary).is_empty():
		tv["bide"]["dmg"] = int(tv["bide"]["dmg"]) + dmg
	await ui.hit_flash(fs, type_mult(md.get("type", "NORMAL"), types_of(fs)))
	t.hp -= dmg
	await ui.sync_hp(fs)

func apply_damage(side: BattleSide, dmg: int) -> void:
	var m := mon(side)
	m.hp = maxi(0, m.hp - dmg)
	await ui.hit_flash(side, 1.0)
	await ui.sync_hp(side)

func side_effect(side: BattleSide, fs: BattleSide, md: Dictionary) -> void:
	var t := mon(fs)
	if int(fs.v["sub"]) > 0:
		return
	var tt := types_of(fs)
	var mtype: String = md.get("type", "NORMAL")
	match str(md.get("effect", "")):
		"BURN_SIDE1":
			if chance(0.1) and not tt.has("FIRE"):
				await inflict(fs, "BRN", true, "")
		"BURN_SIDE2":
			if chance(0.3) and not tt.has("FIRE"):
				await inflict(fs, "BRN", true, "")
		"FREEZE_SIDE1":
			if chance(0.1) and not tt.has("ICE"):
				await inflict(fs, "FRZ", true, "")
		"PARALYZE_SIDE1":
			if chance(0.1):
				await inflict(fs, "PAR", true, mtype)
		"PARALYZE_SIDE2":
			if chance(0.3) and not (mtype == "NORMAL" and tt.has("NORMAL")):
				await inflict(fs, "PAR", true, mtype)
		"POISON_SIDE1":
			if chance(0.2) and not tt.has("POISON"):
				await inflict(fs, "PSN", true, "")
		"POISON_SIDE2":
			if chance(0.4) and not tt.has("POISON"):
				await inflict(fs, "PSN", true, "")
		"FLINCH_SIDE1":
			if chance(0.1):
				fs.v["flinch"] = true
		"FLINCH_SIDE2":
			if chance(0.3):
				fs.v["flinch"] = true
		"CONFUSION_SIDE":
			if chance(0.1) and int(fs.v["confused"]) <= 0:
				fs.v["confused"] = 2 + rnd(4)
				await ui.status_anim(fs, "CONF")
				await ui.msg(label(fs) + " became confused!")
		"SPEED_DOWN_SIDE":
			if chance(0.33):
				await stat_change(fs, "spd", -1, true, false)
		"ATTACK_DOWN_SIDE":
			if chance(0.33):
				await stat_change(fs, "atk", -1, true, false)
		"DEFENSE_DOWN_SIDE":
			if chance(0.33):
				await stat_change(fs, "def", -1, true, false)
		"SPECIAL_DOWN_SIDE":
			if chance(0.33):
				await stat_change(fs, "spc", -1, true, false)
	if mtype == "FIRE" and t.status == "FRZ":
		t.status = ""
		await ui.refresh()
		await ui.msg(label(fs) + " was defrosted!")

func inflict(fs: BattleSide, st: String, _from_move: bool, move_type: String) -> bool:
	var t := mon(fs)
	if t.status != "" or t.is_fainted():
		return false
	if st == "PAR" and move_type == "ELECTRIC" and types_of(fs).has("GROUND"):
		return false
	t.status = st
	if st == "SLP":
		t.sleep = 1 + rnd(7)
	if st == "FRZ" or st == "SLP":
		fs.v["recharge"] = false
	await ui.status_anim(fs, st)
	await ui.refresh()
	var txt: String = {"PSN": " was poisoned!", "BRN": " was burned!", "FRZ": " was frozen solid!",
		"PAR": "'s paralyzed! It may not attack!", "SLP": " fell asleep!"}[st]
	await ui.msg(label(fs) + txt)
	return true

func stat_change(side: BattleSide, k: String, delta: int, by_foe: bool, quiet: bool) -> bool:
	var v := side.v
	if by_foe and v["mist"]:
		await ui.msg(label(side) + "'s protected by MIST!")
		return false
	if by_foe and int(v["sub"]) > 0:
		await ui.msg("But, it failed!")
		return false
	var cur: int = int(v["st"][k])
	if (delta > 0 and cur >= 6) or (delta < 0 and cur <= -6):
		if not quiet:
			await ui.msg("Nothing happened!")
		return false
	v["st"][k] = clampi(cur + delta, -6, 6)
	if quiet:
		return true
	await ui.stat_anim(side, delta > 0)
	var nm: String = STAT_NAME[k]
	var tail := " greatly rose!" if delta > 1 else (" rose!" if delta > 0 else (" greatly fell!" if delta < -1 else " fell!"))
	await ui.msg(label(side) + "'s " + nm + tail)
	return true

func _failed() -> void:
	await ui.msg("But, it failed!")

func status_move(side: BattleSide, md: Dictionary) -> void:
	var a := mon(side)
	var v := side.v
	var fs := foe(side)
	var t := mon(fs)
	var tv := fs.v
	var nm := label(side)
	var tname := label(fs)
	var ef: String = md.get("effect", "")
	var mid: String = md["id"]
	var self_target := ef.contains("_UP") or ["FOCUS_ENERGY", "HEAL", "LIGHT_SCREEN", "REFLECT", "MIST", "SUBSTITUTE",
		"CONVERSION", "HAZE", "SPLASH", "TRANSFORM", "MIMIC", "SWITCH_AND_TELEPORT", "DISABLE"].has(ef)
	if not self_target or ef == "DISABLE" or ef == "MIMIC" or ef == "TRANSFORM":
		if not ["TRANSFORM", "HAZE"].has(ef):
			if tv["invuln"] or not accuracy_check(side, md):
				await ui.msg(nm + "'s attack missed!")
				return
	var immune := type_mult(md.get("type", "NORMAL"), types_of(fs)) == 0.0 and ["PARALYZE", "POISON", "SLEEP", "CONFUSION"].has(ef)
	if immune:
		await ui.msg("It doesn't affect " + tname + "!")
		return
	match ef:
		"ATTACK_UP1", "ATTACK_UP2", "DEFENSE_UP1", "DEFENSE_UP2", "SPEED_UP2", "SPECIAL_UP1", "SPECIAL_UP2", "EVASION_UP1":
			var k: String = {"ATTACK": "atk", "DEFENSE": "def", "SPEED": "spd", "SPECIAL": "spc", "EVASION": "eva"}[ef.split("_")[0]]
			await ui.anim(mid, side, 0)
			await stat_change(side, k, 2 if ef.ends_with("2") else 1, false, false)
		"ATTACK_DOWN1", "DEFENSE_DOWN1", "DEFENSE_DOWN2", "SPEED_DOWN1", "ACCURACY_DOWN1":
			var k2: String = {"ATTACK": "atk", "DEFENSE": "def", "SPEED": "spd", "ACCURACY": "acc"}[ef.split("_")[0]]
			await ui.anim(mid, side, 0)
			await stat_change(fs, k2, -2 if ef.ends_with("2") else -1, true, false)
		"SLEEP":
			if t.status != "":
				await _failed()
				return
			await ui.anim(mid, side, 0)
			await inflict(fs, "SLP", false, "")
		"POISON":
			if t.status != "" or types_of(fs).has("POISON"):
				await _failed()
				return
			await ui.anim(mid, side, 0)
			await inflict(fs, "PSN", false, "")
			if mid == "TOXIC":
				tv["toxic"] = 1
		"PARALYZE":
			if t.status != "":
				await _failed()
				return
			await ui.anim(mid, side, 0)
			await inflict(fs, "PAR", false, md.get("type", ""))
		"CONFUSION":
			if int(tv["confused"]) > 0 or int(tv["sub"]) > 0:
				await _failed()
				return
			await ui.anim(mid, side, 0)
			tv["confused"] = 2 + rnd(4)
			await ui.status_anim(fs, "CONF")
			await ui.msg(tname + " became confused!")
		"LEECH_SEED":
			if tv["seeded"] or types_of(fs).has("GRASS"):
				await ui.msg(tname + " evaded the attack!")
				return
			await ui.anim(mid, side, 0)
			tv["seeded"] = true
			await ui.msg(tname + " was seeded!")
		"HEAL":
			if a.hp >= a.max_hp:
				await _failed()
				return
			await ui.anim(mid, side, 0)
			if mid == "REST":
				a.status = "SLP"
				a.sleep = 2
				a.hp = a.max_hp
				v["toxic"] = 0
				await ui.refresh()
				await ui.sync_hp(side)
				await ui.msg(nm + " started sleeping!")
			else:
				a.hp = mini(a.max_hp, a.hp + int(floor(a.max_hp / 2.0)))
				await ui.sync_hp(side)
				await ui.msg(nm + " regained health!")
		"LIGHT_SCREEN":
			if v["light_screen"]:
				await _failed()
				return
			await ui.anim(mid, side, 0)
			v["light_screen"] = true
			await ui.msg(nm + "'s protected against special attacks!")
		"REFLECT":
			if v["reflect"]:
				await _failed()
				return
			await ui.anim(mid, side, 0)
			v["reflect"] = true
			await ui.msg(nm + " gained armor!")
		"MIST":
			if v["mist"]:
				await _failed()
				return
			await ui.anim(mid, side, 0)
			v["mist"] = true
			await ui.msg(nm + "'s shrouded in mist!")
		"FOCUS_ENERGY":
			if v["focus"]:
				await _failed()
				return
			await ui.anim(mid, side, 0)
			v["focus"] = true
			await ui.msg(nm + "'s getting pumped!")
		"HAZE":
			await ui.anim(mid, side, 0)
			for s: BattleSide in [side, fs]:
				s.v["st"] = {"atk": 0, "def": 0, "spd": 0, "spc": 0, "acc": 0, "eva": 0}
				s.v["confused"] = 0
				s.v["seeded"] = false
				s.v["focus"] = false
				s.v["mist"] = false
				s.v["reflect"] = false
				s.v["light_screen"] = false
				s.v["disabled"] = {}
				s.v["toxic"] = 0
			if t.status != "":
				t.status = ""
			await ui.refresh()
			await ui.msg("All status changes were eliminated!")
		"SUBSTITUTE":
			var cost := int(floor(a.max_hp / 4.0))
			if int(v["sub"]) > 0:
				await ui.msg(nm + " has a SUBSTITUTE already!")
				return
			if a.hp <= cost:
				await ui.msg("Too weak to make a SUBSTITUTE!")
				return
			a.hp -= cost
			v["sub"] = cost + 1
			await ui.sync_hp(side)
			await ui.substitute(side, true)
			await ui.msg("It created a SUBSTITUTE!")
		"DISABLE":
			var last: String = tv["last_used"]
			var ok := false
			for x in move_list(fs):
				if x["id"] == last and int(x["pp"]) > 0:
					ok = true
			if last == "" or not (tv["disabled"] as Dictionary).is_empty() or not ok:
				await _failed()
				return
			await ui.anim(mid, side, 0)
			tv["disabled"] = {"move": last, "turns": 1 + rnd(8)}
			await ui.msg(tname + "'s " + move_name(last) + " was disabled!")
		"MIMIC":
			var opts: Array = []
			for x in move_list(fs):
				opts.append(x["id"])
			var pick := ""
			if side.is_player:
				var r: int = await ui.choose_index(opts.map(func(x): return move_name(x)), "Mimic which move?")
				pick = opts[r] if r >= 0 and r < opts.size() else ""
			else:
				pick = opts[rnd(opts.size())] if not opts.is_empty() else ""
			if pick == "":
				await _failed()
				return
			var m := mon(side)
			var slot := m.moves.find("MIMIC")
			if slot >= 0 and (v["transformed"] as Dictionary).is_empty() and not m.moves.has(pick):
				v["mimic"] = {"slot": slot, "old": "MIMIC", "old_max": m.max_pp("MIMIC")}
				var left: int = int(m.pp.get("MIMIC", 0))
				m.pp.erase("MIMIC")
				m.pp_max.erase("MIMIC")
				m.moves[slot] = pick
				m.pp[pick] = left
				m.pp_max[pick] = v["mimic"]["old_max"]
			await ui.anim(mid, side, 0)
			await ui.msg(nm + " learned " + move_name(pick) + "!")
		"TRANSFORM":
			if tv["invuln"]:
				await _failed()
				return
			await ui.anim(mid, side, 0)
			var mvs: Array = []
			for x in move_list(fs):
				mvs.append({"id": x["id"], "pp": 5, "max": 5})
			var tsp: String = atr_species(fs)
			v["transformed"] = {"species": tsp, "types": types_of(fs).duplicate(), "atk": _raw_stat(fs, "atk"),
				"def": _raw_stat(fs, "def"), "spd": _raw_stat(fs, "spd"), "spc": _raw_stat(fs, "spc"), "moves": mvs}
			v["st"] = (tv["st"] as Dictionary).duplicate()
			await ui.transform_to(side, tsp)
			await ui.msg(nm + " transformed into " + str(GameData.get_species(tsp).get("name", tsp)) + "!")
		"CONVERSION":
			await ui.anim(mid, side, 0)
			v["types"] = types_of(fs).duplicate()
			var tn: String = v["types"][0]
			await ui.msg("Converted type to " + ("PSYCHIC" if tn == "PSYCHIC_TYPE" else tn) + "!")
		"SPLASH":
			await ui.anim(mid, side, 0)
			await ui.msg("No effect!")
		"SWITCH_AND_TELEPORT":
			if wild:
				await ui.anim(mid, side, 0)
				if side.is_player:
					await ui.msg("Got away safely!")
					result = "run"
				else:
					await ui.msg(nm + " ran away!")
					result = "fled"
				await ui.flee(side)
			else:
				await _failed()
		_:
			await _failed()

## Poison / burn / leech seed after the side's move.
func after_move_damage(side: BattleSide) -> void:
	var m := mon(side)
	var v := side.v
	if m.is_fainted() or result != "":
		return
	if m.status == "PSN" or m.status == "BRN":
		var dmg := maxi(1, int(floor(m.max_hp / 16.0)))
		if int(v["toxic"]) > 0:
			dmg = maxi(1, int(floor(m.max_hp / 16.0)) * int(v["toxic"]))
			v["toxic"] = int(v["toxic"]) + 1
		await ui.status_anim(side, m.status)
		await ui.msg(label(side) + "'s hurt by " + ("poison" if m.status == "PSN" else "the burn") + "!")
		await apply_damage(side, dmg)
	if v["seeded"] and not m.is_fainted():
		var sdmg := maxi(1, int(floor(m.max_hp / 16.0)))
		if int(v["toxic"]) > 0:
			sdmg = maxi(1, int(floor(m.max_hp / 16.0)) * int(v["toxic"]))
		sdmg = mini(sdmg, m.hp)
		await ui.anim("LEECH_SEED_DRAIN", side, 0)
		await apply_damage(side, sdmg)
		var f := mon(foe(side))
		if not f.is_fainted():
			f.hp = mini(f.max_hp, f.hp + sdmg)
			await ui.sync_hp(foe(side))
		await ui.msg("LEECH SEED saps " + label(side) + "!")

# ------------------------------------------------------------------ fainting & switching
func check_faints() -> bool:
	var any := false
	var em := mon(e)
	var pm := mon(p)
	if em.is_fainted() and not e.fainted:
		any = true
		e.fainted = true
		await ui.faint(e)
		await ui.msg(label(e) + " fainted!")
		await give_exp()
		if wild:
			_finish("win")
			return true
	if pm.is_fainted() and not p.fainted:
		any = true
		p.fainted = true
		await ui.faint(p)
		await ui.msg(pm.display_name() + " fainted!")
		participants.erase(pm)
		PikachuBuddy.event(PikachuBuddy.FAINTED_VS_STRONGER if mon(e).level - pm.level >= 30 else PikachuBuddy.FAINTED, pm)
	if not any:
		return false
	if p.fainted:
		var alive := false
		for m in p.party:
			if not m.is_fainted():
				alive = true
		if not alive:
			await ui.msg(GameState.player_name + " is out of usable POKéMON!")
			if not wild and str(trainer.get("lose_text", "")) != "":
				await ui.trainer_says(trainer["lose_text"])
			await ui.msg(GameState.player_name + " blacked out!")
			_finish("lose")
			return true
		if wild:
			var go_on: bool = await ui.ask_yes_no("Use next POKéMON?")
			if not go_on:
				var ran: bool = await try_run(true)
				if ran:
					_finish("run")
					return true
		var idx: int = await ui.party_menu(true)
		await switch_in(p, idx, false)
	if e.fainted and not wild:
		var nxt := -1
		for i in e.party.size():
			if not e.party[i].is_fainted():
				nxt = i
				break
		if nxt < 0:
			await ui.trainer_defeated(self)
			_finish("win")
			return true
		await ui.msg(trainer_name() + " is about to use " + e.party[nxt].display_name() + "!")
		await switch_in(e, nxt, false)
	return true

func switch_in(side: BattleSide, idx: int, withdraw: bool) -> void:
	if withdraw and not side.fainted:
		await ui.withdraw(side)
	_undo_mimic(side)
	side.v = new_vol()
	side.fainted = false
	var fs := foe(side)
	fs.v["trapping"] = {}
	fs.v["trapped"] = 0
	side.idx = idx
	if side.is_player:
		_add_participant(mon(side))
	else:
		participants = []
		if not mon(p).is_fainted():
			participants.append(mon(p))
	await ui.send_out(side)
	if not side.is_player:
		GameState.mark_seen(mon(side).species_id)

func give_exp() -> void:
	if o.get("no_exp", false):
		return
	var em := mon(e)
	var parts: Array = participants.filter(func(m): return not m.is_fainted())
	if parts.is_empty():
		return
	var esp := GameData.get_species(em.species_id)
	var exp_all: bool = int(GameState.bag.get("EXP_ALL", 0)) > 0
	var base: int = BattleMath.xp_yield(int(esp.get("baseExp", 0)), em.level, not wild)
	var share := maxi(1, int(floor(base / float(parts.size() * 2 if exp_all else parts.size()))))
	var recips: Array = []
	if exp_all:
		var alive: Array = p.party.filter(func(m): return not m.is_fainted())
		for m in alive:
			recips.append([m, maxi(1, int(floor(base / 2.0 / alive.size()))) + (share if parts.has(m) else 0)])
	else:
		for m in parts:
			recips.append([m, share])
	for rec in recips:
		var m: GameState.PartyMon = rec[0]
		var amt: int = rec[1]
		var traded := m.ot != "" and m.ot != GameState.player_name
		if traded:
			amt = int(floor(amt * 1.5))
		for k in ["hp", "atk", "def", "spd", "spc"]:
			m.sexp[k] = mini(65535, int(m.sexp.get(k, 0)) + int(esp.get(k, 0)))
		if m.level >= 100:
			continue
		await ui.msg(m.display_name() + (" gained a boosted " if traded else " gained ") + str(amt) + " EXP. Points!")
		var active := m == mon(p)
		var remaining := amt
		while remaining > 0 and m.level < 100:
			var need := m.exp_to_next() - m.xp
			var add := mini(need, remaining)
			var from := m.xp
			m.xp += add
			remaining -= add
			if active:
				await ui.exp_bar(m, from, m.xp)
			if m.xp >= m.exp_to_next():
				var old := {"maxhp": m.max_hp, "atk": m.stat("atk"), "def": m.stat("def"), "spd": m.stat("spd"), "spc": m.stat("spc")}
				m.level += 1
				m.recalc_keep_hp()
				m.leveled_in_battle = true
				PikachuBuddy.event(PikachuBuddy.LEVEL_UP, m)   # YELLOW: PIKACHU's friendship
				if active:
					await ui.refresh()
				await ui.msg(m.display_name() + " grew to level " + str(m.level) + "!")
				await ui.level_stats(m, old)
				for mv in m.moves_at_level(m.level):
					await learn_move(m, mv)
		if remaining > 0:
			m.xp += remaining

## upstream G.learnMoveFlow (the in-battle / post-evolution variant).
func learn_move(m: GameState.PartyMon, mv: String) -> bool:
	if m.moves.has(mv):
		return false
	var mn := move_name(mv)
	var nm := m.display_name()
	if m.moves.size() < 4:
		m.add_move(mv)
		await ui.msg(nm + " learned " + mn + "!")
		return true
	while true:
		await ui.msg(nm + " is trying to learn " + mn + "!\fBut, " + nm + " can't learn more than 4 moves!")
		var del: bool = await ui.ask_yes_no("Delete an older move to make room for " + mn + "?")
		if del:
			await ui.msg("Which move should be forgotten?")
			var r: int = await ui.choose_index(m.moves.map(func(x): return move_name(x)), "")
			if r >= 0:
				if GameData.hm_moves.has(m.moves[r]):
					await ui.msg("HM techniques can't be deleted!")
					continue
				var old := move_name(m.moves[r])
				m.replace_move(r, mv)
				await ui.msg("1, 2 and... Poof!\f" + nm + " forgot " + old + "!\fAnd...")
				await ui.msg(nm + " learned " + mn + "!")
				return true
		var give_up: bool = await ui.ask_yes_no("Abandon learning " + mn + "?")
		if give_up:
			await ui.msg(nm + " did not learn " + mn + "!")
			return false
	return false

func try_run(_after_faint: bool) -> bool:
	if o.get("ghost", false):
		await ui.msg("Got away safely!")
		return true
	if not wild:
		await ui.msg("No! There's no running from a trainer battle!")
		return false
	if o.get("no_run", false):
		await ui.msg("Can't escape!")
		return false
	run_attempts += 1
	var ps := mon(p).stat("spd")
	var es := int(floor(mon(e).stat("spd") / 4.0)) % 256
	var ok := true
	if es != 0:
		var f := int(floor(ps * 32.0 / es)) + 30 * run_attempts
		ok = f > 255 or rnd(256) < f
	if ok:
		await ui.msg("Got away safely!")
		return true
	await ui.msg("Can't escape!")
	return false

# ------------------------------------------------------------------ items
static func bag_remove(id: String, n: int = 1) -> void:
	var c: int = int(GameState.bag.get(id, 0)) - n
	if c <= 0:
		GameState.bag.erase(id)
	else:
		GameState.bag[id] = c

static func item_name(id: String) -> String:
	return str(GameData.items.get(id, {}).get("name", id.replace("_", " ")))

static func needs_target(id: String) -> bool:
	return HEAL.has(id) or CURE.has(id) or id.contains("REVIVE") or id.contains("ETHER") or id.contains("ELIXER")

## Items usable from the battle bag (upstream bagMenuBattle's filter).
static func usable_in_battle(id: String) -> bool:
	if id == "POKE_FLUTE":
		return true
	if ["TOWN_MAP", "BICYCLE", "EXP_ALL", "OLD_ROD", "GOOD_ROD", "SUPER_ROD", "ITEMFINDER", "COIN_CASE", "SILPH_SCOPE"].has(id):
		return false
	if id.ends_with("STONE") or id == "RARE_CANDY" or id.begins_with("TM_") or id.begins_with("HM_") or id.contains("REPEL") or id == "ESCAPE_ROPE":
		return false
	return HEAL.has(id) or CURE.has(id) or X_ITEM.has(id) or id.ends_with("BALL") or ["REVIVE", "MAX_REVIVE", "GUARD_SPEC",
		"DIRE_HIT", "POKE_DOLL", "ETHER", "MAX_ETHER", "ELIXER", "MAX_ELIXER"].has(id)

func use_item(item: String, target: int) -> String:
	if item.ends_with("BALL"):
		if not wild:
			await ui.msg("The trainer blocked the BALL!")
			await ui.msg("Don't be a thief!")
			bag_remove(item)
			return "used"
		if o.get("no_catch", false):
			await ui.msg("It dodged the thrown BALL!\fThis POKéMON can't be caught!")
			bag_remove(item)
			return "used"
		bag_remove(item)
		return await throw_ball(item)
	var nm := GameState.player_name
	if item == "POKE_DOLL":
		if not wild:
			await ui.msg("It won't have any effect.")
			return "cancel"
		bag_remove(item)
		await ui.msg("Got away safely!")
		result = "run"
		return "fled"
	if X_ITEM.has(item):
		bag_remove(item)
		await ui.msg(nm + " used " + item_name(item) + "!")
		if item == "X_ACCURACY":
			p.v["xacc"] = true
			await ui.msg(mon(p).display_name() + " became more accurate!")
		else:
			await stat_change(p, X_ITEM[item], 1, false, false)
		return "used"
	if item == "GUARD_SPEC":
		bag_remove(item)
		p.v["mist"] = true
		await ui.msg(nm + " used GUARD SPEC.!")
		await ui.msg(mon(p).display_name() + " is shrouded in mist!")
		return "used"
	if item == "DIRE_HIT":
		bag_remove(item)
		p.v["focus"] = true
		await ui.msg(nm + " used DIRE HIT!")
		await ui.msg(mon(p).display_name() + "'s getting pumped!")
		return "used"
	if item == "POKE_FLUTE":
		var any := false
		for s: BattleSide in [p, e]:
			if mon(s).status == "SLP":
				mon(s).status = ""
				any = true
		await ui.msg("Played the POKé FLUTE.")
		await ui.msg("All sleeping POKéMON woke up!" if any else "Now, that's a catchy tune!")
		return "used"
	if target < 0 or target >= GameState.party.size():
		await ui.msg("That can't be used now.")
		return "cancel"
	var m: GameState.PartyMon = GameState.party[target]
	var ok: bool = await apply_to_mon(item, m)
	if not ok:
		return "cancel"
	bag_remove(item)
	if m == mon(p):
		await ui.sync_hp(p)
		await ui.refresh()
	return "used"

func apply_to_mon(id: String, m: GameState.PartyMon) -> bool:
	var nm := m.display_name()
	if HEAL.has(id) or CURE.has(id):
		if m.is_fainted():
			await ui.msg("It won't have any effect.")
			return false
		var heals := HEAL.has(id) and m.hp < m.max_hp
		var cures: bool = CURE.has(id) and m.status != "" and (CURE[id] as Array).has(m.status)
		if not heals and not cures:
			await ui.msg("It won't have any effect.")
			return false
		var before := m.hp
		if heals:
			m.hp = mini(m.max_hp, m.hp + int(HEAL[id]))
			PikachuBuddy.event(PikachuBuddy.HP_RESTORE, m)
		if cures:
			m.status = ""
			m.sleep = 0
			if m == mon(p):
				p.v["toxic"] = 0
				if id == "FULL_RESTORE" or id == "FULL_HEAL":
					p.v["confused"] = 0
		if heals:
			await ui.msg(nm + " recovered by " + str(m.hp - before) + "!")
		else:
			await ui.msg(nm + " was cured!")
		return true
	if id == "REVIVE" or id == "MAX_REVIVE":
		if not m.is_fainted():
			await ui.msg("It won't have any effect.")
			return false
		m.hp = int(floor(m.max_hp / 2.0)) if id == "REVIVE" else m.max_hp
		m.status = ""
		await ui.msg(nm + " is revitalized!")
		return true
	if id == "ETHER" or id == "MAX_ETHER":
		var r: int = await ui.choose_index(m.moves.map(func(x): return move_name(x) + " %d/%d" % [int(m.pp.get(x, 0)), m.max_pp(x)]), "")
		if r < 0:
			return false
		var mv: String = m.moves[r]
		if int(m.pp.get(mv, 0)) >= m.max_pp(mv):
			await ui.msg("It won't have any effect.")
			return false
		m.pp[mv] = mini(m.max_pp(mv), int(m.pp.get(mv, 0)) + 10) if id == "ETHER" else m.max_pp(mv)
		await ui.msg("PP was restored.")
		return true
	if id == "ELIXER" or id == "MAX_ELIXER":
		var full := true
		for mv2 in m.moves:
			if int(m.pp.get(mv2, 0)) < m.max_pp(mv2):
				full = false
		if full:
			await ui.msg("It won't have any effect.")
			return false
		for mv3 in m.moves:
			m.pp[mv3] = mini(m.max_pp(mv3), int(m.pp.get(mv3, 0)) + 10) if id == "ELIXER" else m.max_pp(mv3)
		await ui.msg("PP was restored.")
		return true
	await ui.msg("It won't have any effect.")
	return false

## Gen 1 catch formula + shake count (upstream throwBall).
func catch_roll(item: String, em: GameState.PartyMon) -> Dictionary:
	var caught := false
	var shakes := 0
	if item == "MASTER_BALL":
		caught = true
	else:
		var r1max := 256 if item == "POKE_BALL" else (201 if item == "GREAT_BALL" else 151)
		var r1 := rnd(r1max)
		var st := 0
		if em.status == "SLP" or em.status == "FRZ":
			st = 25
		elif em.status != "":
			st = 12
		var rate: int = int(GameData.get_species(em.species_id).get("catchRate", 45))
		if safari:
			rate = clampi(int(rate * (2 if safari_rock > 0 else 1) / (2.0 if safari_bait > 0 else 1.0)), 1, 255)
		if r1 - st < 0:
			caught = true
		elif r1 - st > rate:
			caught = false
		else:
			var f: int = mini(255, int(floor(floor(em.max_hp * 255.0 / (8.0 if item == "GREAT_BALL" else 12.0)) / maxi(1, int(floor(em.hp / 4.0))))))
			caught = f >= rnd(256)
			if not caught:
				var x := int(floor(rate * 100.0 / (255.0 if item == "POKE_BALL" else (200.0 if item == "GREAT_BALL" else 150.0))))
				var z := int(floor(x * f / 255.0)) + (10 if st == 25 else (5 if st > 0 else 0))
				shakes = 0 if z < 10 else (1 if z < 30 else (2 if z < 70 else 3))
	if caught:
		shakes = 3
	return {"caught": caught, "shakes": shakes}

func throw_ball(item: String) -> String:
	var em := mon(e)
	await ui.msg(GameState.player_name + " used " + item_name(item) + "!")
	var r := catch_roll(item, em)
	var caught: bool = r["caught"]
	var shakes: int = r["shakes"]
	await ui.ball_throw(item, shakes, caught)
	if not caught:
		await ui.msg(["You missed the POKéMON!", "Darn! The POKéMON broke free!", "Aww! It appeared to be caught!", "Shoot! It was so close too!"][shakes])
		return "used"
	var spname: String = str(GameData.get_species(em.species_id).get("name", em.species_id))
	await ui.msg("All right! " + spname + " was caught!")
	var is_new: bool = not GameState.caught_species.has(em.species_id)
	GameState.caught_species[em.species_id] = true
	GameState.mark_seen(em.species_id)
	if is_new:
		await ui.msg("New POKéDEX data will be added for " + spname + "!")
		await ui.dex_entry(em.species_id)
	em.ot = GameState.player_name
	await receive_mon(em)
	return "caught"

## upstream G.receiveMon (without the naming screen): party, else the PC.
func receive_mon(m: GameState.PartyMon) -> String:
	if GameState.party.size() < 6:
		GameState.party.append(m)
		GameState.party_changed.emit()
		return "party"
	var bx: Array = GameState.box()
	if bx.size() >= 20:
		await ui.msg("The POKéMON BOX is full! It can't accept any more POKéMON!")
		return "full"
	bx.append(m)
	await ui.msg(m.display_name() + " was transferred to someone's PC!")
	return "box"

func enemy_use_item(item: String) -> void:
	var m := mon(e)
	await ui.msg(trainer_name() + " used " + item_name(item) + "!")
	if item.contains("POTION") or item == "FULL_RESTORE":
		var heal: int = {"POTION": 20, "SUPER_POTION": 50, "HYPER_POTION": 200}.get(item, m.max_hp)
		m.hp = mini(m.max_hp, m.hp + heal)
		if item == "FULL_RESTORE":
			m.status = ""
			e.v["toxic"] = 0
			e.v["confused"] = 0
		await ui.anim("HEAL_ITEM", e, 0)
		await ui.sync_hp(e)
		await ui.refresh()
	elif item == "FULL_HEAL":
		m.status = ""
		e.v["toxic"] = 0
		e.v["confused"] = 0
		await ui.refresh()
	elif X_ITEM.has(item):
		await stat_change(e, X_ITEM[item], 1, false, false)
	elif item == "GUARD_SPEC":
		e.v["mist"] = true
		await ui.msg(label(e) + "'s covered by a veil!")
	elif item == "DIRE_HIT":
		e.v["focus"] = true

## Prize money (upstream trainerDefeated): trainer class money / 100 x the last mon's level.
func prize_money() -> int:
	if wild or e.party.is_empty():
		return 0
	var last_lv: int = e.party[e.party.size() - 1].level
	return int(floor(int(trainer.get("money", 0)) / 100.0)) * last_lv

# ------------------------------------------------------------------ trainer construction
## upstream G.makeTrainerParty: party #n (1-based) of the class, Gen 1 trainer DVs,
## plus gym leaders' signature moves and the Elite Four's team moves.
static func make_trainer_party(cls: String, n: int) -> Array:
	var parties: Array = GameData.parties.get(cls, [])
	var entry: Array = [[5, "RATTATA"]]
	if n - 1 >= 0 and n - 1 < parties.size():
		entry = parties[n - 1]
	elif not parties.is_empty():
		entry = parties[0]
	var party: Array = []
	for lv_sp in entry:
		var m := GameState.PartyMon.new(str(lv_sp[1]), int(lv_sp[0]), {"atk": 9, "def": 8, "spd": 8, "spc": 8})
		m.ot = cls
		party.append(m)
	if not GameData.special_moves.is_empty():
		# YELLOW: data/trainers/special_moves.asm hands individual trainers custom movesets ([mon, slot, MOVE] triples)
		for tr in (GameData.special_moves.get(cls, {}) as Dictionary).get(str(n), []):
			var mi: int = int(tr[0]) - 1
			if mi >= 0 and mi < party.size():
				var sm: GameState.PartyMon = party[mi]
				var slot: int = int(tr[1]) - 1
				if slot < sm.moves.size():
					if not sm.moves.has(tr[2]):
						sm.replace_move(slot, tr[2])
				else:
					sm.add_move(tr[2])
		return party
	var lone: String = LONE_MOVES.get(cls, "")
	if lone != "" and not party.is_empty():
		var lm: GameState.PartyMon = party[party.size() - 1]
		if not lm.moves.has(lone):
			if lm.moves.size() >= 4:
				lm.replace_move(3, lone)
			else:
				lm.add_move(lone)
	for tm_entry in _team_moves():
		if tm_entry[0] == cls:
			for tm_mon in party:
				if not tm_mon.moves.has(tm_entry[1]):
					if tm_mon.moves.size() >= 4:
						tm_mon.replace_move(3, tm_entry[1])
					else:
						tm_mon.add_move(tm_entry[1])
	return party

## MISSINGNO. (upstream src/game/glitches.js defGlitch): read from just before
## BULBASAUR's data -- BIRD/NORMAL, 33/136/0/29/6, WATER GUN x2 + SKY ATTACK.
static func ensure_glitch_species() -> void:
	if GameData.species.has("MISSINGNO"):
		return
	GameData.species["MISSINGNO"] = {"id": "MISSINGNO", "name": "MISSINGNO.", "hp": 33, "atk": 136, "def": 0, "spd": 29,
		"spc": 6, "types": ["BIRD", "NORMAL"], "catchRate": 29, "baseExp": 0, "moves1": ["WATER_GUN", "SKY_ATTACK"],
		"fixedMoves": ["WATER_GUN", "WATER_GUN", "SKY_ATTACK"], "growth": "MEDIUM_FAST", "tmhm": [], "evos": [], "learn": [],
		"dex": 0, "ht": [10, 0], "wt": 35071, "glitch": true}

static var _team_moves_cache: Array = []

## pokedata.json teamMoves ([[class, move], ...]); GameData doesn't keep it.
static func _team_moves() -> Array:
	if _team_moves_cache.is_empty():
		var f := FileAccess.open("res://data/pokedata.json", FileAccess.READ)
		if f:
			var d: Variant = JSON.parse_string(f.get_as_text())
			if d is Dictionary:
				_team_moves_cache = (d as Dictionary).get("teamMoves", [])
	return _team_moves_cache

## Builds the engine options for a trainer battle (upstream startTrainerBattle).
static func trainer_opts(cls: String, n: int, extra: Dictionary = {}) -> Dictionary:
	var tc: Dictionary = GameData.trainer_classes.get(cls, {"name": cls, "money": 1000})
	var is_rival := cls.begins_with("RIVAL")
	var display: String = extra.get("name", "")
	if display == "":
		display = GameState.rival_name if is_rival else str(LEADERS.get(cls, tc.get("name", cls)))
	var party: Array = extra.get("party", [])
	if party.is_empty():
		party = make_trainer_party(cls, n)
	return {
		"kind": "trainer", "enemy_party": party,
		"trainer": {"cls": cls, "n": n, "display_name": display, "boss": LEADERS.has(cls) or is_rival, "money": int(extra.get("money", tc.get("money", 1000))),
			"win_text": extra.get("on_win_text", extra.get("win_text", "")), "lose_text": extra.get("lose_text", "")},
		"trainer_items": (TRAINER_ITEMS.get(cls, []) as Array).duplicate(),
		"boss": LEADERS.has(cls) or is_rival,
	}

# ------------------------------------------------------------------ safari zone (upstream safariAction)
static func safari_balls() -> int:
	var v: Variant = GameState.get("safari_balls")
	return int(v) if v != null else int(GameState.get_meta("safari_balls", 30))

static func set_safari_balls(n: int) -> void:
	if GameState.get("safari_balls") != null:
		GameState.set("safari_balls", n)
	else:
		GameState.set_meta("safari_balls", n)

## BALL / BAIT / ROCK / RUN. Returns "caught" | "fled" | "" (battle goes on).
func safari_action(what: String) -> String:
	var em := mon(e)
	match what:
		"ball":
			if safari_balls() <= 0:
				return "fled"
			set_safari_balls(safari_balls() - 1)
			var r: String = await throw_ball("SAFARI_BALL")
			if r == "caught":
				return "caught"
			if safari_balls() <= 0:
				await ui.msg("PA: Ding-dong!\fYou are out of SAFARI BALLs!")
				result = "run"
				return "fled"
		"bait":
			await ui.msg(GameState.player_name + " threw some BAIT.")
			safari_bait = 1 + rnd(5)
			safari_rock = 0
			await ui.msg(label(e) + " is eating!")
		"rock":
			await ui.msg(GameState.player_name + " threw a ROCK.")
			safari_rock = 1 + rnd(5)
			safari_bait = 0
			await ui.anim("ROCK_THROW_SAFARI", p, 0)
			await ui.msg(label(e) + " is angry!")
		"run":
			await ui.msg("Got away safely!")
			return "fled"
	var flee_chance := minf(255.0, em.stat("spd") * 2.0) / 256.0
	if safari_bait > 0:
		flee_chance /= 4.0
		safari_bait -= 1
	if safari_rock > 0:
		flee_chance *= 2.0
		safari_rock -= 1
	if chance(flee_chance * 0.35):
		await ui.msg(label(e) + " ran away!")
		await ui.flee(e)
		return "fled"
	if safari_bait > 0:
		await ui.msg(label(e) + " is eating!")
	elif safari_rock > 0:
		await ui.msg(label(e) + " is angry!")
	else:
		await ui.msg(label(e) + " is watching carefully!")
	return ""
