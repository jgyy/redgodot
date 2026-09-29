extends Node
## Autoload `Story`: port of upstream src/game/story.js (the `S` scripting API),
## src/game/scripts.js (talk/sign/item glue), the trainer line-of-sight flow from
## battleflow.js/overworld.js, pc.js (nurse heal, Poké Mart), fieldmoves.js and
## the per-map event scripts in scripts/story/*.gd (ports of src/scripts/*.js).
##
## Upstream's `function*` / `yield*` generators become GDScript coroutines:
##   await Story.say("PalletTownOakItsUnsafeText")      # S.say
##   if await Story.ask(label): ...                     # S.ask
##   await Story.move("PALLETTOWN_OAK", "UUL")          # S.move
##   var r: String = await Story.battle("RIVAL1", 1, {...})  # S.battle
##
## Map scripts register with def_map(name, spec) exactly like G.defMapScript:
##   enter:  func() -> Callable            (sync part runs now; a valid Callable is run as a script)
##   step:   func(x: int, y: int) -> Callable  (coordinate trigger; Callable() = nothing)
##   talk:   {OBJ_ID: func(obj: Dictionary)}   (coroutine)
##   sign:   {TEXT_CONST: func(sign: Dictionary)}
##   hidden: {"x,y": func(h: Dictionary)}
##
## The Overworld calls the dispatch hooks (see CONTRACT.md): on_enter(map),
## on_step(cell) -> bool, on_talk(obj) -> bool, on_sign(sign) -> bool, plus the
## optional on_interact_cell(cell, dir) -> bool (hidden events, card-key doors,
## cut trees, surf), on_boulder_moved(id, cell), use_field_move(), use_field_item().
## Everything the story needs from the Overworld/UI/SceneRouter goes through
## get_host()/get_ui()/SceneRouter with has_method checks: a missing API logs one
## push_warning and is skipped, so the game never hard-crashes pre-integration.

signal script_started(name: String)
signal script_finished(name: String)

const PLAYER := "PLAYER"
const DIRC := {"U": "up", "D": "down", "L": "left", "R": "right"}
const DCHAR := {"up": "U", "down": "D", "left": "L", "right": "R"}
const DVEC := {"up": Vector2i(0, -1), "down": Vector2i(0, 1), "left": Vector2i(-1, 0), "right": Vector2i(1, 0)}
const OPP := {"up": "down", "down": "up", "left": "right", "right": "left"}

## fieldmoves.js FLY_SPOTS / BLACKOUT_SPOTS
const FLY_SPOTS := {
	"PalletTown": Vector2i(5, 6), "ViridianCity": Vector2i(23, 26), "PewterCity": Vector2i(13, 26),
	"CeruleanCity": Vector2i(19, 18), "LavenderTown": Vector2i(3, 6), "VermilionCity": Vector2i(11, 4),
	"CeladonCity": Vector2i(41, 10), "FuchsiaCity": Vector2i(19, 28), "CinnabarIsland": Vector2i(11, 12),
	"IndigoPlateau": Vector2i(9, 6), "SaffronCity": Vector2i(9, 30),
}
const EXTRA_BLACKOUT_SPOTS := {"Route4": Vector2i(11, 6), "Route10": Vector2i(11, 20)}
const KEY_ITEMS := ["TOWN_MAP", "BICYCLE", "SURFBOARD", "POKEDEX", "OLD_AMBER", "DOME_FOSSIL", "HELIX_FOSSIL",
	"SECRET_KEY", "BIKE_VOUCHER", "CARD_KEY", "S_S_TICKET", "GOLD_TEETH", "COIN_CASE", "OAKS_PARCEL",
	"ITEMFINDER", "SILPH_SCOPE", "POKE_FLUTE", "LIFT_KEY", "EXP_ALL", "OLD_ROD", "GOOD_ROD", "SUPER_ROD"]
const LEADERS := {"BROCK": "BROCK", "MISTY": "MISTY", "LT_SURGE": "LT.SURGE", "ERIKA": "ERIKA", "KOGA": "KOGA",
	"SABRINA": "SABRINA", "BLAINE": "BLAINE", "GIOVANNI": "GIOVANNI", "LORELEI": "LORELEI", "BRUNO": "BRUNO",
	"AGATHA": "AGATHA", "LANCE": "LANCE"}
const GYM_LEADER_MAPS := {"BROCK": "PewterGym", "MISTY": "CeruleanGym", "LT_SURGE": "VermilionGym", "ERIKA": "CeladonGym",
	"KOGA": "FuchsiaGym", "SABRINA": "SaffronGym", "BLAINE": "CinnabarGym", "GIOVANNI": "ViridianGym"}
const DARK_MAPS := ["RockTunnel1F", "RockTunnelB1F"]
const BIKE_TILESETS := ["overworld", "forest", "underground", "ship_port", "cavern"]
const BADGE_FOR := {"CUT": "CASCADEBADGE", "FLY": "THUNDERBADGE", "SURF": "SOULBADGE", "STRENGTH": "RAINBOWBADGE", "FLASH": "BOULDERBADGE"}
## mapdata.bookshelves: [tileset (tsc, upper snake), tile id, text label] (story.js G.fieldInteract)
const BOOKSHELVES := [["PLATEAU", 48, "IndigoPlateauStatues"], ["HOUSE", 61, "TownMapText"], ["HOUSE", 30, "BookOrSculptureText"],
	["MANSION", 50, "BookOrSculptureText"], ["REDS_HOUSE_1", 50, "BookOrSculptureText"], ["LAB", 40, "BookOrSculptureText"],
	["LOBBY", 22, "ElevatorText"], ["GYM", 29, "BookOrSculptureText"], ["DOJO", 29, "BookOrSculptureText"], ["GATE", 34, "BookOrSculptureText"],
	["MART", 84, "PokemonStuffText"], ["MART", 85, "PokemonStuffText"], ["POKECENTER", 84, "PokemonStuffText"], ["POKECENTER", 85, "PokemonStuffText"],
	["LOBBY", 80, "PokemonStuffText"], ["LOBBY", 82, "PokemonStuffText"], ["SHIP", 54, "BookOrSculptureText"]]
const BOOKSHELF_FALLBACK := {"BookOrSculptureText": "Crammed full of POKéMON books!", "TownMapText": "A TOWN MAP.",
	"PokemonStuffText": "Wow! Tons of POKéMON stuff!", "ElevatorText": "This is an elevator.",
	"IndigoPlateauStatues": "INDIGO PLATEAU\fThe ultimate goal of trainers! POKéMON LEAGUE HQ"}
const SCRIPT_FILES := ["res://scripts/story/Pallet.gd", "res://scripts/story/Early.gd", "res://scripts/story/Mid.gd",
	"res://scripts/story/Late.gd", "res://scripts/story/Extra.gd"]

# ------------------------------------------------------------------ injection points (tests / integration)
## Optional explicit Overworld host (the Overworld may call Story.set_host(self)); tests put a fake here.
var host_override: Node = null
## Optional UI double (tests); otherwise /root/UI.
var ui_override: Node = null
## Optional battle runner: Callable(enc: Dictionary) -> String (tests script results here).
var battle_override: Callable = Callable()
## Skip frame waits (tests run every script synchronously against the fake host).
var fast := false
## Extra text table checked before UI.raw_text (tests / tools).
var text_override: Dictionary = {}

# ------------------------------------------------------------------ runtime state
var running := 0                 # G.scriptRunning
var busy := 0                    # late.js `busy` (guarded sequences)
var text_vars: Dictionary = {}   # G.textVars
var maps: Dictionary = {}        # G.MAPSCRIPTS: name -> {enter:[Callable], step:[Callable], talk:{}, sign:{}, hidden:{}, before_static}
var after_trainer: Dictionary = {}   # mid.js AFTER_TRAINER: map -> Callable(obj)
var on_boulder_hooks: Array = []     # late.js G.onBoulderMoved chain: Callable(map, id, cell) -> Callable
var global_enter_hooks: Array = []   # Callable(map) run before map enter scripts
var global_step_hooks: Array = []    # Callable(map, x, y) -> Callable (after-step checks like force-bike)
var encounter_guards: Array = []     # Callable(map, x, y) -> bool (true = no wild battle here)
var pokedata: Dictionary = {}        # marts, trades, goodRod, superRod (not exposed by GameData)
var surfing := false
var biking := false
var strength := false
var flashed := false
var prev_map := ""
var cell_overrides: Dictionary = {}  # map -> {Vector2i: [label, passable]}  (S.setCell)
var warp_redirects: Dictionary = {}  # map -> [to, warp]  (elevators)
var sight_off: Dictionary = {}       # "Map:ID" -> true (Mt.Moon rockets stop spotting)
var modules: Array = []

var _host: Node = null
var _scripted := 0
var _warned: Dictionary = {}
var _overlay: Node = null
var _own_text: Dictionary = {}
var _own_text_loaded := false
var _cur_map := ""
var _last_enc: Dictionary = {}   # the encounter of the battle overlay currently open (SceneRouter.battle_started)

func _ready() -> void:
	pokedata = _load_json("res://data/pokedata.json")
	_patch_trainer_headers()
	for path in SCRIPT_FILES:
		if not ResourceLoader.exists(path):
			continue
		var scr: GDScript = load(path)
		if scr == null:
			push_warning("[Story] missing script module %s" % path)
			continue
		var mod: Object = scr.new()
		modules.append(mod)
		if mod.has_method("register"):
			mod.call("register")
	# random encounters (Overworld -> SceneRouter.start_battle) never pass through wild_battle(): tag them here
	var sr := get_node_or_null("/root/SceneRouter")
	if sr:
		sr.battle_started.connect(_on_battle_started)
		sr.battle_ended.connect(_on_battle_ended)

## Safari Zone flags for a wild encounter that did not come from wild_battle() (upstream encounters.check).
func _on_battle_started(enc: Dictionary) -> void:
	_last_enc = enc
	if str(enc.get("kind", "wild")) == "wild" and mapname().begins_with("SafariZone") and flag("EVENT_IN_SAFARI_ZONE") and GameState.safari_steps >= 0:
		enc["safari"] = true

