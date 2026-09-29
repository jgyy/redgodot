class_name MissingNoBlock
extends Node3D
## MISSINGNO.'s famous glitch block (upstream src/game/glitches.js: decompressed
## garbage in the shape of a backwards L), built as a 3D stack of cubes, each
## face a different seeded garbage tile (checkers, stripes, noise, solid).

const CELL := 0.25

func _init() -> void:
	_build()

func _build() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x1F
	var cells: Array = []
	# 3-wide column, 7 tall, plus a 4x3 foot to the left: the backwards L
	for y in 7:
		for x in range(4, 7):
			cells.append(Vector2i(x, y))
	for y in range(4, 7):
		for x in range(0, 4):
			cells.append(Vector2i(x, y))
	for c in cells:
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(CELL, CELL, CELL * (0.8 + rng.randf() * 0.5))
		mi.mesh = bm
		var mat := StandardMaterial3D.new()
		mat.albedo_texture = _garbage_tile(rng)
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
		mat.roughness = 0.9
		mi.material_override = mat
		mi.position = Vector3((c.x - 3.5) * CELL, (6 - c.y) * CELL + CELL / 2.0, (rng.randf() - 0.5) * CELL * 0.3)
		add_child(mi)

func _garbage_tile(rng: RandomNumberGenerator) -> ImageTexture:
	var img := Image.create(8, 8, false, Image.FORMAT_RGB8)
	var pal := [Color("#101018"), Color("#f4f4f4"), Color("#8a8a92"), Color("#c8c8d0"), Color("#46464e")]
	var kind := rng.randi() % 5
	for y in 8:
		for x in 8:
			var c: Color
			match kind:
				0: c = pal[(x + y) % 2 * 1]
				1: c = pal[0] if (x / 2 + y) % 3 == 0 else pal[3]
				2: c = pal[rng.randi() % pal.size()]
				3: c = pal[2] if y < 4 else pal[0]
				_: c = pal[1] if (x + y * 3) % 5 < 2 else pal[4]
			img.set_pixel(x, y, c)
	return ImageTexture.create_from_image(img)
