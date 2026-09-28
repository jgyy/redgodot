extends Node
## Runtime player/save state: party, position, inventory, flags.

signal party_changed
signal badge_earned(badge: String)

class PartyMon:
	var species_id: String
	var nickname: String
	var level: int
	var xp: int                 # total experience points (upstream Mon.exp)
	var hp: int
	var max_hp: int
	var moves: Array = []       # up to 4 move ids
	var pp: Dictionary = {}     # move id -> current pp
	var status: String = ""     # "", "PSN", "BRN", "PAR", "SLP", "FRZ"
	# --- battle additions (upstream src/game/pokemon.js Mon) ---
	var dvs: Dictionary = {"atk": 0, "def": 0, "spd": 0, "spc": 0, "hp": 0}
	var sexp: Dictionary = {"hp": 0, "atk": 0, "def": 0, "spd": 0, "spc": 0}
	var pp_max: Dictionary = {}  # move id -> max pp (PP Ups raise it)
	var sleep: int = 0           # sleep turns left while status == "SLP"
	var ot: String = ""
	var leveled_in_battle := false

	## `dv_opts` = {atk,def,spd,spc} (0..15); omitted -> all zero (deterministic,
	## identical to the pre-battle-port stat formula). {"random": true} rolls
	## upstream's random wild DVs.
	func _init(sid: String = "", lvl: int = 5, dv_opts: Dictionary = {}) -> void:
		species_id = sid
		level = lvl
		nickname = sid
		if dv_opts.get("random", false):
			set_dvs(randi() % 16, randi() % 16, randi() % 16, randi() % 16)
		elif not dv_opts.is_empty():
			set_dvs(int(dv_opts.get("atk", 0)), int(dv_opts.get("def", 0)), int(dv_opts.get("spd", 0)), int(dv_opts.get("spc", 0)))
		var sp := GameData.get_species(sid)
		xp = GameState.exp_for_level(str(sp.get("growth", "MEDIUM_FAST")), lvl)
		_recalc_stats()
		moves = []
		pp = {}
		if sp.has("fixedMoves"):
			for m in sp["fixedMoves"]:
				add_move(m)
		else:
			var lst: Array = sp.get("moves1", []).duplicate()
			for e in sp.get("learn", []):
				if int(e[0]) <= lvl and not lst.has(e[1]):
					lst.append(e[1])
			for m in lst.slice(maxi(0, lst.size() - 4)):
				add_move(m)

	## Gen 1: the HP DV is built from the low bits of the other four.
	func set_dvs(a: int, d: int, s: int, c: int) -> void:
		dvs = {"atk": a, "def": d, "spd": s, "spc": c,
			"hp": ((a & 1) << 3) | ((d & 1) << 2) | ((s & 1) << 1) | (c & 1)}

	func add_move(mid: String) -> bool:
		var md := GameData.get_move(mid)
		if md.is_empty() or moves.has(mid) or moves.size() >= 4:
			return false
		moves.append(mid)
		pp[mid] = int(md.get("pp", 0))
		pp_max[mid] = int(md.get("pp", 0))
		return true

	func replace_move(slot: int, mid: String) -> void:
		var old: String = moves[slot]
		pp.erase(old)
		pp_max.erase(old)
		moves[slot] = mid
		var p: int = int(GameData.get_move(mid).get("pp", 0))
		pp[mid] = p
		pp_max[mid] = p

	func max_pp(mid: String) -> int:
		return int(pp_max.get(mid, GameData.get_move(mid).get("pp", 0)))

	func _recalc_stats() -> void:
		var sp := GameData.get_species(species_id)
		if sp.is_empty():
			max_hp = 1
			hp = 1
			return
		max_hp = GameState.calc_stat(int(sp.get("hp", 1)), int(dvs.get("hp", 0)), int(sexp.get("hp", 0)), level, true)
		hp = max_hp

	## upstream Mon.recalc() after a level-up/evolution: max HP grows and the
	## current HP gains the same difference.
	func recalc_keep_hp() -> void:
		var old_max := max_hp
		var old_hp := hp
		_recalc_stats()
		hp = old_hp
		if hp > 0:
			hp = mini(max_hp, hp + (max_hp - old_max))

	func stat(key: String) -> int:
		var sp := GameData.get_species(species_id)
		var base: int = int(sp.get(key, 1))
		return GameState.calc_stat(base, int(dvs.get(key, 0)), int(sexp.get(key, 0)), level, false)

	func types() -> Array:
		return GameData.get_species(species_id).get("types", [])

	## upstream Mon.name: the nickname, else the species' display name.
	func display_name() -> String:
		if nickname != "" and nickname != species_id:
			return nickname
		return str(GameData.get_species(species_id).get("name", species_id))

	func growth() -> String:
		return str(GameData.get_species(species_id).get("growth", "MEDIUM_FAST"))

	func exp_this() -> int:
		return GameState.exp_for_level(growth(), level)

	func exp_to_next() -> int:
		return 0 if level >= 100 else GameState.exp_for_level(growth(), level + 1)

	func moves_at_level(lv: int) -> Array:
		var out: Array = []
		for e in GameData.get_species(species_id).get("learn", []):
			if int(e[0]) == lv:
				out.append(e[1])
		return out

	## Species this mon evolves into by level, or "".
	func evo_by_level() -> String:
		for e in GameData.get_species(species_id).get("evos", []):
			if str(e.get("type", "")) == "level" and level >= int(e.get("level", 999)):
				return str(e.get("to", ""))
		return ""

	func evolve_to(sid: String) -> void:
		var default_nick := nickname == species_id
		species_id = sid
		if default_nick:
			nickname = sid
		recalc_keep_hp()

	func heal_full() -> void:
		hp = max_hp
		status = ""
		sleep = 0
		for m in moves:
			pp[m] = max_pp(m)

	func is_fainted() -> bool:
		return hp <= 0

	func to_dict() -> Dictionary:
		return {
			"species_id": species_id, "nickname": nickname, "level": level, "xp": xp,
			"hp": hp, "max_hp": max_hp, "moves": moves, "pp": pp, "status": status,
			"dvs": dvs, "sexp": sexp, "pp_max": pp_max, "sleep": sleep, "ot": ot,
		}

	static func from_dict(d: Dictionary) -> PartyMon:
		var m := PartyMon.new(d.get("species_id", ""), int(d.get("level", 5)))
		if d.has("dvs"):
			var dv: Dictionary = d["dvs"]
			m.set_dvs(int(dv.get("atk", 0)), int(dv.get("def", 0)), int(dv.get("spd", 0)), int(dv.get("spc", 0)))
		if d.has("sexp"):
			var se: Dictionary = d["sexp"]
			for k in se.keys():
				m.sexp[k] = int(se[k])
		m._recalc_stats()
		m.nickname = d.get("nickname", m.species_id)
		m.xp = int(d.get("xp", m.xp))
		m.hp = int(d.get("hp", m.max_hp))
		m.moves = d.get("moves", m.moves)
		var ppd: Dictionary = d.get("pp", m.pp)
		m.pp = {}
		for k in ppd.keys():
			m.pp[k] = int(ppd[k])
		var pmx: Dictionary = d.get("pp_max", {})
		m.pp_max = {}
		for mv in m.moves:
			m.pp_max[mv] = int(pmx.get(mv, GameData.get_move(mv).get("pp", 0)))
		m.status = d.get("status", "")
		m.sleep = int(d.get("sleep", 0))
		m.ot = d.get("ot", "")
		return m

