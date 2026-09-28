class_name DialogueText
extends RefCounted
## Resolves NPC/sign dialogue into DialogueBox entries using upstream's REAL
## text (godot/data/text.json, extracted from src/data/text/*.js by
## pipeline/scripts/extract_text.js), the same way upstream's scripts.js does:
##   talkTo(a):  item ball -> "<PLAYER> found <ITEM>!"
##               trainer   -> th.battle text (th.after once beaten)
##               otherwise -> G.textFor(obj.textLabel)  ('...' if unknown)
##   readSign(): G.textFor(sign.textLabel)
## Labels that upstream answers with a per-map script (story.js/src/scripts)
## fall back to the closest real text for that label (e.g. a gym leader's
## PreBattleText, the nurse's POKéMON CENTER welcome, the clerk's greeting)
## before '...'. Entries are raw upstream strings ('\f' page breaks,
## {PLAYER}/{RIVAL}); DialogueBox formats and paginates them.

const NON_HUMANOID_SPRITES := [
	"poke_ball", "boulder", "monster", "bird", "fairy", "pokedex", "snorlax",
	"fossil", "old_amber", "seel", "clipboard", "paper",
]

## Sprite -> generic upstream text label used when the object's own label is
## handled by a script upstream (pc.js nurseHeal / mart greetings etc.).
const SPRITE_FALLBACK := {
	"nurse": "PokemonCenterWelcomeText",
	"clerk": "PokemartGreetingText",
	"link_receptionist": "CableClubNPCWelcomeText",
}

## Upstream's scripted-label suffix variants, tried in order.
const VARIANTS := ["PreBattleText", "BeforeBattleText", "Text1", "GreetingText", "1Text", "WelcomeText"]

static func is_humanoid_sprite(sprite: String) -> bool:
	return not NON_HUMANOID_SPRITES.has(sprite)

## Text for a label, or "" when upstream has none (no '...' fallback).
static func lookup(label: String) -> String:
	if label == "":
		return ""
	var s := GameText.get_text(label)
	if s != "":
		return s
	var stem := label.trim_suffix("Text")
	for v in VARIANTS:
		s = GameText.get_text(stem + v)
		if s != "":
			return s
	# a scripted object's texts share its label stem (e.g. BikeShopYoungster... )
	var keys: Array = GameText.data()["text"].keys()
	for k: String in keys:
		if k.begins_with(stem) and k.ends_with("Text") and GameText.get_text(k) != "":
			return GameText.get_text(k)
	return ""

## Dialogue entries for an overworld `obj` entry (NPC or prop) from mapdata.json.
static func for_obj(obj: Dictionary, beaten: bool = false) -> Array:
	if obj.has("item"):
		var id: String = obj["item"]
		var nm: String = GameData.items.get(id, {}).get("name", id.replace("_", " "))
		return ["{PLAYER} found %s!" % nm]
	var th: Dictionary = obj.get("th", {})
	if not th.is_empty():
		var s := GameText.get_text(th.get("after" if beaten else "battle", ""))
		if s != "":
			return [s]
	var line := lookup(obj.get("textLabel", ""))
	if line == "":
		line = GameText.get_text(SPRITE_FALLBACK.get(obj.get("sprite", ""), ""))
	return [line if line != "" else "..."]

## Dialogue entries for a `sign` entry.
static func for_sign(sign: Dictionary, _map_name: String = "") -> Array:
	var line := lookup(sign.get("textLabel", ""))
	return [line if line != "" else "..."]
