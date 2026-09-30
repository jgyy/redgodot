class_name OverworldScene
extends Node3D
## The 3D overworld: current map (MapLoader, built from the upstream bake), the player, NPCs, the walking
## partner Pokémon, the camera and day/night. Movement, collision, ledges, warps, connections and NPC idling
## follow upstream src/game/overworld.js; the camera frames the same ~20 x 11 cells as upstream's 320x180 view.
##
## Public API (used by Main.gd captures, the start menu / dialogue, and the Story autoload, see CONTRACT.md):
##   signals  interacted(kind, data), stepped_on(cell), entered_map(map_name)
##   lock_input(on), is_input_locked()
##   get_actor(id) -> Node3D ("PLAYER", "FOLLOWER" or a map object id), actor_cell(id), actor_dir(id)
##   await move_actor(id, "UDLR"), await move_together([[id, "U"], ...]), face_actor(id, dir)
##   show_actor(id, cell), hide_actor(id), is_actor_shown(id), spawn_object(obj) / remove_object(id)
##   await warp_to(map, cell, facing), await emote(id, "!"), await fade_out(frames), await fade_in(frames)
##   path_to(from, to) -> "UDLR" string, is_passable(cell), current_map()
##   open_menu_for_screenshot(key), show_dialogue_for_screenshot(lines)

signal interacted(kind: String, data: Dictionary)
signal stepped_on(cell: Vector2i)
signal entered_map(map_name: String)

const FRAME := 1.0 / 60.0
const CAM_FOV := 20.0
const CAM_DIST := 31.1      # frames 20 cells across at the player's depth (upstream: 320 px = 20 cells)
const FACING_WARP_TILES := {"down": [0x01, 0x12, 0x17, 0x3D, 0x04, 0x18, 0x33], "up": [0x01, 0x5C], "left": [0x1A, 0x4B], "right": [0x0F, 0x4E]}
const FACING_WARP_TILESETS := ["Overworld", "Ship", "ShipPort", "Plateau"]
const FACING_WARP_MAPS := ["RocketHideoutB1F", "RocketHideoutB2F", "RocketHideoutB4F", "RockTunnel1F"]
const OPP := {"up": "down", "down": "up", "left": "right", "right": "left"}
const LETTER := {"U": "up", "D": "down", "L": "left", "R": "right"}

@onready var _map_root: Node3D = $MapRoot
@onready var _camera_rig: Node3D = $CameraRig
@onready var _camera: Camera3D = $CameraRig/Camera3D
@onready var _sun: DirectionalLight3D = $Sun
@onready var _world_env: WorldEnvironment = $WorldEnvironment

var _map_loader: MapLoader
var player: OwActor
var follower: OwActor
var _start_menu: StartMenu
var _dialogue: DialogueBox
var _fade_layer: CanvasLayer
var _fade_rect: ColorRect
var _fade_mat: ShaderMaterial
const TRANSITION_SHADER := preload("res://assets/shaders/transition.gdshader")
## Wipe used by the next fade_out/fade_in pair (see transition.gdshader modes); reset to a plain fade afterwards.
var transition_style := 0
var _amb_layer: CanvasLayer
var _amb_rect: ColorRect
var _amb_mat: ShaderMaterial

var _locks := 0
var _busy := false           # a warp / connection change is in progress
var _was_moving := false
var _turn_delay := 0.0
var _arrived_dir := ""       # the way we came through a door, until the first step
var _pending_conn: Dictionary = {}
var _rng := RandomNumberGenerator.new()
var _light_key := ""
var _light_maps_for := ""   # map whose light/glow textures are on the world materials
var _follower_species := ""
var _hidden_ids := {}        # object ids hidden by scripts on this map
var _shown_ids := {}         # object ids shown by scripts (objs[].shown == false)
var no_encounters := false   # captures / scripted walks
var ride := "walk"           # "walk" | "bike" | "surf"
var flashed := false         # FLASH used (dark caves)
var _pending_land := false
var _exit_redirect: Array = []   # [to_map, warp_index] for every exit warp of this map (elevators)
var _shake := 0.0
var _shake_t := 0.0
var ow_fx: OwFx
var debris: Debris
var fireflies: Fireflies
# camera: critically damped follow with the player's velocity fed forward (no lag at a steady pace, no overshoot
# when it stops), snapped on warps and map changes
const CAM_OMEGA := 22.0
var _cam_pos := Vector3.ZERO
var _cam_vel := Vector3.ZERO
var _cam_snap := true
var _flash_rect: ColorRect
var _heal_count := 0

func _story() -> Node:
	return get_node_or_null("/root/Story")

func _ui_busy() -> bool:
	var ui := get_node_or_null("/root/UI")
	return ui != null and ui.has_method("is_busy") and bool(ui.is_busy())

func _ready() -> void:
	add_to_group("overworld")
	var st := _story()
	if st and st.has_method("set_host"):
		st.set_host(self)
	_rng.randomize()
	_setup_camera()
	_build_fade()
	_build_ambient()
	ow_fx = OwFx.new()
	add_child(ow_fx)
	debris = Debris.new()
	add_child(debris)
	ow_fx.debris = debris
	fireflies = Fireflies.new()
	add_child(fireflies)
	player = OwActor.new()
	player.name = "Player"
	add_child(player)
	player.fx = ow_fx
	player.setup("red")
	player.step_finished.connect(_on_player_step)
	follower = OwActor.new()
	follower.name = "Follower"
	add_child(follower)
	follower.fx = ow_fx
	_load_map(GameState.current_map, GameState.player_cell, GameState.player_facing)
	_dialogue = DialogueBox.new()
	add_child(_dialogue)
	_start_menu = StartMenu.new()
	add_child(_start_menu)
	visibility_changed.connect(_on_visibility_changed)

func _on_visibility_changed() -> void:
	# battles are overlays: when the overworld is shown again, take the camera back and refresh lighting
	if visible and is_inside_tree():
		_camera.make_current()
		_light_key = ""
		_update_lighting()

func _setup_camera() -> void:
	_camera.fov = CAM_FOV
	_camera.near = 0.5
	_camera.far = 200.0
	var pitch := deg_to_rad(WorldData.CAM_PITCH_DEG)
	var dist := CAM_DIST
	for a in OS.get_cmdline_user_args():   # --cam_dist=N : closer inspection shots of props (screenshots only)
		if a.begins_with("--cam_dist="):
			dist = float(a.substr("--cam_dist=".length()))
	_camera.transform = Transform3D.IDENTITY
	_camera.position = Vector3(0.0, sin(pitch) * dist, cos(pitch) * dist)
	_camera.rotation = Vector3(-pitch, 0.0, 0.0)
	_camera.current = true
	_sun.shadow_enabled = false
	_sun.rotation = Vector3(deg_to_rad(-60.0), deg_to_rad(-35.0), 0.0)

