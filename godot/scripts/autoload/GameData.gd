extends Node
## Loads the full Pokemon Claude Red game data (ported verbatim from the original
## JS source's data tables) once at startup and exposes fast lookups.
##
## Source of truth for these JSON files: pipeline/extracted/*.json, produced by
## pipeline/scripts/extract_*.js from https://github.com/levy-street/pokemon-claude-red

var species: Dictionary = {}       # SPECIES_ID -> {hp,atk,def,spd,spc,types,dex,ht,wt,moves1,learn,evos,...}
var dex_order: Array = []
var moves: Dictionary = {}         # MOVE_ID -> {power,type,acc,pp,effect,...}
var move_list: Array = []
var type_chart: Dictionary = {}    # atk_type -> {def_type -> multiplier}
var items: Dictionary = {}
var tm_moves: Array = []
var hm_moves: Array = []
var trainer_classes: Dictionary = {}
var parties: Dictionary = {}
var wild: Dictionary = {}          # map name -> {grass:{rate,mons:[...]}, water:{...}}
var slot_chances: Array = []       # relative weights for the 10 wild-encounter slots

var tilesets: Dictionary = {}
var maps: Dictionary = {}          # map name -> {cells,w,h,warps,signs,conns,...}

var mon_art: Dictionary = {}       # SPECIES_ID -> {pal, parts}  (vector art source, used by the Blender pipeline)
var cast: Dictionary = {}          # character key -> {head, body, colors...}
var sprite_override: Dictionary = {}
var species_override: Dictionary = {}
var head_styles: Dictionary = {}
var body_styles: Dictionary = {}

func _ready() -> void:
	var pd := _load_json("res://data/pokedata.json")
	species = pd.get("species", {})
	dex_order = pd.get("dexOrder", [])
	moves = pd.get("moves", {})
	move_list = pd.get("moveList", [])
	items = pd.get("items", {})
	tm_moves = pd.get("tmMoves", [])
	hm_moves = pd.get("hmMoves", [])
	trainer_classes = pd.get("trainerClasses", {})
	parties = pd.get("parties", {})
	wild = pd.get("wild", {})
	slot_chances = pd.get("slotChances", [])
	_build_type_chart(pd.get("typeChart", []))

	var md := _load_json("res://data/mapdata.json")
	tilesets = md.get("tilesets", {})
	maps = md.get("maps", {})

	mon_art = _load_json("res://data/mons.json")

	var cd := _load_json("res://data/cast.json")
	cast = cd.get("cast", {})
	sprite_override = cd.get("spriteOverride", {})
	species_override = cd.get("speciesOverride", {})

	var chd := _load_json("res://data/chars.json")
	head_styles = chd.get("HEADS", {})
	body_styles = chd.get("BODY", {})

	print("[GameData] loaded %d species, %d moves, %d maps, %d cast members" % [
		species.size(), moves.size(), maps.size(), cast.size()
	])

func _load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		push_error("[GameData] missing data file: %s" % path)
		return {}
	var f := FileAccess.open(path, FileAccess.READ)
	var text := f.get_as_text()
	f.close()
	var parsed = JSON.parse_string(text)
	if parsed == null:
		push_error("[GameData] failed to parse JSON: %s" % path)
		return {}
	return parsed

func _build_type_chart(triples: Array) -> void:
	for t in triples:
		var atk_type: String = t[0]
		var def_type: String = t[1]
		var mult: float = t[2]
		if not type_chart.has(atk_type):
			type_chart[atk_type] = {}
		type_chart[atk_type][def_type] = mult

## Effectiveness multiplier of a single attacking type against a list of defending types.
func type_multiplier(atk_type: String, def_types: Array) -> float:
	var mult := 1.0
	var row: Dictionary = type_chart.get(atk_type, {})
	for dt in def_types:
		mult *= float(row.get(dt, 1.0))
	return mult

func get_species(id: String) -> Dictionary:
	return species.get(id, {})

func get_move(id: String) -> Dictionary:
	return moves.get(id, {})

func get_map(name: String) -> Dictionary:
	return maps.get(name, {})

func get_tileset(name: String) -> Dictionary:
	return tilesets.get(name, {})

## Real-world height in meters, from the species' [feet, inches] pokedex entry.
func species_height_m(id: String) -> float:
	var sp := get_species(id)
	var ht = sp.get("ht", [1, 0])
	var feet: float = ht[0]
	var inches: float = ht[1] if ht.size() > 1 else 0.0
	var m: float = feet * 0.3048 + inches * 0.0254
	return max(m, 0.15)

## Level-up learnset up to (and including) a given level, in order.
func learnset_up_to(id: String, level: int) -> Array:
	var sp := get_species(id)
	var out: Array = []
	for entry in sp.get("learn", []):
		if int(entry[0]) <= level:
			out.append(entry[1])
	return out
