class_name PxCanvas
extends Control
## Base class for pixel-UI overlays: a 320x180 logical canvas (upstream's
## framebuffer size) scaled 3x to the 960x540 viewport with nearest filtering,
## so ports of upstream draw code can use its exact coordinates via Px.*.
## Subclasses draw in _draw(); set `animate = true` to redraw every frame.

@export var animate := true

func _init() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _ready() -> void:
	_fit()
	get_viewport().size_changed.connect(_fit)

func _fit() -> void:
	var vs := get_viewport_rect().size
	var k := maxf(1.0, floorf(minf(vs.x / Px.W, vs.y / Px.H)))
	scale = Vector2(k, k)
	size = Vector2(Px.W, Px.H)
	position = ((vs - size * k) / 2.0).floor()

func _process(_dt: float) -> void:
	if animate and is_visible_in_tree():
		queue_redraw()