## upstream ambient.js env(): which full-screen treatment a map gets
static func ambient_env(map_name: String, outdoor: bool) -> String:
	if map_name.begins_with("PokemonTower"):
		return "tower"
	if map_name.begins_with("Lavender"):
		return "lavender"
	if map_name.contains("Seafoam"):
		return "ice"
	if map_name.contains("PowerPlant"):
		return "power"
	for k in ["MtMoon", "RockTunnel", "Cave", "VictoryRoad", "Diglett"]:
		if map_name.contains(k):
			return "cave"
	if map_name.contains("ViridianForest"):
		return "forest"
	if map_name.contains("SafariZone"):
		return "safari"
	if map_name.contains("Mansion"):
		return "mansion"
	return "outdoor" if outdoor else "indoor"

func _build_ambient() -> void:
	_amb_layer = CanvasLayer.new()
	_amb_layer.layer = -1   # over the 3D view, under the menus / text boxes
	add_child(_amb_layer)
	_amb_rect = ColorRect.new()
	_amb_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_amb_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_amb_mat = ShaderMaterial.new()
	_amb_mat.shader = preload("res://scripts/overworld/shaders/ambient_screen.gdshader")
	_amb_mat.set_shader_parameter("big_tex", load("res://assets/maps/noise_big.png"))
	_amb_rect.material = _amb_mat
	_amb_rect.visible = false
	_amb_layer.add_child(_amb_rect)

func _apply_ambient_env() -> void:
	var e := ambient_env(_map_loader.map_name, _map_loader.outdoor)
	var tint := Vector3.ONE
	var fog := false
	var vig := 0.0
	var vcol := Vector3(13, 10, 18) / 255.0
	var ice := 0.0
	match e:
		"lavender":
			tint = Vector3(225, 215, 240) / 256.0
			fog = true
		"tower":
			tint = Vector3(190, 175, 225) / 256.0
			fog = true
			vig = 0.75
		"cave", "mansion":
			vig = 0.5
		"ice":
			vig = 0.5
			vcol = Vector3(0x20, 0x30, 0x4a) / 255.0
			ice = 0.08
	_amb_mat.set_shader_parameter("tint", tint)
	_amb_mat.set_shader_parameter("fog", fog)
	_amb_mat.set_shader_parameter("vignette", vig)
	_amb_mat.set_shader_parameter("vignette_col", vcol)
	_amb_mat.set_shader_parameter("ice", ice)
	var st := _story()
	var dark := st != null and st.has_method("is_dark") and bool(st.is_dark()) and not flashed
	_amb_mat.set_shader_parameter("dark", dark)
	_amb_rect.visible = fog or vig > 0.0 or ice > 0.0 or tint != Vector3.ONE or dark

func _build_fade() -> void:
	_fade_layer = CanvasLayer.new()
	_fade_layer.layer = 40
	add_child(_fade_layer)
	_fade_rect = ColorRect.new()
	_fade_rect.color = Color(0, 0, 0, 0)
	_fade_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fade_mat = ShaderMaterial.new()
	_fade_mat.shader = TRANSITION_SHADER
	_fade_rect.material = _fade_mat
	_fade_layer.add_child(_fade_rect)
	_flash_rect = ColorRect.new()
	_flash_rect.color = Color(1, 1, 1, 0)
	_flash_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fade_layer.add_child(_flash_rect)

# ---------------------------------------------------------------- map loading
func _load_map(map_name: String, cell: Vector2i, facing: String) -> void:
	for c in _map_root.get_children():
		c.queue_free()
	_map_loader = MapLoader.new()
	_map_loader.name = "Map_%s" % map_name
	_map_root.add_child(_map_loader)
	_map_loader.load_map(map_name)
	GameState.current_map = map_name
	GameState.player_cell = cell
	if _map_loader.outdoor:
		GameState.set_meta("last_outdoor", map_name)
	_hidden_ids.clear()
	_shown_ids.clear()
	_exit_redirect = []
	_spinning = false
	_light_maps_for = ""
	_pending_conn = {}
	_pending_land = false
	if _map_loader.outdoor:
		flashed = false   # FLASH lasts until you're back outside (upstream)
	player.place(cell, facing if facing != "" else player.facing)
	_place_follower()
	_light_key = ""
	_update_lighting()
	_apply_ambient_env()
	ow_fx.clear()
	_cam_snap = true
	_update_camera(0.0)
	entered_map.emit(map_name)
	var story := get_node_or_null("/root/Story")
	# captures of a location (--story=off) show the map as it stands, without its enter scripts
	if story and story.has_method("on_enter") and not OS.get_cmdline_user_args().has("--story=off"):
		story.on_enter(map_name)

func current_map() -> String:
	return _map_loader.map_name if _map_loader else ""

func map_loader() -> MapLoader:
	return _map_loader

# ---------------------------------------------------------------- lighting
func _update_lighting() -> void:
	if _map_loader == null:
		return
	var h := fmod(GameState.clock_minutes / 60.0, 24.0)
	var td := LightingRig.time_of_day(h)
	if not bool(GameState.options.get("day_night", true)):
		td = {"night": 0.0, "dusk": 0.0}   # upstream timeOfDay(): OPTION day/night off = always daytime
	var graded := _map_loader.outdoor or _map_loader.ts_file == "forest"
	var g := LightingRig.grade(td) if graded else Color(1, 1, 1)
	var la := LightingRig.light_amount(td) if graded else 0.0
	var key := "%s|%.3f|%.3f|%.3f|%.2f" % [_map_loader.map_name, g.r, g.g, g.b, la]
	if key == _light_key:
		return
	var rebuild := not _light_key.begins_with(_map_loader.map_name + "|") or (la > 0.0 and _light_maps_for != _map_loader.map_name)
	_light_key = key
	var lt: Texture2D = null
	var gt: Texture2D = null
	if rebuild and la > 0.0:
		var maps := LightingRig.build_light_maps(_map_loader.bake)
		lt = maps[0]
		gt = maps[1]
		_light_maps_for = _map_loader.map_name
	_map_loader.apply_grade(g, la, lt, gt)
	var mn := _map_loader.map_name
	var cloudy_env := (_map_loader.outdoor and not mn.begins_with("PokemonTower")) or mn.begins_with("SafariZone")
	_map_loader.set_clouds(cloudy_env and float(td.night) < 0.5)
	LightingRig.apply_3d(_sun, _world_env.environment, g, _map_loader.interior)
	ow_fx.set_grade(g)