## Out of SAFARI BALLs after such a random encounter: the PA announcement and back to the gate (SafariZoneCheck).
func _on_battle_ended(_result: String) -> void:
	var enc := _last_enc
	_last_enc = {}
	if enc.get("_via_story", false) or not enc.get("safari", false):
		return
	if in_safari() and GameState.safari_balls <= 0 and not flag("EVENT_SAFARI_GAME_OVER") and mapname().begins_with("SafariZone"):
		for m in modules:
			if m.has_method("safari_game_over"):
				spawn(Callable(m, "safari_game_over"), [], "safari_over")

func _load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var f := FileAccess.open(path, FileAccess.READ)
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	return parsed if parsed is Dictionary else {}

# ================================================================== registry
## G.defMapScript + mid/late.js def(): merges talk/sign/hidden, chains enter and step.
func def_map(map_name: String, spec: Dictionary) -> void:
	var cur: Dictionary = maps.get(map_name, {"enter": [], "step": [], "talk": {}, "sign": {}, "hidden": {}})
	for k in ["talk", "sign", "hidden"]:
		if spec.has(k):
			(cur[k] as Dictionary).merge(spec[k], true)
	if spec.has("enter"):
		(cur["enter"] as Array).append(spec["enter"])
	if spec.has("step"):
		(cur["step"] as Array).append(spec["step"])
	if spec.has("before_static"):
		cur["before_static"] = spec["before_static"]
	maps[map_name] = cur

# ================================================================== host / ui / audio resolution
func set_host(node: Node) -> void:
	_host = node

func get_host() -> Node:
	if host_override != null:
		return host_override
	if is_instance_valid(_host) and _host.is_inside_tree():
		return _host
	_host = null
	var sr := get_node_or_null("/root/SceneRouter")
	if sr:
		var act = sr.get("_active")
		if act is Node and is_instance_valid(act) and (act as Node).has_method("move_actor"):
			_host = act
			return _host
	for n in get_tree().get_nodes_in_group("overworld"):
		if n.has_method("move_actor"):
			_host = n
			return _host
	return null

func get_ui() -> Node:
	if ui_override != null:
		return ui_override
	return get_node_or_null("/root/UI")

func _audio() -> Node:
	return get_node_or_null("/root/Audio")

func _warn(what: String) -> void:
	if _warned.has(what):
		return
	_warned[what] = true
	push_warning("[Story] missing API %s - skipped" % what)

## Host query (synchronous). Returns `def` when the host or method is missing.
func hq(method: String, args: Array = [], def: Variant = null) -> Variant:
	var h := get_host()
	if h == null or not h.has_method(method):
		_warn("Overworld." + method)
		return def
	return h.callv(method, args)

## Host action (awaitable: move_actor, warp_to, fade_out...).
func ha(method: String, args: Array = []) -> Variant:
	var h := get_host()
	if h == null or not h.has_method(method):
		_warn("Overworld." + method)
		return null
	var r = await h.callv(method, args)
	return r

func _has_host(method: String) -> bool:
	var h := get_host()
	return h != null and h.has_method(method)

func ui_has(method: String) -> bool:
	var u := get_ui()
	return u != null and u.has_method(method)

# ================================================================== script runner
## G.spawnScript: runs `c` (a coroutine) with overworld input locked. Not awaited by callers.
func spawn(c: Callable, args: Array = [], script_name: String = "script") -> void:
	if not c.is_valid():
		return
	running += 1
	if running == 1:
		hq("lock_input", [true])
	script_started.emit(script_name)
	await c.callv(args)
	running -= 1
	script_finished.emit(script_name)
	if running == 0:
		hq("lock_input", [false])

## True while any story script runs (overworld should pause NPC wandering / input).
func is_running() -> bool:
	return running > 0

func wait(frames: int = 1) -> void:
	if fast or frames <= 0:
		return
	await get_tree().create_timer(frames / 60.0).timeout

## Wait for A/B (G.engine.run(box) with an update() closing on a press), at most max_frames.
func wait_button(max_frames: int = 600) -> void:
	if fast:
		return
	await wait(10)
	for i in max_frames:
		if Input.is_action_just_pressed("confirm") or Input.is_action_just_pressed("cancel"):
			return
		await get_tree().process_frame

# ================================================================== text
func _load_own_text() -> void:
	_own_text_loaded = true
	var d := _load_json("res://data/text.json")
	_own_text = d

## Raw upstream text for a label ('' when unknown): G.TEXT[label] (+ aliases).
func raw(label: String) -> String:
	if label == "":
		return ""
	var key := label.trim_prefix("_")
	if text_override.has(key):
		return str(text_override[key])
	var u := get_ui()
	if u and u.has_method("raw_text"):
		return str(u.call("raw_text", key))
	if not _own_text_loaded:
		_load_own_text()
	var t: Dictionary = _own_text.get("text", {})
	if t.has(key):
		return str(t[key])
	var al: Dictionary = _own_text.get("aliases", {})
	if al.has(key) and t.has(al[key]):
		return str(t[al[key]])
	return ""

func has_text(label: String) -> bool:
	return raw(label) != ""

## S.t / G.textFor: text or '...'.
func t(label: String) -> String:
	var r := raw(label)
	return r if r != "" else "..."

## early.js txt(): G.TEXT[l] or l itself.
func txt(label: String) -> String:
	var r := raw(label)
	return r if r != "" else label

## pc.js T(label, fallback)
func tf(label: String, fallback: String) -> String:
	var r := raw(label)
	return r if r != "" else fallback

## early.js join(...labels): texts joined by page breaks.
func join(labels: Array) -> String:
	var out: PackedStringArray = []
	for l in labels:
		out.append(txt(str(l)))
	return "\f".join(out)

func setvar(k: String, v: Variant) -> void:
	text_vars[k] = v
	var u := get_ui()
	if u and u.has_method("set_var"):
		u.call("set_var", k, v)

## G.fmt
func fmt(s: String) -> String:
	s = s.replace("{PLAYER}", GameState.player_name).replace("{RIVAL}", GameState.rival_name).replace("{PROMPT}", "")
	var re := RegEx.new()
	re.compile("\\{(\\w+)\\}")
	for m in re.search_all(s):
		var k := m.get_string(1)
		if text_vars.has(k):
			s = s.replace(m.get_string(0), str(text_vars[k]))
	re.compile(" +\f")
	s = re.sub(s, "\f", true)
	re.compile("\f +")
	s = re.sub(s, "\f", true)
	re.compile(" +([!?,]|\\.(?!\\.))")
	s = re.sub(s, "$1", true)
	re.compile(" {2,}")
	s = re.sub(s, " ", true)
	return s

## S.say: a text label or a literal string.
func say(x: String, opts: Dictionary = {}) -> void:
	var s := fmt(txt(x))
	var u := get_ui()
	if u == null or not u.has_method("say"):
		_warn("UI.say")
		print("[Story say] ", s)
		return
	await u.call("say", s, opts)

func ask(x: String) -> bool:
	var s := fmt(txt(x))
	var u := get_ui()
	if u == null or not u.has_method("ask"):
		_warn("UI.ask")
		return true
	var r = await u.call("ask", s)
	return bool(r)

func choose(items: Array, opts: Dictionary = {}) -> int:
	var u := get_ui()
	if u == null or not u.has_method("choose"):
		_warn("UI.choose")
		return -1
	var r = await u.call("choose", items, opts)
	return int(r)

## early.js menuWithText / mid.js chooseWith: question kept on screen under a menu.
## Drops the question left on screen by say(..., {"no_wait": true}) (upstream G.engine.pop(StaticBox)).
func drop_sticky() -> void:
	var u := get_ui()
	if u != null and u.has_method("_drop_sticky"):
		u.call("_drop_sticky")

func menu_with_text(label: String, items: Array, opts: Dictionary = {}) -> int:
	await say(label, {"no_wait": true})
	var o := opts.duplicate()
	o["keep_text"] = true
	return await choose(items, o)

# ================================================================== flags / visibility
func flag(f: String) -> bool:
	var v = GameState.flags.get(f)
	return not (v == null or v is bool and v == false)

func setf(f: String, v: Variant = true) -> void:
	GameState.flags[f] = v

func clear(f: String) -> void:
	GameState.flags.erase(f)

func mapname() -> String:
	var m = hq("current_map", [], null)
	if m is String and m != "":
		return m
	return _cur_map if _cur_map != "" else GameState.current_map

func map_data(map_name: String = "") -> Dictionary:
	return GameData.maps.get(map_name if map_name != "" else mapname(), {})

func obj(id: String, map_name: String = "") -> Dictionary:
	for o in map_data(map_name).get("objs", []):
		if o.get("id", "") == id:
			return o
	return {}

func key(map_name: String, id: String) -> String:
	return map_name + ":" + id

## S.isShown (+ picked-up item balls, like Overworld.spawnActors)
func is_shown(id: String, map_name: String = "") -> bool:
	var m := map_name if map_name != "" else mapname()
	var k := key(m, id)
	var o := obj(id, m)
	if o.has("item") and flag("GOT_" + k):
		return false
	if GameState.toggles.has(k):
		return bool(GameState.toggles[k])
	if o.is_empty():
		return false
	return bool(o.get("shown", true))

## S.actor(id) truthiness: shown on the current map right now.
func actor(id: String) -> bool:
	if id == PLAYER:
		return true
	if _has_host("is_actor_shown"):
		return bool(hq("is_actor_shown", [id], false))
	return is_shown(id)

func hide(id: String, map_name: String = "") -> void:
	var m := map_name if map_name != "" else mapname()
	GameState.toggles[key(m, id)] = false
	if m == mapname():
		hq("hide_actor", [id])

## S.show: returns the id, or "" when the object doesn't exist on that map.
func show(id: String, map_name: String = "", pos: Vector2i = Vector2i(-1, -1)) -> String:
	var m := map_name if map_name != "" else mapname()
	GameState.toggles[key(m, id)] = true
	if m != mapname():
		return id
	var o := obj(id, m)
	if o.is_empty():
		return ""
	if not actor(id):
		var c := pos if pos.x >= 0 else Vector2i(int(o.get("x", 0)), int(o.get("y", 0)))
		hq("show_actor", [id, c])
		var d := str(o.get("dir", "")).to_lower()
		hq("face_actor", [id, d if DVEC.has(d) else "down"])
	return id