## Gen 1 stat formula (upstream calcStat).
func calc_stat(base: int, dv: int, sexp_v: int, lvl: int, is_hp: bool) -> int:
	var e: int = int(floor(ceil(sqrt(float(sexp_v))) / 4.0))
	var v: int = int(floor(float((base + dv) * 2 + e) * lvl / 100.0))
	return v + lvl + 10 if is_hp else v + 5

var party: Array = []               # Array[PartyMon]
var bag: Dictionary = {}            # item_id -> count
var badges: Array = []              # Array[String]
var current_map: String = "PalletTown"
var player_cell: Vector2i = Vector2i(5, 8)
var player_facing: String = "down"
var player_name: String = "RED"
var rival_name: String = "BLUE"
var seen_species: Dictionary = {}
var caught_species: Dictionary = {}
var last_heal_map: String = "PalletTown"   # blackout destination (upstream lastHealTown)
var last_heal_cell: Vector2i = Vector2i(5, 6)

## In-game clock, minutes since midnight (0..1440), used for the day/night
## lighting cycle. 1 real second = CLOCK_RATE game-minutes, so a full day/night
## cycle is visible in a couple of minutes of play rather than 24 real hours.
const CLOCK_RATE := 6.0
var clock_minutes: float = 9.0 * 60.0  # start at 9 AM
var clock_running: bool = true

var text_speed: String = "NORMAL"   # "SLOW" | "NORMAL" | "FAST"
var sound_on: bool = true
var money: int = 3000
var play_seconds: float = 0.0

## Upstream G.state.options (menus.js optionsMenu): text_speed 1..3 (SLOW/MID/
## FAST = chars revealed per frame), battle_anim, battle_style "shift"|"set",
## sound, day_night, follower.
const DEFAULT_OPTIONS := {"text_speed": 2, "battle_anim": true, "battle_style": "shift",
	"sound": true, "day_night": true, "follower": true}
