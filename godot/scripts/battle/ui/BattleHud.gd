class_name BattleHud
extends PxCanvas
## Battle UI overlay, a pixel-exact port of upstream src/game/battlescene.js's
## draw code (drawEnemyBox / drawPlayerBox / hpBox / hpBar / statusBadge /
## drawTextArea / gridMenu / moveMenu / drawStatsBox / drawPartyBalls) plus the
## in-battle bag and party screens (bag.js BagScreen, party.js PartyScreen),
## on upstream's 320x180 canvas. BattleScene.gd owns the state and the input;
## this node only draws it.

const INK := Color("#3a3a4c")
const INK_SH := Color("#d6d4cc")
const OUTLINE := Color("#1b1a2e")
const WHITE := Color("#ffffff")
const TYPE_COL := {
	"NORMAL": "#a8a878", "FIRE": "#f08030", "WATER": "#6890f0", "GRASS": "#78c850", "ELECTRIC": "#f8d030",
	"ICE": "#98d8d8", "FIGHTING": "#c03028", "POISON": "#a040a0", "GROUND": "#e0c068", "FLYING": "#a890f0",
	"PSYCHIC_TYPE": "#f85888", "BUG": "#a8b820", "ROCK": "#b8a038", "GHOST": "#705898", "DRAGON": "#7038f8",
	"BIRD": "#a8a878",
}
const STATUS_COL := {"PSN": "#a040a0", "BRN": "#e05030", "FRZ": "#58b8e8", "PAR": "#d8b020", "SLP": "#8a8aa0", "FNT": "#d04040"}

var t := 0
var enemy: GameState.PartyMon
var player: GameState.PartyMon
var boxes := {"e": false, "p": false}
var disp := {"e": 0.0, "p": 0.0}
var exp_disp := -1.0
var wild := true
var enemy_party: Array = []
var menu_balls_p := false
var enemy_caught_before := false
## text box: {lines: Array, chars: int, waiting: bool}
var box: Dictionary = {}
## menu: {kind: "action"|"moves"|"yesno"|"choose", sel, items, moves...}
var menu: Dictionary = {}
var stats_box: Dictionary = {}
## full-screen overlays: {kind: "bag"|"party", ...}
var screen: Dictionary = {}
## 2D effects under the boxes (upstream draws them over the battle area, y < 132)
var flash_amt := 0.0
var flash_color := Color.WHITE
var darken_amt := 0.0
var darken_color := Color("#100818")
var fade := 0.0  # whole-screen fade to black (transitions)
var transition: Dictionary = {}  # {kind, t}

func _process(dt: float) -> void:
	super._process(dt)

func _draw() -> void:
	if darken_amt > 0.0:
		Px.rect(self, 0, 0, 320, 132, Color(darken_color, clampf(darken_amt, 0, 1)))
	if flash_amt > 0.0:
		Px.rect(self, 0, 0, 320, 132, Color(flash_color, clampf(flash_amt, 0, 1)))
	if boxes["e"] and enemy:
		_draw_enemy_box()
	if boxes["p"] and player:
		_draw_player_box()
	if not wild:
		_draw_party_balls()
	if screen.get("kind", "") != "evo":
		_draw_text_area()
	if not stats_box.is_empty():
		_draw_stats_box()
	if not menu.is_empty() and (menu["kind"] == "yesno" or menu["kind"] == "choose"):
		Px.menu(self, menu["items"], menu["sel"], menu["x"], menu["y"], menu.get("w", -1), -1, 0, t)
	if not screen.is_empty():
		if screen["kind"] == "bag":
			_draw_bag()
		elif screen["kind"] == "party":
			_draw_party()
		elif screen["kind"] == "evo":
			_draw_evo_box()
	if not transition.is_empty():
		_draw_transition()
	if fade > 0.0:
		Px.rect(self, 0, 0, 320, 180, Color(0, 0, 0, clampf(fade, 0, 1)))

