class_name DialogueBox
extends PxCanvas
## Port of ui.js TextBox: upstream's framed box at (6,128,308,48), typewriter
## reveal at the TEXT SPEED option (1-3 chars/frame, 4 while A/B is held),
## two lines per page ('\f' forces a page), red bobbing ▼ when a page is done.
##
## Public API (kept compatible with the old Label-based box):
##   show_lines(["Line one.", "Line two."])  each entry is one TextBox (may page)
##   signal finished                          after the last page is dismissed
##   visible                                  true while on screen
## Extra: show_lines(lines, {"no_wait": true}) reveals the last page and emits
## `finished` without waiting (the box stays up until close()), as used by ask().
## Static helpers: await DialogueBox.say(host, text); await DialogueBox.ask(host, text).

signal finished

var _queue: Array = []
var _pages: Array = []
var _page := 0
var _chars := 0.0
var _opts: Dictionary = {}
var _time := 0.0
var _frames := 0
var _done := false

static func say(host: Node, text: String, opts: Dictionary = {}) -> void:
	var box := DialogueBox.new()
	host.add_child(box)
	box.show_lines([text], opts)
	if box.visible and not box._done:
		await box.finished
	box.queue_free()

## Question box + YES/NO menu (ui.js ask()); the question stays visible.
static func ask(host: Node, text: String, opts: Dictionary = {}) -> bool:
	var box := DialogueBox.new()
	host.add_child(box)
	box.show_lines([text], {"no_wait": true})
	if not box._done:
		await box.finished
	var mo := {"x": 320 - 58, "y": Px.BOX.position.y - 44, "w": 52}
	mo.merge(opts, true)
	var r: int = await PxMenu.pick(host, ["YES", "NO"], mo)
	box.queue_free()
	return r == 0

func _init() -> void:
	super()
	visible = false

func show_lines(lines: Array, opts: Dictionary = {}) -> void:
	_queue = lines.duplicate()
	_opts = opts
	_done = false
	if _queue.is_empty():
		return
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_next_box()

func revealed() -> bool:
	return _done

func _next_box() -> void:
	var s: String = str(_queue.pop_front())
	_pages = Px.paginate(GameText.fmt(s))
	if _pages.is_empty():
		_pages = [[""]]
	_page = 0
	_chars = 0.0
	_frames = 0

func _total() -> int:
	return "\n".join(PackedStringArray(_pages[_page])).length()

func _speed() -> float:
	return float(GameState.text_speed_chars())

func _last() -> bool:
	return _queue.is_empty() and _page == _pages.size() - 1

func _process(dt: float) -> void:
	if not visible or _pages.is_empty():
		return
	_time += dt
	var target := int(_time * 60.0)
	while _frames < target:
		_frames += 1
		_step_frame()
	super(dt)

func _step_frame() -> void:
	var tot := _total()
	if _chars < tot:
		var fast := Input.is_action_pressed("confirm") or Input.is_action_pressed("cancel")
		_chars = minf(tot, _chars + (4.0 if fast else _speed()))
		if _chars >= tot and _opts.get("no_wait", false) and _last() and not _done:
			_done = true
			finished.emit()

## Instantly reveals the current page (screenshots / tests).
func reveal_all() -> void:
	if not _pages.is_empty():
		_chars = _total()

func _unhandled_input(event: InputEvent) -> void:
	if not visible or _pages.is_empty() or not event.is_pressed():
		return
	if not (event.is_action_pressed("confirm") or event.is_action_pressed("cancel")):
		return
	_accept_input()
	if _opts.get("no_wait", false) and _last():
		return
	if _chars < _total():
		return
	UI.sfx("blip")
	if _page < _pages.size() - 1:
		_page += 1
		_chars = 0.0
	elif not _queue.is_empty():
		_next_box()
	else:
		_close()

func close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _close() -> void:
	close()
	_done = true
	finished.emit()

func _draw() -> void:
	if _pages.is_empty():
		return
	var tf := _frames
	var show_prompt: bool = _chars >= _total() and not (_opts.get("no_wait", false) and _last())
	Px.text_box(self, _pages[_page], int(_chars), show_prompt, tf, _opts.get("theme", ""))

func _accept_input() -> void:
	var vp := get_viewport()
	if vp:
		vp.set_input_as_handled()
