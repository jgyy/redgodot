class_name WorldData
extends RefCounted
## Static tables the overworld needs that GameData doesn't keep: the per-tileset quad table (cell pattern ->
## four 8x8 tile ids; the bottom-left one is the collision tile, exactly like upstream src/game/map.js), the
## ledge table and the tile-pair collision table. Loaded once from res://data/mapdata.json.

const CELL := 1.0                 # world units per map cell
const CAM_PITCH_DEG := 60.0       # camera pitch; world heights of 2D art are scaled by K = tan(pitch)
static var K: float = tan(deg_to_rad(CAM_PITCH_DEG))

static var quads: Dictionary = {}      # tileset file -> Array[[tl,tr,bl,br]]
static var ledges: Array = []          # [dir, stand_tile, ledge_tile]
static var pair_land: Array = []       # [tilesetName, t1, t2]
static var pair_water: Array = []
static var _loaded := false

static func ensure() -> void:
	if _loaded:
		return
	_loaded = true
	var f := FileAccess.open("res://data/mapdata.json", FileAccess.READ)
	if f == null:
		push_error("[WorldData] mapdata.json missing")
		return
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var d: Dictionary = parsed
	quads = d.get("quads", {})
	ledges = d.get("ledges", [])
	var pc: Dictionary = d.get("pairColl", {})
	pair_land = pc.get("land", [])
	pair_water = pc.get("water", [])

## Height in world units of `px` pixels of 2D art (16 px = one cell).
static func px_h(px: float) -> float:
	return px / 16.0 * CELL * K
