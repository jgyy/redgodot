class_name FadeCanvas
extends PxCanvas
## Full-screen colour fade (upstream G.fadeOut / G.fadeIn) on its own canvas.

var fade_color := Color(0, 0, 0, 0)

func _init() -> void:
	super()
	animate = true

func _draw() -> void:
	if fade_color.a > 0.0:
		Px.rect(self, -4, -4, Px.W + 8, Px.H + 8, fade_color)

## Fades to (out = true) or from `color` over `frames` 60 fps frames.
func fade(frames: int, color: Color = Color.BLACK, out: bool = true) -> void:
	var tw := create_tween()
	fade_color = Color(color, 0.0 if out else 1.0)
	tw.tween_property(self, "fade_color", Color(color, 1.0 if out else 0.0), frames / 60.0)
	await tw.finished
