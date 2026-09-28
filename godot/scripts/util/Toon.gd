class_name Toon
extends RefCounted
## Swaps the materials of an imported glb (Pokemon or character) for the cel shader
## (res://assets/shaders/toon.gdshader) + inverted-hull outline next pass, keeping the
## glb's own albedo texture / colour.  Per-instance override materials, so the shared
## imported resources are never mutated.
##
##   Toon.apply(model)                   # after instantiate()
##   Toon.set_param(model, "tint", Color(0.6, 0.6, 0.9))  # e.g. night
##   Toon.set_param(model, "flash", Color(1, 1, 1, 0.8))   # hit flash
##   Toon.set_param(model, "width_px", 3.0)  # outline width (px of a 540-tall screen)

const TOON_SHADER := preload("res://assets/shaders/toon.gdshader")
const OUTLINE_SHADER := preload("res://assets/shaders/outline.gdshader")

## outline_px: outline width in pixels of a 540-tall screen (scales with resolution); 0 disables it.
static func apply(model: Node, outline_px: float = 2.4, max_outline_world: float = 0.05) -> void:
	for mi in _mesh_instances(model):
		var inst: MeshInstance3D = mi
		if inst.mesh == null:
			continue
		for i in range(inst.mesh.get_surface_count()):
			var src: Material = inst.get_surface_override_material(i)
			if src == null:
				src = inst.mesh.surface_get_material(i)
			if src is ShaderMaterial and (src as ShaderMaterial).shader == TOON_SHADER:
				continue
			inst.set_surface_override_material(i, make_material(src, outline_px, max_outline_world))

## Builds a toon ShaderMaterial from any source material (StandardMaterial3D from a glb,
## or null for plain white).
static func make_material(src: Material, outline_px: float = 2.4, max_outline_world: float = 0.05) -> ShaderMaterial:
	var tex: Texture2D = null
	var col := Color(1, 1, 1)
	if src is BaseMaterial3D:
		var bm: BaseMaterial3D = src
		tex = bm.albedo_texture
		col = bm.albedo_color
	var m := ShaderMaterial.new()
	m.shader = TOON_SHADER
	m.set_shader_parameter("albedo_color", col)
	m.set_shader_parameter("use_texture", tex != null)
	if tex:
		m.set_shader_parameter("albedo_tex", tex)
	if outline_px > 0.0:
		var o := ShaderMaterial.new()
		o.shader = OUTLINE_SHADER
		o.set_shader_parameter("albedo_color", col)
		o.set_shader_parameter("use_texture", tex != null)
		o.set_shader_parameter("width_px", outline_px)
		o.set_shader_parameter("max_world", max_outline_world)
		if tex:
			o.set_shader_parameter("albedo_tex", tex)
		m.next_pass = o
	return m

## Sets a uniform on every toon material (and its outline pass when it has that uniform:
## tint, fade) under `model`.
static func set_param(model: Node, param: String, value: Variant) -> void:
	for mi in _mesh_instances(model):
		var inst: MeshInstance3D = mi
		if inst.mesh == null:
			continue
		for i in range(inst.mesh.get_surface_count()):
			var m := inst.get_surface_override_material(i) as ShaderMaterial
			if m == null:
				continue
			m.set_shader_parameter(param, value)
			var o := m.next_pass as ShaderMaterial
			if o and (param == "tint" or param == "fade" or param == "viewport_h" or param == "width_px"):
				o.set_shader_parameter(param, value)

static func _mesh_instances(node: Node) -> Array:
	var out: Array = []
	if node is MeshInstance3D:
		out.append(node)
	for c in node.get_children():
		out.append_array(_mesh_instances(c))
	return out
