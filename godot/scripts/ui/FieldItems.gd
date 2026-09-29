class_name FieldItems
extends RefCounted
## Bag items that work on one POKeMON outside battle, ported from pokered engine/items/item_effects.asm and
## engine/items/tms.asm: TMs and HMs (teach a move), evolution stones, the five vitamins, PP UP and the ETHER family.
## `ps` is the PartyMenu showing the pick (anything with party_say(text), ask(text) -> bool and choose(items, opts) -> int
## works, which is how the tests drive it).  Each function returns true when the item was used up; HMs never are.

const VITAMINS := {"HP_UP": ["hp", "HEALTH"], "PROTEIN": ["atk", "ATTACK"], "IRON": ["def", "DEFENSE"],
	"CARBOS": ["spd", "SPEED"], "CALCIUM": ["spc", "SPECIAL"]}
const PP_ITEMS := ["PP_UP", "ETHER", "MAX_ETHER", "ELIXER", "MAX_ELIXER"]

## Items BagMenu sends to the party pick (besides the healing ones it already knew).
static func handles(id: String) -> bool:
	return id.begins_with("TM_") or id.begins_with("HM_") or id.ends_with("STONE") or VITAMINS.has(id) or PP_ITEMS.has(id)

const NOTHING := 0    ## the item had no effect: keep it, keep the party screen open
const USED := 1       ## it worked and is used up
const KEPT := 2       ## it worked but stays in the bag (an HM)

static func use(id: String, m: GameState.PartyMon, ps: Object) -> int:
	var ok := false
	if id.begins_with("TM_") or id.begins_with("HM_"):
		ok = await teach(str(GameData.items.get(id, {}).get("move", "")), m, ps, id.begins_with("HM_"))
		if ok:
			PikachuBuddy.event(PikachuBuddy.TM_HM, m)
			return KEPT if id.begins_with("HM_") else USED
		return NOTHING
	if id.ends_with("STONE"):
		ok = await stone(id, m, ps)
	elif VITAMINS.has(id):
		ok = await vitamin(id, m, ps)
	elif PP_ITEMS.has(id):
		ok = await pp_item(id, m, ps)
	return USED if ok else NOTHING

# ---------------------------------------------------------------- TMs / HMs / level-up moves
## Teaches `move` to `m` (asks which old move to forget when it knows four). true = learned.
static func teach(move: String, m: GameState.PartyMon, ps: Object, is_hm := false) -> bool:
	var mn: String = str(GameData.get_move(move).get("name", move))
	if m.moves.has(move):
		await ps.party_say("%s knows %s!" % [m.display_name(), mn])
		return false
	var machine := "HM" if is_hm else "TM"
	if not (GameData.get_species(m.species_id).get("tmhm", []) as Array).has(move):
		await ps.party_say("%s is not compatible with this %s. It can't learn %s!" % [m.display_name(), machine, mn])
		return false
	return await learn(move, m, ps)

## Level-up / TM learning flow shared with evolution (engine.learn_move's field variant).
static func learn(move: String, m: GameState.PartyMon, ps: Object) -> bool:
	var mn: String = str(GameData.get_move(move).get("name", move))
	var nm := m.display_name()
	if m.moves.has(move):
		return false
	if m.moves.size() < 4:
		m.add_move(move)
		await ps.party_say("%s learned %s!" % [nm, mn])
		return true
	while true:
		await ps.party_say("%s is trying to learn %s! But, %s can't learn more than 4 moves!" % [nm, mn, nm])
		if not await ps.ask("Delete an older move to make room for %s?" % mn):
			await ps.party_say("%s did not learn %s!" % [nm, mn])
			return false
		var names: Array = m.moves.map(func(x): return str(GameData.get_move(x).get("name", x)))
		var r: int = await ps.choose(names, {"x": 150, "y": 20})
		if r < 0:
			continue
		if GameData.hm_moves.has(m.moves[r]):
			await ps.party_say("HM techniques can't be deleted!")
			continue
		var old_name: String = names[r]
		m.replace_move(r, move)
		await ps.party_say("1, 2 and... Poof! %s forgot %s! And... %s learned %s!" % [nm, old_name, nm, mn])
		return true
	return false

# ---------------------------------------------------------------- evolution stones (and trade evolutions)
## The evolution `id` stone would cause for `m`, or "".
static func stone_target(id: String, m: GameState.PartyMon) -> String:
	for e in GameData.get_species(m.species_id).get("evos", []):
		if str(e.get("type", "")) == "item" and str(e.get("item", "")) == id:
			return str(e.get("to", ""))
	return ""

