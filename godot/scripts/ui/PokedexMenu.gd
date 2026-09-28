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

func species_at(n: int) -> String:
	return GameData.dex_order[n] if n > 0 and n < GameData.dex_order.size() and GameData.dex_order[n] != null else ""

func _input_event(e: InputEvent) -> bool:
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
			page_species = sp
		return true
	else:
		return false
	if sel < top:
		top = sel
	if sel > top + 7:
		top = sel - 7
	return true

func _draw() -> void:
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
