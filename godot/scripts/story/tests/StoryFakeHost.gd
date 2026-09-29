extends Node
## Test double of the Overworld contract (CONTRACT.md) that the Story autoload
## drives, in the spirit of upstream tools/drive.js: a grid of actors built from
## mapdata objs (visibility via Story.is_shown), instant moves, and a call log.
## Terrain is fully passable inside the map bounds except `blocked` cells.

var map := ""
var w := 0
var h := 0
var actors: Dictionary = {}     # id -> {cell: Vector2i, dir: String}
var blocked: Dictionary = {}    # Vector2i -> true
var locked := false
var calls: Array = []           # "method:args" strings
var warps: Array = []           # [map, cell, dir]
var cell_labels: Dictionary = {}
var auto_enter := true          # warp_to calls Story.on_enter like the real Overworld

const DV := {"U": Vector2i(0, -1), "D": Vector2i(0, 1), "L": Vector2i(-1, 0), "R": Vector2i(1, 0)}
const DN := {"U": "up", "D": "down", "L": "left", "R": "right"}

func load_map(name: String, c: Vector2i, facing: String = "down", enter: bool = true) -> void:
	map = name
	var md: Dictionary = GameData.maps.get(name, {})
	w = int(md.get("w", 20))
	h = int(md.get("h", 18))
	actors = {"PLAYER": {"cell": c, "dir": facing}}
	blocked = {}
	cell_labels = {}
	for o in md.get("objs", []):
		var id: String = o.get("id", "")
		if Story.is_shown(id, name):
			var d := str(o.get("dir", "")).to_lower()
			actors[id] = {"cell": Vector2i(int(o["x"]), int(o["y"])), "dir": d if Story.DVEC.has(d) else "down"}
	GameState.current_map = name
	GameState.player_cell = c
	if enter:
		Story.on_enter(name)

func _log(s: String) -> void:
	calls.append(s)

# ---------------------------------------------------------------- contract
func lock_input(on: bool) -> void:
	locked = on

func current_map() -> String:
	return map

func get_actor(_id: String) -> Node3D:
	return null

func actor_cell(id: String) -> Vector2i:
	return actors[id]["cell"] if actors.has(id) else Vector2i(-1, -1)

func actor_dir(id: String) -> String:
	return actors[id]["dir"] if actors.has(id) else "down"

func face_actor(id: String, d: String) -> void:
	if actors.has(id):
		actors[id]["dir"] = d

func show_actor(id: String, c: Vector2i = Vector2i(-1, -1)) -> void:
	_log("show:" + id)
	if not actors.has(id):
		var o := Story.obj(id, map)
		actors[id] = {"cell": Vector2i(int(o.get("x", 0)), int(o.get("y", 0))), "dir": "down"}
	if c.x >= 0:
		actors[id]["cell"] = c

func hide_actor(id: String) -> void:
	_log("hide:" + id)
	actors.erase(id)

func is_actor_shown(id: String) -> bool:
	return actors.has(id)

func actor_at(c: Vector2i, except: String = "") -> String:
	for id in actors:
		if id != except and actors[id]["cell"] == c:
			return id
	return ""

func move_actor(id: String, path: String) -> void:
	_log("move:%s:%s" % [id, path])
	if not actors.has(id):
		return
	for ch in path:
		if not DV.has(ch):
			continue
		actors[id]["dir"] = DN[ch]
		actors[id]["cell"] += DV[ch]
	if id == "PLAYER":
		GameState.player_cell = actors[id]["cell"]

func move_together(pairs: Array) -> void:
	for p in pairs:
		move_actor(str(p[0]), str(p[1]))

func warp_to(m: String, c: Vector2i, facing: String) -> void:
	_log("warp:%s:%d,%d" % [m, c.x, c.y])
	warps.append([m, c, facing])
	load_map(m, c, facing, auto_enter)

func emote(id: String, kind: String = "!") -> void:
	_log("emote:%s:%s" % [id, kind])

func fade_out(_frames: int = 10) -> void:
	_log("fade_out")

func fade_in(_frames: int = 10) -> void:
	_log("fade_in")

func is_passable(c: Vector2i) -> bool:
	return c.x >= 0 and c.y >= 0 and c.x < w and c.y < h and not blocked.has(c)

func is_water(_c: Vector2i) -> bool:
	return false

func cell_label(c: Vector2i) -> String:
	return cell_labels.get(c, "")

func set_cell_override(c: Vector2i, label: String, passable: bool) -> void:
	_log("cell:%d,%d:%s" % [c.x, c.y, label])
	if not passable:
		blocked[c] = true
	else:
		blocked.erase(c)

func clear_cell_override(c: Vector2i) -> void:
	blocked.erase(c)

func path_to(from: Vector2i, to: Vector2i) -> String:
	if from == to:
		return ""
	var prev := {from: ""}
	var q: Array = [from]
	while not q.is_empty():
		var c: Vector2i = q.pop_front()
		if c == to:
			var s := ""
			var k := c
			while prev[k] != "":
				var d: String = prev[k]
				s = d + s
				k -= DV[d]
			return s
		for d in "UDLR":
			var n: Vector2i = c + DV[d]
			if prev.has(n) or not is_passable(n):
				continue
			if n != to and actor_at(n) != "":
				continue
			prev[n] = d
			q.append(n)
	return ""

# ---------------------------------------------------------------- driving helpers (like drive.js)
## Player presses a direction: turn + step (if free) + Story.on_step.
func walk(path: String) -> void:
	for ch in path:
		var p: Vector2i = actors["PLAYER"]["cell"]
		actors["PLAYER"]["dir"] = DN[ch]
		var n: Vector2i = p + DV[ch]
		if not is_passable(n) or actor_at(n, "PLAYER") != "":
			continue
		actors["PLAYER"]["cell"] = n
		GameState.player_cell = n
		Story.on_step(n)

## Player faces `id` (must be adjacent) and presses A.
func talk(id: String) -> bool:
	var p: Vector2i = actors["PLAYER"]["cell"]
	var c: Vector2i = actors[id]["cell"] if actors.has(id) else Vector2i(int(Story.obj(id).get("x", 0)), int(Story.obj(id).get("y", 0)))
	actors["PLAYER"]["dir"] = Story.dir_towards(p, c)
	return Story.on_talk(Story.obj(id, map))