# ------------------------------------------------------------------ HP boxes
func _hp_color(frac: float) -> Array:
	if frac > 0.5:
		return [Color("#58d080"), Color("#2a9a50"), Color("#98f0b0")]
	if frac > 0.2:
		return [Color("#f8c838"), Color("#c89010"), Color("#fff0a0")]
	return [Color("#f05848"), Color("#b02828"), Color("#ffa090")]

func _draw_enemy_box() -> void:
	var m := enemy
	var x := 10
	var y := 12
	var w := 132
	var h := 34
	_hp_box(x, y, w, h, "e")
	Px.text(self, m.display_name(), x + 10, y + 6, INK, INK_SH)
	Px.small(self, "Lv" + str(m.level), x + w - 34, y + 8, INK)
	if m.status != "":
		_status_badge(x + 10, y + 21, m.status)
	_hp_bar(x + 44, y + 22, 78, disp["e"] / maxf(1.0, m.max_hp))
	if wild and enemy_caught_before:
		var bx := x + w - 12
		var by := y + 8
		_disc(bx, by + 2, 2.5, Color("#e04848"))
		Px.pset(self, bx - 2, by + 2, OUTLINE)
		Px.pset(self, bx + 2, by + 2, OUTLINE)
		Px.pset(self, bx, by + 2, WHITE)

func _draw_player_box() -> void:
	var m := player
	var x := 176
	var y := 88
	var w := 138
	var h := 42
	_hp_box(x, y, w, h, "p")
	Px.text(self, m.display_name(), x + 12, y + 6, INK, INK_SH)
	Px.small(self, "Lv" + str(m.level), x + w - 34, y + 8, INK)
	if m.status != "":
		_status_badge(x + 12, y + 20, m.status)
	_hp_bar(x + 48, y + 21, 80, disp["p"] / maxf(1.0, m.max_hp))
	var hp_txt := "%d/%d" % [int(ceil(disp["p"])), m.max_hp]
	Px.small(self, hp_txt, x + w - 10 - Px.measure_small(hp_txt), y + 27, INK)
	var lo := m.exp_this()
	var hi := m.exp_to_next()
	var ex: float = exp_disp if exp_disp >= 0.0 else float(m.xp)
	var frac := clampf((ex - lo) / float(hi - lo), 0.0, 1.0) if hi > lo else 1.0
	var bx := x + 12
	var by := y + h - 7
	var bw := w - 24
	Px.rect(self, bx - 1, by - 1, bw + 2, 4, OUTLINE)
	Px.rect(self, bx, by, bw, 2, Color("#50506a"))
	Px.rect(self, bx, by, roundi(bw * frac), 2, Color("#48b8f8"))
	Px.rect(self, bx, by, roundi(bw * frac), 1, Color("#a8e8ff"))

func _hp_box(x: int, y: int, w: int, h: int, k: String) -> void:
	var dark := Color("#2e3450")
	var mid := Color("#f4f2e6")
	var light := Color("#ffffff")
	var edge := Color("#b8b4a0")
	# rows as runs (the enemy box has its bottom-right corner cut at a slant)
	for j in h:
		var i_end := w
		if k == "e":
			for i in range(w - 8, w):
				if j > h - (w - i) * 2:
					i_end = i
					break
		for i in range(i_end):
			var c := mid
			if j == 0 or i == 0 or j == h - 1 or i == w - 1:
				c = dark
			elif j == 1 or i == 1:
				c = light
			elif j == h - 2 or i == w - 2:
				c = edge
			if c != mid:
				Px.pset(self, x + i, y + j, c)
		# fill the interior run in one rect
		if j >= 2 and j < h - 2:
			Px.rect(self, x + 2, y + j, mini(i_end, w - 2) - 2, 1, mid)
	var tab := Color("#d05858") if k == "e" else Color("#5878d0")
	Px.rect(self, x + 2, y + 2, 2, h - 4, tab)
	# drop shadow (upstream multiplies by rgb(150,150,180))
	var shc := Color(0.13, 0.13, 0.32, 0.4)
	Px.rect(self, x + 2, y + h, w, 1, shc)
	Px.rect(self, x + w, y + 2, 1, h - 2, shc)

