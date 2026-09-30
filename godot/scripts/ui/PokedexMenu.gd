class_name PokedexMenu
extends PxScreen
## Port of menus.js pokedex(): red stripes, the 8-row numbered list with a
## Poké Ball on owned species and "----------" for unseen ones, the portrait
## panel (the species' real 3D model where upstream blits its sprite, "?" if
## unseen) and SEEN/OWN counts. A on a seen species opens its dex page
## (dexPage(): name, category, HT/WT, types, real Pokédex text).

var sel := 0
var top := 0
var page_species := ""
var area_species := ""     # POKeDEX > AREA: the species whose habitats are listed
var area_top := 0
var _view: PxView3D
var _page_view: PxView3D

func _ready() -> void:
	super()
	_view = PxView3D.new(64, 64)
	add_child(_view)
	_page_view = PxView3D.new(64, 64)
	add_child(_page_view)

func _on_open() -> void:
	page_species = ""
	area_species = ""

func species_at(n: int) -> String:
	return GameData.dex_order[n] if n > 0 and n < GameData.dex_order.size() and GameData.dex_order[n] != null else ""

func _input_event(e: InputEvent) -> bool:
	if area_species != "":
		var n := GameData.habitats(area_species).size()
		if pressed(e, "move_down", true):
			area_top = mini(maxi(0, n - 8), area_top + 1)
		elif pressed(e, "move_up", true):
			area_top = maxi(0, area_top - 1)
		elif pressed(e, "confirm") or pressed(e, "cancel"):
			area_species = ""
		else:
			return false
		return true
	if page_species != "":
		if pressed(e, "confirm") or pressed(e, "cancel"):
			page_species = ""
			return true
		return false
	if pressed(e, "move_up", true):
		sel = maxi(0, sel - 1)
	elif pressed(e, "move_down", true):
		sel = mini(150, sel + 1)
	elif pressed(e, "move_left", true):
		sel = maxi(0, sel - 7)
	elif pressed(e, "move_right", true):
		sel = mini(150, sel + 7)
	elif pressed(e, "cancel"):
		exit()
		return true
	elif pressed(e, "confirm"):
		var sp := species_at(sel + 1)
		if GameState.seen_species.has(sp):
			_species_menu(sp)
		return true
	else:
		return false
	if sel < top:
		top = sel
	if sel > top + 7:
		top = sel - 7
	return true

## DATA / CRY / AREA / QUIT, like the cartridge's POKeDEX menu.
func _species_menu(sp: String) -> void:
	var r := await choose(["DATA", "CRY", "AREA", "QUIT"], {"x": 226, "y": 8, "w": 88})
	match r:
		0:
			page_species = sp
		1:
			Audio.cry(sp)
		2:
			area_species = sp
			area_top = 0

func _draw_area(sp: String) -> void:
	Px.menu_bg(self, Color("#e8e0c8"), Color("#dcd2b8"), t)
	Px.frame(self, 4, 4, 312, 172, "red")
	var d := GameData.get_species(sp)
	Px.text(self, "%s's AREA" % str(d.get("name", sp)), 16, 12)
	var places: Array = GameData.habitats(sp)
	if places.is_empty():
		Px.text(self, "AREA UNKNOWN", 16, 48)
		Px.small(self, "(%s VERSION: not found in the wild)" % GameState.version, 16, 68, Px.INK)
		return
	for i in 8:
		if area_top + i >= places.size():
			break
		Px.text(self, str(places[area_top + i]), 24, 34 + i * 16)
	if area_top > 0:
		Px.text(self, "▲", 296, 30, Px.RED, Color(0, 0, 0, 0))
	if area_top + 8 < places.size():
		Px.text(self, "▼", 296, 156, Px.RED, Color(0, 0, 0, 0))
	Px.small(self, "%s VERSION" % GameState.version, 200, 164, GameState.version_color(GameState.version).darkened(0.2))

func _draw() -> void:
	if area_species != "":
		_draw_area(area_species)
		return
	if page_species != "":
		_draw_page(page_species)
		return
	Px.menu_bg(self, Color("#d84848"), Color("#c83838"), 0)
	Px.frame(self, 4, 4, 180, 172, "red")
	for i in 8:
		var n := top + i + 1
		if n > 151:
			break
		var sp := species_at(n)
		var seen := GameState.seen_species.has(sp)
		var caught := GameState.caught_species.has(sp)
		var y := 12 + i * 20
		if n - 1 == sel:
			Px.rect(self, 9, y - 3, 170, 18, Color("#f8e0c0"))
		Px.small(self, "%03d" % n, 24, y + 3, Px.INK)
		if caught:
			Px.draw_ball(self, 46, y + 5)
		Px.text(self, GameData.get_species(sp).get("name", sp) if seen else "----------", 56, y)
	var cur := species_at(sel + 1)
	Px.frame(self, 188, 4, 128, 110)
	if GameState.seen_species.has(cur):
		_view.show_mon(cur)
		_view.draw_at(self, 220, 20 + roundf(sin(t / 20.0)))
	else:
		Px.text(self, "?", 250, 50)
	Px.frame(self, 188, 116, 128, 60)
	Px.text(self, "SEEN  %d" % GameState.seen_species.size(), 200, 126)
	Px.text(self, "OWN   %d" % GameState.caught_species.size(), 200, 144)

func _draw_page(sp: String) -> void:
	var d := GameData.get_species(sp)
	var caught := GameState.caught_species.has(sp)
	Px.menu_bg(self, Color("#e8e0c8"), Color("#dcd2b8"), t)
	Px.frame(self, 4, 4, 312, 100, "red")
	_page_view.show_mon(sp)
	_page_view.draw_at(self, 16, 22)
	Px.text(self, "No.%03d  %s" % [int(d.get("dex", 0)), d.get("name", sp)], 100, 16)
	Px.text(self, "%s POKéMON" % d.get("cat", "???"), 100, 34)
	if caught:
		var ht: Array = d.get("ht", [0, 0])
		Px.text(self, "HT  %d'%02d\"" % [int(ht[0]), int(ht[1]) if ht.size() > 1 else 0], 100, 54)
		Px.text(self, "WT  %.1f lb" % (float(d.get("wt", 0)) / 10.0), 100, 70)
	var types: Array = d.get("types", [])
	for i in types.size():
		var c := Px.type_color(types[i])
		Px.rect(self, 220 + i * 46, 54, 42, 12, Px.OUTLINE)
		Px.rect(self, 221 + i * 46, 55, 40, 10, c)
		Px.text(self, Px.type_name(types[i]), 223 + i * 46, 56, Px.WHITE, Px.shade(c, -0.4))
	Px.frame(self, 4, 106, 312, 70)
	var txt := GameText.dex(sp) if caught else "No further data. Catch this POKéMON to learn more."
	var lines := Px.wrap_text(txt, 290)
	for i in mini(4, lines.size()):
		Px.text(self, lines[i], 14, 114 + i * 14)
