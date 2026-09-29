class_name PokemonActor
extends Node3D
## Loads a Pokemon's generated 3D model (from the Blender pipeline) and exposes a
## small, animation-name-based API used by both the battle scene and (later)
## overworld followers. Falls back to a simple colored primitive so the game
## works even for species the asset pipeline hasn't generated yet.

const TYPE_COLORS := {
	"NORMAL": Color(0.66, 0.66, 0.47), "FIRE": Color(0.93, 0.51, 0.19),
	"WATER": Color(0.39, 0.56, 0.94), "ELECTRIC": Color(0.97, 0.82, 0.19),
	"GRASS": Color(0.48, 0.78, 0.30), "ICE": Color(0.6, 0.85, 0.85),
	"FIGHTING": Color(0.76, 0.18, 0.16), "POISON": Color(0.63, 0.24, 0.63),
	"GROUND": Color(0.88, 0.75, 0.41), "FLYING": Color(0.66, 0.56, 0.95),
	"PSYCHIC_TYPE": Color(0.95, 0.31, 0.49), "BUG": Color(0.65, 0.72, 0.11),
	"ROCK": Color(0.71, 0.63, 0.22), "GHOST": Color(0.44, 0.34, 0.6),
	"DRAGON": Color(0.44, 0.22, 0.97),
}

## Every glb carries these clips (pipeline/blender/gen_rigged_pokemon.py); Idle/Walk/Run/Sleep/Charge/Taunt/Hover/Talk loop.
const CLIPS := ["Idle", "Walk", "Run", "Attack", "Special", "Hurt", "Faint", "Victory", "Sleep", "Roar",
		"Dodge", "Spin", "Hop", "Charge", "Taunt", "Spawn", "Hover", "Talk"]
## Species that float or fly idle in Hover (flapping / bobbing) instead of standing.
const HOVERERS := ["GASTLY", "HAUNTER", "GENGAR", "MAGNEMITE", "MAGNETON", "KOFFING", "WEEZING", "VOLTORB", "ELECTRODE",
		"PORYGON", "STARYU", "STARMIE", "MEW", "MEWTWO"]

var species_id: String = ""
var model: Node3D
var _anim: AnimationPlayer
## Sleeping mons (status SLP) loop the Sleep clip instead of Idle.
var sleeping := false:
	set(v):
		if v == sleeping:
			return
		sleeping = v
		if _anim and current_clip() in ["Idle", "Hover", "Sleep"]:
			play("Idle")

static var _manifest: Dictionary = {}

func setup(sid: String) -> void:
	species_id = sid
	for c in get_children():
		c.queue_free()
	_anim = null

	model = null
	var path := "res://assets/models/pokemon/%s.glb" % sid
	if ResourceLoader.exists(path):
		var scene: PackedScene = load(path)
		if scene:
			model = scene.instantiate()
	if model == null:
		model = _fallback_model(sid)
	add_child(model)
	Toon.apply(model)
	_anim = _find_anim_player(model)
	AnimUtil.fix_looping(_anim)
	if _anim:
		# cross-fade between clips (Idle <-> Walk <-> Attack ...): the baked clips start/end in different poses.
		# (--noblend: contact-sheet tooling seeks paused poses, where a pending blend would hide the clip)
		_anim.playback_default_blend_time = 0.0 if OS.get_cmdline_user_args().has("--noblend") else 0.12
	play("Idle")

## Plays a baked clip: Idle / Walk (looping), Attack / Hurt / Faint / Special (one-shot).
func play(anim_name: String) -> void:
	if anim_name == "Idle":
		anim_name = idle_clip()
	if _anim and _anim.has_animation(anim_name):
		_anim.play(anim_name)

## The looping clip a mon rests in: Sleep when asleep, Hover for fliers and floaters, else Idle.
func idle_clip() -> String:
	if sleeping and has_anim("Sleep"):
		return "Sleep"
	if is_hoverer() and has_anim("Hover"):
		return "Hover"
	return "Idle"

func is_hoverer() -> bool:
	if HOVERERS.has(species_id):
		return true
	return "FLYING" in GameData.get_species(species_id).get("types", [])

## One-shot clip that returns to Idle when done (Faint stays on its last frame).
func play_once(anim_name: String) -> void:
	if _anim == null or not _anim.has_animation(anim_name):
		return
	_anim.play(anim_name, 0.06)   # quick lead-in, the hand-back to Idle uses the longer blend from AnimUtil
	if anim_name != "Faint":
		_anim.queue(idle_clip())

## Name of the clip that is playing now ("" if none).
func current_clip() -> String:
	return _anim.current_animation if _anim else ""

func has_anim(anim_name: String) -> bool:
	return _anim != null and _anim.has_animation(anim_name)

## Cel-shader uniform on the whole model (tint, flash, fade, gloss... see toon.gdshader).
func set_shader_param(param: String, value: Variant) -> void:
	if model:
		Toon.set_param(model, param, value)

## Sizes the model the way upstream sizes battle sprites: every species is drawn in the
## same 64x64 frame, so a model's on-screen size is its height in sprite pixels (manifest
## "px_height") relative to that frame.  Afterwards a full 64 px sprite frame spans
## `frame_height_m` metres (e.g. ~1.6 for the foe).  Returns the scale applied.
func use_sprite_scale(frame_height_m: float) -> float:
	if model == null:
		return 1.0
	var info: Dictionary = species_info(species_id)
	var px: float = float(info.get("px_height", 0.0))
	var h: float = float(info.get("height_m", 0.0))
	if px <= 0.0 or h <= 0.0:
		return 1.0
	var s := (frame_height_m / 64.0) / (h / px)
	model.scale = Vector3.ONE * s
	return s

## manifest.json entry for a species ({height_m, px_height, tris, ...}), or {}.
static func species_info(sid: String) -> Dictionary:
	if _manifest.is_empty():
		var f := FileAccess.open("res://assets/models/pokemon/manifest.json", FileAccess.READ)
		if f:
			var data: Variant = JSON.parse_string(f.get_as_text())
			if data is Dictionary:
				_manifest = (data as Dictionary).get("species", {})
		if _manifest.is_empty():
			_manifest = {"_": {}}
	return _manifest.get(sid, {})

## Model height in metres (Pokedex height; the glb is authored at real scale).
func model_height() -> float:
	return GameData.species_height_m(species_id)

## Local-space AABB of all meshes (rest pose), e.g. for battle framing.
func model_aabb() -> AABB:
	var box := AABB()
	var first := true
	for mi in Toon._mesh_instances(self):
		var inst: MeshInstance3D = mi
		if inst.mesh == null:
			continue
		var b: AABB = global_transform.affine_inverse() * inst.global_transform * inst.mesh.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box

func _find_anim_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var found := _find_anim_player(c)
		if found:
			return found
	return null

func _fallback_model(sid: String) -> Node3D:
	var sp := GameData.get_species(sid)
	var types: Array = sp.get("types", ["NORMAL"])
	var color: Color = TYPE_COLORS.get(types[0], Color(0.7, 0.7, 0.7))
	var height := GameData.species_height_m(sid)

	var body := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = max(0.2, height * 0.45)
	sphere.height = sphere.radius * 2.0
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	sphere.material = mat
	body.mesh = sphere
	body.position.y = sphere.radius
	return body