func _hp_bar(x: int, y: int, w: int, frac: float) -> void:
	frac = clampf(frac, 0.0, 1.0)
	Px.rect(self, x - 16, y - 1, w + 18, 6, OUTLINE)
	Px.rect(self, x - 15, y, 14, 4, Color("#e8a040"))
	Px.small(self, "HP", x - 14, y, Color("#fff4d8"))
	Px.rect(self, x, y, w, 4, Color("#50506a"))
	var cols := _hp_color(frac)
	var fw := roundi(w * frac)
	Px.rect(self, x, y, fw, 4, cols[0])
	Px.rect(self, x, y + 3, fw, 1, cols[1])
	Px.rect(self, x, y, fw, 1, cols[2])

func _status_badge(x: int, y: int, st: String) -> void:
	Px.rect(self, x, y - 1, 20, 7, OUTLINE)
	Px.rect(self, x + 1, y, 18, 5, Color(STATUS_COL.get(st, "#8a8aa0")))
	Px.small(self, st, x + 2, y, WHITE)

func _disc(cx: float, cy: float, r: float, c: Color) -> void:
	for j in range(int(floor(cy - r)), int(ceil(cy + r)) + 1):
		for i in range(int(floor(cx - r)), int(ceil(cx + r)) + 1):
			if (i - cx) * (i - cx) + (j - cy) * (j - cy) <= r * r:
				Px.pset(self, i, j, c)

func _mini_ball(x: int, y: int, st: String) -> void:
	var c := Color("#e04848") if st == "ok" else (Color("#e0a040") if st == "bad" else Color("#6a6a7a"))
	_disc(x, y, 3, OUTLINE)
	_disc(x, y, 2.2, WHITE)
	for i in range(-2, 3):
		for j in range(-2, 0):
			if i * i + j * j <= 5:
				Px.pset(self, x + i, y + j, c)
	Px.rect(self, x - 2, y, 5, 1, OUTLINE)
	Px.pset(self, x, y, WHITE)

func _mon_state(m: GameState.PartyMon) -> String:
	return "fnt" if m.is_fainted() else ("bad" if m.status != "" else "ok")

func _draw_party_balls() -> void:
	for i in 6:
		var x := 18 + i * 8
		if i < enemy_party.size():
			_mini_ball(x, 50, _mon_state(enemy_party[i]))
		else:
			_circle(x, 50, 2, Color("#8a8aa0"))
	if menu_balls_p or not boxes["p"]:
		var pp: Array = GameState.party
		for i in mini(6, pp.size()):
			_mini_ball(262 + i * 8, 126, _mon_state(pp[i]))

func _circle(cx: int, cy: int, r: int, c: Color) -> void:
	for a in 16:
		var an := a / 16.0 * TAU
		Px.pset(self, roundi(cx + cos(an) * r), roundi(cy + sin(an) * r), c)

# ------------------------------------------------------------------ text area & menus
func _draw_text_area() -> void:
	var y := 132
	Px.rect(self, 0, y, 320, 48, Color("#2a2c44"))
	Px.rect(self, 0, y, 320, 1, OUTLINE)
	Px.rect(self, 0, y + 1, 320, 1, Color("#8a8ec8"))
	Px.rect(self, 0, y + 2, 320, 1, Color("#50548a"))
	var bw := 180 if (not menu.is_empty() and menu["kind"] == "action") else 314
	Px.frame(self, 3, y + 4, bw, 42, "red", Color("#3c4a78"))
	if not box.is_empty():
		var left: int = box.get("chars", 999)
		var ly := y + 12
		for ln in box.get("lines", []):
			var line: String = ln
			Px.text(self, line.substr(0, maxi(0, left)), 14, ly, WHITE, Color("#5a5a7a"))
			left -= line.length() + 1
			ly += 15
		if box.get("waiting", false) and (t / 16) % 2 == 0:
			Px.text(self, "▼", bw - 12, y + 34, Color("#f8d048"), Color(0, 0, 0, 0))
	if not menu.is_empty():
		if menu["kind"] == "action":
			_draw_action_menu()
		elif menu["kind"] == "moves":
			_draw_move_menu()