# ---------------------------------------------------------------- per frame
func _process(dt: float) -> void:
	if _map_loader == null or not visible:
		return
	_update_lighting()
	var ui_open := _start_menu.is_open() or _dialogue.visible or _ui_busy()
	# the d-pad let go (or a menu opened) while a step runs: the walkers ease into the stop instead of halting dead
	var held := _input_dir() != "" and not ui_open
	if not held:
		var st := _story()
		held = st != null and st.has_method("forced_direction") and String(st.forced_direction()) != ""
	if not player.scripted:   # a scripted path (move_actor) chains its own steps with start_move(..., more)
		player.stop_hint = not held
		follower.stop_hint = not held
	if not ui_open and _locks == 0 and not _busy:
		_player_control(dt)
		_npcs_idle(dt)
		_player_gestures(dt, false)
	elif not player.moving:
		_was_moving = false
		_player_idle = 0.0   # menus / dialogue count as activity: no fidget the instant they close
	_update_camera(dt)
	_update_follower_visibility()

func _update_fireflies() -> void:
	if fireflies == null or player == null or _map_loader == null:
		return
	fireflies.center = player.global_position
	var m := _map_loader
	# night, outdoors, away from towns' streets (grass routes, forests, the safari zone)
	var env := ambient_env(m.map_name, m.outdoor)
	var wild: bool = env == "outdoor" or env == "safari" or env == "forest"
	fireflies.set_active(wild and float(LightingRig.time_of_day(fmod(GameState.clock_minutes / 60.0, 24.0)).night) > 0.5 and bool(GameState.options.get("day_night", true)))

func _update_camera(dt: float) -> void:
	_update_fireflies()
	if player == null:
		return
	var target := player.position + Vector3(0.0, 0.0, 0.5 - OwActor.FOOT_Z)
	if _cam_snap or dt <= 0.0 or (target - _cam_pos).length() > 6.0:
		_cam_pos = target
		_cam_vel = Vector3.ZERO
		_cam_snap = false
	else:
		# Aim slightly ahead along the player's velocity. A critically damped spring lags v * 2 / omega behind a
		# target moving at v; leading by half of that leaves a lag of v / omega, which is exactly the most the
		# camera can trail by and still never overshoot when the player stops dead.
		var lead := player.velocity * (1.0 / CAM_OMEGA)
		lead.y = 0.0
		var aim := target + lead
		var r := Smooth.damp3(_cam_pos, _cam_vel, aim, CAM_OMEGA, dt)
		_cam_pos = r[0]
		_cam_vel = r[1]
	_camera_rig.position = _cam_pos
	if _shake > 0.0:
		_shake_t += dt
		# smooth two-axis wobble instead of white noise, decaying at upstream's 0.9 per 60 Hz frame
		var w := Vector3(sin(_shake_t * 131.0), 0.0, sin(_shake_t * 97.0 + 1.7))
		_camera_rig.position += w * _shake / 16.0
		_shake *= pow(0.9, dt * 60.0)
		if _shake <= 0.5:
			_shake = 0.0
	if _amb_rect and _amb_rect.visible:
		_amb_mat.set_shader_parameter("cam_px", Vector2(_cam_pos.x * 16.0 - 160.0, _cam_pos.z * 16.0 - 90.0))

func _input_dir() -> String:
	if Input.is_action_pressed("move_up"):
		return "up"
	if Input.is_action_pressed("move_down"):
		return "down"
	if Input.is_action_pressed("move_left"):
		return "left"
	if Input.is_action_pressed("move_right"):
		return "right"
	return ""

func _player_control(dt: float) -> void:
	if player.moving:
		return
	var d := _input_dir()
	var story := _story()
	if d == "" and story and story.has_method("forced_direction"):
		d = String(story.forced_direction())
	if d == "":
		_was_moving = false
		_turn_delay = 0.0
		return
	var bounce: bool = _arrived_dir != "" and (d == _arrived_dir or bool(can_move(player, d).get("ok", false)))
	if not bounce and _push_warp(player.cell, d):
		player.face(d)
		_do_warp(_map_loader.warp_index_at(player.cell))
		return
	if player.facing != d and not _was_moving:
		player.face(d)
		_turn_delay = 6.0 * FRAME
		return
	if _turn_delay > 0.0:
		_turn_delay -= dt
		if _turn_delay > 0.0:
			return
	if story and story.has_method("try_push_boulder") and bool(story.try_push_boulder(d)):
		player.face(d)
		_was_moving = false
		return
	var r := can_move(player, d)
	if r.get("ok", false):
		var speed := 3.0 if ride == "bike" else (2.0 if Input.is_action_pressed("cancel") and ride != "surf" else 1.0)
		_step_player(d, speed, r)
	else:
		player.face(d)
		_was_moving = false

func _step_player(d: String, speed: float, r: Dictionary) -> void:
	var from := player.cell
	var jump: bool = r.get("jump", false)
	_pending_conn = r.get("conn", {})
	_pending_land = bool(r.get("land", false))
	# a held d-pad means the next step follows straight away: don't slow down at the end of this one
	var story := _story()
	var forced: String = String(story.forced_direction()) if story and story.has_method("forced_direction") else ""
	var more := (_input_dir() == d or forced == d) and not jump
	var target: Vector2i = from + OwActor.DIRS[d]
	_set_ground_fx(player, target)
	player.start_move(d, 2.0 if jump else speed, jump, more)
	_was_moving = true
	_arrived_dir = ""
	if _map_loader.is_tall_grass(target):
		TileKit.rustle(_map_loader.grass_node, target)
		ow_fx.grass(OwActor.cell_pos(target), 4)
	_follower_follow(from, speed, jump, more)

## upstream Overworld.canMove -> {ok, jump, conn}
func can_move(who: OwActor, dir: String) -> Dictionary:
	var m := _map_loader
	var nxt: Vector2i = who.cell + OwActor.DIRS[dir]
	var is_player := who == player
	if not m.in_bounds(nxt):
		if not is_player:
			return {"ok": false}
		var side := m.connection_dir(nxt)
		var conns: Dictionary = m.map_data.get("conns", {})
		if not conns.has(side):
			return {"ok": false}
		var c: Dictionary = conns[side]
		var tm := MapLoader.new()
		tm.load_map(String(c.get("map", "")), false)
		var tc := nxt - Vector2i(int(c.get("ox", 0)), int(c.get("oy", 0)))
		var ok := tm.passable(tc) or (ride == "surf" and tm.is_water(tc))
		tm.free()
		return {"ok": ok, "conn": c}
	if _actor_blocking(nxt, who):
		return {"ok": false}
	if is_player:
		if m.is_ledge_jump(who.cell, dir):
			var land: Vector2i = nxt + OwActor.DIRS[dir]
			if m.passable(land) and not _actor_blocking(land, who):
				return {"ok": true, "jump": true}
			return {"ok": false}
		if ride == "surf":
			if m.is_water(nxt):
				return {"ok": true}
			if m.passable(nxt):
				return {"ok": true, "land": true}
			return {"ok": false}
		if m.pair_blocked(who.cell, nxt):
			return {"ok": false}
	else:
		if absi(nxt.x - who.home.x) > 3 or absi(nxt.y - who.home.y) > 3:
			return {"ok": false}
		if m.warp_index_at(nxt) >= 0:
			return {"ok": false}
	if not m.passable(nxt):
		return {"ok": false}
	return {"ok": true}

