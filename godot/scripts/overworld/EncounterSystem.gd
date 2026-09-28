class_name EncounterSystem
extends RefCounted
## Wild-encounter rolling, ported from the original game's slot-table approach
## (src/data/pokedata.json: wild[cnst].grass/water + top-level slotChances).

static func wild_table_for_map(map_key: String, in_water: bool = false) -> Dictionary:
	var map_data := GameData.get_map(map_key)
	var cnst: String = map_data.get("cnst", "")
	var table: Dictionary = GameData.wild.get(cnst, {})
	return table.get("water" if in_water else "grass", {"rate": 0, "mons": []})

## Returns {} if no encounter this step, else {species, level}.
static func roll(map_key: String, in_water: bool = false, rng: RandomNumberGenerator = null) -> Dictionary:
	var table := wild_table_for_map(map_key, in_water)
	var rate: int = table.get("rate", 0)
	if rate <= 0:
		return {}
	var roll255: int = (rng.randi_range(0, 254) if rng else randi() % 255)
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
