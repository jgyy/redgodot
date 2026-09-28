extends Node3D
## Pre-title narrative beat: Professor Oak's classic introduction, delivered
## through the same DialogueBox used in the overworld, over a starry backdrop
## with a slowly-turning real 3D Pokemon model. Advances to Title on finish.

const LINES := [
	"Hello there! Welcome to the world of POKéMON!",
	"My name is OAK! People call me the POKéMON PROF!",
	"This world is inhabited by creatures called POKéMON!",
	"For some people, POKéMON are pets. Others use them for fights.",
	"Myself... I study POKéMON as a profession.",
	"Your very own POKéMON legend is about to unfold!",
	"A world of dreams and adventures with POKéMON awaits! Let's go!",
]

@onready var _slot: Node3D = $MonSlot

var _actor: PokemonActor
var _dialogue: DialogueBox

func _ready() -> void:
	_actor = PokemonActor.new()
	_slot.add_child(_actor)
	_actor.setup("BULBASAUR")

	_dialogue = DialogueBox.new()
	add_child(_dialogue)
	_dialogue.finished.connect(_on_finished)
	_dialogue.show_lines(LINES)

func _process(delta: float) -> void:
	if _slot:
		_slot.rotate_y(delta * 0.6)

func _on_finished() -> void:
	SceneRouter.goto_title()