## rival.x = x; rival.y = y; rival.dir = d  (teleport a shown actor)
func place(id: String, x: int, y: int, d: String = "down") -> void:
	hq("show_actor", [id, Vector2i(x, y)])
	face(id, d)

# ================================================================== actors
func pcell() -> Vector2i:
	var c = hq("actor_cell", [PLAYER], null)
	return c if c is Vector2i else GameState.player_cell

func pdir() -> String:
	var d = hq("actor_dir", [PLAYER], null)
	return d if d is String and d != "" else GameState.player_facing

func cell(id: String) -> Vector2i:
	if id == PLAYER:
		return pcell()
	var c = hq("actor_cell", [id], null)
	if c is Vector2i:
		return c
	var o := obj(id)
	return Vector2i(int(o.get("x", 0)), int(o.get("y", 0)))

func dir_of(id: String) -> String:
	if id == PLAYER:
		return pdir()
	var d = hq("actor_dir", [id], null)
	if d is String and d != "":
		return d
	var od := str(obj(id).get("dir", "")).to_lower()
	return od if DVEC.has(od) else "down"

func face(id: String, d: String) -> void:
	if id == "" or not DVEC.has(d):
		return
	hq("face_actor", [id, d])
	if id == PLAYER:
		GameState.player_facing = d

static func dir_towards(from: Vector2i, to: Vector2i) -> String:
	var dx := to.x - from.x
	var dy := to.y - from.y
	if absi(dx) > absi(dy):
		return "right" if dx > 0 else "left"
	return "down" if dy > 0 else "up"

func face_player(id: String) -> void:
	face(id, dir_towards(cell(id), pcell()))

func face_to(a: String, b: String) -> void:
	face(a, dir_towards(cell(a), cell(b)))

func _occupied(c: Vector2i, except: String) -> bool:
	if except != PLAYER and pcell() == c:
		return true
	for o in map_data().get("objs", []):
		var id: String = o.get("id", "")
		if id == except or not actor(id):
			continue
		if cell(id) == c:
			return true
	return false

func _passable(c: Vector2i) -> bool:
	return bool(hq("is_passable", [c], true))

## story.js safeRoute: keep a hand-written route while it's walkable, else re-route to its end.
func _safe_route(id: String, path: String) -> String:
	var c := cell(id)
	var ok := true
	for i in path.length():
		var ch := path[i]
		if not DIRC.has(ch):
			return path
		var n: Vector2i = c + DVEC[DIRC[ch]]
		if i < path.length() - 1 and (not _passable(n) or _occupied(n, id)):
			ok = false
		c = n
	if ok:
		return path
	if not _has_host("path_to"):
		return path
	var p = hq("path_to", [cell(id), c], "")
	return p if p is String and p != "" else path

## S.pathTo: walkable route, else straight lines (y-up first, then x, then y-down).
func path_to(id: String, tx: int, ty: int) -> String:
	var from := cell(id)
	if from == Vector2i(tx, ty):
		return ""
	var p = hq("path_to", [from, Vector2i(tx, ty)], "")
	if p is String and p != "":
		return p
	var s := ""
	var dx := tx - from.x
	var dy := ty - from.y
	if dy < 0:
		s += "U".repeat(-dy)
	s += ("R" if dx > 0 else "L").repeat(absi(dx))
	if dy > 0:
		s += "D".repeat(dy)
	return s

## S.move: walk an actor along 'UDLR'.
func move(id: String, path: String, speed: int = 1) -> void:
	if id == "" or path == "":
		return
	if id == PLAYER:
		await move_player(path, speed)
		return
	if not actor(id):
		return
	await ha("move_actor", [id, _safe_route(id, path)])

## S.movePlayer: scripted walk (never sets off step triggers / trainers).
func move_player(path: String, _speed: int = 1) -> void:
	if path == "":
		return
	_scripted += 1
	await ha("move_actor", [PLAYER, _safe_route(PLAYER, path)])
	_scripted -= 1
	GameState.player_cell = pcell()
	GameState.player_facing = pdir()

## S.moveTogether: [[id, "UUL"], [PLAYER, "DUU"]] walked in lock-step.
func move_together(pairs: Array) -> void:
	var n := 0
	for p in pairs:
		n = maxi(n, str(p[1]).length())
	_scripted += 1
	for i in n:
		var step: Array = []
		for p in pairs:
			var path := str(p[1])
			if i < path.length() and DIRC.has(path[i]):
				step.append([p[0], path[i]])
		if not step.is_empty():
			await ha("move_together", [step])
	_scripted -= 1
	GameState.player_cell = pcell()

func emote(id: String, kind: String = "!", _n: int = 40) -> void:
	sfx("exclaim" if kind == "!" else "blip")
	await ha("emote", [id, kind])

func fade_out(frames: int = 10) -> void:
	await ha("fade_out", [frames])

func fade_in(frames: int = 10) -> void:
	await ha("fade_in", [frames])

## S.warp
func warp(map_name: String, x: int, y: int, d: String = "", _no_fade: bool = false) -> void:
	await ha("warp_to", [map_name, Vector2i(x, y), d if d != "" else pdir()])

func shake(frames: int = 6) -> void:
	hq("shake", [frames])

# ================================================================== audio
func music(song: String, jingle: bool = false) -> void:
	var a := _audio()
	if a and a.has_method("music"):
		a.call("music", song, jingle)

func stop_music() -> void:
	var a := _audio()
	if a and a.has_method("stop_music"):
		a.call("stop_music")

func map_music() -> void:
	var a := _audio()
	if a and a.has_method("map_song"):
		music(str(a.call("map_song", mapname())))

func sfx(n: String) -> void:
	var a := _audio()
	if a and a.has_method("sfx"):
		a.call("sfx", n)

func cry(sp: String) -> void:
	var a := _audio()
	if a and a.has_method("cry"):
		a.call("cry", sp)

# ================================================================== names / dex
func item_name(id: String) -> String:
	var it: Dictionary = GameData.items.get(id, {})
	return str(it.get("name", id))

func item_price(id: String) -> int:
	return int((GameData.items.get(id, {}) as Dictionary).get("price", 0))

func species_name(sp: String) -> String:
	return str(GameData.get_species(sp).get("name", sp))

func mon_name(m: Object) -> String:
	# upstream Mon.name: the nickname, else the species' display name (PartyMon.nickname defaults to the species id,
	# e.g. "MR_MIME" / "NIDORAN_M")
	if m == null:
		return ""
	if m.has_method("display_name"):
		return str(m.call("display_name"))
	return str(m.get("nickname"))

func dex_seen(sp: String) -> void:
	GameState.mark_seen(sp)

func dex_caught(sp: String) -> void:
	GameState.seen_species[sp] = true
	GameState.caught_species[sp] = true

func caught_count() -> int:
	return GameState.caught_species.size()

func dex_page(sp: String) -> void:
	dex_seen(sp)
	var u := get_ui()
	if u and u.has_method("dex_page"):
		await u.call("dex_page", sp)
	elif u != null and u.get("layer") is Node and is_inside_tree():
		# no UI hook: show the POKéDEX data page (menus.js dexPage) with the pokedex screen itself
		var screen := PokedexMenu.new()
		(u.get("layer") as Node).add_child(screen)
		screen.open()
		screen.page_species = sp
		screen.busy = false
		while is_instance_valid(screen) and screen.page_species != "":
			await get_tree().process_frame
		if is_instance_valid(screen):
			screen.queue_free()
	else:
		_warn("UI.dex_page")

# ================================================================== bag / money (bag.js)
func is_key(id: String) -> bool:
	return KEY_ITEMS.has(id) or id.begins_with("HM_")

func bag_count(id: String) -> int:
	return int(GameState.bag.get(id, 0))

func bag_has(id: String) -> bool:
	return bag_count(id) > 0

## 20 slots, 99 per stack; anything that won't fit is refused whole.
func bag_can_add(id: String, n: int = 1) -> bool:
	if GameState.bag.has(id):
		return KEY_ITEMS.has(id) or bag_count(id) + n <= 99
	return GameState.bag.size() < 20

func bag_add(id: String, n: int = 1) -> bool:
	if not bag_can_add(id, n):
		return false
	if GameState.bag.has(id):
		if not KEY_ITEMS.has(id):
			GameState.bag[id] = bag_count(id) + n
		return true
	GameState.bag[id] = 1 if KEY_ITEMS.has(id) else n
	return true

func bag_remove(id: String, n: int = 1) -> bool:
	if not GameState.bag.has(id):
		return false
	GameState.bag[id] = bag_count(id) - n
	if bag_count(id) <= 0:
		GameState.bag.erase(id)
	return true

func has_badge(b: String) -> bool:
	return GameState.badges.has(b)

func badge_count() -> int:
	return GameState.badges.size()

func party_has(sp: String) -> bool:
	for m in GameState.party:
		if m.species_id == sp:
			return true
	return false

func heal_all() -> void:
	# PartyMon.heal_full(): HP, status, sleep counter and PP back to each move's max (PP UPs included)
	for m in GameState.party:
		m.heal_full()
	GameState.party_changed.emit()

## G.rivalParty: rival party index offset by the starter he picked.
func rival_party(base: int) -> int:
	var off := {"CHARMANDER": 1, "SQUIRTLE": 2, "BULBASAUR": 3}
	return base + int(off.get(GameState.starter, 1)) - 1

## S.give: "{PLAYER} received ITEM!" (or `msg`), with the right jingle.
func give(item: String, n: int = 1, msg: String = "") -> bool:
	if not bag_add(item, n):
		await say("No more room for items!")
		return false
	sfx("get_tm" if item.begins_with("TM_") or item.begins_with("HM_") else ("get_key" if is_key(item) else "get_item"))
	setvar("wStringBuffer", item_name(item))
	setvar("wNameBuffer", item_name(item))
	if msg != "":
		await say(fmt(txt(msg)))
	else:
		await say(GameState.player_name + " received " + (str(n) + " " if n > 1 else "") + item_name(item) + "!")
	return true

## early.js got(): silent add + jingle + optional label.
func got(item: String, n: int = 1, label: String = "") -> bool:
	if not bag_add(item, n):
		return false
	setvar("wStringBuffer", item_name(item))
	sfx("get_tm" if item.begins_with("TM_") or item.begins_with("HM_") else ("get_key" if is_key(item) else "get_item"))
	if label != "":
		await say(label)
	return true