func _actor_blocking(cell: Vector2i, except: OwActor) -> bool:
	for a in _map_loader.actors:
		var act: OwActor = a
		if act == except or not act.visible:
			continue
		if act.cell == cell:
			return true
	if player != except and player.cell == cell:
		return true
	return false

## upstream pushWarp: standing on a warp cell and pushing toward its exit
func _push_warp(cell: Vector2i, d: String) -> bool:
	var m := _map_loader
	if m.warp_index_at(cell) < 0:
		return false
	var nxt: Vector2i = cell + OwActor.DIRS[d]
	if not m.in_bounds(nxt):
		return true
	if (FACING_WARP_MAPS.has(m.map_name) or FACING_WARP_TILESETS.has(m.tileset_name)) and FACING_WARP_TILES[d].has(m.tile(nxt)):
		return true
	return d == "down" and not m.is_warp_tile(cell) and not m.passable(cell + Vector2i(0, 1))

func _on_player_step(_a: OwActor) -> void:
	GameState.player_cell = player.cell
	GameState.player_facing = player.facing
	_arrived_dir = ""   # upstream onPlayerStep: `arrived` only lasts until the first step is done
	if not _pending_conn.is_empty():
		var c := _pending_conn
		_pending_conn = {}
		var nc := player.cell - Vector2i(int(c.get("ox", 0)), int(c.get("oy", 0)))
		_load_map(String(c.get("map", "")), nc, player.facing)
		return
	var m := _map_loader
	var wi := m.warp_index_at(player.cell)
	# scripted walks onto a door leave the warp to the script (it warps itself right after)
	if wi >= 0 and not player.scripted and (m.is_warp_tile(player.cell) or m.is_door_tile(player.cell)):
		_do_warp(wi)
		return
	if player.scripted:
		return
	if _spinner_continue():
		return
	if _pending_land:
		_pending_land = false
		var st0 := _story()
		if st0 and st0.has_method("set_surfing"):
			st0.set_surfing(false)
		else:
			set_ride("walk")
	stepped_on.emit(player.cell)
	var story := _story()
	if story and story.has_method("on_step") and story.on_step(player.cell):
		return
	if no_encounters or (story and story.has_method("encounters_blocked") and bool(story.encounters_blocked(player.cell))):
		return
	var on_water := ride == "surf" and m.is_water(player.cell)
	# upstream encounters.check: repel ticks down every step, and the message ends the step
	if GameState.repel > 0:
		GameState.repel -= 1
		if GameState.repel == 0:
			_dialogue.show_lines(["REPEL's effect wore off."])
			return
	# tilesets without a tall-grass tile (caves, buildings) roll on every dry cell
	if m.is_tall_grass(player.cell) or on_water or (m.has_no_grass_tile() and not m.is_water(player.cell)):
		var res := EncounterSystem.roll(m.map_name, on_water, _rng)
		if not res.is_empty() and GameState.repel > 0 and not GameState.party.is_empty():
			for pm in GameState.party:
				if pm.hp > 0:
					if int(res["level"]) < pm.level:
						res = {}
					break
		if not res.is_empty():
			SceneRouter.start_battle({"kind": "wild", "species": res["species"], "level": res["level"]})

## Spinner tiles (Rocket Hideout B2F/B3F, Viridian Gym; upstream fieldmoves.js afterStep): an arrow tile keeps sliding
## you at double speed in its direction until a spinner_stop tile or a wall ends the ride.
var _spinning := false

func _spinner_continue() -> bool:
	var lbl := cell_label(player.cell)
	var d := ""
	if lbl.begins_with("spinner_") and lbl != "spinner_stop":
		d = lbl.substr(8)
	elif _spinning and lbl != "spinner_stop":
		d = player.facing
	if d != "" and bool(can_move(player, d).get("ok", false)):
		if not _spinning:
			ow_fx.dust(OwActor.cell_pos(player.cell), 3, 1.2)
		_spinning = true
		var from := player.cell
		_set_ground_fx(player, from + OwActor.DIRS[d])
		player.start_move(d, 2.0, false, true)
		_was_moving = true
		_follower_follow(from, 2.0, false, true)
		return true
	_spinning = false
	return false

func is_spinning() -> bool:
	return _spinning

func _do_warp(wi: int) -> void:
	if _busy or wi < 0:
		return
	var w: Dictionary = (_map_loader.map_data.get("warps", [])[wi] as Dictionary).duplicate()
	if not _exit_redirect.is_empty():
		w["to"] = _exit_redirect[0]
		w["warp"] = _exit_redirect[1]
	var to := String(w.get("to", ""))
	if to == "LAST_MAP":
		var lo: Variant = GameState.get("last_outdoor")
		to = String(lo) if lo != null and String(lo) != "" else String(GameState.get_meta("last_outdoor", "PalletTown"))
	var dmd := GameData.get_map(to)
	if dmd.is_empty():
		push_warning("[Overworld] warp target not found: %s" % to)
		return
	_busy = true
	var dws: Array = dmd.get("warps", [])
	var wv := int(w.get("warp", 0))
	var dw: Dictionary = dws[wv] if wv >= 0 and wv < dws.size() else (dws[0] if not dws.is_empty() else {"x": 0, "y": 0})
	var dcell := Vector2i(int(dw.get("x", 0)), int(dw.get("y", 0)))
	var dir := player.facing
	var entering_door := _map_loader.is_door_tile(player.cell) and _map_loader.outdoor
	if entering_door:
		await get_tree().create_timer(8.0 * FRAME).timeout
		player.visible = false
		follower.visible = false
		await get_tree().create_timer(4.0 * FRAME).timeout
	transition_style = style_for_map(to, entering_door)
	await fade_out(14 if transition_style != 0 else 10)
	player.visible = true
	_load_map(to, dcell, dir)
	_arrived_dir = dir
	await fade_in(14 if transition_style != 0 else 10)
	var m := _map_loader
	if m.is_door_tile(dcell) or (m.outdoor and m.is_warp_tile(dcell) and m.passable(dcell + Vector2i(0, 1))):
		if can_move(player, "down").get("ok", false):
			player.start_move("down", 1.0)
			await player.step_finished
	_busy = false

# ---------------------------------------------------------------- input: A / START
func _unhandled_input(event: InputEvent) -> void:
	if not visible or _dialogue.visible or _start_menu.is_open() or _locks > 0 or _busy or _ui_busy():
		return
	if event.is_action_pressed("menu"):
		_start_menu.open()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("confirm") and not player.moving:
		_try_interact()
		get_viewport().set_input_as_handled()