var options: Dictionary = DEFAULT_OPTIONS.duplicate()
var trainer_id: int = 0
## Bill's PC: 12 boxes of PartyMon (upstream S.boxes / S.box), and the
## player's PC item storage (upstream S.pc, item_id -> count).
var pc_boxes: Array = []
var current_box: int = 0
var pc_items: Dictionary = {}
## Town map: towns visited (lit squares / FLY targets) and the last outdoor map.
var visited: Dictionary = {"PalletTown": true}
var last_outdoor: String = "PalletTown"

func text_speed_chars() -> int:
	return clampi(int(options.get("text_speed", 2)), 1, 3)

## "H:MM" play time as on the trainer card.
func play_time_text() -> String:
	var mins := int(play_seconds / 60.0)
	return "%d:%02d" % [mins / 60, mins % 60]

func box(i: int = -1) -> Array:
	var idx := current_box if i < 0 else i
	while pc_boxes.size() <= idx:
		pc_boxes.append([])
	return pc_boxes[idx]

## Gen-1 experience needed to reach level n for a growth rate (pokemon.js).
static func exp_for_level(growth: String, n: int) -> int:
	var n3 := float(n * n * n)
	match growth:
		"FAST":
			return int(floor(4.0 * n3 / 5.0))
		"SLOW":
			return int(floor(5.0 * n3 / 4.0))
		"MEDIUM_SLOW":
			return maxi(0, int(floor(1.2 * n3 - 15.0 * n * n + 100.0 * n - 140.0)))
		_:
			return int(n3)

## Upstream G.newState() for NEW GAME (title.js newGameIntro): no POKéMON yet,
## an empty bag, a POTION in the PC, ₽3000, standing in RED's room facing up.
func start_new_adventure() -> void:
	party.clear()
	bag = {}
	pc_items = {"POTION": 1}
	pc_boxes = []
	current_box = 0
	money = 3000
	badges = []
	seen_species = {}
	caught_species = {}
	options = DEFAULT_OPTIONS.duplicate()
	trainer_id = randi() % 65536
	play_seconds = 0.0
	visited = {"PalletTown": true}
	last_outdoor = "PalletTown"
	current_map = "RedsHouse2F"
	player_cell = Vector2i(3, 6)
	player_facing = "up"
	party_changed.emit()

## The fixed save the reference screenshots were taken with (Main.gd
## --save=showcase): RED, ₽48210, dex 126 seen / 75 owned, a Lv42-52 party and
## a bag of 7 staple items, standing in PALLET TOWN at noon.
func build_showcase() -> void:
	new_game("CHARIZARD")
	party.clear()
	var roster := [["CHARIZARD", 52, 158], ["PIKACHU", 45, 92], ["LAPRAS", 44, 178],
		["SNORLAX", 46, 213], ["ALAKAZAM", 43, 102], ["JOLTEON", 42, 112]]
	for r in roster:
		var m := PartyMon.new(r[0], r[1])
		m.max_hp = r[2]
		m.hp = r[2]
		m.xp = exp_for_level(GameData.get_species(r[0]).get("growth", "MEDIUM_FAST"), r[1])
		party.append(m)
	player_name = "RED"
	rival_name = "BLUE"
	money = 48210
	trainer_id = 0
	play_seconds = 0.0
	badges = ["BOULDERBADGE", "CASCADEBADGE", "THUNDERBADGE", "RAINBOWBADGE", "SOULBADGE"]
	bag = {"POTION": 3, "SUPER_POTION": 3, "POKE_BALL": 3, "GREAT_BALL": 3,
		"ULTRA_BALL": 3, "REVIVE": 3, "ESCAPE_ROPE": 3}
	options = DEFAULT_OPTIONS.duplicate()
	# 75 owned: the even dex numbers, trading 10-18 for the party's odd ones.
	var own := {}
	for n in range(2, 152, 2):
		own[n] = true
	for n in [10, 12, 14, 16, 18]:
		own.erase(n)
	for n in [25, 65, 131, 135, 143]:
		own[n] = true
	# 126 seen: everything but #005 and the 24 highest odd numbers not owned.
	var unseen := {5: true}
	var n2 := 151
	while unseen.size() < 25:
		if not own.has(n2):
			unseen[n2] = true
		n2 -= 2
	seen_species.clear()
	caught_species.clear()
	for n in range(1, 152):
		var sid: String = GameData.dex_order[n] if n < GameData.dex_order.size() else ""
		if sid == "":
			continue
		if not unseen.has(n):
			seen_species[sid] = true
		if own.has(n):
			caught_species[sid] = true
	visited = {"PalletTown": true}
	last_outdoor = "PalletTown"
	current_map = "PalletTown"
	player_cell = Vector2i(5, 8)
	player_facing = "down"
	clock_minutes = 12.0 * 60.0
	clock_running = false
	party_changed.emit()