## mid.js / late.js giveItem(): the NPC's own no-room text when the bag is full.
func give_item(item: String, recv: String, no_room: String = "", n: int = 1) -> bool:
	if not bag_add(item, n):
		if no_room != "":
			await say(no_room)
		else:
			await say("No more room for items!")
		return false
	setvar("wStringBuffer", item_name(item))
	setvar("wNameBuffer", item_name(item))
	sfx("get_tm" if item.begins_with("TM_") or item.begins_with("HM_") else ("get_key" if is_key(item) else "get_item"))
	if recv != "":
		await say(recv)
	else:
		await say(GameState.player_name + " received " + item_name(item) + "!")
	return true

# ================================================================== Pokémon
func new_mon(sp: String, lv: int) -> Object:
	# upstream new G.Mon(sp, lv): random DVs and the player as original trainer
	var m := GameState.PartyMon.new(sp, lv, {"random": true})
	m.ot = GameState.player_name
	return m

func _box() -> Array:
	return GameState.box()

## G.receiveMon: nickname prompt, then party or PC box.
func receive_mon(m: Object) -> String:
	var spn := species_name(str(m.get("species_id")))
	if await ask("Do you want to give a nickname to " + spn + "?"):
		var n := await name_entry(spn + "'s nickname?", spn, 10)
		if n != "" and n != spn:
			m.set("nickname", n)
	if GameState.party.size() < 6:
		GameState.party.append(m)
		GameState.party_changed.emit()
		return "party"
	var box := _box()
	if box.size() >= 20:
		await say("The POKéMON BOX is full! It can't accept any more POKéMON!")
		return "full"
	box.append(m)
	await say(mon_name(m) + " was transferred to " + ("BILL's PC" if flag("EVENT_MET_BILL") else "someone's PC") + "!")
	return "box"

## S.giveMon
func give_mon(sp: String, lv: int) -> String:
	var m := new_mon(sp, lv)
	sfx("get_mon")
	await say(GameState.player_name + " got " + species_name(sp) + "!")
	dex_caught(sp)
	return await receive_mon(m)

## S.giftMon
func gift_mon(sp: String, lv: int, f: String = "") -> bool:
	if f != "" and flag(f):
		return false
	if GameState.party.size() >= 6 and _box().size() >= 20:
		await say("There's no more room for POKéMON!")
		return false
	await give_mon(sp, lv)
	if f != "":
		setf(f)
	return true

func name_entry(prompt: String, def: String, max_len: int = 10) -> String:
	var u := get_ui()
	if u and u.has_method("name_entry"):
		var r = await u.call("name_entry", prompt, def, max_len)
		return str(r)
	# no UI hook: use the naming screen directly on the UI layer (menus.js namingScreen)
	if u != null and u.get("layer") is Node:
		return await NamingScreen.ask_name(u.get("layer") as Node, prompt, def, max_len)
	_warn("UI.name_entry")
	return def

## G.partyScreen({msg}) -> index or -1
func party_screen(msg: String) -> int:
	var u := get_ui()
	if u and u.has_method("choose_party"):
		var r = await u.call("choose_party", msg)
		return int(r)
	var names: Array = []
	for m in GameState.party:
		names.append("%s  Lv%d" % [m.display_name(), m.level])
	await say(msg, {"no_wait": true})
	return await choose(names, {"x": 100, "y": 4, "w": 214})

## S.inGameTrade (story.js) - texts: {ask, wrong, no, done, after} labels or strings.
func in_game_trade(idx: int, texts: Dictionary) -> void:
	var tr: Dictionary = (pokedata.get("trades", []) as Array)[idx]
	var k := "TRADED_%d" % idx
	var give_n := species_name(tr["give"])
	var get_n := species_name(tr["get"])
	setvar("wInGameTradeGiveMonName", give_n)
	setvar("wInGameTradeReceiveMonName", get_n)
	if flag(k):
		await say(texts.get("after", "How is my old " + get_n + "?"))
		return
	if not await ask(texts.get("ask", "I'm looking for " + give_n + "! Wanna trade one for " + get_n + "?")):
		await say(texts.get("no", "Well, if you don't want to..."))
		return
	var i := await party_screen("Trade which POKéMON?")
	if i < 0:
		await say(texts.get("no", "Well, if you don't want to..."))
		return
	var m: Object = GameState.party[i]
	if m.get("species_id") != tr["give"]:
		await say(texts.get("wrong", "Hmmm? This isn't " + give_n + "."))
		return
	var nm := new_mon(tr["get"], int(m.get("level")))
	nm.set("nickname", tr["nick"])
	nm.set("ot", "TRAINER")  # traded: BattleEngine gives it the 1.5x traded-Pokémon EXP bonus
	GameState.party[i] = nm
	GameState.party_changed.emit()
	dex_caught(tr["get"])
	setf(k)
	await trade_animation(m, nm)
	await say(GameState.player_name + " traded " + mon_name(m) + " for " + str(tr["nick"]) + "!")
	await say(texts.get("done", "Thanks!"))

func trade_animation(give_m: Object, get_m: Object) -> void:
	var u := get_ui()
	if u and u.has_method("trade_animation"):
		await u.call("trade_animation", give_m, get_m)
		return
	await fade_out(10)
	await wait(60)
	cry(str(get_m.get("species_id")))
	await fade_in(10)

# ================================================================== battles
## S.battle(cls, n, {win_text, lose_text, no_blackout}) -> "win"|"lose"|"run"|"caught"
func battle(cls: String, n: int = 1, opts: Dictionary = {}) -> String:
	var tc: Dictionary = GameData.trainer_classes.get(cls, {"name": cls, "money": 1000})
	var is_rival := cls.begins_with("RIVAL")
	var display: String = opts.get("display_name", GameState.rival_name if is_rival else LEADERS.get(cls, str(tc.get("name", cls))))
	var boss := LEADERS.has(cls) or is_rival
	var enc := {
		"kind": "trainer", "trainer_class": cls, "party_index": maxi(1, n), "name": display,
		"win_text": opts.get("win_text", ""), "lose_text": opts.get("lose_text", ""),
		"no_blackout": bool(opts.get("no_blackout", false)), "money": int(tc.get("money", 1000)),
		"transition": "boss" if boss else "trainer", "music": battle_song(cls),
	}
	return await _run_battle(enc)

func battle_song(cls: String) -> String:
	if cls == "RIVAL3":
		return "final_battle"
	if cls == "LANCE" or (GYM_LEADER_MAPS.get(cls, "") == mapname()):
		return "gym_leader"
	return "trainer"

## G.startWildBattle (+ Pokémon Tower ghosts / Safari flags from mid.js & late.js)
func wild_battle(sp: String, lv: int, opts: Dictionary = {}) -> String:
	var enc := {"kind": "wild", "species": sp, "level": lv, "_via_story": true}
	enc.merge(opts, true)
	var tower := RegEx.create_from_string("^PokemonTower[1-7]F$")
	if not opts.get("restless_soul", false) and tower.search(mapname()) != null and not bag_has("SILPH_SCOPE"):
		enc["ghost"] = true
	if opts.get("restless_soul", false) and not bag_has("SILPH_SCOPE"):
		enc["ghost"] = true
	if enc.get("ghost", false) or enc.get("restless_soul", false):
		enc["no_catch"] = true
	if mapname().begins_with("SafariZone") and flag("EVENT_IN_SAFARI_ZONE") and GameState.safari_steps >= 0:
		enc["safari"] = true
	var r := await _run_battle(enc)
	if enc.get("safari", false) and in_safari() and GameState.safari_balls <= 0 and not flag("EVENT_SAFARI_GAME_OVER") and mapname().begins_with("SafariZone"):
		for m in modules:
			if m.has_method("safari_game_over"):
				await m.call("safari_game_over")
	return r

func in_safari() -> bool:
	return flag("EVENT_IN_SAFARI_ZONE") and GameState.safari_steps >= 0

func _run_battle(enc: Dictionary) -> String:
	var r := "win"
	if battle_override.is_valid():
		r = str(await battle_override.call(enc))
	else:
		var sr := get_node_or_null("/root/SceneRouter")
		if sr and sr.has_method("battle"):
			r = str(await sr.call("battle", enc))
		else:
			_warn("SceneRouter.battle")
	if r == "lose" and not enc.get("no_blackout", false):
		await blackout()
	return r

## battleflow.js blackout(): back to the last healed town, money halved, party restored.
func blackout() -> void:
	GameState.money = int(GameState.money / 2.0)
	heal_all()
	surfing = false
	biking = false
	hq("set_ride", ["walk"])
	var h: Dictionary = GameState.last_heal_town if not GameState.last_heal_town.is_empty() else {"map": "PalletTown", "x": 5, "y": 6}
	await warp(str(h["map"]), int(h["x"]), int(h["y"]), "down")

## S.awardBadge
func award_badge(badge: String, text: String = "") -> void:
	if not GameState.badges.has(badge):
		GameState.badges.append(badge)
		GameState.badge_earned.emit(badge)
	sfx("get_badge")
	music("badge", true)
	await say(text if text != "" else GameState.player_name + " received the " + badge + "!")
	map_music()

