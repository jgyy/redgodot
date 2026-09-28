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

var species_id: String = ""
var _anim: AnimationPlayer

func setup(sid: String) -> void:
	species_id = sid
	for c in get_children():
		c.queue_free()
	_anim = null

	var path := "res://assets/models/pokemon/%s.glb" % sid
	var model: Node3D
	if ResourceLoader.exists(path):
		var scene: PackedScene = load(path)
		if scene:
			model = scene.instantiate()
	if model == null:
		model = _fallback_model(sid)
	add_child(model)
	_anim = _find_anim_player(model)
	AnimUtil.fix_looping(_anim)
	play("Idle")

func play(anim_name: String) -> void:
	if _anim and _anim.has_animation(anim_name):
		_anim.play(anim_name)

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
