extends Node
## Test double of the UI autoload contract: records every line said, answers
## ask/choose/quantity from scripted queues (defaults: YES / first item / 1).
## raw_text("SomeLabel") returns "[SomeLabel]" so tests can assert on text keys.

var said: Array = []
var asked: Array = []
var menus: Array = []
var answers: Array = []     # bools for ask()
var choices: Array = []     # ints for choose()
var quantities: Array = []  # ints for quantity()
var vars: Dictionary = {}

var _label := RegEx.create_from_string("^[A-Za-z][A-Za-z0-9_]*Text[0-9A-Za-z_]*$")

func raw_text(key: String) -> String:
	if _label.search(key) != null or key.begins_with("OakRating"):
		return "[" + key + "]"
	return ""

func text(key: String) -> String:
	var r := raw_text(key)
	return r if r != "" else "..."

func set_var(k: String, v: Variant) -> void:
	vars[k] = v

func say(t: String, _opts: Dictionary = {}) -> void:
	said.append(t)

func ask(t: String, _opts: Dictionary = {}) -> bool:
	asked.append(t)
	return bool(answers.pop_front()) if not answers.is_empty() else true

func choose(items: Array, _opts: Dictionary = {}) -> int:
	menus.append(items)
	return int(choices.pop_front()) if not choices.is_empty() else 0

func quantity(_mx: int, _price: int) -> int:
	return int(quantities.pop_front()) if not quantities.is_empty() else 1

func said_has(key: String) -> bool:
	for s in said:
		if str(s).contains(key):
			return true
	return false

func asked_has(key: String) -> bool:
	for s in asked:
		if str(s).contains(key):
			return true
	return false

func name_entry(_prompt: String, def: String, _max_len: int = 10) -> String:
	return def
