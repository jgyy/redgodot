class_name LightingRig
extends RefCounted
## Day / dusk / night, ported from upstream src/art/ambient.js:
##  - `time_of_day(hour)` is upstream G.timeOfDay() ({night, dusk} in 0..1)
##  - `grade(td)` is its multiplicative colour grade (applied in the world shaders, in sRGB, like the 2D game)
##  - `light_amount(td)` is the strength of its dithered light pools (lit windows, Center/Mart signs, fires)
##  - `build_light_maps(bake)` splats those pools exactly as upstream's splat() does, into textures the world
##    shaders sample in 2D screen space.
## The 3D-lit parts (characters, Pokémon) get a sun + ambient matched to the same grade (`apply_3d`).
## `apply(sun, env, period)` keeps the old preset API for Title/Battle.

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

## Hours used for the three named periods (what `--time=` selects for captures).
const PERIOD_HOUR := {"day": 12.0, "dusk": 19.0, "night": 23.0}

const LIGHT_COL := {
	"sign_poke": Color8(0xff, 0x9a, 0x9a), "sign_mart": Color8(0xa8, 0xc8, 0xff), "fire": Color8(0xff, 0x9a, 0x48),
	"def": Color8(0xff, 0xd4, 0x8a),
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

## upstream G.timeOfDay(): hour in 0..24 -> {night, dusk}
static func time_of_day(h: float) -> Dictionary:
	var night := 0.0
	if h >= 20.0 or h < 5.0:
		night = 1.0
	elif h >= 18.0:
		night = (h - 18.0) / 2.0
	elif h < 7.0:
		night = 1.0 - (h - 5.0) / 2.0
	var dusk := 0.0
	if h >= 16.5 and h < 20.0:
		dusk = sin(minf(1.0, (h - 16.5) / 3.0) * PI)
	elif h >= 5.0 and h < 7.5:
		dusk = sin(((h - 5.0) / 2.5) * PI) * 0.7
	return {"night": clampf(night, 0.0, 1.0), "dusk": dusk}

## upstream dayNight(): per-channel multiplier (sRGB)
static func grade(td: Dictionary) -> Color:
	var n: float = float(td.night) * 0.8
	var du: float = float(td.dusk) * 0.4
	var mr := roundf(255.0 * (1.0 - n * 0.68) * (1.0 - du * 0.02)) / 256.0
	var mg := roundf(255.0 * (1.0 - n * 0.6) * (1.0 - du * 0.2)) / 256.0
	var mb := roundf(255.0 * (1.0 - n * 0.3) * (1.0 - du * 0.45)) / 256.0
	if float(td.night) <= 0.01 and float(td.dusk) <= 0.01:
		return Color(1, 1, 1)
	return Color(mr, mg, mb)

static func light_amount(td: Dictionary) -> float:
	var nt: float = td.night
	return minf(1.0, (nt - 0.3) * 1.6) if nt > 0.3 else 0.0

## Light pools + lit-window rectangles for a bake (px space of the baked ground). Returns [light_tex, glow_tex].
static func build_light_maps(bake: Dictionary) -> Array:
	var w := int(bake.get("cw", 1)) * 16
	var h := int(bake.get("ch", 1)) * 16
	var light := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var glow := Image.create(w, h, false, Image.FORMAT_R8)
	var vbuf := PackedFloat32Array()
	vbuf.resize(w * h)
	for l in bake.get("lights", []):
		var x := float(l[0])
		var y := float(l[1])
		var k := String(l[2])
		if k == "fire":
			_splat(light, vbuf, x, y + 8.0, 30.0, 18.0, 0.95, LIGHT_COL.fire)
		else:
			_splat(light, vbuf, x, y + 6.0, 20.0, 12.0, 0.8, LIGHT_COL.get(k, LIGHT_COL.def))
		if k == "window":
			for yy in range(int(y) - 3, int(y) + 3):
				for xx in range(int(x) - 4, int(x) + 5):
					if xx >= 0 and yy >= 0 and xx < w and yy < h:
						glow.set_pixel(xx, yy, Color(1, 0, 0))
	return [ImageTexture.create_from_image(light), ImageTexture.create_from_image(glow)]

static func _splat(img: Image, vbuf: PackedFloat32Array, x0: float, y0: float, rx: float, ry: float, k: float, col: Color) -> void:
	var w := img.get_width()
	var h := img.get_height()
	var xa := maxi(0, int(floor(x0 - rx)))
	var xb := mini(w - 1, int(ceil(x0 + rx)))
	var ya := maxi(0, int(floor(y0 - ry)))
	var yb := mini(h - 1, int(ceil(y0 + ry)))
	for y in range(ya, yb + 1):
		var dy := (y + 0.5 - y0) / ry
		var dy2 := dy * dy
		if dy2 >= 1.0:
			continue
		for x in range(xa, xb + 1):
			var dx := (x + 0.5 - x0) / rx
			var dd := dx * dx + dy2
			if dd >= 1.0:
				continue
			var v := k * (1.0 - dd) * (1.0 - dd)
			var i := y * w + x
			if v > vbuf[i]:
				vbuf[i] = v
				img.set_pixel(x, y, Color(col.r, col.g, col.b, v))

## Sun + ambient for the 3D-lit characters, matched to the world grade.
static func apply_3d(sun: DirectionalLight3D, env: Environment, g: Color, interior: bool) -> void:
	var lum := (g.r + g.g + g.b) / 3.0
	if sun:
		sun.light_color = Color(minf(1.0, g.r * 1.05), g.g, g.b)
		sun.light_energy = 0.75 * lum if not interior else 0.65
	if env:
		env.background_color = Color8(13, 12, 22) if interior else Color8(23, 61, 47)
		env.ambient_light_color = g
		env.ambient_light_energy = 0.7
