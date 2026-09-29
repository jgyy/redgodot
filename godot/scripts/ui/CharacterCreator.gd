class_name CharacterCreator
extends PxScreen
## New-game character creator (upstream customizer.js, in 3D): boy/girl, hair style + colour, skin tone, eyes + eye
## colour, hat + colour, outfit + shirt / pants / shoes / bag colours, RANDOM and DONE.  The preview is the player's real
## 3D model (PlayerModel), rebuilt on every change, turning slowly and cycling through its gesture clips.
## Usage: var look: PlayerLook = await CharacterCreator.run(host_node, current_look)

signal finished(look: PlayerLook)

const PREVIEW_CLIPS := ["Idle", "Wave", "Cheer", "Dance", "Think", "Salute", "Nod", "Laugh", "Point", "Stretch"]

var look: PlayerLook
var row := 0
var _view: PxView3D
var _clip_t := 0.0
var _clip_i := 0
var _bump := 0.0
var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	super()
	_rng.randomize()
	_view = PxView3D.new(112, 150)
	_view.anchor = "bottom"
	_view.yaw = -20.0
	_view.fill = 0.96
	_view.spin = 0.5
	add_child(_view)

static func run(host: Node, start: PlayerLook) -> PlayerLook:
	var cc := CharacterCreator.new()
	host.add_child(cc)
	cc.look = start.duplicate_look() if start else PlayerLook.default_boy()
	cc.open()
	var l: PlayerLook = await cc.finished
	cc.queue_free()
	return l

func _on_open() -> void:
	row = 0
	_rebuild()

func _rebuild() -> void:
	_view.show_look(look)
	_bump = 1.0

## Row definitions for the current look: {key, label, kind ("opt" | "col" | "act"), off}.
func rows() -> Array:
	var col_label := "DRESS" if look.outfit == "dress" else ("COAT" if look.outfit == "coat_pants" else "SHIRT")
	return [
		{"key": "gender", "label": "LOOK", "kind": "opt"},
		{"key": "hair", "label": "HAIR", "kind": "opt"},
		{"key": "hair_c", "label": "HAIR COLOR", "kind": "col", "off": look.hair == "bald"},
		{"key": "skin_c", "label": "SKIN", "kind": "col"},
		{"key": "eyes", "label": "EYES", "kind": "opt"},
		{"key": "iris_c", "label": "EYE COLOR", "kind": "col"},
		{"key": "hat", "label": "HAT", "kind": "opt"},
		{"key": "hat_c", "label": "HAT COLOR", "kind": "col", "off": look.hat == "none"},
		{"key": "outfit", "label": "OUTFIT", "kind": "opt"},
		{"key": "shirt_c", "label": col_label, "kind": "col"},
		{"key": "pants_c", "label": "PANTS", "kind": "col"},
		{"key": "shoes_c", "label": "SHOES", "kind": "col"},
		{"key": "bag_c", "label": "BAG", "kind": "col"},
		{"key": "random", "label": "RANDOM", "kind": "act"},
		{"key": "done", "label": "DONE", "kind": "act"},
	]

func _palette(key: String) -> Array:
	match key:
		"hair_c": return PlayerLook.HAIR_COL
		"skin_c": return PlayerLook.SKIN
		"iris_c": return PlayerLook.EYE_COL
		"hat_c": return PlayerLook.HAT_COL
		"shirt_c": return PlayerLook.COAT_COL if look.outfit == "coat_pants" else PlayerLook.SHIRT_COL
		"pants_c": return PlayerLook.PANTS_COL
		"shoes_c": return PlayerLook.SHOES_COL
		"bag_c": return PlayerLook.BAG_COL
	return []

func _color_slot(key: String) -> String:
	return {"hair_c": "hair", "skin_c": "skin", "iris_c": "iris", "hat_c": "hat",
			"shirt_c": "coat" if look.outfit == "coat_pants" else "shirt", "pants_c": "pants", "shoes_c": "shoes", "bag_c": "bag"}.get(key, "")

func _opt_values(key: String) -> Array:
	match key:
		"gender": return PlayerLook.GENDERS
		"hair": return PlayerLook.HAIRS
		"eyes": return PlayerLook.EYES
		"hat": return PlayerLook.HATS
		"outfit": return PlayerLook.OUTFITS
	return []

func _opt_names(key: String) -> Array:
	match key:
		"gender": return PlayerLook.GENDER_NAMES
		"hair": return PlayerLook.HAIR_NAMES
		"eyes": return PlayerLook.EYE_NAMES
		"hat": return PlayerLook.HAT_NAMES
		"outfit": return PlayerLook.OUTFIT_NAMES
	return []

