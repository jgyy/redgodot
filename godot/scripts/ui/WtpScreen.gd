class_name WtpScreen
extends PxScreen
## "Who's that POKéMON?" (upstream wtp.js): a silhouette quiz over all 151 species, played with the same generated 3D
## models as the rest of the game.  Five rounds, four name choices each; the silhouette lights up (and the mon
## celebrates or flinches) once you answer.  Reached from the title menu.

const ROUNDS := 5

var round_i := 0
var score := 0
var species := ""
var revealed := false
var _view: PxView3D
var _rng := RandomNumberGenerator.new()
var streak_text := ""

func _ready() -> void:
	super()
	_view = PxView3D.new(96, 96)
	add_child(_view)

func _on_open() -> void:
	round_i = 0
	score = 0
	_rng.randomize()
	_play()

func pick_species() -> String:
	var all: Array = GameData.species.keys()
	all.sort()
	return all[_rng.randi_range(0, all.size() - 1)]

func choices_for(answer: String) -> Array:
	var all: Array = GameData.species.keys()
	all.sort()
	var out: Array = [answer]
	while out.size() < 4:
		var s: String = all[_rng.randi_range(0, all.size() - 1)]
		if not out.has(s):
			out.append(s)
	out.shuffle()
	return out

func _shade(black: bool) -> void:
	if _view.model is PokemonActor:
		(_view.model as PokemonActor).set_shader_param("tint", Color(0, 0, 0, 1) if black else Color.WHITE)
		(_view.model as PokemonActor).set_shader_param("rim", 0.0 if black else 0.12)

func _play() -> void:
	while round_i < ROUNDS:
		species = pick_species()
		revealed = false
		_view.show_mon(species)
		_shade(true)
		streak_text = ""
		var opts := choices_for(species)
		var names: Array = []
		for o in opts:
			names.append(GameData.get_species(o).get("name", o))
		await get_tree().create_timer(0.35).timeout
		var r := await choose(names, {"x": 196, "y": 96, "w": 118, "no_cancel": true})
		revealed = true
		_shade(false)
		var actor := _view.model as PokemonActor
		if opts[r] == species:
			score += 1
			streak_text = "It's %s!" % GameData.get_species(species).get("name", species)
			UI.sfx("select")
			if actor:
				actor.play_once("Victory")
		else:
			streak_text = "No... it's %s!" % GameData.get_species(species).get("name", species)
			if actor:
				actor.play_once("Hurt")
		await get_tree().create_timer(1.6).timeout
		round_i += 1
	await say("You got %d out of %d right!" % [score, ROUNDS])
	exit()

func _draw() -> void:
	Px.menu_bg(self, Color("#f8d848"), Color("#f0c838"), t)
	Px.frame(self, 4, 4, 312, 26, "red")
	Px.text_c(self, "WHO'S THAT POKéMON?", 160, 11)
	Px.frame(self, 8, 36, 180, 136)
	if species != "":
		_view.draw_at(self, 50, 50 + roundf(sin(t / 24.0)))
	Px.frame(self, 196, 36, 116, 52)
	Px.text(self, "ROUND %d/%d" % [mini(round_i + 1, ROUNDS), ROUNDS], 206, 46)
	Px.text(self, "SCORE  %d" % score, 206, 64)
	if revealed and streak_text != "":
		Px.frame(self, 8, 140, 180, 32)
		Px.text(self, streak_text, 16, 150)
