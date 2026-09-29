class_name BattleTransition
extends CanvasLayer
## Plays the battle intro wipe (wild spiral / trainer bands / boss Poke Ball) over a snapshot of the screen taken just
## before the battle scene opened (upstream battleflow.js transition()).  Not used without a snapshot (headless, tests).

const SHADER := preload("res://assets/shaders/battle_transition.gdshader")
const FRAMES := {"wild": 62, "trainer": 52, "boss": 52}   # upstream: 62 for wild, 52 for everything else
const KINDS := {"wild": 0, "trainer": 1, "boss": 2}

var _rect: ColorRect
var _mat: ShaderMaterial

static func snapshot(vp: Viewport) -> Texture2D:
	if DisplayServer.get_name() == "headless":
		return null
	var img := vp.get_texture().get_image()
	if img == null or img.is_empty():
		return null
	return ImageTexture.create_from_image(img)

func _init(tex: Texture2D, kind: String) -> void:
	layer = 80
	_rect = ColorRect.new()
	_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mat = ShaderMaterial.new()
	_mat.shader = SHADER
	_mat.set_shader_parameter("snap", tex)
	_mat.set_shader_parameter("kind", int(KINDS.get(kind, 0)))
	_rect.material = _mat
	add_child(_rect)

func set_frame(f: float) -> void:
	_mat.set_shader_parameter("t", f)