## The species `m` becomes when traded (Kadabra -> Alakazam ...), or "".
static func trade_target(m: GameState.PartyMon) -> String:
	for e in GameData.get_species(m.species_id).get("evos", []):
		if str(e.get("type", "")) == "trade":
			return str(e.get("to", ""))
	return ""

static func stone(id: String, m: GameState.PartyMon, ps: Object) -> bool:
	var to := stone_target(id, m)
	if to == "":
		await ps.party_say("It won't have any effect.")
		return false
	await evolve(m, to, ps)
	return true

## Evolves `m` into `to` with the messages and cry of the evolution scene (the animated sequence itself only plays after a
## battle level-up, where the 3D stage is on screen), then offers the new species' moves for this level.
static func evolve(m: GameState.PartyMon, to: String, ps: Object) -> void:
	var old_name := m.display_name()
	await ps.party_say("What? %s is evolving!" % old_name)
	Audio.cry(to)
	m.evolve_to(to)
	GameState.caught_species[to] = true
	GameState.mark_seen(to)
	GameState.party_changed.emit()
	await ps.party_say("Congratulations! Your %s evolved into %s!" % [old_name, str(GameData.get_species(to).get("name", to))])
	for mv in m.moves_at_level(m.level):
		await learn(mv, m, ps)

## Story-driven stand-in for the PartyMenu (party_say / ask / choose), for scripts that evolve or teach outside a menu.
class StoryPS extends RefCounted:
	func party_say(text: String) -> void:
		await Story.say(text)

	func ask(text: String) -> bool:
		return await Story.ask(text)

	func choose(items: Array, opts: Dictionary = {}) -> int:
		return await Story.choose(items, opts)

# ---------------------------------------------------------------- vitamins
static func vitamin(id: String, m: GameState.PartyMon, ps: Object) -> bool:
	var stat: String = VITAMINS[id][0]
	var cur := int(m.sexp.get(stat, 0))
	if m.hp <= 0 or cur >= 25600:   # a vitamin only works up to 25600 stat experience (about 10 of them)
		await ps.party_say("It won't have any effect.")
		return false
	m.sexp[stat] = mini(65535, cur + 2560)
	m.recalc_keep_hp()
	await ps.party_say("%s's %s rose." % [m.display_name(), VITAMINS[id][1]])
	return true

# ---------------------------------------------------------------- PP UP, ETHER, ELIXER
static func _pp_step(mv: String) -> int:
	return maxi(1, int(GameData.get_move(mv).get("pp", 0)) / 5)

static func _pp_ups(m: GameState.PartyMon, mv: String) -> int:
	return (m.max_pp(mv) - int(GameData.get_move(mv).get("pp", 0))) / _pp_step(mv)

static func pp_item(id: String, m: GameState.PartyMon, ps: Object) -> bool:
	if m.moves.is_empty():
		await ps.party_say("It won't have any effect.")
		return false
	if id == "ELIXER" or id == "MAX_ELIXER":
		var any := false
		for mv in m.moves:
			var room := m.max_pp(mv) - int(m.pp.get(mv, 0))
			if room > 0:
				any = true
				m.pp[mv] = mini(m.max_pp(mv), int(m.pp.get(mv, 0)) + (10 if id == "ELIXER" else 99))
		if not any:
			await ps.party_say("It won't have any effect.")
			return false
		await ps.party_say("PP was restored.")
		return true
	var names: Array = m.moves.map(func(x): return "%s %d/%d" % [str(GameData.get_move(x).get("name", x)), int(m.pp.get(x, 0)), m.max_pp(x)])
	var r: int = await ps.choose(names, {"x": 100, "y": 20})
	if r < 0:
		return false
	var mv: String = m.moves[r]
	if id == "PP_UP":
		if _pp_ups(m, mv) >= 3 or m.max_pp(mv) >= 61:
			await ps.party_say("It won't have any effect.")
			return false
		m.pp_max[mv] = m.max_pp(mv) + _pp_step(mv)
		await ps.party_say("%s's PP increased." % str(GameData.get_move(mv).get("name", mv)))
		return true
	if int(m.pp.get(mv, 0)) >= m.max_pp(mv):
		await ps.party_say("It won't have any effect.")
		return false
	m.pp[mv] = mini(m.max_pp(mv), int(m.pp.get(mv, 0)) + (10 if id == "ETHER" else 99))
	await ps.party_say("PP was restored.")
	return true
