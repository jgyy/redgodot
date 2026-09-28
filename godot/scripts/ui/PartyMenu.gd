class_name PartyMenu
extends PxScreen
## Port of party.js PartyScreen: blue diagonal-stripe background, the lead's
## big card at (6,18,112,58), five 192x26 cards on the right, the grey
## "Choose a POKéMON." box and CANCEL. Each card's portrait is the species'
## real 3D model (PxView3D) where upstream blits its 32px sprite.
## A on a mon opens the field submenu (field moves / SUMMARY / SWITCH /
## CANCEL); SWITCH swaps two slots. open_with({"msg":..., "pick": Callable})
## runs upstream's pick mode (item targets, PC deposit): `pick` is awaited
## with (mon, index, self) and the screen closes with `picked(index)` when it
## returns true.

signal mon_selected(mon: GameState.PartyMon)
signal picked(index: int)

const FIELD_MOVES := ["CUT", "FLY", "SURF", "STRENGTH", "FLASH", "DIG", "TELEPORT", "SOFTBOILED"]
const BADGE_FOR := {"CUT": "CASCADEBADGE", "FLY": "THUNDERBADGE", "SURF": "SOULBADGE", "STRENGTH": "RAINBOWBADGE", "FLASH": "BOULDERBADGE"}

var summary_screen: SummaryScreen
var sel := 0
var swap_from := -1
var msg := "Choose a POKéMON."
var mode: Dictionary = {}
var _views: Array = []

func _ready() -> void:
	super()
	for i in 6:
		var v := PxView3D.new(32, 32)
		v.yaw = -30.0
		v.fill = 0.95
		add_child(v)
		_views.append(v)

func open_with(o: Dictionary) -> void:
	mode = o
	open()

func open() -> void:
	super()
	msg = mode.get("msg", "Choose a POKéMON.")

func _on_open() -> void:
	sel = clampi(int(mode.get("sel", 0)), 0, maxi(0, GameState.party.size() - 1))
	swap_from = -1
	_sync_views()

func _sync_views() -> void:
	for i in 6:
		var v: PxView3D = _views[i]
		if i < GameState.party.size():
			v.show_mon(GameState.party[i].species_id)
			v.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		else:
			v.clear()
			v.render_target_update_mode = SubViewport.UPDATE_DISABLED

func exit() -> void:
	if mode.has("pick"):
		var o := mode
		mode = {}
		close()
		picked.emit(-1)
		if o.has("on_done"):
			(o["on_done"] as Callable).call()
		return
	mode = {}
	super()

func _input_event(e: InputEvent) -> bool:
	var n := GameState.party.size()
	if pressed(e, "move_up", true):
		sel = n - 1 if sel == n else (sel - 1 + n + 1) % (n + 1)
	elif pressed(e, "move_down", true):
		sel = (sel + 1) % (n + 1)
	elif pressed(e, "move_left"):
		if sel > 0 and sel < n:
			sel = 0
	elif pressed(e, "move_right"):
		if sel == 0 and n > 1:
			sel = 1
	elif pressed(e, "cancel"):
		if swap_from >= 0:
			swap_from = -1
			msg = "Choose a POKéMON."
		elif not mode.get("forced", false):
			exit()
	elif pressed(e, "confirm"):
		if sel == n:
			if not mode.get("forced", false):
				exit()
		elif swap_from >= 0:
			var a := swap_from
			var tmp = GameState.party[a]
			GameState.party[a] = GameState.party[sel]
			GameState.party[sel] = tmp
			swap_from = -1
			msg = "Choose a POKéMON."
			_sync_views()
			GameState.party_changed.emit()
		else:
			_choose(sel)
	else:
		return false
	return true

func _choose(i: int) -> void:
	busy = true
	var m: GameState.PartyMon = GameState.party[i]
	if mode.has("pick"):
		var ok: bool = await (mode["pick"] as Callable).call(m, i, self)
		busy = false
		if ok:
			var o := mode
			mode = {}
			close()
			picked.emit(i)
			if o.has("on_done"):
				(o["on_done"] as Callable).call()
		return
	var fms: Array = []
	for mv in m.moves:
		if FIELD_MOVES.has(mv):
			fms.append(mv)
	var all: Array = fms.map(func(x): return GameData.get_move(x).get("name", x))
	all.append_array(["SUMMARY", "SWITCH", "CANCEL"])
	var r := await choose(all, {"x": 320 - 96, "y": 180 - 10 - all.size() * 15 - 14})
	busy = false
	if r < 0 or all[r] == "CANCEL":
		return
	if r < fms.size():
		await _field_move(fms[r], m)
		return
	if all[r] == "SUMMARY":
		mon_selected.emit(m)
		if summary_screen:
			close()
			summary_screen.open_for(m)
			await summary_screen.closed
			open_with(mode.merged({"sel": i}))
	elif all[r] == "SWITCH":
		swap_from = i
		msg = "Move to where?"

