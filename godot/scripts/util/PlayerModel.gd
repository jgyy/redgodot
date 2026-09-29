class_name PlayerModel
extends RefCounted
## Assembles the player's 3D model from a PlayerLook: a head part (head, face, hair, hat + the skeleton and every
## clip) and a body part (arms, torso, legs, shoes, backpack skinned to the same bones), both built by
## pipeline/blender/gen_player_parts.py.  Each part's atlas carries a role map in its alpha channel
## (a = 255 - 20 * role); pixels of role r are multiplied by target / reference colour so the choices in the
## creator recolour skin, hair, hat, clothes, shoes, bag and eyes without any extra model files.

const DIR := "res://assets/models/player/"
const ROLES := ["skin", "hair", "hat", "hatk", "shirt", "pants", "shoes", "bag", "coat", "iris"]
const REFERENCE := {"skin": "#f4cca4", "hair": "#d0d0d0", "hat": "#d0d0d0", "hatk": "#d0d0d0", "shirt": "#d0d0d0",
		"pants": "#d0d0d0", "shoes": "#d0d0d0", "bag": "#d0d0d0", "coat": "#d0d0d0", "iris": "#d0d0d0"}

static var _idx_cache: Dictionary = {}     # atlas path -> PackedInt32Array of pixel indices that carry a role
static var _tex_cache: Dictionary = {}     # path + colours -> ImageTexture

static func available() -> bool:
	return ResourceLoader.exists(DIR + "head_short_cap_round.glb")

## The finished, cel-shaded model (faces +Z, feet at y = 0) or null when the part files are missing.
static func build(look: PlayerLook, toon: bool = true) -> Node3D:
	if look == null or not available():
		return null
	var head_path := DIR + look.head_key() + ".glb"
	var body_path := DIR + look.body_key() + ".glb"
	if not ResourceLoader.exists(head_path) or not ResourceLoader.exists(body_path):
		return null
	var root: Node3D = (load(head_path) as PackedScene).instantiate()
	var skel: Skeleton3D = root.find_child("Skeleton3D", true, false) as Skeleton3D
	var head_mi := _first_mesh(root)
	var body_root: Node3D = (load(body_path) as PackedScene).instantiate()
	var body_mi := _first_mesh(body_root)
	if skel == null or head_mi == null or body_mi == null:
		body_root.free()
		return root
	body_mi.get_parent().remove_child(body_mi)
	skel.add_child(body_mi)
	body_mi.skeleton = NodePath("..")
	body_root.free()
	var colors := _resolved_colors(look)
	if CharacterSkin.fit_bounds:   # like every other character: tall hair / a beanie must not shrink the player in OwActor._fit_height
		CharacterSkin._fit_bounds(root)
	if toon:
		Toon.apply(root, 1.3, 0.02)
		Toon.set_param(root, "ramp_bias", 0.28)
		Toon.set_param(root, "ramp_strength", 0.6)
	_texture(head_mi, DIR + look.head_key() + ".png", colors)
	_texture(body_mi, DIR + look.body_key() + ".png", colors)
	CharacterSkin.finish_model(root)
	return root

static func _first_mesh(n: Node) -> MeshInstance3D:
	if n is MeshInstance3D:
		return n
	for c in n.get_children():
		var f := _first_mesh(c)
		if f:
			return f
	return null

## Role -> Color, with the cap panel following the hat colour (white panel unless the cap itself is white).
static func _resolved_colors(look: PlayerLook) -> Dictionary:
	var out := {}
	for r in ROLES:
		out[r] = Color(look.colors.get(r, REFERENCE[r]))
	var hat_c: Color = out["hat"]
	out["hatk"] = Color("#d8383a") if hat_c.get_luminance() > 0.85 else Color("#f4f4f4")
	return out

static func _texture(mi: MeshInstance3D, path: String, colors: Dictionary) -> void:
	var tex := recolored_texture(path, colors)
	if tex == null:
		return
	for i in mi.mesh.get_surface_count():
		var m := mi.get_surface_override_material(i) as ShaderMaterial
		if m == null:
			continue
		m.set_shader_parameter("albedo_tex", tex)
		m.set_shader_parameter("use_texture", true)
		m.set_shader_parameter("albedo_color", Color.WHITE)
		if m.next_pass is ShaderMaterial:
			(m.next_pass as ShaderMaterial).set_shader_parameter("albedo_tex", tex)
			(m.next_pass as ShaderMaterial).set_shader_parameter("use_texture", true)
			(m.next_pass as ShaderMaterial).set_shader_parameter("albedo_color", Color.WHITE)

## The part's atlas recoloured for `colors` (role name -> Color).  Cached per palette.
static func recolored_texture(path: String, colors: Dictionary) -> ImageTexture:
	var key := path
	for r in ROLES:
		key += (colors[r] as Color).to_html(false)
	if _tex_cache.has(key):
		return _tex_cache[key]
	var src: Texture2D = load(path) as Texture2D
	if src == null:
		return null
	var img: Image = src.get_image()
	if img == null or img.is_empty():
		return null
	img.convert(Image.FORMAT_RGBA8)
	var data: PackedByteArray = img.get_data()
	if not _idx_cache.has(path):
		var idx := PackedInt32Array()
		for p in range(0, data.size(), 4):
			if data[p + 3] != 255:
				idx.append(p)
		_idx_cache[path] = idx
	var mul: Array = []
	for r in ROLES:
		var t: Color = colors[r]
		var ref := Color(REFERENCE[r])
		mul.append(Vector3(t.r / maxf(ref.r, 0.01), t.g / maxf(ref.g, 0.01), t.b / maxf(ref.b, 0.01)))
	for p in (_idx_cache[path] as PackedInt32Array):
		var role := int(roundf((255 - data[p + 3]) / 20.0))
		if role >= 1 and role <= ROLES.size():
			var m: Vector3 = mul[role - 1]
			data[p] = mini(255, int(data[p] * m.x))
			data[p + 1] = mini(255, int(data[p + 1] * m.y))
			data[p + 2] = mini(255, int(data[p + 2] * m.z))
		data[p + 3] = 255
	var out := ImageTexture.create_from_image(Image.create_from_data(img.get_width(), img.get_height(), false, Image.FORMAT_RGBA8, data))
	if _tex_cache.size() > 64:
		_tex_cache.clear()
	_tex_cache[key] = out
	return out
