class_name GameText
extends RefCounted
## Upstream's text tables (G.TEXT / G.DEX_TEXT, extracted by
## pipeline/scripts/extract_text.js into godot/data/text.json), keyed exactly
## like upstream: pokered text labels without the leading underscore.
##   GameText.get_text("PalletTownGirlText")  -> raw string ('\f' page breaks,
##                                                {PLAYER}/{RIVAL} unresolved)
##   GameText.text_for(label)                  -> upstream G.textFor(): '...' if missing
##   GameText.dex("CHARIZARD")                 -> Pokédex flavour text
##   GameText.labels_in("maps_a")              -> labels defined in that source file

const PATH := "res://data/text.json"

static var _data: Dictionary = {}

static func data() -> Dictionary:
	if _data.is_empty():
		var f := FileAccess.open(PATH, FileAccess.READ)
		if f:
			var parsed = JSON.parse_string(f.get_as_text())
			if parsed is Dictionary:
				_data = parsed
		if _data.is_empty():
			_data = {"text": {}, "dex": {}, "aliases": {}, "files": {}}
	return _data

static func has(label: String) -> bool:
	return data()["text"].has(label.trim_prefix("_"))

static func get_text(label: String, fallback: String = "") -> String:
	var t: Dictionary = data()["text"]
	var key := label.trim_prefix("_")
	if t.has(key):
		return t[key]
	var al: Dictionary = data()["aliases"]
	if al.has(key) and t.has(al[key]):
		return t[al[key]]
	return fallback

static func text_for(label: String) -> String:
	if label == "":
		return "..."
	return get_text(label, "...")

static func dex(species: String) -> String:
	return data()["dex"].get(species, "")

static func labels_in(file: String) -> Array:
	return data()["files"].get(file, [])