func _try_interact() -> void:
	var m := _map_loader
	var t := player.facing_cell()
	var a := m.actor_at(t)
	if a == null and m.is_counter(t):
		a = m.actor_at(t + OwActor.DIRS[player.facing])
	if a == null and follower.visible and follower.cell == t and not follower.moving:
		follower.face(OPP[player.facing])
		interacted.emit("follower", {"species": _follower_species})
		var mon: GameState.PartyMon = GameState.party[0] if not GameState.party.is_empty() else null
		if GameState.is_yellow() and PikachuBuddy.buddy() != null:
			mon = PikachuBuddy.buddy()   # YELLOW: the partner is always the starter PIKACHU, wherever it stands in the party
		if mon:
			var mood: Array = PikachuBuddy.mood(mon, _map_loader.map_name, _map_loader.is_tall_grass(player.cell), _rng) if mon.buddy \
				else follower_mood(mon, _map_loader.map_name, _map_loader.is_tall_grass(player.cell), _rng)
			var au := get_node_or_null("/root/Audio")
			if au and au.has_method("cry"):
				au.cry(mon.species_id)
			var pa := _follower_actor()
			if pa:
				pa.play_once("Talk" if pa.has_anim("Talk") else "Idle")
				if pa.has_anim("Talk"):   # Talk is a looping clip: play_once's queued Idle never comes, hand back by hand
					get_tree().create_timer(1.6).timeout.connect(func() -> void:
						if is_instance_valid(pa) and pa.current_clip() == "Talk":
							pa.play("Idle"))
			emote_on(follower, str(mood[1]))
			_dialogue.show_lines([str(mood[0])])
		return
	var story := get_node_or_null("/root/Story")
	if a:
		if not a.is_object:   # upstream talkTo: every non-object actor turns to face you, fixed-facing ones too
			a.face(OPP[player.facing])
		interacted.emit("npc", a.obj)
		if OwActor.gesture_pool(a.sprite, a.obj) != ["Sleep"]:
			a.stop_gesture()
			a.gesture("Talk", 2.6)
		if story and story.has_method("on_talk") and story.on_talk(a.obj):
			return
		_dialogue.show_lines(DialogueText.for_obj(a.obj))
		return
	var s := m.sign_at(t)
	if not s.is_empty():
		interacted.emit("sign", s)
		if story and story.has_method("on_sign") and story.on_sign(s):
			return
		_dialogue.show_lines(DialogueText.for_sign(s, m.map_name))
		return
	interacted.emit("cell", {"x": t.x, "y": t.y, "label": m.label_at(t)})
	if story and story.has_method("on_interact_cell"):
		story.on_interact_cell(t, player.facing)

# ---------------------------------------------------------------- NPC gestures
## Idle NPCs occasionally play a gesture from their pool (stretch, think, nod, salute, dance ...); sleepers keep snoring.
func _npc_gestures(act: OwActor, dt: float) -> void:
	if act.is_gesturing():
		return
	var pool: Array = OwActor.gesture_pool(act.sprite, act.obj)
	if pool == ["Sleep"]:
		act.gesture("Sleep", 1e6)
		return
	if act.gesture_wait < 0.0:
		act.gesture_wait = 2.0 + _rng.randf() * 12.0
	act.gesture_wait -= dt
	if act.gesture_wait <= 0.0:
		act.gesture_wait = 7.0 + _rng.randf() * 14.0
		act.gesture(pool[_rng.randi() % pool.size()])

var _player_idle := 0.0

## The player also fidgets after standing still for a while (stretches, thinks, dances a little).
func _player_gestures(dt: float, ui_open: bool) -> void:
	if player.moving or ui_open or player.scripted or _input_dir() != "":
		_player_idle = 0.0
		player.stop_gesture()
		return
	_player_idle += dt
	if _player_idle > 14.0 and not player.is_gesturing():
		_player_idle = 8.0 + _rng.randf() * 4.0
		var pool := ["Stretch", "Think", "Nod", "Dance", "Wave"]
		player.gesture(pool[_rng.randi() % pool.size()])

## Emote bubbles come with a matching body reaction.
const EMOTE_GESTURE := {"!": "Surprised", "?": "Think", "heart": "Dance", "...": "Sad"}

# ---------------------------------------------------------------- NPC idle (upstream npcIdle)
func _npcs_idle(dt: float) -> void:
	for a in _map_loader.actors:
		var act: OwActor = a
		if act.moving or act.scripted or not act.visible:
			continue
		if not act.is_mon and not act.is_object:
			_npc_gestures(act, dt)
		act.idle_t -= dt
		if act.idle_t > 0.0:
			continue
		act.idle_t = (60.0 + _rng.randf() * 140.0) * FRAME
		var o := act.obj
		if String(o.get("move", "")) == "WALK":
			var dirs := ["up", "down", "left", "right"]
			if String(o.get("dir", "")) == "UP_DOWN":
				dirs = ["up", "down"]
			elif String(o.get("dir", "")) == "LEFT_RIGHT":
				dirs = ["left", "right"]
			var d: String = dirs[_rng.randi() % dirs.size()]
			act.face(d)
			if can_move(act, d).get("ok", false) and _rng.randf() < 0.7:
				act.start_move(d, 1.0)
		elif String(o.get("dir", "")) == "NONE" and not o.has("trainer") and not o.has("item") and not act.is_object:
			act.face(["up", "down", "left", "right"][_rng.randi() % 4])

# ---------------------------------------------------------------- walking partner (upstream follower.js)
## The follower's PokemonActor (its model node), if it has one.
func _follower_actor() -> PokemonActor:
	for n in follower.find_children("*", "Node3D", true, false):
		if n is PokemonActor:
			return n
	return null