# ================================================================== trainers (battleflow.js)
func _patch_trainer_headers() -> void:
	# early.js patchRoute9, mid.js patchRockTunnel1F, late.js patchRoute15: headers the importer missed
	var r9 := [["COOLTRAINER_F1", 0, 3, "CooltrainerF1"], ["COOLTRAINER_M1", 1, 2, "CooltrainerM1"], ["COOLTRAINER_M2", 2, 4, "CooltrainerM2"],
		["COOLTRAINER_F2", 3, 2, "CooltrainerF2"], ["HIKER1", 4, 2, "Hiker1"], ["HIKER2", 5, 3, "Hiker2"], ["YOUNGSTER1", 6, 4, "Youngster1"],
		["HIKER3", 7, 2, "Hiker3"], ["YOUNGSTER2", 8, 2, "Youngster2"]]
	for h in r9:
		var o := obj("ROUTE9_" + str(h[0]), "Route9")
		if not o.is_empty() and o.has("trainer") and not o.has("th"):
			o["th"] = {"flag": "EVENT_BEAT_ROUTE_9_TRAINER_%d" % h[1], "range": h[2], "battle": "Route9%sBattleText" % h[3],
				"end": "Route9%sEndBattleText" % h[3], "after": "Route9%sAfterBattleText" % h[3]}
	var rt := {"HIKER1": [0, 4, "Hiker1"], "HIKER2": [1, 4, "Hiker2"], "HIKER3": [2, 3, "Hiker3"], "SUPER_NERD": [3, 3, "SuperNerd"],
		"COOLTRAINER_F1": [4, 4, "CooltrainerF1"], "COOLTRAINER_F2": [5, 4, "CooltrainerF2"], "COOLTRAINER_F3": [6, 4, "CooltrainerF3"]}
	for o in map_data("RockTunnel1F").get("objs", []):
		var k := str(o.get("id", "")).replace("ROCKTUNNEL1F_", "")
		if not rt.has(k) or o.has("th"):
			continue
		var h: Array = rt[k]
		var p := "RockTunnel1F" + str(h[2])
		o["th"] = {"flag": "EVENT_BEAT_ROCK_TUNNEL_1_TRAINER_%d" % h[0], "range": h[1], "battle": p + "BattleText", "end": p + "EndBattleText", "after": p + "AfterBattleText"}
	var names := ["CooltrainerF1", "CooltrainerF2", "CooltrainerM1", "CooltrainerM2", "Beauty1", "Beauty2", "Biker1", "Biker2", "CooltrainerF3", "CooltrainerF4"]
	var ranges := [2, 3, 3, 3, 2, 3, 3, 3, 3, 3]
	var i := 0
	for o in map_data("Route15").get("objs", []):
		if not o.has("trainer"):
			continue
		if not o.has("th") and i < names.size():
			o["th"] = {"flag": "EVENT_BEAT_ROUTE_15_TRAINER_%d" % i, "range": ranges[i], "battle": "Route15%sBattleText" % names[i],
				"end": "Route15%sEndBattleText" % names[i], "after": "Route15%sAfterBattleText" % names[i]}
		i += 1

## G.trainerTalk
func trainer_talk(o: Dictionary) -> void:
	var th: Dictionary = o.get("th", {})
	if flag(th.get("flag", "")):
		await say(th.get("after", ""))
		return
	await trainer_battle_flow(o)

## G.trainerBattleFlow (+ mid.js AFTER_TRAINER per-map hooks)
func trainer_battle_flow(o: Dictionary) -> String:
	var th: Dictionary = o.get("th", {})
	var tr: Dictionary = o.get("trainer", {})
	await say(th.get("battle", ""))
	var r := await battle(str(tr.get("cls", "")), int(tr.get("n", 1)), {"win_text": fmt(t(th.get("end", "")))})
	if r == "win":
		setf(th.get("flag", ""))
		var hook: Callable = after_trainer.get(mapname(), Callable())
		if hook.is_valid():
			await hook.call(o)
	return r

## Overworld.trainerInSight: {id, dist} of an undefeated trainer looking at the player.
func trainer_in_sight() -> Dictionary:
	var p := pcell()
	var m := mapname()
	for o in map_data(m).get("objs", []):
		if not o.has("trainer") or not o.has("th"):
			continue
		var id: String = o.get("id", "")
		if sight_off.has(key(m, id)) or not actor(id) or flag(o["th"].get("flag", "")):
			continue
		var d := dir_of(id)
		var c := cell(id)
		var rng := int(o["th"].get("range", 0))
		for k in range(1, rng + 1):
			var q: Vector2i = c + DVEC[d] * k
			if q == p:
				return {"id": id, "dist": k - 1}
			if not (_passable(q) or bool(hq("is_water", [q], false))) or _occupied(q, id):
				break
	return {}

## G.startTrainerSighted: "!" emote, walk up to the player, battle.
func trainer_sighted(id: String, dist: int) -> void:
	var o := obj(id)
	music("encounter_" + str(o.get("trainer", {}).get("cls", "")))
	await emote(id, "!", 40)
	var d := dir_of(id)
	if dist > 0:
		await ha("move_actor", [id, str(DCHAR[d]).repeat(dist)])
	face(PLAYER, OPP[d])
	await trainer_battle_flow(o)

# ================================================================== dispatch hooks (called by the Overworld)
## Map loaded (called after actors spawn). Runs global hooks + the map's enter scripts.
func on_enter(map_name: Variant = "") -> void:
	var m := ""
	if map_name is String:
		m = map_name
	elif map_name is Object:
		m = str((map_name as Object).get("name"))
	if m == "":
		m = mapname()
	prev_map = _cur_map
	_cur_map = m
	GameState.current_map = m
	var md := map_data(m)
	var ts := str(md.get("ts", ""))
	if ts == "overworld" or ts == "plateau":
		GameState.last_outdoor = m
		if FLY_SPOTS.has(m):
			GameState.visited[m] = true
	if biking and not bike_allowed(m):
		biking = false
	# re-apply persistent cell overrides / elevator exits for this map
	for c in (cell_overrides.get(m, {}) as Dictionary):
		var v: Array = cell_overrides[m][c]
		hq("set_cell_override", [c, v[0], v[1]])
	if warp_redirects.has(m):
		hq("set_exit_warps", [warp_redirects[m][0], warp_redirects[m][1]])
	for h in global_enter_hooks:
		(h as Callable).call(m)
	var ms: Dictionary = maps.get(m, {})
	for e in ms.get("enter", []):
		var g = (e as Callable).call()
		if g is Callable and (g as Callable).is_valid():
			spawn(g, [], "enter:" + m)

## Player finished a step onto `c` (not called for scripted walks). true = a script took over.
func on_step(c: Variant = null) -> bool:
	var p: Vector2i = c if c is Vector2i else pcell()
	GameState.player_cell = p
	if _scripted > 0:
		return false
	GameState.steps += 1
	if not GameState.daycare.is_empty():
		GameState.daycare["steps"] = int(GameState.daycare.get("steps", 0)) + 1
	var m := mapname()
	for h in global_step_hooks:
		var g = (h as Callable).call(m, p.x, p.y)
		if g is Callable and (g as Callable).is_valid():
			spawn(g, [], "after_step")
			return true
	if _poison_step():
		return true
	var ms: Dictionary = maps.get(m, {})
	for s in ms.get("step", []):
		var g2 = (s as Callable).call(p.x, p.y)
		if g2 is Callable and (g2 as Callable).is_valid():
			spawn(g2, [], "step:" + m)
			return true
	var seen := trainer_in_sight()
	if not seen.is_empty():
		spawn(trainer_sighted, [seen["id"], seen["dist"]], "sighted")
		return true
	return false

## Talking to an object (A button). obj = mapdata obj Dictionary or its id.
func on_talk(o: Variant) -> bool:
	var od: Dictionary = o if o is Dictionary else obj(str(o))
	if od.is_empty():
		return false
	var id: String = od.get("id", "")
	var full := obj(id)
	if not full.is_empty():
		od = full
	var item := str(od.get("item", ""))
	if item != "" and item != "0":
		spawn(pickup_item, [od], "item")
		return true
	var sprite := str(od.get("sprite", ""))
	var cobj = (GameData.cast.get(sprite, {}) as Dictionary).get("object")
	if cobj == null or (cobj is bool and cobj == false):
		face(id, OPP.get(pdir(), "down"))
	var m := mapname()
	var ms: Dictionary = maps.get(m, {})
	var talk: Dictionary = ms.get("talk", {})
	if talk.has(id):
		spawn(talk[id], [od], "talk:" + id)
		return true
	if sprite == "nurse":
		spawn(nurse_heal, [od], "nurse")
		return true
	if sprite == "link_receptionist" and (m.contains("Pokecenter") or m.contains("Lobby")):
		spawn(_cable_club_default, [], "cable")
		return true
	if od.has("mon"):
		spawn(static_encounter, [od], "static")
		return true
	var marts: Dictionary = pokedata.get("marts", {})
	if sprite == "clerk" and marts.has(od.get("textLabel", "")):
		spawn(mart, [marts[od["textLabel"]]], "mart")
		return true
	if od.has("trainer") and od.has("th"):
		spawn(trainer_talk, [od], "trainer")
		return true
	if get_ui() == null:
		return false
	spawn(say, [t(str(od.get("textLabel", "")))], "talk")
	return true

func _cable_club_default() -> void:
	await say(tf("CableClubNPCWelcomeText", "Welcome to the Cable Club!"))
	await say(tf("CableClubNPCAreaReservedFor2FriendsLinkedByCableText", "This area is reserved for 2 friends linked by cable."))
	await say(tf("CableClubNPCPleaseComeAgainText", "Please come again!"))

func on_sign(s: Variant) -> bool:
	var sd: Dictionary = s if s is Dictionary else {}
	var ms: Dictionary = maps.get(mapname(), {})
	var signs: Dictionary = ms.get("sign", {})
	var k := str(sd.get("text", ""))
	if signs.has(k):
		spawn(signs[k], [sd], "sign:" + k)
		return true
	if get_ui() == null:
		return false
	spawn(say, [t(str(sd.get("textLabel", "")))], "sign")
	return true

## A pressed facing `c` with nothing to talk to / no sign: hidden events,
## card-key doors, cut trees, water (upstream hiddenEvent + fieldInteract).
func on_interact_cell(c: Vector2i, d: String = "") -> bool:
	if d == "":
		d = pdir()
	for h in map_data().get("hidden", []):
		if int(h.get("x", -1)) == c.x and int(h.get("y", -1)) == c.y:
			var g := hidden_event(h, d)
			if g.is_valid():
				spawn(g, [h], "hidden")
				return true
	var f := field_interact(c)
	if f.is_valid():
		spawn(f, [], "field")
		return true
	return false

