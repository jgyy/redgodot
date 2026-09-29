class_name PikachuBuddy
extends RefCounted
## POKeMON YELLOW's partner PIKACHU: the friendship (happiness) value, what changes it, how it feels about you and what
## it says when you talk to it. Ported from pokeyellow engine/events/pikachu_happiness.asm (the HappinessChangeTable)
## and engine/pikachu/pikachu_emotions.asm; the value lives in GameState.pikachu_happiness (0..255, starts at 90).

## Happiness events, in pret's order (PIKAHAPPY_*): +[under 100, 100..199, 200+] or -[same].
const LEVEL_UP := 1
const HP_RESTORE := 2
const X_ITEM := 3
const GYM_LEADER := 4
const TM_HM := 5
const WALKING := 6
const DEPOSITED := 7
const FAINTED := 8
const POISON_FAINT := 9
const FAINTED_VS_STRONGER := 10
const TRADED_AWAY := 11
const TABLE := {
	LEVEL_UP: [5, 3, 2], HP_RESTORE: [5, 3, 2], X_ITEM: [1, 1, 0], GYM_LEADER: [3, 2, 1], TM_HM: [1, 1, 0], WALKING: [2, 1, 1],
	DEPOSITED: [-3, -3, -5], FAINTED: [-1, -1, -1], POISON_FAINT: [-5, -5, -10], FAINTED_VS_STRONGER: [-5, -5, -10],
	TRADED_AWAY: [-10, -10, -20],
}
## Events that count while PIKACHU is anywhere in the party (the rest need it to be the mon concerned).
const PARTY_WIDE := [GYM_LEADER, WALKING]
## Melanie (BULBASAUR) and Officer Jenny (SQUIRTLE) only trust a trainer whose PIKACHU is at least this fond of them.
const FRIENDLY := 147

## The PIKACHU Prof. Oak gave the player, if it is in the party.
static func buddy() -> GameState.PartyMon:
	for m in GameState.party:
		if m.buddy:
			return m
	return null

static func alive() -> bool:
	var b := buddy()
	return b != null and b.hp > 0

## Applies happiness event `kind`. `who` is the mon it happened to (null for party-wide events like walking).
static func event(kind: int, who: Object = null) -> void:
	if not GameState.is_yellow() or not TABLE.has(kind):
		return
	var b := buddy()
	if b == null:
		return
	if PARTY_WIDE.has(kind):
		if b.hp <= 0:
			return
	elif who != b:
		return
	var h := GameState.pikachu_happiness
	var band := 0 if h < 100 else (1 if h < 200 else 2)
	GameState.pikachu_happiness = clampi(h + int((TABLE[kind] as Array)[band]), 0, 255)

## 0 = cold .. 4 = devoted (drives the expression and the lines it has for you).
static func tier() -> int:
	var h := GameState.pikachu_happiness
	if h < 50:
		return 0
	if h < 100:
		return 1
	if h < 147:
		return 2
	if h < 200:
		return 3
	return 4

static func is_friendly() -> bool:
	return GameState.pikachu_happiness >= FRIENDLY

const TIER_NAMES := ["cold", "wary", "curious", "fond", "devoted"]

## What PIKACHU does when you talk to it: [text, emote]. It reacts to its mood first, then to where you are.
static func mood(m: GameState.PartyMon, map_name: String, in_grass: bool, rng: RandomNumberGenerator) -> Array:
	var n := m.display_name()
	var st := {"PSN": [n + " is shivering from the poison!", "..."], "BRN": [n + " is hurting from its burn.", "..."],
		"PAR": [n + " is paralyzed. It can barely move!", "..."], "SLP": [n + " is fast asleep... zzz", "..."],
		"FRZ": [n + " is frozen solid!", "..."]}
	if st.has(m.status):
		return st[m.status]
	if float(m.hp) / maxf(1.0, float(m.max_hp)) < 0.25:
		return [n + " looks exhausted... Maybe rest at a POKéMON CENTER?", "..."]
	var t := tier()
	var lines: Array = []
	match t:
		0:
			lines = [[n + " turns away from you and glares.", "..."], [n + " ignores you completely.", "!"],
				[n + " is sulking. It doesn't seem to trust you yet.", "..."]]
		1:
			lines = [[n + " looks at you warily.", "?"], [n + " keeps its distance.", "..."],
				[n + " isn't sure about you yet.", "?"]]
		2:
			lines = [[n + " sniffs around and glances at you.", "?"], [n + " is walking along beside you.", "..."],
				[n + " seems to be warming up to you.", "heart"]]
		3:
			lines = [[n + " is happy to be with you!", "heart"], [n + " nuzzles up against your leg.", "heart"],
				[n + " is beaming at you.", "heart"]]
		_:
			lines = [[n + " is overjoyed! It adores you!", "heart"], [n + " leaps into the air and cheers!", "!"],
				[n + " snuggles up to you happily.", "heart"]]
	if map_name.contains("Pokecenter"):
		lines.append([n + " looks relaxed here.", "heart"])
	if map_name.ends_with("Gym") and t >= 2:
		lines.append([n + " is fired up for a GYM battle!", "!"])
	if map_name.begins_with("PokemonTower"):
		lines.append([n + " is trembling... it senses something.", "..."])
	if in_grass and t >= 2:
		lines.append([n + " is rustling around in the tall grass!", "!"])
	if map_name == "PalletTown" and t >= 2:
		lines.append([n + " seems to like PALLET TOWN.", "heart"])
	return lines[rng.randi_range(0, lines.size() - 1)]

## Text for the trainer card / summary: how PIKACHU feels (Yellow shows it as a face; here it is a word).
static func mood_word() -> String:
	return TIER_NAMES[tier()]