## upstream follower.js mood(): what your partner says (and which emote it shows) when you talk to it, from status, HP,
## the place you are in, its type and level.  Returns [text, emote].
static func follower_mood(m: GameState.PartyMon, map_name: String, in_grass: bool, rng: RandomNumberGenerator) -> Array:
	var n := m.display_name()
	var st := {"PSN": [n + " is shivering from the poison!", "..."], "BRN": [n + " is hurting from its burn.", "..."],
		"PAR": [n + " is paralyzed. It can barely move!", "..."], "SLP": [n + " is fast asleep... zzz", "..."],
		"FRZ": [n + " is frozen solid!", "..."]}
	if st.has(m.status):
		return st[m.status]
	if float(m.hp) / maxf(1.0, float(m.max_hp)) < 0.25:
		return [n + " looks exhausted. Maybe rest at a POKéMON CENTER?", "..."]
	var lines: Array = []
	if map_name.contains("Pokecenter") or map_name.contains("PokemonCenter"):
		lines.append([n + " looks relaxed here.", "heart"])
	if map_name.ends_with("Gym"):
		lines.append([n + " is fired up for a GYM battle!", "!"])
	if map_name.begins_with("PokemonTower"):
		lines.append([n + " is trembling... it senses something.", "..."])
	for cave in ["MtMoon", "RockTunnel", "DiglettsCave", "SeafoamIslands", "CeruleanCave", "VictoryRoad"]:
		if map_name.begins_with(cave):
			lines.append([n + " is sticking close to you in the dark.", "..."])
	if map_name.begins_with("SafariZone"):
		lines.append([n + " is excited by all the wild POKéMON!", "!"])
	if map_name == "PalletTown":
		lines.append([n + " seems to like PALLET TOWN.", "heart"])
	if in_grass:
		lines.append([n + " is rustling around in the tall grass!", "!"])
	var by_type := {"FIRE": " is giving off a gentle warmth.", "WATER": " wants to go for a swim!",
		"ELECTRIC": "'s cheeks are crackling with electricity!", "GRASS": " is soaking up the sunshine.",
		"GHOST": " is floating around mischievously.", "PSYCHIC_TYPE": " is staring into the distance...",
		"ICE": " is chilling the air around it.", "DRAGON": " looks proud and powerful.",
		"FIGHTING": " is throwing punches at the air!", "BUG": " is chasing a butterfly.",
		"FLYING": " is watching the birds overhead.", "POISON": " is sniffing the air.",
		"ROCK": " is sitting as still as a stone.", "GROUND": " is digging at the ground."}
	for t in GameData.get_species(m.species_id).get("types", []):
		if by_type.has(t):
			lines.append([n + by_type[t], "..."])
	lines.append([n + " is happy to be walking with you!", "heart"])
	lines.append([n + " is looking around curiously.", "?"])
	lines.append([n + " seems to be enjoying the walk!", "heart"])
	lines.append([n + " is keeping a close eye on you.", "..."])
	if m.level >= 50:
		lines.append([n + " looks strong and confident!", "!"])
	return lines[rng.randi_range(0, lines.size() - 1)]

## upstream follower.js lead(): the first party Pokémon, while it hasn't fainted (OPTION > FOLLOWER off hides it)
func _lead_species() -> String:
	if bool(GameState.get_meta("no_follower", false)) or not bool(GameState.options.get("follower", true)) or GameState.party.is_empty():
		return ""
	if GameState.is_yellow():   # YELLOW: PIKACHU walks behind you (and only PIKACHU), while it is up
		var b := PikachuBuddy.buddy()
		return b.species_id if b != null and b.hp > 0 else ""
	var pm: GameState.PartyMon = GameState.party[0]
	return pm.species_id if pm.hp > 0 else ""

func _place_follower() -> void:
	var sp := _lead_species()
	if sp == "":
		follower.visible = false
		return
	if sp != _follower_species:
		_follower_species = sp
		follower.setup("mon:" + sp, _follower_px(sp))
	var d: String = player.facing
	var back: Vector2i = player.cell - OwActor.DIRS.get(d, Vector2i(0, 1))
	var m := _map_loader
	var ok := m.in_bounds(back) and m.passable(back) and m.warp_index_at(back) < 0 and not _actor_blocking(back, player) and not m.is_water(back)
	follower.place(back if ok else player.cell, d)

## upstream follower sizeFor(): sprite size from the Pokédex height
func _follower_px(sp: String) -> float:
	var d := GameData.get_species(sp)
	var ht: Variant = d.get("ht", null)
	var feet := 0.0
	if typeof(ht) == TYPE_ARRAY and (ht as Array).size() >= 2:
		feet = float(ht[0]) + float(ht[1]) / 12.0
	var size := clampf(roundf(10.0 + 9.0 * sqrt(feet)), 16.0, 42.0) if feet > 0.0 else 28.0
	return size * 0.8

## What an actor kicks up while stepping onto `target`: nothing indoors or on water, blades in tall grass, dust on
## open ground.
func _set_ground_fx(a: OwActor, target: Vector2i) -> void:
	var m := _map_loader
	if m == null or not m.outdoor or m.is_water(target):
		a.fx_kind = ""
	elif m.is_tall_grass(target):
		a.fx_kind = ""
	else:
		a.fx_kind = "dust"

func _follower_follow(from: Vector2i, speed: float, jump: bool, more: bool = false) -> void:
	if _follower_species == "":
		return
	var dv := from - follower.cell
	var far := absi(dv.x) + absi(dv.y)
	var dir := ("right" if dv.x > 0 else "left") if absi(dv.x) >= absi(dv.y) else ("down" if dv.y > 0 else "up")
	if far == 0:
		follower.face(player.facing)
	elif far == 1:
		_set_ground_fx(follower, from)
		follower.start_move(dir, speed, false, more)
	elif far == 2 and (dv.x == 0 or dv.y == 0):
		follower.start_move(dir, 2.0, true)
	else:
		follower.place(from, player.facing)
	if jump:
		pass

func _update_follower_visibility() -> void:
	var lead := _lead_species()
	if lead != "" and lead != _follower_species and _map_loader != null:
		_place_follower()   # first Pokémon received / a new lead / the option switched back on (upstream tick())
	if _follower_species == "" or lead == "":
		follower.visible = false
		return
	if not player.visible or ride != "walk":   # it goes back in its ball while surfing or cycling
		follower.visible = false
		return
	var tucked := not follower.moving and follower.cell == player.cell
	follower.visible = not tucked and not (_map_loader.is_water(follower.cell) and not follower.moving)

# ---------------------------------------------------------------- Story / script API
func lock_input(on: bool) -> void:
	_locks = maxi(0, _locks + (1 if on else -1))

func is_input_locked() -> bool:
	return _locks > 0

func get_actor(id: String) -> Node3D:
	if id == "PLAYER":
		return player
	if id == "FOLLOWER":
		return follower
	if _map_loader == null:
		return null
	for a in _map_loader.actors:
		var act: OwActor = a
		if String(act.obj.get("id", "")) == id:
			return act
	return null

func actor_cell(id: String) -> Vector2i:
	var a := get_actor(id) as OwActor
	return a.cell if a else Vector2i(-1, -1)

func actor_dir(id: String) -> String:
	var a := get_actor(id) as OwActor
	return a.facing if a else "down"

func face_actor(id: String, dir: String) -> void:
	var a := get_actor(id) as OwActor
	if a:
		a.face(dir)

## Walk an actor along an upstream "UDLR" path, one cell per letter, awaiting each step. Ignores collision
## (scripts own the path), like upstream's scripted walks.
func move_actor(id: String, path: String) -> void:
	var a := get_actor(id) as OwActor
	if a == null:
		return
	a.scripted = true
	for idx in path.length():
		var d: String = LETTER.get(path[idx].to_upper(), "")
		if d == "":
			continue
		var from := a.cell
		var more := idx < path.length() - 1
		if a.sprite == "boulder":   # Strength: rock chips + dust kicked up as it grinds along
			var bp := OwActor.cell_pos(from)
			debris.ground_y = bp.y
			debris.chips(bp + Vector3(0, 0.1, 0), 6, 0.8)
			ow_fx.dust(bp, 4, 1.4)
		a.start_move(d, 1.0, false, more)
		if a == player:
			_follower_follow(from, 1.0, false, more)
		await a.step_finished
		if a == player:
			GameState.player_cell = a.cell
	a.scripted = false