func _field_move(mv: String, m: GameState.PartyMon) -> void:
	if BADGE_FOR.has(mv) and not GameState.badges.has(BADGE_FOR[mv]):
		await party_say("No! A new BADGE is required.")
		return
	match mv:
		"SOFTBOILED":
			var cost := maxi(1, m.max_hp / 5)
			if m.hp <= cost:
				await party_say("Not enough HP!")
				return
			var r := await choose(GameState.party.map(func(x): return x.nickname), {"x": 150, "y": 20})
			if r < 0:
				return
			var tgt: GameState.PartyMon = GameState.party[r]
			m.hp -= cost
			var before := tgt.hp
			tgt.hp = mini(tgt.max_hp, tgt.hp + cost)
			await party_say("%s recovered by %d!" % [tgt.nickname, tgt.hp - before])
		_:
			await party_say("There's no place to use %s here." % GameData.get_move(mv).get("name", mv))

## PartyScreen.say(): shows a message in the party's own box until A/B.
func party_say(text: String) -> void:
	busy = true
	msg = text
	await get_tree().process_frame
	while true:
		await get_tree().process_frame
		if Input.is_action_just_pressed("confirm") or Input.is_action_just_pressed("cancel"):
			break
	msg = "Choose a POKéMON."
	busy = false

func _draw() -> void:
	Px.menu_bg(self, Color("#5a8ad8"), Color("#4a78c8"), t)
	var n := GameState.party.size()
	for i in n:
		_draw_slot(i)
	var cy := 150
	var csel := sel == n
	Px.frame(self, 238, cy - 2, 78, 22, "red" if csel else "gray")
	Px.text(self, "CANCEL", 256, cy + 4)
	Px.frame(self, 4, 150, 230, 26, "gray")
	Px.text(self, msg, 14, 159)

func _draw_slot(i: int) -> void:
	var m: GameState.PartyMon = GameState.party[i]
	var is_sel := i == sel
	var swap := i == swap_from
	var x := 6
	var y := 18
	var w := 112
	var h := 58
	if i > 0:
		x = 124
		y = 6 + (i - 1) * 28
		w = 192
		h = 26
	var fainted := m.hp <= 0
	var base := Color("#c86a6a") if fainted else (Color("#e8a840") if swap else (Color("#f8b060") if is_sel else Color("#3a6ab8")))
	var hi := Px.shade(base, 0.25)
	var lo := Px.shade(base, -0.2)
	# plate: outline with clipped corners, lighter top 2 rows, darker bottom 3
	Px.rect(self, x + 1, y, w - 2, h, Px.OUTLINE)
	Px.rect(self, x, y + 1, w, h - 2, Px.OUTLINE)
	Px.rect(self, x + 1, y + 1, w - 2, h - 2, base)
	Px.rect(self, x + 1, y + 1, w - 2, 2, hi)
	Px.rect(self, x + 1, y + h - 3, w - 2, 2, lo)
	var bob := (((t / 8) % 2) * -2) if (is_sel and not fainted) else 0
	var tc := Px.WHITE
	var sh := Px.shade(base, -0.45)
	var name := m.nickname
	var v: PxView3D = _views[i]
	if i == 0:
		v.draw_at(self, x + 2, y + 2 + bob)
		Px.text(self, name, x + 38, y + 8, tc, sh)
		Px.small(self, "Lv%d" % m.level, x + 38, y + 22, tc, sh)
		if m.status != "" or fainted:
			Px.status_tag(self, x + 70, y + 21, "FNT" if fainted else m.status)
		Px.hp_bar(self, x + 38, y + 36, 66, float(m.hp) / maxf(1.0, m.max_hp))
		var hp := "%d/%d" % [m.hp, m.max_hp]
		Px.small(self, hp, x + w - 8 - Px.measure_small(hp), y + 44, tc, sh)
	else:
		# sprite clipped to its top 30 rows ({sh: 30})
		v.draw_clipped(self, x - 2, y - 5 + bob, 30)
		Px.text(self, name, x + 32, y + 4, tc, sh)
		Px.small(self, "Lv%d" % m.level, x + 32, y + 16, tc, sh)
		if m.status != "" or fainted:
			Px.status_tag(self, x + 58, y + 15, "FNT" if fainted else m.status)
		Px.hp_bar(self, x + 108, y + 8, 60, float(m.hp) / maxf(1.0, m.max_hp))
		var hp2 := "%d/%d" % [m.hp, m.max_hp]
		Px.small(self, hp2, x + 168 - Px.measure_small(hp2), y + 15, tc, sh)