## G.hiddenEvent: returns the coroutine to run (Callable taking h) or Callable().
func hidden_event(h: Dictionary, d: String) -> Callable:
	var ms: Dictionary = maps.get(mapname(), {})
	var k := "%d,%d" % [int(h.get("x", 0)), int(h.get("y", 0))]
	if (ms.get("hidden", {}) as Dictionary).has(k):
		return ms["hidden"][k]
	var fn := str(h.get("fn", ""))
	match fn:
		"OpenPokemonCenterPC", "OpenRedsPC", "BillsHousePC":
			return use_pc_h if d == "up" else Callable()
		"HiddenItems":
			return _hidden_item
		"HiddenCoins":
			return _hidden_coins
		"PrintBenchGuyText":
			return Callable()
		"PrintBookcaseText":
			return _say_h.bind(tf("BookcaseText", "Crammed full of POKéMON books!"))
		"PrintMagazinesText":
			return _say_h.bind(tf("MagazinesText", "POKéMON magazines! POKéMON notebooks! POKéMON graphs!"))
		"PrintTrashText":
			return _say_h.bind(tf("TrashText", "Nothing here but trash."))
		"PrintRedSNESText":
			return _say_h.bind(tf("RedBedroomSNESText", GameState.player_name + " is playing the SNES!\f...Okay! It's time to go!"))
		"GymStatues":
			return _gym_statue if d == "up" else Callable()
		"StartSlotMachine":
			return Callable()
		"GymTrashScript", "PrintCinnabarQuiz":
			for m in modules:
				if m.has_method("hidden_fn"):
					var c: Callable = m.call("hidden_fn", fn, h, d)
					if c.is_valid():
						return c
			return Callable()
	var arg := str(h.get("arg", ""))
	if arg != "" and has_text(arg):
		return _say_h.bind(raw(arg))
	return Callable()

func _say_text(text: String) -> void:
	await say(text)

func _say_h(_h: Dictionary, text: String) -> void:
	await say(text)

func use_pc_h(_h: Dictionary) -> void:
	await use_pc()

func _hidden_item(h: Dictionary) -> void:
	var k := "HIDDEN_%s_%d_%d" % [mapname(), int(h["x"]), int(h["y"])]
	if flag(k):
		return
	var item := str(h.get("arg", ""))
	var found := GameState.player_name + " found " + item_name(item) + "!"
	if not bag_can_add(item, 1):
		await say(found + "\f" + fmt(t("HiddenItemBagFullText")))
		return
	setf(k)
	await give(item, 1, found)

func _hidden_coins(h: Dictionary) -> void:
	var k := "HIDDENCOIN_%s_%d_%d" % [mapname(), int(h["x"]), int(h["y"])]
	if flag(k) or not bag_has("COIN_CASE"):
		return
	setf(k)
	var digits := RegEx.create_from_string("\\D").sub(str(h.get("arg", "")), "", true)
	var n := int(digits) if digits != "" else 10
	if n == 0:
		n = 10
	GameState.coins = mini(9999, GameState.coins + n)
	await say(GameState.player_name + " found " + str(n) + " coins!")

func _gym_statue(_h: Dictionary) -> void:
	var gym := mapname().replace("Gym", "").to_upper()
	var leader_flag: String = {"PEWTER": "EVENT_BEAT_BROCK", "CERULEAN": "EVENT_BEAT_MISTY", "VERMILION": "EVENT_BEAT_LT_SURGE",
		"CELADON": "EVENT_BEAT_ERIKA", "FUCHSIA": "EVENT_BEAT_KOGA", "SAFFRON": "EVENT_BEAT_SABRINA", "CINNABAR": "EVENT_BEAT_BLAINE",
		"VIRIDIAN": "EVENT_BEAT_VIRIDIAN_GYM_GIOVANNI"}.get(gym, "")
	var leader: String = {"PEWTER": "BROCK", "CERULEAN": "MISTY", "VERMILION": "LT.SURGE", "CELADON": "ERIKA", "FUCHSIA": "KOGA",
		"SAFFRON": "SABRINA", "CINNABAR": "BLAINE", "VIRIDIAN": "?"}.get(gym, "?")
	await say(gym + " POKéMON GYM\fLEADER: " + leader + "\fWINNING TRAINERS: " +
		(GameState.rival_name + "\f" + GameState.player_name if flag(leader_flag) else GameState.rival_name))

## G.pickupItem: item balls (the ball stays when the bag is full, as in Red).
func pickup_item(o: Dictionary) -> void:
	var item := str(o.get("item", ""))
	var found := GameState.player_name + " found " + item_name(item) + "!"
	if not bag_add(item, 1):
		await say(found + "\f" + fmt(t("NoMoreRoomForItemText")))
		return
	var id := str(o.get("id", ""))
	setf("GOT_" + key(mapname(), id))
	hq("hide_actor", [id])
	sfx("item")
	await say(found)

## G.staticEncounter: Snorlax/Voltorb/legendaries placed as map objects.
func static_encounter(o: Dictionary) -> void:
	var mon: Dictionary = o.get("mon", {})
	var sp := str(mon.get("species", ""))
	var ms: Dictionary = maps.get(mapname(), {})
	var bs: Callable = ms.get("before_static", Callable())
	if bs.is_valid():
		var ok = await bs.call(o)
		if ok is bool and ok == false:
			return
	cry(sp)
	var lbl := t(str(o.get("textLabel", "")))
	await say(species_name(sp) + "!" if lbl == "..." else lbl)
	var r := await wild_battle(sp, int(mon.get("level", 5)), {"music": "legendary"})
	if r == "win" or r == "caught":
		hide(str(o.get("id", "")))

# ================================================================== Pokémon Center / Mart / PC (pc.js)
## G.nurseHeal
func nurse_heal(o: Dictionary) -> void:
	var id := str(o.get("id", ""))
	await say(tf("PokemonCenterWelcomeText", "Welcome to our POKéMON CENTER!\fWe restore your tired POKéMON to full health."))
	if not await ask(tf("ShallWeHealYourPokemonText", "Shall we heal your POKéMON?")):
		await say(tf("PokemonCenterFarewellText", "We hope to see you again!"))
		return
	await say(tf("NeedYourPokemonText", "OK. We'll need your POKéMON."), {"no_wait": true})
	face(id, "left")
	var n := GameState.party.size()
	for i in n:
		hq("heal_machine", [i + 1, false])
		sfx("ballplace")
		await wait(18)
	hq("heal_machine", [n, true])
	music("heal", true)
	await wait(110)
	hq("heal_machine", [0, false])
	heal_all()
	var p := pcell()
	GameState.last_heal = {"map": mapname(), "x": p.x, "y": p.y}
	var town := GameState.last_outdoor
	var spot: Variant = blackout_spot(town)
	if spot is Vector2i:
		GameState.last_heal_town = {"map": town, "x": spot.x, "y": spot.y}
		# SceneRouter.whiteout() (random-encounter losses) reads the legacy pair: keep it in sync with the blackout point
		GameState.last_heal_map = town
		GameState.last_heal_cell = spot
	face(id, "down")
	map_music()
	await say(tf("PokemonFightingFitText", "Thank you!\fYour POKéMON are fighting fit!"))
	await say(tf("PokemonCenterFarewellText", "We hope to see you again!"))

func blackout_spot(town: String) -> Variant:
	if FLY_SPOTS.has(town):
		return FLY_SPOTS[town]
	if EXTRA_BLACKOUT_SPOTS.has(town):
		return EXTRA_BLACKOUT_SPOTS[town]
	return null

## G.mart: BUY / SELL / QUIT with upstream's menu coordinates.
func mart(items: Array) -> void:
	await say(tf("PokemartGreetingText", "Hi there!\fMay I help you?"), {"no_wait": true})
	while true:
		var r := await choose(["BUY", "SELL", "QUIT"], {"x": 6, "y": 6, "w": 80})
		if r < 0 or r == 2:
			await say(tf("PokemartThankYouText", "Thank you!"))
			return
		if r == 0:
			while true:
				var names: Array = []
				for id in items:
					names.append(item_name(id))
				var i := await choose(names, {"x": 110, "y": 4, "w": 204, "prices": items.map(func(x): return item_price(x))})
				if i < 0:
					break
				var id: String = items[i]
				var price := item_price(id)
				var mx := mini(99, int(GameState.money / float(maxi(1, price))))
				if mx < 1:
					await say(tf("PokemartNotEnoughMoneyText", "You don't have enough money."))
					continue
				var q := await quantity(mx, price)
				if q <= 0:
					continue
				if await ask(item_name(id) + "? That will be $" + str(q * price) + ". OK?"):
					if not bag_add(id, q):
						await say(tf("PokemartItemBagFullText", "You can't carry any more items."))
						continue
					GameState.money -= q * price
					sfx("buy")
					await say(tf("PokemartBoughtItemText", "Here you are!\fThank you!"))
		else:
			while true:
				var bag_ids: Array = GameState.bag.keys()
				if bag_ids.is_empty():
					await say("You have nothing to sell.")
					break
				var names2: Array = []
				for id in bag_ids:
					names2.append(item_name(id) + " ×" + str(bag_count(id)))
				var i2 := await choose(names2, {"x": 110, "y": 4, "w": 204})
				if i2 < 0:
					break
				var sid: String = bag_ids[i2]
				var sprice := int(item_price(sid) / 2.0)
				if is_key(sid) or sprice <= 0:
					await say(tf("PokemartUnsellableItemText", "I can't put a price on that."))
					continue
				var sq := await quantity(bag_count(sid), sprice)
				if sq <= 0:
					continue
				if await ask("I can pay $" + str(sq * sprice) + " for that."):
					bag_remove(sid, sq)
					GameState.money += sq * sprice
					sfx("buy")

## pc.js quantity(): ×NN picker (+ price) at upstream's coords. Returns 0 on B.
func quantity(mx: int, price: int = 0) -> int:
	var u := get_ui()
	if u and u.has_method("quantity"):
		var r = await u.call("quantity", mx, price)
		return int(r)
	var ov := overlay()
	if ov == null:
		return 1
	return await ov.call("pick_quantity", mx, price)

func use_pc() -> void:
	sfx("pc_on")
	var u := get_ui()
	if u and u.has_method("open_pc"):
		await u.call("open_pc")
	else:
		_warn("UI.open_pc")
		await say(GameState.player_name + " turned on the PC.")

# ================================================================== overlays (money / coin boxes, mon pictures)
func overlay() -> Node:
	if is_instance_valid(_overlay):
		return _overlay
	var scr: GDScript = load("res://scripts/story/StoryOverlay.gd")
	if scr == null:
		return null
	var layer := CanvasLayer.new()
	layer.layer = 61
	layer.name = "StoryLayer"
	add_child(layer)
	_overlay = scr.new()
	layer.add_child(_overlay)
	return _overlay