## Several actors stepping in lockstep: pairs = [[id, "U"], [id2, "L"], ...] (one step each, then await all).
func move_together(pairs: Array) -> void:
	var movers: Array = []
	for p in pairs:
		var a := get_actor(String(p[0])) as OwActor
		var d: String = LETTER.get(String(p[1]).to_upper(), "")
		if a == null or d == "":
			continue
		a.scripted = true
		var from := a.cell
		a.start_move(d, 1.0)
		if a == player:
			_follower_follow(from, 1.0, false)
		movers.append(a)
	for a in movers:
		var act: OwActor = a
		if act.moving:
			await act.step_finished
		act.scripted = false
	GameState.player_cell = player.cell

func show_actor(id: String, cell: Vector2i = Vector2i(-1, -1)) -> void:
	_hidden_ids.erase(id)
	_shown_ids[id] = true
	var a := get_actor(id) as OwActor
	if a == null and _map_loader:
		for o in _map_loader.map_data.get("objs", []):
			if String(o.get("id", "")) == id:
				a = _map_loader.spawn_actor(o)
				break
	if a:
		a.visible = true
		if cell.x >= 0:
			a.place(cell)

func hide_actor(id: String) -> void:
	_hidden_ids[id] = true
	var a := get_actor(id) as OwActor
	if a:
		a.visible = false

func is_actor_shown(id: String) -> bool:
	var a := get_actor(id) as OwActor
	return a != null and a.visible

## Add a new object (NPC / item ball) to the current map at runtime; returns its actor.
func spawn_object(obj: Dictionary) -> Node3D:
	return _map_loader.spawn_actor(obj) if _map_loader else null

func remove_object(id: String) -> void:
	var a := get_actor(id) as OwActor
	if a and a != player and a != follower:
		_map_loader.remove_actor(a)

func warp_to(map_name: String, cell: Vector2i, facing: String = "") -> void:
	_busy = true
	await fade_out(10)
	_load_map(map_name, cell, facing)
	await fade_in(10)
	_busy = false

## Picks the wipe for a warp: doors close in on the player (iris), caves dissolve into pixels, towers/dungeons
## use blinds, big buildings a diagonal wipe, everything else a plain fade.
static func style_for_map(map_name: String, entering_door: bool) -> int:
	var n := map_name.to_lower()
	for k in ["cave", "tunnel", "mtmoon", "seafoam", "victoryroad", "diglett", "hideout", "powerplant", "underground"]:
		if k in n:
			return 4
	if "tower" in n or "mansion" in n or "silph" in n or "ssanne" in n:
		return 2
	if "gym" in n or "lab" in n or "league" in n or "indigo" in n or "lorelei" in n or "bruno" in n or "agatha" in n or "lance" in n:
		return 3
	if entering_door:
		return 1
	return 0

func _player_uv() -> Vector2:
	var cam := get_viewport().get_camera_3d()
	if cam == null or player == null:
		return Vector2(0.5, 0.5)
	var sz := get_viewport().get_visible_rect().size
	var p := cam.unproject_position(player.global_position + Vector3(0, 0.5, 0))
	return Vector2(clampf(p.x / sz.x, 0.0, 1.0), clampf(p.y / sz.y, 0.0, 1.0))

func _apply_transition_style() -> void:
	_fade_mat.set_shader_parameter("mode", transition_style)
	_fade_mat.set_shader_parameter("center", _player_uv())
	var sz := get_viewport().get_visible_rect().size
	_fade_mat.set_shader_parameter("aspect", sz.x / maxf(1.0, sz.y))

func fade_out(frames: int = 10) -> void:
	_apply_transition_style()
	var tw := create_tween()
	tw.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(_fade_rect, "color:a", 1.0, frames * FRAME)
	await tw.finished

func fade_in(frames: int = 10) -> void:
	_apply_transition_style()
	var tw := create_tween()
	tw.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(_fade_rect, "color:a", 0.0, frames * FRAME)
	await tw.finished
	transition_style = 0

## Emote bubble ("!", "?", "...", "heart") above an actor for ~1 s.
func emote(id: String, kind: String = "!") -> void:
	await emote_on(get_actor(id) as OwActor, kind)

func emote_on(a: OwActor, kind: String) -> void:
	if a == null:
		return
	if EMOTE_GESTURE.has(kind):
		a.gesture(EMOTE_GESTURE[kind])
	var l := _emote_node(kind)
	a.add_child(l)
	# pops up with an overshoot, bobs while it hangs there, then shrinks away
	l.scale = Vector3.ONE * 0.01
	var tw := l.create_tween()
	tw.tween_property(l, "scale", Vector3.ONE * 1.15, 10.0 * FRAME).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(l, "scale", Vector3.ONE, 5.0 * FRAME)
	await get_tree().create_timer(50.0 * FRAME).timeout
	if not is_instance_valid(l):   # the actor's map was unloaded while the bubble hung there
		return
	var tw2 := l.create_tween()
	tw2.tween_property(l, "scale", Vector3.ONE * 0.01, 8.0 * FRAME)
	await get_tree().create_timer(8.0 * FRAME).timeout   # (a tween on a freed bubble never emits `finished`)
	if is_instance_valid(l):
		l.queue_free()

const EMOTE_MESHES := {"!": "emote_exclaim", "?": "emote_question", "heart": "emote_heart", "...": "emote_dots"}

## 3D speech-bubble glyph (exclaim / question / heart / dots) above an actor; falls back to a text label.
func _emote_node(kind: String) -> Node3D:
	var holder := Node3D.new()
	holder.position = Vector3(0, WorldData.px_h(26.0), 0)
	var path := "res://assets/models/world/%s.glb" % EMOTE_MESHES.get(kind, "")
	if EMOTE_MESHES.has(kind) and ResourceLoader.exists(path):
		var inst: Node = (load(path) as PackedScene).instantiate()
		var mi := TileKit._find_mesh(inst)
		if mi:
			var m := MeshInstance3D.new()
			m.mesh = mi.mesh
			var mat := StandardMaterial3D.new()
			mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			mat.vertex_color_use_as_albedo = true
			mat.no_depth_test = true
			mat.render_priority = 5
			mat.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
			m.material_override = mat
			m.scale = Vector3(1.0, 1.0, 1.0) * 0.9
			holder.add_child(m)
			inst.free()
			return holder
		inst.free()
	var l := Label3D.new()
	l.text = {"heart": "♥", "...": "…"}.get(kind, kind)   # (the glyph-less fallback must not print the word "heart")
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.font_size = 64
	l.outline_size = 12
	l.modulate = Color(0.1, 0.1, 0.15)
	l.outline_modulate = Color(1, 1, 1)
	holder.add_child(l)
	return holder

