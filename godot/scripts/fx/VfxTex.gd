class_name VfxTex
extends RefCounted
## Procedural textures for battle effects (no image files): soft glows, a thin ring, a beam streak, a spark
## cross. All are white with the shape in alpha, tinted per use by the material's albedo colour.

static var _cache: Dictionary = {}

static func _cached(key: String, maker: Callable) -> Texture2D:
	if not _cache.has(key):
		_cache[key] = maker.call()
	return _cache[key]

static func _image_tex(w: int, h: int, f: Callable) -> Texture2D:
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in w:
			var a: float = f.call((float(x) + 0.5) / w * 2.0 - 1.0, (float(y) + 0.5) / h * 2.0 - 1.0)
			img.set_pixel(x, y, Color(1, 1, 1, clampf(a, 0.0, 1.0)))
	return ImageTexture.create_from_image(img)

## Soft round glow: bright centre, smooth long tail (gaussian-ish), zero at the edge.
static func soft() -> Texture2D:
	return _cached("soft", func() -> Texture2D:
		return _image_tex(64, 64, func(x: float, y: float) -> float:
			var r2 := x * x + y * y
			if r2 >= 1.0:
				return 0.0
			var g := exp(-r2 * 4.2)
			return g * (1.0 - r2 * r2)))

## Tight hot core: a small bright disc with a soft rim (white-hot centres of flames, bolts, impacts).
static func core() -> Texture2D:
	return _cached("core", func() -> Texture2D:
		return _image_tex(64, 64, func(x: float, y: float) -> float:
			var r := sqrt(x * x + y * y)
			return 1.0 - smoothstep(0.35, 0.95, r)))

## Thin soft ring, radius 0.82 of the quad (shock waves, ripples).
static func ring() -> Texture2D:
	return _cached("ring", func() -> Texture2D:
		return _image_tex(128, 128, func(x: float, y: float) -> float:
			var r := sqrt(x * x + y * y)
			var a := smoothstep(0.62, 0.8, r) * (1.0 - smoothstep(0.8, 0.98, r))
			return a))

## Horizontal capsule streak, brightest along its axis (beam glow, speed lines, trails): x along the length.
static func streak() -> Texture2D:
	return _cached("streak", func() -> Texture2D:
		return _image_tex(128, 32, func(x: float, y: float) -> float:
			var ex := 1.0 - smoothstep(0.55, 1.0, absf(x))
			var ey := exp(-y * y * 5.0) * (1.0 - y * y)
			return ex * ey))

## Four-point twinkle (sparkles, star bursts).
static func twinkle() -> Texture2D:
	return _cached("twinkle", func() -> Texture2D:
		return _image_tex(64, 64, func(x: float, y: float) -> float:
			var ax := absf(x)
			var ay := absf(y)
			var cross := exp(-ax * 22.0) * (1.0 - ay) + exp(-ay * 22.0) * (1.0 - ax)
			var glow := exp(-(x * x + y * y) * 9.0)
			return maxf(cross * 0.9, glow)))
