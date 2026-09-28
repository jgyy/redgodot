class_name SummaryScreen
extends PxScreen
## Port of party.js Summary: beige stripes, INFO/STATS/MOVES tabs at the top
## right, the blue portrait panel (dex number, name, level, type badges) with
## the species' real 3D model where upstream blits its sprite, the right-hand
## data panel per tab, and the grey bottom panel with the real Pokédex text
## (upstream DEX_TEXT via godot/data/text.json) or the selected move's info.
## Left/right: tab; up/down: previous/next party member (move cursor on MOVES).

const TABS := ["INFO", "STATS", "MOVES"]
const LABEL := Color("#7a7a90")

var page := 0
var idx := 0
var msel := 0
var _view: PxView3D

func _ready() -> void:
	super()
	_view = PxView3D.new(64, 64)
	_view.yaw = -30.0
	add_child(_view)

func open_for(m: GameState.PartyMon) -> void:
	idx = maxi(0, GameState.party.find(m))
	page = 0
	msel = 0
	open()

func mon() -> GameState.PartyMon:
	if GameState.party.is_empty():
		return null
	return GameState.party[clampi(idx, 0, GameState.party.size() - 1)]

func _tick() -> void:
	var m := mon()
	if m:
		_view.show_mon(m.species_id)

func _input_event(e: InputEvent) -> bool:
	var m := mon()
	if m == null:
		exit()
		return true
	var n := GameState.party.size()
	if pressed(e, "move_left"):
		page = (page + 2) % 3
	elif pressed(e, "move_right"):
		page = (page + 1) % 3
	elif pressed(e, "move_up", true):
		if page == 2:
			msel = maxi(0, msel - 1)
		else:
			idx = (idx + n - 1) % n
	elif pressed(e, "move_down", true):
		if page == 2:
			msel = mini(m.moves.size() - 1, msel + 1)
		else:
			idx = (idx + 1) % n
	elif pressed(e, "cancel") or (pressed(e, "confirm") and page != 2):
		exit()
	else:
		return false
	return true

static func move_effect_text(md: Dictionary) -> String:
	return EFFECT_TEXT.get(md.get("effect", ""), "A special technique.")

func _draw() -> void:
	var m := mon()
	if m == null:
		return
	var sp := GameData.get_species(m.species_id)
	Px.menu_bg(self, Color("#e8e0c8"), Color("#dcd2b8"), t)
	for i in 3:
		var tx := 170 + i * 50
		Px.frame(self, tx, 2, 48, 20, "red" if i == page else "gray")
		Px.text(self, TABS[i], tx + 24 - Px.measure(TABS[i]) / 2.0, 8)
	Px.frame(self, 4, 4, 160, 118, "blue")
	Px.text(self, "No.%03d" % int(sp.get("dex", 0)), 14, 12)
	Px.text(self, m.nickname, 60, 12)
	Px.small(self, "Lv%d" % m.level, 130, 14, Px.INK)
	_view.draw_at(self, 50, 34 + roundf(sin(t / 20.0)))
	if m.status != "":
		Px.status_tag(self, 12, 104, m.status)
	var types: Array = sp.get("types", [])
	for i in types.size():
		Px.type_tag(self, 60 + i * 46, 104, types[i])
	var x := 170
	var y := 26
	Px.frame(self, x, y, 146, 96)
	if page == 0:
		var growth: String = sp.get("growth", "MEDIUM_FAST")
		var to_next := maxi(0, GameState.exp_for_level(growth, m.level + 1) - m.xp)
		var rows := [["OT", GameState.player_name], ["ID No.", "%05d" % GameState.trainer_id],
			["SPECIES", sp.get("name", m.species_id)],
			["STATUS", m.status if m.status != "" else ("OK" if m.hp > 0 else "FAINTED")],
			["EXP", str(m.xp)], ["TO NEXT", str(to_next)]]
		for i in rows.size():
			Px.text(self, rows[i][0], x + 10, y + 8 + i * 14, LABEL)
			Px.text_r(self, str(rows[i][1]), x + 136, y + 8 + i * 14)
	elif page == 1:
		var rows2 := [["HP", "%d/%d" % [m.hp, m.max_hp]], ["ATTACK", m.stat("atk")], ["DEFENSE", m.stat("def")],
			["SPEED", m.stat("spd")], ["SPECIAL", m.stat("spc")]]
		for i in rows2.size():
			Px.text(self, rows2[i][0], x + 10, y + 8 + i * 15, LABEL)
			Px.text_r(self, str(rows2[i][1]), x + 136, y + 8 + i * 15)
		Px.hp_bar(self, x + 60, y + 84, 76, float(m.hp) / maxf(1.0, m.max_hp))
	else:
		for i in m.moves.size():
			var mv: String = m.moves[i]
			var md := GameData.get_move(mv)
			var yy := y + 6 + i * 22
			if i == msel:
				Px.rect(self, x + 5, yy - 2, 136, 20, Color("#f8e8b0"))
			Px.type_tag(self, x + 8, yy + 3, md.get("type", "NORMAL"), true)
			Px.text(self, md.get("name", mv), x + 48, yy)
			Px.small(self, "PP %d/%d" % [int(m.pp.get(mv, md.get("pp", 0))), int(md.get("pp", 0))], x + 90, yy + 11, Px.INK)
	Px.frame(self, 4, 124, 312, 52, "gray")
	if page == 2 and msel < m.moves.size():
		var md2 := GameData.get_move(m.moves[msel])
		var pw: int = int(md2.get("power", 0))
		Px.text(self, "POWER %s   ACCURACY %d%%" % [str(pw) if pw > 1 else "---", int(md2.get("acc", 100))], 14, 134)
		var lines := Px.wrap_text(move_effect_text(md2), 290)
		for i in mini(2, lines.size()):
			Px.text(self, lines[i], 14, 150 + i * 13)
	else:
		var lines2 := Px.wrap_text(GameText.dex(m.species_id), 290)
		for i in mini(3, lines2.size()):
			Px.text(self, lines2[i], 14, 131 + i * 13)

