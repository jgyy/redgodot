extends PxCanvas
## Visual self-test for the Px kit (Main.gd --scene=px_test): every frame
## theme, the text box, a menu and both fonts, at upstream coordinates.

func _draw() -> void:
	var t := Px.frame_count()
	Px.rect(self, 0, 0, Px.W, Px.H, Color("#5a6a8a"))
	var x := 4
	for th in Px.THEMES.keys():
		Px.frame(self, x, 4, 60, 30, th)
		Px.text(self, th, x + 8, 12)
		x += 63
	Px.menu(self, ["POKéDEX", "POKéMON", "ITEM", "RED", "SAVE", "OPTION", "EXIT"], 1, 230, 38, -1, -1, 0, t)
	Px.small(self, "Lv50 HP: 140/140 No.006", 10, 44, Px.INK)
	Px.text(self, "The quick brown fox jumps! 0123456789 ♂♀ $ …", 10, 56, Color.WHITE, Px.OUTLINE)
	Px.text_box(self, Px.paginate("Welcome to the world of POKéMON! Every pixel here was drawn by code.")[0], 999, true, 0)