## early.js moneyBox() / late.js moneyBoxScene() / mid.js infoBox(): returns a handle for close_box().
func money_box(style: String = "early") -> int:
	var ov := overlay()
	return int(ov.call("add_box", {"kind": "money_" + style})) if ov else -1

func info_box(lines: Callable) -> int:
	var ov := overlay()
	return int(ov.call("add_box", {"kind": "info", "lines": lines})) if ov else -1

## Pokémon picture in a frame (pickBall / monPopup / monBox): rect = upstream frame.
func mon_popup(sp: String, rect: Rect2i, fossil: bool = false) -> int:
	var ov := overlay()
	return int(ov.call("add_box", {"kind": "mon", "species": sp, "rect": rect, "fossil": fossil})) if ov else -1

func close_box(handle: int) -> void:
	var ov := overlay()
	if ov and handle >= 0:
		ov.call("remove_box", handle)

func coin_str() -> String:
	return "COIN " + str(GameState.coins).lpad(4, " ")

func money_str() -> String:
	return "MONEY $" + str(GameState.money)

func add_coins(n: int) -> void:
	GameState.coins = clampi(GameState.coins + n, 0, 9999)

# ================================================================== map cells (S.setCell) / warps
func set_cell(x: int, y: int, label: String, passable: bool, map_name: String = "") -> void:
	var m := map_name if map_name != "" else mapname()
	if not cell_overrides.has(m):
		cell_overrides[m] = {}
	cell_overrides[m][Vector2i(x, y)] = [label, passable]
	if m == mapname():
		hq("set_cell_override", [Vector2i(x, y), label, passable])

## clear a script override so the cell shows its original data again
func restore_cell(x: int, y: int, map_name: String = "") -> void:
	var m := map_name if map_name != "" else mapname()
	if cell_overrides.has(m):
		(cell_overrides[m] as Dictionary).erase(Vector2i(x, y))
	if m == mapname():
		hq("clear_cell_override", [Vector2i(x, y)])

## late.js setCells([[x, y, label|null, passable]]): null label = original tile
func set_cells(cells: Array, map_name: String = "") -> void:
	for c in cells:
		if c[2] == null:
			var m := map_name if map_name != "" else mapname()
			if not cell_overrides.has(m):
				cell_overrides[m] = {}
			cell_overrides[m][Vector2i(c[0], c[1])] = ["", c[3]]
			if m == mapname():
				# the original look comes back (drops an earlier "barrier"/"door" label), only passability is overridden
				hq("clear_cell_override", [Vector2i(c[0], c[1])])
				hq("set_cell_override", [Vector2i(c[0], c[1]), "", c[3]])
		else:
			set_cell(int(c[0]), int(c[1]), str(c[2]), bool(c[3]), map_name)

func cell_label(c: Vector2i) -> String:
	var ov: Dictionary = cell_overrides.get(mapname(), {})
	if ov.has(c) and str(ov[c][0]) != "":
		return str(ov[c][0])
	return str(hq("cell_label", [c], ""))

func is_water(c: Vector2i) -> bool:
	return bool(hq("is_water", [c], false))

## Elevators: every exit warp of the current map now leads to (to, warp).
func set_exit_warps(to: String, warp_idx: int) -> void:
	warp_redirects[mapname()] = [to, warp_idx]
	hq("set_exit_warps", [to, warp_idx])

## S.elevator
func elevator(floors: Array) -> void:
	var labels: Array = floors.map(func(f): return f["label"])
	labels.append("CANCEL")
	var r := await choose(labels, {"x": 230, "y": 4, "w": 84})
	if r < 0 or r >= floors.size():
		return
	var f: Dictionary = floors[r]
	set_exit_warps(f["map"], int(f["warp"]))
	sfx("elevator")
	shake(40)
	await wait(40)
	sfx("ding")

## Destination of the warp at `c` on the current map (honouring elevators / LAST_MAP), or {}.
func warp_dest_at(c: Vector2i) -> Dictionary:
	var m := mapname()
	var ws: Array = map_data(m).get("warps", [])
	for w in ws:
		if int(w["x"]) == c.x and int(w["y"]) == c.y:
			var to := str(w["to"])
			var wi := int(w["warp"])
			if warp_redirects.has(m):
				to = warp_redirects[m][0]
				wi = int(warp_redirects[m][1])
			if to == "LAST_MAP":
				to = GameState.last_outdoor
			var dws: Array = map_data(to).get("warps", [])
			if dws.is_empty():
				return {}
			var dw: Dictionary = dws[wi] if wi < dws.size() else dws[0]
			return {"map": to, "cell": Vector2i(int(dw["x"]), int(dw["y"]))}
	return {}

## late.js takeWarp(): take the warp the player is standing on.
func take_warp() -> bool:
	if _has_host("take_warp"):
		await ha("take_warp")
		return true
	var d := warp_dest_at(pcell())
	if d.is_empty():
		return false
	await warp(d["map"], d["cell"].x, d["cell"].y, pdir())
	return true

# ================================================================== field moves & items (fieldmoves.js)
func bike_allowed(m: String) -> bool:
	return BIKE_TILESETS.has(str(map_data(m).get("ts", ""))) or m == "Route23" or m == "IndigoPlateau"

func is_outdoor(m: String = "") -> bool:
	var ts := str(map_data(m).get("ts", ""))
	return ts == "overworld" or ts == "plateau"

## Rock Tunnel needs FLASH (the overworld darkens the view while this is true).
func is_dark() -> bool:
	return DARK_MAPS.has(mapname()) and not flashed

## Cycling Road (Route 17) slopes downhill: with nothing pressed the bike rolls down.
## The Overworld should treat a non-empty result as a held d-pad direction.
func forced_direction() -> String:
	return "down" if mapname() == "Route17" and biking and running == 0 else ""

## True where scripts forbid wild battles (Mt.Moon fossil area, Tower 5F purified zone...).
func encounters_blocked(c: Vector2i) -> bool:
	for g in encounter_guards:
		if (g as Callable).call(mapname(), c.x, c.y):
			return true
	return false

func set_surfing(on: bool) -> void:
	surfing = on
	if on:
		biking = false
	hq("set_ride", ["surf" if on else ("bike" if biking else "walk")])

func set_biking(on: bool) -> void:
	biking = on
	if on:
		surfing = false
	hq("set_ride", ["bike" if on else ("surf" if surfing else "walk")])

func front() -> Vector2i:
	return pcell() + DVEC.get(pdir(), Vector2i.ZERO)

func party_with(mv: String) -> Object:
	for m in GameState.party:
		if m.hp > 0 and m.moves.has(mv):
			return m
	for m in GameState.party:
		if m.moves.has(mv):
			return m
	return null

## Party menu FIELD moves. Returns true when the menus should close.
func use_field_move(mon: Object, mv: String) -> bool:
	var need: String = BADGE_FOR.get(mv, "")
	if need != "" and not has_badge(need):
		await say("No! A new BADGE is required.")
		return false
	match mv:
		"CUT":
			var f := front()
			if cell_label(f) != "cut_tree":
				await say("There isn't anything to CUT!")
				return false
			await do_cut(mon, f)
			return true
		"SURF":
			if not is_water(front()) or surfing:
				await say("No SURFing on " + mon_name(mon) + " here!")
				return false
			await do_surf(mon)
			return true
		"STRENGTH":
			strength = true
			await say(mon_name(mon) + " used STRENGTH.")
			await say(mon_name(mon) + " can move boulders.")
			return true
		"FLASH":
			flashed = true
			hq("set_flash", [true])
			await say("A blinding FLASH lights the area!")
			return true
		"FLY":
			if not is_outdoor():
				await say("Can't use that here.")
				return false
			var dest := await fly_menu()
			if dest == "":
				return false
			await do_fly(dest)
			return true
		"DIG":
			if is_outdoor():
				await say("Can't use that here.")
				return false
			await escape_to()
			return true
		"TELEPORT":
			if not is_outdoor():
				await say("Can't use that here.")
				return false
			await escape_to()
			return true
		"SOFTBOILED":
			var mh: int = mon.get("max_hp")
			if int(mon.get("hp")) <= int(mh / 5.0):
				await say("Not enough HP!")
				return false
			var ti := await party_screen("Use on which POKéMON?")
			if ti < 0:
				return false
			var tgt: Object = GameState.party[ti]
			if tgt == mon or int(tgt.get("hp")) >= int(tgt.get("max_hp")) or int(tgt.get("hp")) <= 0:
				await say("It won't have any effect.")
				return false
			var amt := int(mh / 5.0)
			mon.set("hp", int(mon.get("hp")) - amt)
			tgt.set("hp", mini(int(tgt.get("max_hp")), int(tgt.get("hp")) + amt))
			await say(mon_name(tgt) + " recovered by " + str(amt) + "!")
			return false
	return false

func do_cut(mon: Object, c: Vector2i) -> void:
	await say(mon_name(mon) + " hacked away with CUT!")
	sfx("cut")
	hq("fx", ["cut", c])
	set_cell(c.x, c.y, "grass", true)
	await wait(20)

func do_surf(mon: Object) -> void:
	await say(GameState.player_name + " got on " + mon_name(mon) + "!")
	set_surfing(true)
	music("surf")
	await move_player(DCHAR.get(pdir(), "D"))

func fly_menu() -> String:
	var visited: Array = []
	for n in FLY_SPOTS:
		if GameState.visited.has(n):
			visited.append(n)
	if visited.is_empty():
		return ""
	var u := get_ui()
	if u and u.has_method("town_map_fly"):
		var r = await u.call("town_map_fly", visited)
		return str(r) if r else ""
	var names: Array = visited.map(func(n): return display_name(n))
	var i := await choose(names, {"x": 150, "y": 4, "w": 164})
	return visited[i] if i >= 0 else ""

func do_fly(dest: String) -> void:
	sfx("fly")
	surfing = false
	biking = false
	hq("set_ride", ["walk"])
	var c: Vector2i = FLY_SPOTS[dest]
	await warp(dest, c.x, c.y, "down")
	map_music()

