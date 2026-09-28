class_name BagMenu
extends PxScreen
## Port of bag.js BagScreen: orange stripes, the red-framed bag illustration
## (drawBagArt, pixel-for-pixel) labelled ITEMS, the 7-row item list with
## ×quantities and scroll arrows, and the grey description box. A opens
## USE / TOSS / CANCEL (bag.js G.bagScreen); USE runs the field effect
## (healing/cure/revive on a party target, TOWN MAP) like G.useItemField.

signal item_selected(item_id: String)

const KEY := ["TOWN_MAP", "BICYCLE", "SURFBOARD", "POKEDEX", "OLD_AMBER", "DOME_FOSSIL", "HELIX_FOSSIL", "SECRET_KEY",
	"BIKE_VOUCHER", "CARD_KEY", "S_S_TICKET", "GOLD_TEETH", "COIN_CASE", "OAKS_PARCEL", "ITEMFINDER", "SILPH_SCOPE",
	"POKE_FLUTE", "LIFT_KEY", "EXP_ALL", "OLD_ROD", "GOOD_ROD", "SUPER_ROD"]
const HEAL := {"POTION": 20, "SUPER_POTION": 50, "HYPER_POTION": 200, "MAX_POTION": 9999, "FULL_RESTORE": 9999,
	"FRESH_WATER": 50, "SODA_POP": 60, "LEMONADE": 80}
const CURE := {"ANTIDOTE": ["PSN"], "BURN_HEAL": ["BRN"], "ICE_HEAL": ["FRZ"], "AWAKENING": ["SLP"], "PARLYZ_HEAL": ["PAR"],
	"FULL_HEAL": ["PSN", "BRN", "FRZ", "SLP", "PAR"], "FULL_RESTORE": ["PSN", "BRN", "FRZ", "SLP", "PAR"]}
const DESC := {
	"POTION": "Restores 20 HP to one POKéMON.", "SUPER_POTION": "Restores 50 HP to one POKéMON.", "HYPER_POTION": "Restores 200 HP to one POKéMON.",
	"MAX_POTION": "Fully restores the HP of one POKéMON.", "FULL_RESTORE": "Fully restores HP and cures all status problems.", "ANTIDOTE": "Cures a poisoned POKéMON.",
	"BURN_HEAL": "Heals a burned POKéMON.", "ICE_HEAL": "Thaws a frozen POKéMON.", "AWAKENING": "Wakes up a sleeping POKéMON.", "PARLYZ_HEAL": "Cures paralysis.",
	"FULL_HEAL": "Cures any status problem.", "REVIVE": "Revives a fainted POKéMON with half its HP.", "MAX_REVIVE": "Revives a fainted POKéMON with full HP.",
	"POKE_BALL": "A device for catching wild POKéMON.", "GREAT_BALL": "A good BALL with a higher catch rate.", "ULTRA_BALL": "A very high-performance BALL.",
	"MASTER_BALL": "The ultimate BALL. It never fails.", "SAFARI_BALL": "A special BALL used only in the SAFARI ZONE.", "ESCAPE_ROPE": "Escape instantly from a cave or dungeon.",
	"REPEL": "Keeps weak wild POKéMON away for 100 steps.", "SUPER_REPEL": "Keeps weak wild POKéMON away for 200 steps.", "MAX_REPEL": "Keeps weak wild POKéMON away for 250 steps.",
	"RARE_CANDY": "Raises the level of a POKéMON by one.", "ETHER": "Restores 10 PP to one move.", "MAX_ETHER": "Fully restores the PP of one move.",
	"ELIXER": "Restores 10 PP to all moves.", "MAX_ELIXER": "Fully restores the PP of all moves.", "PP_UP": "Raises the max PP of one move.",
	"NUGGET": "A nugget of pure gold. Sells for a high price.", "POKE_DOLL": "An attractive doll. Lets you escape any wild battle.",
	"FRESH_WATER": "Mineral water. Restores 50 HP.", "SODA_POP": "A fizzy soda. Restores 60 HP.", "LEMONADE": "Very sweet. Restores 80 HP.",
	"BICYCLE": "A folding bike. Ride it for faster travel.", "TOWN_MAP": "A map of the KANTO region.", "ITEMFINDER": "Detects hidden items nearby.",
	"OLD_ROD": "An old fishing rod.", "GOOD_ROD": "A decent fishing rod.", "SUPER_ROD": "An excellent fishing rod.", "EXP_ALL": "Shares EXP. among all POKéMON in the party.",
	"POKE_FLUTE": "Its tune awakens sleeping POKéMON.", "COIN_CASE": "A case for holding GAME CORNER coins.", "SILPH_SCOPE": "Lets you see through ghostly disguises.",
}

