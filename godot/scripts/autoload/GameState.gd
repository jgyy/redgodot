extends Node
## Runtime player/save state: party, position, inventory, flags.

signal party_changed
signal badge_earned(badge: String)

class PartyMon:
	var species_id: String
	var nickname: String
	var level: int
	var xp: int
	var hp: int
	var max_hp: int
	var moves: Array = []       # up to 4 move ids
	var pp: Dictionary = {}     # move id -> current pp
	var status: String = ""     # "", "PSN", "BRN", "PAR", "SLP", "FRZ"

	func _init(sid: String = "", lvl: int = 5) -> void:
		species_id = sid
		level = lvl
		nickname = sid
		xp = 0
		_recalc_stats()
		var sp := GameData.get_species(sid)
		moves = sp.get("moves1", []).duplicate()
		for m in moves:
			pp[m] = GameData.get_move(m).get("pp", 0)

	func _recalc_stats() -> void:
		var sp := GameData.get_species(species_id)
		if sp.is_empty():
			max_hp = 1
			hp = 1
			return
		# Simplified Gen-1 style stat growth (no IV/EV modelling in this MVP).
		max_hp = int(floor((2.0 * sp.get("hp", 1) * level) / 100.0)) + level + 10
		hp = max_hp

	func stat(key: String) -> int:
		var sp := GameData.get_species(species_id)
		var base: int = sp.get(key, 1)
		return int(floor((2.0 * base * level) / 100.0)) + 5

	func types() -> Array:
		return GameData.get_species(species_id).get("types", [])

	func is_fainted() -> bool:
		return hp <= 0

	func to_dict() -> Dictionary:
		return {
			"species_id": species_id, "nickname": nickname, "level": level, "xp": xp,
			"hp": hp, "max_hp": max_hp, "moves": moves, "pp": pp, "status": status,
		}

	static func from_dict(d: Dictionary) -> PartyMon:
		var m := PartyMon.new(d.get("species_id", ""), d.get("level", 5))
		m.nickname = d.get("nickname", m.species_id)
		m.xp = d.get("xp", 0)
		m.hp = d.get("hp", m.max_hp)
		m.max_hp = d.get("max_hp", m.max_hp)
		m.moves = d.get("moves", m.moves)
		m.pp = d.get("pp", m.pp)
		m.status = d.get("status", "")
		return m

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
		m.hp = m.max_hp
		m.status = ""

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
	party_changed.emit()
	return true