func _opt_get(key: String) -> String:
	match key:
		"gender": return look.gender
		"hair": return look.hair
		"eyes": return look.eyes
		"hat": return look.hat
		"outfit": return look.outfit
	return ""

func _opt_set(key: String, v: String) -> void:
	match key:
		"gender": look.set_gender(v)
		"hair": look.hair = v
		"eyes": look.eyes = v
		"hat": look.hat = v
		"outfit": look.outfit = v

## Steps the value of the selected row by `d` (-1 / +1).  Returns true if the look changed.
func step_value(d: int) -> bool:
	var r: Dictionary = rows()[row]
	match r["kind"]:
		"opt":
			var vals: Array = _opt_values(r["key"])
			var i := vals.find(_opt_get(r["key"]))
			_opt_set(r["key"], vals[posmod(i + d, vals.size())])
			return true
		"col":
			var pal: Array = _palette(r["key"])
			var slot := _color_slot(r["key"])
			var i2 := pal.find(look.colors.get(slot, ""))
			look.colors[slot] = pal[posmod(i2 + d, pal.size())]
			return true
	return false

func move(d: int) -> void:
	var rs := rows()
	for k in rs.size():
		row = posmod(row + d, rs.size())
		if not rs[row].get("off", false):
			break
	UI.sfx("cursor")

func _input_event(e: InputEvent) -> bool:
	if pressed(e, "move_up", true):
		move(-1)
	elif pressed(e, "move_down", true):
		move(1)
	elif pressed(e, "move_left", true) or pressed(e, "move_right", true):
		var d := -1 if pressed(e, "move_left", true) else 1
		if step_value(d):
			UI.sfx("cursor")
			_rebuild()
	elif pressed(e, "confirm"):
		var key: String = rows()[row]["key"]
		if key == "done":
			UI.sfx("select")
			finished.emit(look)
		elif key == "random":
			var g := PlayerLook.random(_rng)
			look = g
			UI.sfx("select")
			_rebuild()
		else:
			if step_value(1):
				UI.sfx("cursor")
				_rebuild()
	else:
		return false
	return true

func _tick() -> void:
	_clip_t += 1.0 / 60.0
	_bump = maxf(0.0, _bump - 0.05)
	if _clip_t > 3.2:
		_clip_t = 0.0
		_clip_i = (_clip_i + 1) % PREVIEW_CLIPS.size()
		_view.play_clip(PREVIEW_CLIPS[_clip_i])
	queue_redraw()

func _draw() -> void:
	Px.menu_bg(self, Color("#f8e0a0"), Color("#f0d488"), t)
	Px.frame(self, 4, 4, 148, 172, "red")
	Px.text_c(self, "YOUR LOOK", 78, 10, Color("#c04040"))
	_view.draw_at(self, 22, 26 - roundf(_bump * 3.0))
	var clip: String = PREVIEW_CLIPS[_clip_i]
	Px.small(self, clip.to_upper(), 12, 166, Px.mix(Color("#8a7a60"), Color("#c04040"), _bump))
	Px.frame(self, 156, 4, 160, 172)
	var rs := rows()
	for i in rs.size():
		var r: Dictionary = rs[i]
		var y := 10 + i * 11
		var off: bool = r.get("off", false)
		var ink := Color("#a0a0a8") if off else Px.INK
		if i == row:
			Px.rect(self, 160, y - 2, 152, 11, Color("#f8e0c0"))
			Px.cursor(self, 162, y, t)
		Px.small(self, r["label"], 170, y, ink)
		match r["kind"]:
			"opt":
				var vals: Array = _opt_values(r["key"])
				var names: Array = _opt_names(r["key"])
				var nm: String = names[maxi(0, vals.find(_opt_get(r["key"])))]
				var w := Px.measure_small(nm)
				Px.small(self, nm, 296 - w, y, ink)
				if i == row:
					_arrow(296 - w - 7, y + 2, -1)
					_arrow(301, y + 2, 1)
			"col":
				var c := Color(look.colors.get(_color_slot(r["key"]), "#888888"))
				if off:
					c = c.darkened(0.3)
					c.a = 0.4
				Px.rect(self, 268, y, 30, 8, Px.OUTLINE)
				Px.rect(self, 269, y + 1, 28, 6, c)
				if i == row:
					_arrow(261, y + 1, -1)
					_arrow(302, y + 1, 1)

## Small triangle arrow (the pixel font has no < >): dir -1 points left, +1 right.
func _arrow(x: float, y: float, dir: int) -> void:
	for i in 3:
		var h := 1 + i * 2
		var cx := x + (2 - i if dir < 0 else i)
		Px.rect(self, cx, y + 3 - i, 1, h, Px.INK)
