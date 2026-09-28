class_name Mon3DPreview
extends SubViewportContainer
## Small reusable live 3D preview of a Pokemon species (real Blender-generated
## glb model, same PokemonActor used in battle), for menu screens that show a
## species portrait (Pokedex, Summary). Owns its own SubViewport/World3D so it
## renders independently of the main 3D scene behind it.

var _viewport: SubViewport
var _actor: PokemonActor

func _ready() -> void:
	stretch = true
	_viewport = SubViewport.new()
	_viewport.size = Vector2i(200, 200)
	_viewport.transparent_bg = true
	_viewport.own_world_3d = true
	add_child(_viewport)

	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0, 0, 0, 0)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.85, 0.85, 0.9)
	env.ambient_light_energy = 1.0
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	_viewport.add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(-0.7, 0.5, 0.0)
	sun.light_energy = 1.1
	_viewport.add_child(sun)

	var cam := Camera3D.new()
	cam.position = Vector3(0, 1.0, 2.6)
	cam.rotation = Vector3(-0.15, 0.0, 0.0)
	cam.fov = 30.0
	cam.current = true
	_viewport.add_child(cam)

	_actor = PokemonActor.new()
	_viewport.add_child(_actor)

func show_species(species_id: String) -> void:
	_actor.setup(species_id)
	_actor.use_sprite_scale(1.5)  # size like upstream's 64px sprite frame, not Pokedex metres
