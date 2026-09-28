class_name NamingScreen
extends PxScreen
## Port of menus.js namingScreen(): blue stripes, the prompt box with the
## typed name and blinking "_", and the 9x7 letter grid with DEL / END.
## Arrows move, A types (or DEL/END), B deletes, START finishes; letters typed
## on a keyboard go straight in.  var n: String = await NamingScreen.ask_name(host, "YOUR NAME?", "RED")

signal named(name: String)

const ROWS := ["ABCDEFGHI", "JKLMNOPQR", "STUVWXYZ ", "abcdefghi", "jklmnopqr", "stuvwxyz ", "012345678"]

var prompt := "YOUR NAME?"
var default_name := "RED"
var max_len := 7
var cur := ""
var cx := 0
var cy := 0

static func ask_name(host: Node, p: String, def: String, mx: int = 7) -> String:
	var s := NamingScreen.new()
	s.prompt = p
	s.default_name = def
	s.max_len = mx
	host.add_child(s)
	s.open()
	var n: String = await s.named
	s.queue_free()
	return n

func _on_open() -> void:
	cur = ""
	cx = 0
	cy = 0

func _add(ch: String) -> void:
	if cur.length() < max_len:
		cur += ch
	if cur.length() >= max_len:
		cy = ROWS.size()
		cx = 5

func _finish() -> void:
	close()
	var n := cur.strip_edges()
	named.emit(n if n != "" else default_name)

func _input_event(e: InputEvent) -> bool:
	var nrows := ROWS.size()
	if e is InputEventKey and e.pressed and not e.echo and e.unicode > 32 and e.unicode < 127 \
			and not (e.is_action("confirm") or e.is_action("cancel") or e.is_action("menu")):
		_add(char(e.unicode))
		return true
	if pressed(e, "move_left", true):
		cx = (cx + 8) % 9
	elif pressed(e, "move_right", true):
		cx = (cx + 1) % 9
	elif pressed(e, "move_up", true):
		cy = (cy + nrows) % (nrows + 1)
	elif pressed(e, "move_down", true):
		cy = (cy + 1) % (nrows + 1)
	elif pressed(e, "menu"):
		_finish()
	elif pressed(e, "cancel"):
		cur = cur.substr(0, maxi(0, cur.length() - 1))
	elif pressed(e, "confirm"):
		if cy == nrows:
			if cx < 4:
				cur = cur.substr(0, maxi(0, cur.length() - 1))
			else:
				_finish()
		else:
			_add(ROWS[cy][cx])
	else:
		return false
	return true

func _draw() -> void:
	Px.menu_bg(self, Color("#6a9ae0"), Color("#5a88d0"), t)
	Px.frame(self, 20, 6, 280, 36)
	Px.text(self, prompt, 32, 12)
	Px.text(self, cur + ("_" if (t / 20) % 2 == 1 else ""), 32, 26, Color("#c04040"))
	Px.frame(self, 20, 44, 280, 132)
	for j in ROWS.size():
		var r: String = ROWS[j]
		for i in r.length():
			var x := 44 + i * 28
			var y := 54 + j * 15
			Px.text(self, r[i], x, y, Px.INK, Color("#d6d4cc"))
			if i == cx and j == cy:
				Px.cursor(self, x - 10, y, t)
	var yb := 54 + ROWS.size() * 15
	Px.text(self, "DEL", 60, yb)
	Px.text(self, "END", 200, yb)
	if cy == ROWS.size():
		Px.cursor(self, 50 if cx < 4 else 190, yb, t)
