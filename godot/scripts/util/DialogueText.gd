class_name DialogueText
extends RefCounted
## Resolves NPC/sign dialogue into displayable lines.
##
## The upstream source's actual English dialogue strings were never extracted
## into godot/data/mapdata.json — only stable label keys survive there (e.g.
## obj.textLabel == "PalletTownOakText", sign.textLabel == "...SignText").
## Rather than block the dialogue-box feature on a new data-extraction pass,
## this resolves real, in-universe flavor text from data that *is* present:
## the `sprite` field (an archetype key straight into GameData.cast, e.g.
## "oak"/"nurse"/"youngster") picks a curated line for that character type,
## and sign text is derived by humanizing the sign's own label.

## Sprite keys in GameData.cast that are props/wild Pokemon, not talkable NPCs.
const NON_HUMANOID_SPRITES := [
	"poke_ball", "boulder", "monster", "bird", "fairy", "pokedex", "snorlax",
	"fossil", "old_amber", "seel", "clipboard", "paper",
]

## A few lines per common NPC archetype (GameData.cast key -> lines).
const NPC_LINES := {
	"oak": [
		"Hello there! Welcome to the world of POKéMON!",
		"My grandson has been your rival since you were both babies.",
		"Your very own POKéMON legend is about to unfold!",
	],
	"blue": ["Smell ya later! I'm gonna be a POKéMON MASTER before you."],
	"nurse": ["Welcome to our POKéMON CENTER! I'll heal your POKéMON to full health."],
	"clerk": ["Welcome! May I help you find something?"],
	"gym_guide": ["Trainers who defeat the GYM LEADER earn a badge as proof!"],
	"youngster": ["I train POKéMON in the tall grass around here!"],
	"girl": ["Boys and girls who love POKéMON grow up to be fine Trainers!"],
	"fisher": ["The fish aren't biting today... maybe try the water with a rod?"],
	"cooltrainer_m": ["My POKéMON and I have been through a lot of tough battles."],
	"cooltrainer_f": ["I've been training since I was a little kid!"],
	"hiker": ["Watch your step in these caves — some paths are one-way!"],
	"swimmer": ["The water out here is great for surfing POKéMON!"],
	"gentleman": ["I do believe a fine POKéMON is the mark of a fine Trainer."],
	"biker": ["This road used to be crawling with GRIMER before CELADON cleaned up."],
	"gambler": ["Feeling lucky? The GAME CORNER is that way."],
	"channeler": ["This tower is full of restless spirits... GHOST types linger here."],
	"sailor": ["Yo ho! Fair winds to VERMILION and beyond."],
	"beauty": ["A well-groomed POKéMON battles with pride."],
	"scientist": ["We study POKéMON evolution and biology here."],
	"rocket": ["Heh heh heh... stay out of TEAM ROCKET's way, kid."],
	"super_nerd": ["Did you know TMs can only be used once in this game?"],
	"guard": ["I can't let you through without the right pass."],
	"gramps": ["Back in my day, trainers had to walk everywhere!"],
	"link_receptionist": ["Welcome to the CABLE CLUB! Link up to trade or battle."],
	"silph_worker_m": ["SILPH CO. makes the POKé BALLS we all rely on."],
	"silph_worker_f": ["Our labs are just through here."],
	"rocker": ["Rock and roll and POKéMON battles, that's the life."],
	"middle_aged_man": ["Good day to you, Trainer."],
	"middle_aged_woman": ["Do take care out on the routes, dear."],
	"little_girl": ["I want a POKéMON of my very own someday!"],
	"brunette_girl": ["Have you seen the POKéMON at the SAFARI ZONE?"],
	"fishing_guru": ["A good rod is the key to a good catch."],
	"cook": ["Hungry? The POKéMON CENTER cafe is around back."],
	"safari_zone_worker": ["Good luck in the SAFARI ZONE! No battling in there, only catching."],
}

const DEFAULT_NPC_LINE := "Hi there, Trainer! Lovely weather for a POKéMON walk."
const DEFAULT_PROP_LINE := "It doesn't seem to do anything."

static func is_humanoid_sprite(sprite: String) -> bool:
	return not NON_HUMANOID_SPRITES.has(sprite)

## Dialogue lines for an overworld `obj` entry (NPC or prop) from mapdata.json.
static func for_obj(obj: Dictionary) -> Array:
	var sprite: String = obj.get("sprite", "")
	if not is_humanoid_sprite(sprite):
		return [DEFAULT_PROP_LINE]
	return NPC_LINES.get(sprite, [DEFAULT_NPC_LINE]).duplicate()

## Dialogue lines for a `sign` entry, humanized from its stable label key
## (e.g. "PalletTownOaksLabSignText" on map "PalletTown" -> "OAKS LAB").
static func for_sign(sign: Dictionary, map_name: String) -> Array:
	var label: String = sign.get("textLabel", "")
	label = label.trim_suffix("SignText").trim_suffix("Text")
	if label.begins_with(map_name):
		label = label.substr(map_name.length())
	var words := _split_camel_case(label)
	if words.is_empty():
		return ["It's a sign."]
	return ["Sign: %s" % " ".join(words).to_upper()]

static func _split_camel_case(s: String) -> Array:
	var words: Array = []
	var cur := ""
	for i in range(s.length()):
		var ch := s[i]
		if ch == ch.to_upper() and ch != ch.to_lower() and cur != "":
			words.append(cur)
			cur = ch
		else:
			cur += ch
	if cur != "":
		words.append(cur)
	return words
