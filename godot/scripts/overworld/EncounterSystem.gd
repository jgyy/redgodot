class_name EncounterSystem
extends RefCounted
## Wild-encounter rolling, ported from the original game's slot-table approach
## (src/data/pokedata.json: wild[cnst].grass/water + top-level slotChances).

static func wild_table_for_map(map_key: String, in_water: bool = false) -> Dictionary:
	var map_data := GameData.get_map(map_key)
	var cnst: String = map_data.get("cnst", "")
	var table: Dictionary = GameData.wild.get(cnst, {})
	return table.get("water" if in_water else "grass", {"rate": 0, "mons": []})

## The Old Man glitch (all three versions): after the Viridian City old man's catching demo, surfing along the
## eastern edge of Cinnabar Island reads the wild table from garbage (the demo's "OLD MAN" name buffer) and meets
## MISSINGNO. Any trainer battle overwrites the buffer again (Story._run_battle clears the flag).
const GLITCH_FLAG := "GLITCH_OLD_MAN"

static func glitch_roll(map_key: String, in_water: bool, rng: RandomNumberGenerator = null) -> Dictionary:
	if map_key != "CinnabarIsland" or not in_water or not bool(GameState.flags.get(GLITCH_FLAG, false)):
		return {}
	var w := int(GameData.get_map(map_key).get("w", 20))
	if GameState.player_cell.x < w - 2:
		return {}
	var r: int = (rng.randi_range(0, 255) if rng else randi() % 256)
	return {"level": 80, "species": "MISSINGNO"} if r < 25 else {}

## Returns {} if no encounter this step, else {species, level}.
static func roll(map_key: String, in_water: bool = false, rng: RandomNumberGenerator = null) -> Dictionary:
	if bool(GameState.flags.get(GLITCH_FLAG, false)):
		var g := glitch_roll(map_key, in_water, rng)
		if not g.is_empty():
			return g
	var table := wild_table_for_map(map_key, in_water)
	var rate: int = table.get("rate", 0)
	if rate <= 0:
		return {}
	var roll255: int = (rng.randi_range(0, 255) if rng else randi() % 256)
	if roll255 >= rate:
		return {}
	var mons: Array = table.get("mons", [])
	if mons.is_empty():
		return {}
	var slot := _pick_slot(mons.size(), rng)
	var entry = mons[slot]
	return {"level": int(entry[0]), "species": String(entry[1])}

static func _pick_slot(count: int, rng: RandomNumberGenerator = null) -> int:
	var weights: Array = GameData.slot_chances
	if weights.is_empty():
		return (rng.randi_range(0, count - 1) if rng else randi() % count)
	var total := 0
	for w in weights:
		total += int(w)
	var r: int = (rng.randi_range(0, max(0, total - 1)) if rng else randi() % max(1, total))
	var acc := 0
	for i in range(min(count, weights.size())):
		acc += int(weights[i])
		if r < acc:
			return i
	return count - 1