func _draw_action_menu() -> void:
	var x := 186
	var y := 136
	Px.frame(self, x, y, 130, 42)
	var items: Array = menu["items"]
	for i in items.size():
		var cx := x + 18 + (i % 2) * 58
		var cy := y + 8 + (i / 2) * 15
		Px.text(self, items[i], cx, cy)
		if i == int(menu["sel"]):
			Px.cursor(self, cx - 10, cy, t)

func _draw_move_menu() -> void:
	Px.frame(self, 3, 136, 214, 42, "gray")
	var moves: Array = menu["moves"]  # [{id, pp, max}]
	var sel: int = menu["sel"]
	for i in moves.size():
		var cx := 20 + (i % 2) * 100
		var cy := 144 + (i / 2) * 15
		Px.text(self, BattleEngine.move_name(moves[i]["id"]), cx, cy)
		if i == sel:
			Px.cursor(self, cx - 10, cy, t)
	if moves.is_empty():
		return
	var mv: Dictionary = moves[sel]
	var md := GameData.get_move(mv["id"])
	Px.frame(self, 220, 136, 96, 42, "gray")
	Px.text(self, "PP", 230, 144)
	var pp := "%d/%d" % [int(mv["pp"]), int(mv["max"])]
	Px.text(self, pp, 306 - Px.measure(pp), 144, Color("#d04040") if int(mv["pp"]) == 0 else INK)
	var tc := Color(TYPE_COL.get(md.get("type", "NORMAL"), "#888888"))
	Px.rect(self, 229, 158, 78, 12, OUTLINE)
	Px.rect(self, 230, 159, 76, 10, tc)
	var tn: String = md.get("type", "NORMAL")
	if tn == "PSYCHIC_TYPE":
		tn = "PSYCHIC"
	Px.text(self, tn, 268 - Px.measure(tn) / 2.0, 160, WHITE, tc.darkened(0.45))

func _draw_stats_box() -> void:
	var x := 206
	var y := 20
	var w := 108
	var h := 88
	Px.frame(self, x, y, w, h)
	var names := [["maxhp", "MAX. HP"], ["atk", "ATTACK"], ["def", "DEFENSE"], ["spd", "SPEED"], ["spc", "SPECIAL"]]
	var m: GameState.PartyMon = stats_box["m"]
	var old: Dictionary = stats_box["old"]
	for i in names.size():
		var k: String = names[i][0]
		var now := m.max_hp if k == "maxhp" else m.stat(k)
		Px.text(self, names[i][1], x + 10, y + 8 + i * 15)
		var v := ("+" + str(now - int(old[k]))) if int(stats_box.get("phase", 0)) == 0 else str(now)
		Px.text(self, v, x + w - 10 - Px.measure(v), y + 8 + i * 15)

# ------------------------------------------------------------------ full-screen: bag & party
func _menu_bg(c1: String, c2: String) -> void:
	var a := Color(c1)
	var b := Color(c2)
	Px.rect(self, 0, 0, 320, 180, b)
	# diagonal 8px stripes, scrolling (upstream ((x + y + t/4) >> 3) % 2)
	var off := (t / 4) % 16
	for k in range(-24, 44):
		var x0 := k * 16 - off
		for yy in 180:
			var xs := x0 - yy
			Px.rect(self, xs, yy, 8, 1, a)

func _draw_bag() -> void:
	_menu_bg("#e0a860", "#d49850")
	Px.frame(self, 4, 4, 104, 118, "red", Color("#f8e8c8"))
	_draw_bag_art(56, 64)
	Px.text(self, "ITEMS", 38, 104)
	Px.frame(self, 112, 4, 204, 118)
	var items: Array = screen["items"]  # [[id, n]]
	var sel: int = screen["sel"]
	var scroll: int = screen["scroll"]
	var l := items.size() + 1
	for i in 7:
		var idx := scroll + i
		if idx >= l:
			break
		var y := 12 + i * 15
		if idx == items.size():
			Px.text(self, "CANCEL", 132, y)
		else:
			Px.text(self, BattleEngine.item_name(items[idx][0]), 132, y)
			var n := "×" + str(items[idx][1])
			Px.text(self, n, 304 - Px.measure(n), y)
		if idx == sel:
			Px.cursor(self, 120, y, t)
	if scroll > 0:
		Px.text(self, "▲", 210, 5, Color("#d04a4a"), Color(0, 0, 0, 0))
	if scroll + 7 < l:
		Px.text(self, "▼", 210, 114, Color("#d04a4a"), Color(0, 0, 0, 0))
	Px.frame(self, 4, 124, 312, 52, "gray")
	var txt: String = screen.get("msg", "")
	if txt == "":
		txt = "Close the BAG." if sel >= items.size() else _item_desc(items[sel][0])
	var lines := Px.wrap_text(txt, 290)
	for i in mini(2, lines.size()):
		Px.text(self, lines[i], 14, 134 + i * 15)

