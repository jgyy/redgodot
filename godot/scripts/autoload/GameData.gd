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

# ---- version support (RED / BLUE / YELLOW): data/versions.json, see pipeline/scripts/extract_versions.py ----
const VERSIONS := ["RED", "BLUE", "YELLOW"]
var versions_data: Dictionary = {}
var active_version: String = "RED"
var version_text: Dictionary = {}     # label -> text that replaces text.json's for the active version (Story.raw reads it)
var pokedata_extra: Dictionary = {}   # the version's trades / goodRod / superRod / marts / prizes (Story reads these)
var special_moves: Dictionary = {}    # YELLOW: class -> {party no -> [[mon, slot, MOVE]...]}
var _pristine := {}                   # what apply_version() must restore before applying another version

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

	versions_data = _load_json("res://data/versions.json")
	_snapshot_pristine(pd)
	apply_version("RED")

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

# ------------------------------------------------------------------ versions
func _snapshot_pristine(pd: Dictionary) -> void:
	_pristine = {"wild": wild.duplicate(true), "parties": parties.duplicate(true), "species": {}, "objs": {}, "pd": pd}

## Switches every version-dependent table (wild encounters, fishing, trainer teams, species data, NPC trades, Game
## Corner prizes, Marts, NPC/trainer/item placement and Yellow's dialogue) to RED, BLUE or YELLOW. Idempotent: it always
## starts again from the RED base data that pokedata.json / mapdata.json hold.
func apply_version(v: String) -> void:
	if not VERSIONS.has(v):
		v = "RED"
	active_version = v
	var vd := versions_data
	var pd: Dictionary = _pristine.get("pd", {})
	# wild encounter tables: the version's file lists the maps that have grass/water encounters, every other map has none
	var vw: Dictionary = (vd.get("wild", {}) as Dictionary).get(v, {})
	if v == "RED" or vw.is_empty():
		wild = (_pristine["wild"] as Dictionary).duplicate(true)
	else:
		var w: Dictionary = {}
		for k in (_pristine["wild"] as Dictionary).keys():
			w[k] = {"grass": {"rate": 0, "mons": []}, "water": {"rate": 0, "mons": []}}
		for k in vw.keys():
			w[k] = vw[k]
		wild = w
	# trainer teams
	var vp: Dictionary = (vd.get("parties", {}) as Dictionary).get(v, {})
	parties = vp if not vp.is_empty() else (_pristine["parties"] as Dictionary).duplicate(true)
	special_moves = ((vd.get("specialMoves", {}) as Dictionary).get(v, {}) as Dictionary)
	# species: restore then override (Yellow changed base stats, start moves, learnsets and evolutions)
	var orig: Dictionary = _pristine["species"]
	for sid in orig.keys():
		species[sid] = orig[sid]
	var so: Dictionary = (vd.get("species", {}) as Dictionary).get(v, {})
	for sid in so.keys():
		if not species.has(sid):
			continue
		if not orig.has(sid):
			orig[sid] = species[sid]
		var merged: Dictionary = (species[sid] as Dictionary).duplicate(true)
		for f in (so[sid] as Dictionary).keys():
			merged[f] = so[sid][f]
		species[sid] = merged
	# NPC trades, rods, prizes, marts
	pokedata_extra = {}
	for k in ["trades", "goodRod", "superRod", "prizes"]:
		var d: Dictionary = vd.get(k, {})
		if d.has(v):
			pokedata_extra[k] = d[v]
	var vm: Dictionary = (vd.get("marts", {}) as Dictionary).get(v, {})
	var marts: Dictionary = (pd.get("marts", {}) as Dictionary).duplicate(true)
	for lab in vm.keys():
		marts[lab] = vm[lab]
	pokedata_extra["marts"] = marts
	version_text = ((vd.get("text", {}) as Dictionary).get(v, {}) as Dictionary).duplicate()
	_apply_object_overlay(v)
	var st := get_node_or_null("/root/Story")
	if st:
		sync_story(st.pokedata)

## Copies the active version's trades / rods / prizes / marts into Story's own pokedata dictionary.
func sync_story(story_pokedata: Dictionary) -> void:
	for k in pokedata_extra.keys():
		story_pokedata[k] = pokedata_extra[k]

## Restores each touched map's objects from the RED originals, then applies the version's patches / additions / removals
## (matched by the object's TEXT_* constant, which pret keeps stable across versions).
func _apply_object_overlay(v: String) -> void:
	var saved: Dictionary = _pristine["objs"]
	for m in saved.keys():
		maps[m]["objs"] = (saved[m] as Array).duplicate(true)
	var ov: Dictionary = (versions_data.get("objects", {}) as Dictionary).get(v, {})
	for m in ov.keys():
		if not maps.has(m):
			continue
		if not saved.has(m):
			saved[m] = (maps[m].get("objs", []) as Array).duplicate(true)
			maps[m]["objs"] = (saved[m] as Array).duplicate(true)
		var objs: Array = maps[m].get("objs", [])
		var spec: Dictionary = ov[m]
		var removed: Array = spec.get("remove", [])
		for o in objs:
			if removed.has(o.get("text", "")):
				o["shown"] = false
				o["removed"] = true
		var patch: Dictionary = spec.get("patch", {})
		for o in objs:
			var pt: Variant = patch.get(o.get("text", ""), null)
			if pt == null:
				continue
			for f in (pt as Dictionary).keys():
				if pt[f] == null:
					o.erase(f)
				else:
					o[f] = pt[f]
			if pt.has("trainer") and pt["trainer"] != null and not o.has("th"):
				o["th"] = _synth_trainer_header(m, o)
		for a in spec.get("add", []):
			var no: Dictionary = (a as Dictionary).duplicate(true)
			no["shown"] = true
			no["textLabel"] = _label_for(m, str(no.get("text", "")))
			if no.has("item"):
				no["textLabel"] = "PickUpItemText"
			if no.has("trainer"):
				no["th"] = _synth_trainer_header(m, no)
			objs.append(no)

## TEXT_ROUTE24_COOLTRAINER_M4 on Route24 -> "Route24CooltrainerM4Text" (the label stem pret's text files use).
static func _label_for(map_name: String, text_const: String) -> String:
	var parts := text_const.trim_prefix("TEXT_").split("_")
	var skip := map_name.to_upper().length()
	var acc := 0
	var i := 0
	while i < parts.size() and acc < skip:   # drop the map-name prefix (it may span several "_" parts, e.g. VIRIDIAN_FOREST)
		acc += parts[i].length()
		i += 1
	var out := ""
	for j in range(i, parts.size()):
		var w: String = parts[j]
		out += w.substr(0, 1).to_upper() + w.substr(1).to_lower()
	return map_name + out + ("Text" if not out.ends_with("Text") else "")

static func _synth_trainer_header(map_name: String, o: Dictionary) -> Dictionary:
	var stem := _label_for(map_name, str(o.get("text", ""))).trim_suffix("Text")
	return {"flag": "EVENT_BEAT_" + str(o.get("id", "")), "range": 4, "battle": stem + "BattleText",
		"end": stem + "EndBattleText", "after": stem + "AfterBattleText"}
