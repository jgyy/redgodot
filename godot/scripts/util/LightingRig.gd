class_name LightingRig
extends RefCounted
## Applies a day/dusk/night lighting preset (sun color/energy, sky/ambient color)
## to a scene's DirectionalLight3D + WorldEnvironment. Shared by Overworld (driven
## by GameState.time_period()), and used once at load by Title/Battle so every
## screen reads consistently against the same three presets.

const PRESETS := {
	"day": {
		"sun_energy": 1.1, "sun_color": Color(1.0, 0.98, 0.92),
		"bg": Color(0.55, 0.75, 0.95), "ambient": Color(0.75, 0.8, 0.9), "ambient_energy": 0.9,
	},
	"dusk": {
		"sun_energy": 0.75, "sun_color": Color(1.0, 0.58, 0.32),
		"bg": Color(0.45, 0.27, 0.33), "ambient": Color(0.62, 0.44, 0.48), "ambient_energy": 0.75,
	},
	"night": {
		"sun_energy": 0.16, "sun_color": Color(0.55, 0.6, 0.88),
		"bg": Color(0.08, 0.1, 0.2), "ambient": Color(0.25, 0.28, 0.46), "ambient_energy": 0.55,
	},
}

static func periods() -> Array:
	return PRESETS.keys()

static func apply(sun: DirectionalLight3D, env: Environment, period: String) -> void:
	var p: Dictionary = PRESETS.get(period, PRESETS["day"])
	if sun:
		sun.light_energy = p["sun_energy"]
		sun.light_color = p["sun_color"]
	if env:
		env.background_color = p["bg"]
		env.ambient_light_color = p["ambient"]
		env.ambient_light_energy = p["ambient_energy"]
