class_name TitleOverlay
extends PxCanvas
## The 2D layer of upstream's title.js over the 3D diorama: the logo.js
## POKéMON / CLAUDE RED logo (baked by bake_ui.js) bobbing at y 12/44,
## the blinking PRESS START and the control hints, plus a full-screen fade used by the menu flow.

const LOGO_BIG: Texture2D = preload("res://assets/ui/title_logo_big.png")
const LOGO_RED: Texture2D = preload("res://assets/ui/title_logo_red.png")

var t := 0
var hide_hints := false
var fade_color := Color(0, 0, 0, 0)

func _draw() -> void:
	var bob := roundf(sin(t / 30.0) * 2.0)
	Px.blit(self, LOGO_BIG, 160 - (LOGO_BIG.get_width() >> 1), 12 + bob)
	Px.blit(self, LOGO_RED, 160 - (LOGO_RED.get_width() >> 1), 44 + bob)
	if not hide_hints and (t / 30) % 2 == 0:
		var tx := "PRESS START"
		Px.text_outlined(self, tx, 160 - Px.measure(tx) / 2.0, 164, Color("#fff8e0"), Color("#301818"))
	var help := "ARROWS OR CLICK  Z:A  X:B  ENTER:START"
	if not hide_hints:
		Px.small(self, help, 316 - Px.measure_small(help), 174, Color("#8090a8"), Color("#101a18"))
	if fade_color.a > 0.0:
		Px.rect(self, 0, 0, Px.W, Px.H, fade_color)

## Fades to (out = true) or from `color` over `frames` 60 fps frames.
func fade(frames: int, color: Color = Color.BLACK, out: bool = true) -> void:
	var tw := create_tween()
	var from := Color(color, 0.0 if out else 1.0)
	var to := Color(color, 1.0 if out else 0.0)
	fade_color = from
	tw.tween_property(self, "fade_color", to, frames / 60.0)
	await tw.finished
