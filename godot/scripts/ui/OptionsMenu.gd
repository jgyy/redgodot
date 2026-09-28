class_name OptionsMenu
extends PxScreen
## Port of menus.js optionsMenu(): a 190-wide menu at (120, 30) over whatever
## is behind it; A toggles the highlighted option in place, CANCEL/B leaves.
## Writes GameState.options (text_speed 1-3, battle_anim, battle_style,
## sound, day_night, follower).

var sel := 0

func items() -> Array:
	var o := GameState.options
	var ts := int(o.get("text_speed", 2))
	return [
		"TEXT SPEED: " + ["SLOW", "MID", "FAST"][clampi(ts - 1, 0, 2)],
		"BATTLE ANIM: " + ("ON" if o.get("battle_anim", true) else "OFF"),
		"BATTLE STYLE: " + ("SHIFT" if o.get("battle_style", "shift") == "shift" else "SET"),
		"SOUND: " + ("ON" if o.get("sound", true) else "OFF"),
		"DAY/NIGHT: " + ("ON" if o.get("day_night", true) else "OFF"),
		"FOLLOWER: " + ("ON" if o.get("follower", true) else "OFF"),
		"CANCEL",
	]

func _on_open() -> void:
	sel = 0

## Toggles option row r (0-5), exactly as upstream's loop body.
static func toggle(r: int) -> void:
	var o := GameState.options
	match r:
		0: o["text_speed"] = int(o.get("text_speed", 2)) % 3 + 1
		1: o["battle_anim"] = not o.get("battle_anim", true)
		2: o["battle_style"] = "set" if o.get("battle_style", "shift") == "shift" else "shift"
		3:
			o["sound"] = not o.get("sound", true)
			GameState.sound_on = o["sound"]
		4: o["day_night"] = not o.get("day_night", true)
		5: o["follower"] = not o.get("follower", true)
	GameState.text_speed = ["SLOW", "NORMAL", "FAST"][int(o["text_speed"]) - 1]

func _input_event(e: InputEvent) -> bool:
	if pressed(e, "move_up", true):
		sel = (sel + 6) % 7
	elif pressed(e, "move_down", true):
		sel = (sel + 1) % 7
	elif pressed(e, "confirm"):
		if sel == 6:
			exit()
		else:
			toggle(sel)
	elif pressed(e, "cancel"):
		exit()
	else:
		return false
	return true

func _draw() -> void:
	Px.menu(self, items(), sel, 120, 30, 190, -1, 0, Px.frame_count())
