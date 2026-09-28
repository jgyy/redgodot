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

func new_game(starter_id: String) -> void:
	party.clear()
	add_to_party(starter_id, 5)
	bag = {"POKE_BALL": 5}
	badges.clear()
	current_map = "PalletTown"
	player_cell = Vector2i(5, 8)

func add_to_party(species_id: String, level: int) -> PartyMon:
	var mon := PartyMon.new(species_id, level)
	if party.size() < 6:
		party.append(mon)
	caught_species[species_id] = true
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
