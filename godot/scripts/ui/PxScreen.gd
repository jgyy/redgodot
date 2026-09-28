class_name PxScreen
extends PxCanvas
## Base for every menu/screen port: a PxCanvas with upstream's frame counter
## `t` (60 fps), open/close, an input guard while a popup owns the keyboard,
## and awaitable popups mirroring upstream's generator helpers:
##   var r := await choose(["YES", "NO"], {"x": 262, "y": 84})   # G.choose
##   await say("Hello!")                                         # G.say
##   if await ask("Save the game?"): ...                         # G.ask
## Popups are added as later siblings, so they draw on top and get input first.

signal closed

var t := 0
var busy := false
var _time := 0.0

func _init() -> void:
	super()
	visible = false
	clip_contents = true

func open() -> void:
	visible = true
	busy = false
	_time = 0.0
	t = 0
	_on_open()
	queue_redraw()

## Hides without notifying (used when another screen takes over).
func close() -> void:
	visible = false

## Hides and emits `closed` (the player backed out).
func exit() -> void:
	close()
	closed.emit()

func _on_open() -> void:
	pass

func _process(dt: float) -> void:
	if visible:
		_time += dt
		t = int(_time * 60.0)
		_tick()
	super(dt)

## Per-frame logic hook (upstream update()).
func _tick() -> void:
	pass

func _unhandled_input(event: InputEvent) -> void:
	if not visible or busy or not (event is InputEventKey or event is InputEventJoypadButton or event is InputEventAction):
		return
	if not event.is_pressed():
		return
	if _input_event(event):
		_accept_input()

## Return true when the event was consumed. Override in screens.
func _input_event(_event: InputEvent) -> bool:
	return false

static func pressed(event: InputEvent, action: String, repeat: bool = false) -> bool:
	return event.is_action_pressed(action, repeat)

# ---------------------------------------------------------------- popups
func _host() -> Node:
	return get_parent() if get_parent() else self

func choose(items: Array, opts: Dictionary = {}) -> int:
	busy = true
	var r: int = await PxMenu.pick(_host(), items, opts)
	busy = false
	return r

func say(text: String, opts: Dictionary = {}) -> void:
	busy = true
	await DialogueBox.say(_host(), text, opts)
	busy = false

func ask(text: String, opts: Dictionary = {}) -> bool:
	busy = true
	var r: bool = await DialogueBox.ask(_host(), text, opts)
	busy = false
	return r

func _accept_input() -> void:
	var vp := get_viewport()
	if vp:
		vp.set_input_as_handled()