const EFFECT_TEXT := {
	"NO_ADDITIONAL": "A straightforward attack.", "TWO_TO_FIVE_ATTACKS": "Hits 2 to 5 times in a row.", "PAY_DAY": "Scatters coins you can pick up after battle.",
	"BURN_SIDE1": "May burn the target.", "BURN_SIDE2": "High chance to burn the target.", "FREEZE_SIDE1": "May freeze the target.", "PARALYZE_SIDE1": "May paralyze the target.",
	"PARALYZE_SIDE2": "High chance to paralyze the target.", "OHKO": "Knocks out the target in one hit if it lands.", "CHARGE": "Charges up on the first turn, strikes on the second.",
	"ATTACK_UP2": "Sharply raises ATTACK.", "SWITCH_AND_TELEPORT": "Flees from wild battles.", "FLY": "Flies up high, then strikes next turn.", "TRAPPING": "Traps the target for 2-5 turns.",
	"FLINCH_SIDE1": "May make the target flinch.", "FLINCH_SIDE2": "High chance to make the target flinch.", "ATTACK_TWICE": "Hits twice in a row.", "JUMP_KICK": "The user is hurt if it misses.",
	"ACCURACY_DOWN1": "Lowers the target's accuracy.", "RECOIL": "The user takes recoil damage.", "THRASH_PETAL_DANCE": "Attacks for 2-3 turns, then the user becomes confused.",
	"DEFENSE_DOWN1": "Lowers the target's DEFENSE.", "DEFENSE_DOWN2": "Sharply lowers the target's DEFENSE.", "POISON_SIDE1": "May poison the target.", "POISON_SIDE2": "High chance to poison the target.",
	"TWINEEDLE": "Hits twice; may poison.", "ATTACK_DOWN1": "Lowers the target's ATTACK.", "SLEEP": "Puts the target to sleep.", "CONFUSION": "Confuses the target.",
	"SPECIAL_DAMAGE": "Deals a fixed amount of damage.", "DISABLE": "Disables the target's last move.", "DEFENSE_DOWN_SIDE": "May lower the target's DEFENSE.", "MIST": "Protects against stat reduction.",
	"CONFUSION_SIDE": "May confuse the target.", "SPEED_DOWN_SIDE": "May lower the target's SPEED.", "ATTACK_DOWN_SIDE": "May lower the target's ATTACK.", "HYPER_BEAM": "Powerful, but the user must recharge.",
	"DRAIN_HP": "Restores HP by half the damage dealt.", "LEECH_SEED": "Drains HP from the target every turn.", "SPECIAL_UP1": "Raises SPECIAL.", "POISON": "Poisons the target.",
	"PARALYZE": "Paralyzes the target.", "SPEED_DOWN1": "Lowers the target's SPEED.", "SPECIAL_DOWN_SIDE": "May lower the target's SPECIAL.", "ATTACK_UP1": "Raises ATTACK.", "SPEED_UP2": "Sharply raises SPEED.",
	"RAGE": "ATTACK rises each time the user is hit.", "MIMIC": "Copies one of the target's moves.", "EVASION_UP1": "Raises evasiveness.", "HEAL": "Restores the user's HP.", "DEFENSE_UP1": "Raises DEFENSE.",
	"DEFENSE_UP2": "Sharply raises DEFENSE.", "LIGHT_SCREEN": "Halves damage from special attacks.", "HAZE": "Removes all stat changes.", "REFLECT": "Halves damage from physical attacks.",
	"FOCUS_ENERGY": "Raises the critical-hit ratio.", "BIDE": "Endures for 2-3 turns, then strikes back double.", "METRONOME": "Uses a random move.", "MIRROR_MOVE": "Copies the target's last move.",
	"EXPLODE": "A huge blast; the user faints.", "SWIFT": "Never misses.", "SPECIAL_UP2": "Sharply raises SPECIAL.", "DREAM_EATER": "Drains HP from a sleeping target.", "TRANSFORM": "Transforms into the target.",
	"SPLASH": "Does nothing at all.", "CONVERSION": "Changes the user's type to the target's.", "SUPER_FANG": "Cuts the target's HP in half.", "SUBSTITUTE": "Makes a decoy using 1/4 of the user's HP.",
}