func _item_desc(id: String) -> String:
	if BattleEngine.HEAL.has(id):
		return "Restores %d HP to one POKéMON." % int(BattleEngine.HEAL[id]) if int(BattleEngine.HEAL[id]) < 9999 else "Fully restores the HP of one POKéMON."
	if id.ends_with("BALL"):
		return "A device for catching wild POKéMON."
	if BattleEngine.CURE.has(id):
		return "Cures a status problem."
	if BattleEngine.X_ITEM.has(id):
		return "Raises a stat during battle."
	if id.contains("REVIVE"):
		return "Revives a fainted POKéMON."
	return "An item."

func _draw_bag_art(cx: int, cy: int) -> void:
	var B := [Color("#6a3a1a"), Color("#8a5028"), Color("#b0703a"), Color("#d09050"), Color("#e8b070")]
	var sway := roundi(sin(t / 30.0))
	for y in range(-26, 25):
		var w: float = 14 + (y + 26) * 0.4 if y < -14 else 24 - maxf(0, y - 14) * 0.6
		for x in range(-24, 25):
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
			Px.pset(self, cx + x + sway, cy + y, c)
	_disc(cx + sway, cy - 4, 2.5, Color("#e8c040"))

func _draw_party() -> void:
	_menu_bg("#5a8ad8", "#4a78c8")
	var party: Array = GameState.party
	var n := party.size()
	for i in n:
		_draw_slot(i, party[i])
	var cy := 150
	var sel_cancel: bool = int(screen["sel"]) == n
	Px.frame(self, 238, cy - 2, 78, 22, "red" if sel_cancel else "gray")
	Px.text(self, "CANCEL", 256, cy + 4)
	Px.frame(self, 4, 150, 230, 26, "gray")
	Px.text(self, screen.get("msg", "Choose a POKéMON."), 14, 159)
	if screen.has("sub"):
		var sub: Dictionary = screen["sub"]
		Px.menu(self, sub["items"], sub["sel"], 236, 96, -1, -1, 0, t)

func _small_hp_bar(x: int, y: int, w: int, frac: float) -> void:
	frac = clampf(frac, 0, 1)
	Px.rect(self, x - 1, y - 1, w + 2, 5, OUTLINE)
	Px.rect(self, x, y, w, 3, Color("#50506a"))
	var c := Color("#58d080") if frac > 0.5 else (Color("#f8c838") if frac > 0.2 else Color("#f05848"))
	Px.rect(self, x, y, roundi(w * frac), 3, c)
	Px.rect(self, x, y, roundi(w * frac), 1, c.lerp(WHITE, 0.5))

func _status_tag(x: int, y: int, st: String) -> void:
	Px.rect(self, x, y, 19, 7, OUTLINE)
	Px.rect(self, x + 1, y + 1, 17, 5, Color(STATUS_COL.get(st, "#8a8aa0")))
	Px.small(self, st, x + 2, y + 1, WHITE)