var town_map: TownMap
var party_menu: PartyMenu
var sel := 0
var scroll := 0
var msg := ""
static var _art: Array = []

static func item_name(id: String) -> String:
	return GameData.items.get(id, {}).get("name", id.replace("_", " "))

static func is_key(id: String) -> bool:
	return KEY.has(id) or id.begins_with("HM_")

static func desc(id: String) -> String:
	if DESC.has(id):
		return DESC[id]
	var it: Dictionary = GameData.items.get(id, {})
	if it.has("move"):
		return "Teaches the move " + str(it["move"]).replace("_", " ") + " to a POKéMON."
	if id.ends_with("STONE"):
		return "A peculiar stone that makes certain POKéMON evolve."
	if id in ["HP_UP", "PROTEIN", "IRON", "CARBOS", "CALCIUM"]:
		return "A nutritious drink that raises a base stat."
	if id.begins_with("X_"):
		return "Raises a stat during battle."
	return "An item."

func list() -> Array:
	var l: Array = []
	for id in GameState.bag.keys():
		if int(GameState.bag[id]) > 0:
			l.append(id)
	l.append("CANCEL")
	return l

func _on_open() -> void:
	sel = 0
	scroll = 0
	msg = ""

func _input_event(e: InputEvent) -> bool:
	var l := list()
	if pressed(e, "move_up", true):
		sel = maxi(0, sel - 1)
	elif pressed(e, "move_down", true):
		sel = mini(l.size() - 1, sel + 1)
	elif pressed(e, "cancel"):
		exit()
		return true
	elif pressed(e, "confirm"):
		var id: String = l[sel]
		if id == "CANCEL":
			exit()
		else:
			item_selected.emit(id)
			_pick(id)
		return true
	else:
		return false
	if sel < scroll:
		scroll = sel
	if sel > scroll + 6:
		scroll = sel - 6
	return true

func _pick(id: String) -> void:
	var r := await choose(["USE", "TOSS", "CANCEL"], {"x": 250, "y": 60})
	if r == 0:
		await use_item_field(id)
	elif r == 1:
		if is_key(id):
			await bag_say("That's too important to toss!")
		elif await ask("Throw away " + item_name(id) + "?"):
			GameState.bag.erase(id)
			sel = mini(sel, list().size() - 1)

## bag.js BagScreen.say(): message in the description box until A/B.
func bag_say(text: String) -> void:
	busy = true
	msg = text
	await get_tree().process_frame
	while true:
		await get_tree().process_frame
		if Input.is_action_just_pressed("confirm") or Input.is_action_just_pressed("cancel"):
			break
	msg = ""
	busy = false

static func needs_target(id: String) -> bool:
	return HEAL.has(id) or CURE.has(id) or id in ["REVIVE", "MAX_REVIVE", "RARE_CANDY"]

func use_item_field(id: String) -> void:
	if needs_target(id) and party_menu:
		busy = true
		close()
		party_menu.open_with({"msg": "Use on which POKéMON?", "pick": func(m, _i, ps): return await BagMenu.apply_to_mon(id, m, ps)})
		await party_menu.picked
		visible = true
		busy = false
		return
	if id == "TOWN_MAP" and town_map:
		busy = true
		close()
		town_map.open()
		await town_map.closed
		visible = true
		busy = false
		return
	if id.ends_with("BALL") or id.begins_with("X_") or id in ["POKE_DOLL", "GUARD_SPEC", "DIRE_HIT"]:
		await bag_say("That can't be used now.")
		return
	await bag_say(Px.fmt("OAK: {PLAYER}! This isn't the time to use that!", GameState.player_name))

