class_name PxMenu
extends PxCanvas
## Port of ui.js Menu: a framed choice list with the blinking ▶ cursor,
## scrolling ▲/▼ arrows and upstream's default placement (right edge, just
## above the text box). Emits `done(index)` (-1 = cancelled).
##   var r: int = await PxMenu.pick(host, ["YES", "NO"], {"x": 262, "y": 84, "w": 52})
## opts: x, y, w, rows, sel, no_cancel, theme, on_move (Callable(sel)).

signal done(result: int)

var items: Array = []
var sel := 0
var top := 0
var rows := 1
var x := 0
var y := 0
var w := 0
var h := 0
var opts: Dictionary = {}
var finished := false
var _time := 0.0

static func pick(host: Node, list: Array, o: Dictionary = {}) -> int:
	var m := PxMenu.new()
	m.setup(list, o)
	host.add_child(m)
	var r: int = await m.done
	m.queue_free()
	return r

func setup(list: Array, o: Dictionary = {}) -> void:
	items = list
	opts = o
	sel = int(o.get("sel", 0))
	if o.has("w"):
		w = int(o["w"])
	else:
		var mw := 0
		for it in items:
			mw = maxi(mw, Px.measure(str(it)))
		w = mw + 30
	var room: int = (178 - int(o["y"])) if o.has("y") else Px.BOX.position.y - 4
	var want: int = int(o.get("rows", floori((room - 12) / 15.0)))
	rows = maxi(1, mini(items.size(), want))
	h = rows * 15 + 12
	x = int(o.get("x", 320 - w - 6))
	y = int(o.get("y", Px.BOX.position.y - h - 2))
	_follow()

func _follow() -> void:
	top = maxi(maxi(0, mini(mini(top, sel), items.size() - rows)), sel - rows + 1)

func _process(dt: float) -> void:
	_time += dt
	super(dt)

func _unhandled_input(event: InputEvent) -> void:
	if finished or not is_visible_in_tree() or not event.is_pressed():
		return
	var n := items.size()
	var handled := true
	if n == 0:
		if event.is_action_pressed("cancel") or event.is_action_pressed("confirm"):
			_finish(-1)
			_accept_input()
		return
	if event.is_action_pressed("move_up", true):
		sel = (sel + n - 1) % n
		UI.sfx("cursor")
	elif event.is_action_pressed("move_down", true):
		sel = (sel + 1) % n
		UI.sfx("cursor")
	elif event.is_action_pressed("confirm"):
		UI.sfx("select")
		_finish(sel)
	elif event.is_action_pressed("cancel"):
		if not opts.get("no_cancel", false):
			_finish(-1)
	else:
		handled = event is InputEventKey
	_follow()
	if opts.has("on_move") and not finished:
		(opts["on_move"] as Callable).call(sel)
	if handled:
		_accept_input()

func _finish(r: int) -> void:
	finished = true
	visible = false
	done.emit(r)

func _draw() -> void:
	var tf := int(_time * 60.0)
	var th: String = opts.get("theme", "")
	Px.frame(self, x, y, w, h, th)
	for k in rows:
		var i := top + k
		if i >= items.size():
			break
		Px.text(self, str(items[i]), x + 18, y + 8 + k * 15)
		if i == sel:
			Px.cursor(self, x + 8, y + 8 + k * 15, Px.frame_count())
	var ax := x + w - 14
	var blink := (tf / 20) % 2
	if top > 0:
		Px.text(self, "▲", ax, y + 3 + blink, Px.RED, Color(0, 0, 0, 0))
	if top + rows < items.size():
		Px.text(self, "▼", ax, y + h - 13 - blink, Px.RED, Color(0, 0, 0, 0))

func _accept_input() -> void:
	var vp := get_viewport()
	if vp:
		vp.set_input_as_handled()
