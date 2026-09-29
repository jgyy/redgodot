extends Node
## Autoload `UI`: upstream's ui.js dialogue/menu primitives over ANY scene
## (overworld, battle, title), drawn on a top CanvasLayer with the Px ports
## (DialogueBox = ui.js TextBox, PxMenu = ui.js Menu). Await them like
## upstream's generators:
##   await UI.say("Hello {PLAYER}!\fBye.")          # G.say  (typewriter, \f pages, ▼, A/B)
##   var yes: bool = await UI.ask("Heal?")           # G.ask  (question stays up + YES/NO)
##   var i: int = await UI.choose(["A", "B"], {"x": 6, "y": 6})   # G.choose (-1 = B)
##   UI.text("PalletTownGirlText")                   # G.textFor + G.fmt
##   await UI.open_pc()                              # pc.js usePC()
##   UI.sfx("cursor")                                # Audio autoload if present
## opts for say: {"no_wait": bool, "theme": "blue"|"red"|...};
## choose opts: x, y, w, rows, sel, no_cancel, theme, on_move (Callable(sel)).

const LAYER := 60

var layer: CanvasLayer
var _busy := 0
var _pc: PCMenu
## A no_wait text box stays up (ui.js StaticBox) until the next say/ask or
## until the menu that follows it closes, so "question + menu" flows (marts,
## menu_with_text) keep their text visible like upstream.
var _sticky: DialogueBox = null

func _drop_sticky() -> void:
	if is_instance_valid(_sticky):
		_sticky.queue_free()
	_sticky = null

func _ready() -> void:
	layer = CanvasLayer.new()
	layer.layer = LAYER
	layer.name = "UILayer"
	add_child(layer)

## True while a UI.say/ask/choose/open_pc is on screen (lock player input).
func is_busy() -> bool:
	return _busy > 0

func say(text: String, opts: Dictionary = {}) -> void:
	_busy += 1
	_drop_sticky()
	if opts.get("no_wait", false):
		var box := DialogueBox.new()
		layer.add_child(box)
		box.show_lines([text], opts)
		if box.visible and not box._done:
			await box.finished
		_sticky = box
	else:
		await DialogueBox.say(layer, text, opts)
	_busy -= 1

func ask(text: String, opts: Dictionary = {}) -> bool:
	_busy += 1
	_drop_sticky()
	var r: bool = await DialogueBox.ask(layer, text, opts)
	_busy -= 1
	return r

func choose(items: Array, opts: Dictionary = {}) -> int:
	_busy += 1
	var r: int = await PxMenu.pick(layer, items, opts)
	_drop_sticky()
	_busy -= 1
	return r

## Upstream text by label (G.textFor: '...' when unknown), G.fmt-substituted.
func text(key: String) -> String:
	return GameText.fmt(GameText.text_for(key))

## Raw upstream text ('' when unknown), unformatted (S.t / G.TEXT[key]).
func raw_text(key: String) -> String:
	return GameText.get_text(key)

## Sets an upstream G.textVars placeholder (e.g. "wStringBuffer").
func set_var(key: String, value: Variant) -> void:
	GameText.vars[key] = value

## Bill's PC / player's PC / Oak's rating (pc.js usePC()).
func open_pc() -> void:
	_busy += 1
	if _pc == null:
		_pc = PCMenu.new()
		layer.add_child(_pc)
		var pm := PartyMenu.new()
		layer.add_child(pm)
		_pc.party_menu = pm
	await _pc.use_pc()
	_busy -= 1

## The Audio autoload (or null when running without it).
func audio() -> Node:
	return get_node_or_null("/root/Audio")

func sfx(sfx_name: String) -> void:
	var a := audio()
	if a and a.has_method("sfx"):
		a.sfx(sfx_name)
