extends PxCanvas
## Story-owned pixel overlays drawn with upstream's exact coordinates:
##   money_early  early.js moneyBox()        (museum, Magikarp salesman, bike shop)
##   money_late   late.js moneyBoxScene()    (Safari Zone gate)
##   info         mid.js infoBox(lines)      (Game Corner coins / money, vending machine)
##   mon          Pokémon picture in a frame (Oak's lab balls, fossils, binoculars)
## and pc.js quantity() (the ×NN / $price picker used by the Poké Mart).
## Pokémon pictures come from UI.mon_picture(species) -> Texture2D when the UI
## provides it; otherwise the species name is printed inside the frame.

var _boxes: Dictionary = {}
var _next := 1
var _q_active := false
var _q := 1
var _q_max := 1
var _q_price := 0
var _q_result := -1
var _hold := 0.0

signal quantity_done(q: int)

func add_box(spec: Dictionary) -> int:
	var h := _next
	_next += 1
	_boxes[h] = spec
	queue_redraw()
	return h

func remove_box(h: int) -> void:
	_boxes.erase(h)
	queue_redraw()

func pick_quantity(mx: int, price: int) -> int:
	_q_active = true
	_q = 1
	_q_max = maxi(1, mx)
	_q_price = price
	queue_redraw()
	var r: int = await quantity_done
	_q_active = false
	queue_redraw()
	return r

func _process(dt: float) -> void:
	super._process(dt)
	if not _q_active:
		return
	var step := 0
	for pair in [["move_up", 1], ["move_down", -1], ["move_right", 10], ["move_left", -10]]:
		var a: String = pair[0]
		if not InputMap.has_action(a):
			continue
		if Input.is_action_just_pressed(a):
			step = pair[1]
			_hold = 0.0
		elif Input.is_action_pressed(a):
			_hold += dt
			if _hold > 0.35:
				_hold -= 0.08
				step = pair[1]
	if step == 1:
		_q = 1 if _q >= _q_max else _q + 1
	elif step == -1:
		_q = _q_max if _q <= 1 else _q - 1
	elif step == 10:
		_q = mini(_q_max, _q + 10)
	elif step == -10:
		_q = maxi(1, _q - 10)
	if InputMap.has_action("confirm") and Input.is_action_just_pressed("confirm"):
		quantity_done.emit(_q)
	elif InputMap.has_action("cancel") and Input.is_action_just_pressed("cancel"):
		quantity_done.emit(0)

func _draw() -> void:
	for h in _boxes:
		var b: Dictionary = _boxes[h]
		match str(b.get("kind", "")):
			"money_early":
				var tx := "$" + str(GameState.money)
				var w := maxi(90, Px.measure(tx) + 30)
				Px.frame(self, 316 - w, 4, w, 38, "gray")
				Px.text(self, "MONEY", 328 - w, 11)
				Px.text(self, tx, 304 - Px.measure(tx), 25)
			"money_late":
				var t2 := "$" + str(GameState.money)
				Px.frame(self, 214, 4, 100, 38)
				Px.text(self, "MONEY", 224, 11, Color("#8a7a60"))
				Px.text(self, t2, 304 - Px.measure(t2), 24)
			"info":
				var lines: Array = (b["lines"] as Callable).call()
				var mw := 0
				for l in lines:
					mw = maxi(mw, Px.measure(str(l)))
				var w2 := mw + 28
				var h2 := lines.size() * 15 + 14
				Px.frame(self, 320 - w2 - 4, 4, w2, h2)
				for i in lines.size():
					Px.text(self, str(lines[i]), 320 - w2 + 10, 11 + i * 15)
			"mon":
				var r: Rect2i = b["rect"]
				Px.frame(self, r.position.x, r.position.y, r.size.x, r.size.y)
				var sp := str(b.get("species", ""))
				var tex: Texture2D = null
				var ui := get_node_or_null("/root/UI")
				if ui and ui.has_method("mon_picture"):
					tex = ui.call("mon_picture", sp)
				if tex:
					var mod := Color("#b8a888") if b.get("fossil", false) else Color.WHITE
					draw_texture(tex, Vector2(r.position.x + (r.size.x - tex.get_width()) / 2.0, r.position.y + (r.size.y - tex.get_height()) / 2.0), mod)
				else:
					Px.text_c(self, Story.species_name(sp), r.position.x + r.size.x / 2.0, r.position.y + r.size.y / 2.0 - 6)
	if _q_active:
		var w3 := 130 if _q_price > 0 else 60
		Px.frame(self, 314 - w3, 104, w3, 22)
		Px.text(self, "×" + str(_q).pad_zeros(2), 324 - w3, 111)
		if _q_price > 0:
			var pt := "$" + str(_q * _q_price)
			Px.text(self, pt, 306 - Px.measure(pt), 111)