func escape_to() -> void:
	var h: Dictionary = GameState.last_heal_town if not GameState.last_heal_town.is_empty() else {"map": "PalletTown", "x": 5, "y": 6}
	sfx("teleport")
	surfing = false
	biking = false
	hq("set_ride", ["walk"])
	await warp(str(h["map"]), int(h["x"]), int(h["y"]), "down")
	map_music()

## A pressed facing a cut tree / water (fieldMoveInteract) + module hooks (card-key doors).
func field_interact(c: Vector2i) -> Callable:
	for m in modules:
		if m.has_method("field_interact"):
			var g: Callable = m.call("field_interact", c)
			if g.is_valid():
				return g
	var shelf := _bookshelf_label(c)
	if shelf != "":
		return _say_text.bind(tf(shelf, str(BOOKSHELF_FALLBACK.get(shelf, "..."))))
	if cell_label(c) == "cut_tree":
		return _cut_prompt.bind(c)
	if is_water(c) and not surfing:
		return _surf_prompt
	return Callable()

## Text label of the tile-based "sign" (bookshelf, wall map, PC shelf, elevator panel...) at cell `c`, or "".
func _bookshelf_label(c: Vector2i) -> String:
	var md := map_data()
	var w := int(md.get("w", 0))
	var cells: Array = md.get("cells", [])
	if c.x < 0 or c.y < 0 or c.x >= w or c.y * w + c.x >= cells.size():
		return ""
	WorldData.ensure()
	var quads: Array = WorldData.quads.get(str(md.get("ts", "")), [])
	var qi := int(cells[c.y * w + c.x])
	if qi < 0 or qi >= quads.size():
		return ""
	var quad: Array = quads[qi]
	var ts_name := RegEx.create_from_string("([a-z])([A-Z0-9])").sub(str(md.get("tsc", "")), "$1_$2", true).to_upper()
	for e in BOOKSHELVES:
		if (e[0] == ts_name or (e[0] == "REDS_HOUSE_1" and str(md.get("ts", "")) == "reds_house")) and quad.has(int(e[1])):
			return str(e[2])
	return ""

func _cut_prompt(c: Vector2i) -> void:
	var mon := party_with("CUT")
	if mon == null or not has_badge("CASCADEBADGE"):
		await say(tf("CutTreeText", "This tree can be CUT!"))
		return
	if await ask(raw("CutTreeText") + "\fWould you like to use CUT?" if has_text("CutTreeText") else "This tree can be CUT! Would you like to use CUT?"):
		await do_cut(mon, c)

func _surf_prompt() -> void:
	var mon := party_with("SURF")
	if mon == null or not has_badge("SOULBADGE"):
		return
	if await ask("The water is calm.\fWould you like to SURF?"):
		await do_surf(mon)

## Bag items used in the field. Returns true when the menus should close.
func use_field_item(item: String) -> bool:
	match item:
		"BICYCLE":
			if surfing:
				await say("No cycling on water!")
				return false
			if GameState.always_on_bike and biking:
				await say(t("CannotGetOffHereText"))
				return false
			if not biking and not bike_allowed(mapname()):
				await say("No cycling allowed here.")
				return false
			set_biking(not biking)
			await say(GameState.player_name + (" got on the BICYCLE." if biking else " got off the BICYCLE."))
			if biking:
				music("bike")
			else:
				map_music()
			return true
		"OLD_ROD", "GOOD_ROD", "SUPER_ROD":
			spawn(fish, [item], "fish")
			return true
		"ESCAPE_ROPE":
			var re := RegEx.create_from_string("Cave|Moon|Tunnel|Forest|Seafoam|Victory|Mansion|Tower|Hideout|SilphCo|PowerPlant|Diglett|SafariZone")
			if is_outdoor() or re.search(mapname()) == null:
				await say("Can't use that here.")
				return false
			bag_remove("ESCAPE_ROPE", 1)
			spawn(escape_to, [], "escape")
			return true
		"REPEL", "SUPER_REPEL", "MAX_REPEL":
			bag_remove(item, 1)
			GameState.repel = {"REPEL": 100, "SUPER_REPEL": 200, "MAX_REPEL": 250}[item]
			await say("REPEL's effect lingers around you.")
			return false
		"POKE_FLUTE":
			spawn(_poke_flute, [], "flute")
			return true
		"ITEMFINDER":
			var p := pcell()
			var near := false
			for h in map_data().get("hidden", []):
				if h.get("fn", "") == "HiddenItems" and not flag("HIDDEN_%s_%d_%d" % [mapname(), int(h["x"]), int(h["y"])]) \
						and absi(int(h["x"]) - p.x) <= 5 and absi(int(h["y"]) - p.y) <= 4:
					near = true
			await say("Yes! ITEMFINDER indicates there's an item nearby." if near else "Nope! ITEMFINDER isn't responding.")
			return false
		"COIN_CASE":
			await say("Coins: " + str(GameState.coins))
			return false
	return false

func _poke_flute() -> void:
	for m in modules:
		if m.has_method("poke_flute_field"):
			var r = await m.call("poke_flute_field")
			if r:
				return
	await say("Played the POKé FLUTE.\fNow, that's a catchy tune!")

## fieldmoves.js fish()
func fish(rod: String) -> void:
	if not is_water(front()):
		await say("Can't use that here.")
		return
	await say(GameState.player_name + " used the " + item_name(rod) + "!", {"no_wait": true})
	await wait(40 + randi() % 60)
	var mon: Array = []
	if rod == "OLD_ROD":
		if randf() < 0.8:
			mon = ["MAGIKARP", 5]
	elif rod == "GOOD_ROD":
		var g: Array = pokedata.get("goodRod", [])
		if randf() < 0.6 and not g.is_empty():
			var e: Array = g[randi() % g.size()]
			mon = [e[1], e[0]]
	else:
		var grp: Array = (pokedata.get("superRod", {}) as Dictionary).get(str(map_data().get("cnst", "")), [])
		if not grp.is_empty() and randf() < 0.7:
			var e2: Array = grp[randi() % grp.size()]
			mon = [e2[1], e2[0]]
	if mon.is_empty():
		await say("Not even a nibble!")
		return
	await emote(PLAYER, "!", 30)
	await say("Oh! It's a bite!")
	await wild_battle(str(mon[0]), int(mon[1]))

## Strength: push the boulder in front of the player (G.tryPushBoulder). true = pushed.
func try_push_boulder(d: String) -> bool:
	if not strength:
		# the party menu has no STRENGTH entry (use_field_move is never called from it), so nothing else could ever
		# switch it on: pushing against a boulder with the badge and a STRENGTH mon uses the move (ow.strength)
		var smon := party_with("STRENGTH")
		if smon == null or not has_badge("RAINBOWBADGE") or not _boulder_ahead(d):
			return false
		strength = true
		spawn(_strength_used, [smon], "strength")
		return true
	var b := ""
	var ahead: Vector2i = pcell() + DVEC[d]
	for o in map_data().get("objs", []):
		if str(o.get("sprite", "")) == "boulder" and actor(o["id"]) and cell(o["id"]) == ahead:
			b = o["id"]
	if b == "":
		return false
	var to: Vector2i = ahead + DVEC[d]
	if not (_passable(to) or cell_label(to) == "hole") or _occupied(to, b):
		return false
	sfx("boulder")
	spawn(_push_boulder, [b, d], "boulder")
	return true

func _boulder_ahead(d: String) -> bool:
	var ahead: Vector2i = pcell() + DVEC[d]
	for o in map_data().get("objs", []):
		if str(o.get("sprite", "")) == "boulder" and actor(o["id"]) and cell(o["id"]) == ahead:
			return true
	return false

func _strength_used(mon: Object) -> void:
	await say(mon_name(mon) + " used STRENGTH.")
	await say(mon_name(mon) + " can move boulders.")

func _push_boulder(b: String, d: String) -> void:
	await ha("move_actor", [b, DCHAR[d]])
	await on_boulder_moved(b, cell(b))

func on_boulder_moved(id: String, c: Vector2i) -> void:
	for h in on_boulder_hooks:
		var g = (h as Callable).call(mapname(), id, c)
		if g is Callable and (g as Callable).is_valid():
			await g.call()
			return

## Map display names for banners and menus (story.js G.mapDisplayName)
func display_name(n: String) -> String:
	var special := {"MtMoon": "MT.MOON", "SSAnne": "S.S.ANNE", "CeruleanCave": "CERULEAN CAVE", "SeafoamIslands": "SEAFOAM ISLANDS",
		"PokemonTower": "POKéMON TOWER", "PokemonMansion": "POKéMON MANSION", "SilphCo": "SILPH CO.", "SafariZone": "SAFARI ZONE",
		"RockTunnel": "ROCK TUNNEL", "VictoryRoad": "VICTORY ROAD", "DiglettsCave": "DIGLETT's CAVE", "PowerPlant": "POWER PLANT",
		"ViridianForest": "VIRIDIAN FOREST", "IndigoPlateau": "INDIGO PLATEAU", "UndergroundPath": "UNDERGROUND PATH", "RocketHideout": "ROCKET HIDEOUT"}
	for k in special:
		if n.begins_with(k):
			return special[k]
	var r := RegEx.create_from_string("^Route(\\d+)").search(n)
	if r:
		return "ROUTE " + r.get_string(1)
	return RegEx.create_from_string("([a-z])([A-Z0-9])").sub(n, "$1 $2", true).to_upper()

# ================================================================== poison (Overworld.onPlayerStep)
func _poison_step() -> bool:
	if GameState.steps % 4 != 0:
		return false
	var any := false
	var fainted: Array = []
	for m in GameState.party:
		if m.status == "PSN" and m.hp > 0:
			any = true
			m.hp -= 1
			if m.hp <= 0:
				m.status = ""
				fainted.append(m)
	if any:
		hq("poison_flash", [])
	if fainted.is_empty():
		return false
	spawn(_poison_faint, [fainted], "poison")
	return true

func _poison_faint(fainted: Array) -> void:
	for m in fainted:
		await say(mon_name(m) + " fainted!")
	if GameState.party_wiped():
		await say(GameState.player_name + " is out of usable POKéMON!\f" + GameState.player_name + " blacked out!")
		await blackout()