## BFS over passable, unoccupied cells; returns an upstream "UDLR" path or "" (also "" when from == to).
func path_to(from: Vector2i, to: Vector2i) -> String:
	if from == to or _map_loader == null:
		return ""
	var prev := {from: null}
	var q: Array = [from]
	var dirs := [["U", Vector2i(0, -1)], ["D", Vector2i(0, 1)], ["L", Vector2i(-1, 0)], ["R", Vector2i(1, 0)]]
	while not q.is_empty():
		var c: Vector2i = q.pop_front()
		if c == to:
			break
		for dd in dirs:
			var n: Vector2i = c + dd[1]
			if prev.has(n) or not _map_loader.passable(n):
				continue
			if n != to and _actor_blocking(n, player):
				continue
			prev[n] = [c, dd[0]]
			q.append(n)
	if not prev.has(to):
		return ""
	var out := ""
	var cur: Vector2i = to
	while cur != from:
		var p: Array = prev[cur]
		out = String(p[1]) + out
		cur = p[0]
	return out

func is_passable(cell: Vector2i) -> bool:
	return _map_loader != null and _map_loader.passable(cell)

# ---------------------------------------------------------------- captures (Main.gd)
func open_menu_for_screenshot(key: String) -> void:
	match key:
		"start_menu": _start_menu.open()
		"party": _start_menu.party_menu.open()
		"summary":
			if not GameState.party.is_empty():
				_start_menu.summary_screen.open_for(GameState.party[0])
		"bag": _start_menu.bag_menu.open()
		"pokedex": _start_menu.pokedex_menu.open()
		"trainer_card": _start_menu.trainer_card.open()
		"town_map": _start_menu.town_map.open()
		"options": _start_menu.options_menu.open()

func show_dialogue_for_screenshot(lines: Array) -> void:
	_dialogue.show_lines(lines)

## Capture helper: face the player and put the follower one step behind.
func set_player_facing_for_screenshot(dir: String) -> void:
	player.face(dir)
	GameState.player_facing = dir
	_place_follower()

# ---------------------------------------------------------------- Story extras (STORY_HOOKS.md)
func is_water(cell: Vector2i) -> bool:
	return _map_loader != null and _map_loader.is_water(cell)

func cell_label(cell: Vector2i) -> String:
	return _map_loader.label_at(cell) if _map_loader else ""

## Script cell change (S.setCell): passability, and a new look ("" = keep the look). Objects baked on that cell
## (cut trees, card-key doors, gates...) disappear when the label changes.
func set_cell_override(cell: Vector2i, label: String, passable: bool) -> void:
	if _map_loader:
		_map_loader.set_cell_override(cell, label, passable)

func clear_cell_override(cell: Vector2i) -> void:
	if _map_loader:
		_map_loader.clear_cell_override(cell)

## Elevators: every exit warp of this map now leads to (to_map, warp_index).
func set_exit_warps(to_map: String, warp_index: int) -> void:
	_exit_redirect = [to_map, warp_index]

## "walk" | "bike" | "surf": surfing rides the lead Pokémon over water, the bike walks at 3x speed.
func set_ride(mode: String) -> void:
	ride = mode
	var sp := _lead_species()
	player.set_mount(("mon:" + (sp if sp != "" else "LAPRAS")) if mode == "surf" else "")
	_update_follower_visibility()

func take_warp() -> void:
	var wi := _map_loader.warp_index_at(player.cell) if _map_loader else -1
	if wi < 0:
		return
	await _do_warp(wi)

func is_warping() -> bool:
	return _busy

func shake(frames: int = 6) -> void:
	_shake = maxf(_shake, float(frames) * 0.5)

func set_flash(on: bool) -> void:
	flashed = on
	_apply_ambient_env()

var _flash_tw: Tween = null   # the running flash fade (a new flash replaces it instead of fighting it)

func _flash_fade(start: Color, secs: float, trans: Tween.TransitionType = Tween.TRANS_LINEAR) -> Tween:
	if _flash_tw and _flash_tw.is_valid():
		_flash_tw.kill()
	_flash_rect.color = start
	_flash_tw = create_tween()
	_flash_tw.set_trans(trans).set_ease(Tween.EASE_OUT)
	_flash_tw.tween_property(_flash_rect, "color:a", 0.0, secs)
	return _flash_tw

func flash_white(frames: int = 8) -> void:
	_flash_fade(Color(1, 1, 1, 1), frames * FRAME, Tween.TRANS_QUAD)
	await get_tree().create_timer(frames * FRAME).timeout   # (a killed tween never emits `finished`)

func poison_flash() -> void:
	_flash_fade(Color(0.69, 0.28, 0.63, 0.35), 6.0 * FRAME)

## Pokémon Center healing machine: `count` balls placed, `glow` while it runs.
func heal_machine(count: int, glow: bool) -> void:
	if _map_loader:
		for na in _map_loader.actors:
			if (na as OwActor).sprite == "nurse" and not (na as OwActor).is_gesturing():   # called once per ball: don't restart the bow
				(na as OwActor).gesture("Bow")
	_heal_count = count
	if glow:
		_flash_fade(Color(1.0, 0.95, 0.8, 0.25), 20.0 * FRAME)

## S.S. Anne leaves Vermilion's dock (Early.gd): the ship sails off into a fade.
func ship_departs() -> void:
	shake(20)
	await get_tree().create_timer(40.0 * FRAME).timeout
	await fade_out(20)
	await fade_in(20)

## Small field effects: "cut" (a tree is cut down), "purified_zone" (Pokémon Tower).
func fx(kind: String, cell: Vector2i) -> void:
	var at := OwActor.cell_pos(cell)
	debris.ground_y = at.y
	if kind == "cut":
		debris.leaves(at + Vector3(0, 0.4, 0), 18)
		ow_fx.grass(at + Vector3(0, 0.1, 0), 6)
		return
	if kind == "purified_zone":
		ow_fx.sparkle(at + Vector3(0, 0.3, 0), 8, Color(0.85, 0.8, 1.0))
	var l := Label3D.new()
	l.text = {"cut": "✂", "purified_zone": "✦"}.get(kind, "*")
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.font_size = 48
	l.modulate = Color(0.55, 0.85, 0.4) if kind == "cut" else Color(0.85, 0.8, 1.0)
	l.position = OwActor.cell_pos(cell) + Vector3(0, WorldData.px_h(12.0), 0)
	_map_root.add_child(l)
	var tw := create_tween()
	tw.tween_property(l, "modulate:a", 0.0, 30.0 * FRAME)
	tw.tween_callback(l.queue_free)