func _draw_slot(i: int, m: GameState.PartyMon) -> void:
	var sel: bool = i == int(screen["sel"])
	var x := 6 if i == 0 else 124
	var y := 18 if i == 0 else 6 + (i - 1) * 28
	var w := 112 if i == 0 else 192
	var h := 58 if i == 0 else 26
	var fainted := m.is_fainted()
	var base := Color("#c86a6a") if fainted else (Color("#f8b060") if sel else Color("#3a6ab8"))
	Px.rect(self, x + 1, y, w - 2, h, OUTLINE)
	Px.rect(self, x, y + 1, w, h - 2, OUTLINE)
	Px.rect(self, x + 1, y + 1, w - 2, h - 2, base)
	Px.rect(self, x + 1, y + 1, w - 2, 2, base.lightened(0.25))
	Px.rect(self, x + 1, y + h - 4, w - 2, 3, base.darkened(0.2))
	var sh := base.darkened(0.45)
	var types: Array = m.types()
	var ic := Color(TYPE_COL.get(types[0] if not types.is_empty() else "NORMAL", "#a8a878"))
	var bob := -2 * ((t / 8) % 2) if sel and not fainted else 0
	if i == 0:
		_mon_icon(x + 18, y + 18 + bob, ic)
		Px.text(self, m.display_name(), x + 38, y + 8, WHITE, sh)
		Px.small(self, "Lv" + str(m.level), x + 38, y + 22, WHITE, sh)
		if m.status != "" or fainted:
			_status_tag(x + 70, y + 21, "FNT" if fainted else m.status)
		_small_hp_bar(x + 38, y + 36, 66, m.hp / maxf(1.0, m.max_hp))
		var tx := "%d/%d" % [m.hp, m.max_hp]
		Px.small(self, tx, x + w - 8 - Px.measure_small(tx), y + 44, WHITE, sh)
	else:
		_mon_icon(x + 14, y + 12 + bob, ic)
		Px.text(self, m.display_name(), x + 32, y + 4, WHITE, sh)
		Px.small(self, "Lv" + str(m.level), x + 32, y + 16, WHITE, sh)
		if m.status != "" or fainted:
			_status_tag(x + 58, y + 15, "FNT" if fainted else m.status)
		_small_hp_bar(x + 108, y + 8, 60, m.hp / maxf(1.0, m.max_hp))
		var tx2 := "%d/%d" % [m.hp, m.max_hp]
		Px.small(self, tx2, x + 168 - Px.measure_small(tx2), y + 15, WHITE, sh)

func _mon_icon(cx: int, cy: int, c: Color) -> void:
	_disc(cx, cy, 8, OUTLINE)
	_disc(cx, cy, 7, c)
	_disc(cx - 2, cy - 3, 2, c.lightened(0.4))

# ------------------------------------------------------------------ evolution text box & transitions
func _draw_evo_box() -> void:
	Px.frame(self, 6, 128, 308, 48)
	var txt: String = screen.get("text", "")
	if txt != "":
		var lines := Px.wrap_text(txt, 284)
		for i in mini(2, lines.size()):
			Px.text(self, lines[i], 18, 138 + i * 15)

## upstream battleflow.js transition(): wild = white flashes then a black
## spiral wipe; trainer = alternating horizontal bands sweep in.
func _draw_transition() -> void:
	var kind: String = transition["kind"]
	var tt: int = transition["t"]
	if kind == "wild":
		if tt < 24:
			if (tt / 4) % 2 == 0:
				Px.rect(self, 0, 0, 320, 180, Color(1, 1, 1, 0.7))
		else:
			var k := (tt - 24) / 36.0
			for y in range(0, 180, 2):
				for x in range(0, 320, 2):
					var a := atan2(y - 90.0, x - 160.0) / TAU + 0.5
					var r := Vector2(x - 160, y - 90).length() / 184.0
					if fmod(a + r * 0.6, 1.0) < k * 1.4:
						Px.rect(self, x, y, 2, 2, Color.BLACK)
	else:
		var k2 := maxf(0, tt - 8) / 40.0
		for band in 15:
			var cover := minf(1.0, k2 * 1.3 - band * 0.012) * 320
			if cover <= 0:
				continue
			if band % 2 == 1:
				Px.rect(self, 0, band * 12, cover, 12, Color.BLACK)
			else:
				Px.rect(self, 320 - cover, band * 12, cover, 12, Color.BLACK)
		if tt < 8 and tt % 4 < 2:
			Px.rect(self, 0, 0, 320, 180, Color(1, 1, 1, 0.6))