## bag.js applyToMon() (field subset): heal / cure / revive / RARE CANDY.
static func apply_to_mon(id: String, m: GameState.PartyMon, ps: PartyMenu) -> bool:
	var ok := false
	if HEAL.has(id) or CURE.has(id):
		var heals := HEAL.has(id) and m.hp < m.max_hp and m.hp > 0
		var cures := CURE.has(id) and m.status != "" and (CURE[id] as Array).has(m.status) and m.hp > 0
		if not heals and not cures:
			await ps.party_say("It won't have any effect.")
			return false
		var before := m.hp
		if heals:
			m.hp = mini(m.max_hp, m.hp + int(HEAL[id]))
		if cures:
			m.status = ""
		await ps.party_say((m.nickname + " recovered by %d!" % (m.hp - before)) if heals else (m.nickname + " was cured!"))
		ok = true
	elif id == "REVIVE" or id == "MAX_REVIVE":
		if m.hp > 0:
			await ps.party_say("It won't have any effect.")
			return false
		m.hp = m.max_hp / 2 if id == "REVIVE" else m.max_hp
		m.status = ""
		await ps.party_say(m.nickname + " is revitalized!")
		ok = true
	elif id == "RARE_CANDY":
		if m.level >= 100:
			await ps.party_say("It won't have any effect.")
			return false
		var frac := float(m.hp) / maxf(1.0, m.max_hp)
		m.level += 1
		m._recalc_stats()
		m.hp = int(round(m.max_hp * frac))
		await ps.party_say(m.nickname + " grew to level %d!" % m.level)
		ok = true
	if ok:
		GameState.bag[id] = int(GameState.bag.get(id, 1)) - 1
		if int(GameState.bag[id]) <= 0:
			GameState.bag.erase(id)
	return ok

func _draw() -> void:
	Px.menu_bg(self, Color("#e0a860"), Color("#d49850"), t)
	Px.frame(self, 4, 4, 104, 118, "red", Color("#f8e8c8"))
	var sway := int(roundf(sin(t / 30.0)))
	Px.blit(self, bag_art(sway), 56 - 24 + sway, 64 - 26)
	Px.text(self, "ITEMS", 38, 104)
	Px.frame(self, 112, 4, 204, 118)
	var l := list()
	for i in 7:
		if scroll + i >= l.size():
			break
		var id: String = l[scroll + i]
		var y := 12 + i * 15
		Px.text(self, "CANCEL" if id == "CANCEL" else item_name(id), 132, y)
		if id != "CANCEL" and not is_key(id):
			Px.text_r(self, "×%d" % int(GameState.bag[id]), 304, y)
		if scroll + i == sel:
			Px.cursor(self, 120, y, Px.frame_count())
	if scroll > 0:
		Px.text(self, "▲", 210, 5, Px.RED, Color(0, 0, 0, 0))
	if scroll + 7 < l.size():
		Px.text(self, "▼", 210, 114, Px.RED, Color(0, 0, 0, 0))
	Px.frame(self, 4, 124, 312, 52, "gray")
	var cur: String = l[clampi(sel, 0, l.size() - 1)]
	var txt := msg if msg != "" else ("Close the BAG." if cur == "CANCEL" else desc(cur))
	var lines := Px.wrap_text(txt, 290)
	for i in mini(2, lines.size()):
		Px.text(self, lines[i], 14, 134 + i * 15)

## bag.js drawBagArt() baked to a 49x51 texture (origin = art's top-left,
## i.e. (cx-24, cy-26)); cached (the sway is applied by the caller).
static func bag_art(_sway: int = 0) -> ImageTexture:
	if not _art.is_empty():
		return _art[0]
	var B := [Color("#6a3a1a"), Color("#8a5028"), Color("#b0703a"), Color("#d09050"), Color("#e8b070")]
	var img := Image.create(49, 51, false, Image.FORMAT_RGBA8)
	for y in range(-26, 25):
		for x in range(-24, 25):
			var w := 14.0 + (y + 26) * 0.4 if y < -14 else 24.0 - maxf(0.0, y - 14) * 0.6
			if absf(x) > w:
				continue
			var c: Color = B[2]
			if absf(x) > w - 2:
				c = B[0]
			elif x < -w * 0.5:
				c = B[3]
			elif x > w * 0.5:
				c = B[1]
			if y == -14 or y == -13:
				c = B[0]
			if y > -10 and y < 2 and absi(x) < 10:
				c = B[0] if (y == -9 or y == 1 or absi(x) == 9) else B[4]
			img.set_pixel(x + 24, y + 26, c)
	# s.disc(cx, cy - 4, 2.5, gold) (gfx ellipse scanlines)
	var ccx := 24.0
	var ccy := 22.0
	for yy in range(int(floor(ccy - 2.5)), int(ceil(ccy + 2.5)) + 1):
		var dy := (yy + 0.5 - ccy) / 2.5
		if absf(dy) > 1.0:
			continue
		var hw := 2.5 * sqrt(1.0 - dy * dy)
		for xx in range(int(round(ccx - hw)), int(round(ccx + hw))):
			img.set_pixel(xx, yy, Color("#e8c040"))
	var tex := ImageTexture.create_from_image(img)
	_art.append(tex)
	return tex