func _process(delta: float) -> void:
	if clock_running:
		clock_minutes = fmod(clock_minutes + delta * CLOCK_RATE, 1440.0)
	play_seconds += delta

## "day" | "dusk" | "night" from the current in-game clock (or an override).
func time_period(minutes: float = -1.0) -> String:
	var m: float = clock_minutes if minutes < 0.0 else minutes
	if m >= 360.0 and m < 18.0 * 60.0:
		return "day"
	if m >= 18.0 * 60.0 and m < 20.0 * 60.0:
		return "dusk"
	if m >= 5.0 * 60.0 and m < 6.0 * 60.0:
		return "dusk"
	return "night"

func new_game(starter_id: String) -> void:
	party.clear()
	add_to_party(starter_id, 5)
	bag = {"POTION": 3, "SUPER_POTION": 3, "POKE_BALL": 3, "GREAT_BALL": 3,
		"ULTRA_BALL": 3, "REVIVE": 3, "ESCAPE_ROPE": 3, "TOWN_MAP": 1}
	badges.clear()
	current_map = "PalletTown"
	player_cell = Vector2i(5, 8)

func add_to_party(species_id: String, level: int) -> PartyMon:
	var mon := PartyMon.new(species_id, level)
	if party.size() < 6:
		party.append(mon)
	caught_species[species_id] = true
	mark_seen(species_id)
	party_changed.emit()
	return mon

func first_healthy_mon() -> PartyMon:
	for m in party:
		if not m.is_fainted():
			return m
	return null

func party_wiped() -> bool:
	return first_healthy_mon() == null

func heal_party() -> void:
	for m in party:
		m.heal_full()

func mark_seen(species_id: String) -> void:
	seen_species[species_id] = true

const SAVE_PATH := "user://save.json"

## Writes the current run to disk. Returns true on success.
func save() -> bool:
	var d := {
		"party": party.map(func(m): return m.to_dict()),
		"bag": bag, "badges": badges, "current_map": current_map,
		"player_cell": [player_cell.x, player_cell.y], "player_facing": player_facing,
		"player_name": player_name, "rival_name": rival_name,
		"seen_species": seen_species, "caught_species": caught_species,
		"clock_minutes": clock_minutes,
		"last_heal_map": last_heal_map, "last_heal_cell": [last_heal_cell.x, last_heal_cell.y],
		"options": options, "trainer_id": trainer_id, "money": money, "play_seconds": play_seconds,
		"pc_boxes": pc_boxes.map(func(b): return b.map(func(m): return m.to_dict())),
		"current_box": current_box, "pc_items": pc_items,
		"visited": visited, "last_outdoor": last_outdoor,
	}
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(JSON.stringify(d))
	f.close()
	return true

func has_save() -> bool:
	return FileAccess.file_exists(SAVE_PATH)

func load_save() -> bool:
	if not has_save():
		return false
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if parsed == null:
		return false
	var d: Dictionary = parsed
	party = []
	for pm in d.get("party", []):
		party.append(PartyMon.from_dict(pm))
	bag = d.get("bag", {})
	badges = d.get("badges", [])
	current_map = d.get("current_map", "PalletTown")
	var pc: Array = d.get("player_cell", [5, 8])
	player_cell = Vector2i(int(pc[0]), int(pc[1]))
	player_facing = d.get("player_facing", "down")
	player_name = d.get("player_name", "RED")
	rival_name = d.get("rival_name", "BLUE")
	seen_species = d.get("seen_species", {})
	caught_species = d.get("caught_species", {})
	clock_minutes = d.get("clock_minutes", clock_minutes)
	last_heal_map = d.get("last_heal_map", last_heal_map)
	var lh: Array = d.get("last_heal_cell", [last_heal_cell.x, last_heal_cell.y])
	last_heal_cell = Vector2i(int(lh[0]), int(lh[1]))
	options = DEFAULT_OPTIONS.duplicate()
	options.merge(d.get("options", {}), true)
	options["text_speed"] = int(options["text_speed"])
	trainer_id = int(d.get("trainer_id", 0))
	money = int(d.get("money", money))
	play_seconds = float(d.get("play_seconds", 0.0))
	pc_boxes = []
	for b in d.get("pc_boxes", []):
		var arr: Array = []
		for pm in b:
			arr.append(PartyMon.from_dict(pm))
		pc_boxes.append(arr)
	current_box = int(d.get("current_box", 0))
	pc_items = d.get("pc_items", {})
	for k in pc_items.keys():
		pc_items[k] = int(pc_items[k])
	visited = d.get("visited", {"PalletTown": true})
	last_outdoor = d.get("last_outdoor", "PalletTown")
	party_changed.emit()
	return true
