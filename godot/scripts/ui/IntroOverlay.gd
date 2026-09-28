class_name IntroOverlay
extends PxCanvas
## The 2D half of intro.js, drawn with upstream's own coordinates/timings:
##  - drawPresents(): the whole LEVY ST. GAMES card (opaque, frames 0-329),
##  - over the 3D battle: energy-shot twinkles, the lunge slash, the leap's
##    spark trail, the clash's ray burst and white-out, the letterbox bars,
##    the PRESS ANY KEY hints and the fade from black.
## `scene` is the IntroScene (frame counter, choreography, particles).

const NAVY := Color("#141a2e")
const IVORY := Color("#f3f0e9")
const ORANGE := Color("#d97757")
const LEVY_MARK: Texture2D = preload("res://assets/ui/levy_mark.png")
const LEVY_WORD: Texture2D = preload("res://assets/ui/levy_word.png")

var scene: Node
static var _spark_icon: ImageTexture

func _init() -> void:
	super()
	animate = false

func _pblend(x: float, y: float, c: Color, a: float) -> void:
	if a <= 0.0:
		return
	Px.rect(self, floorf(x), floorf(y), 1, 1, Color(c, clampf(a, 0.0, 1.0)))

## intro.js sparkle(): a four-point twinkle.
func _sparkle(x: float, y: float, r: int, c: Color) -> void:
	x = roundf(x)
	y = roundf(y)
	Px.pset(self, x, y, c)
	for i in range(1, r + 1):
		var k := 0.45 if i == r else 0.85
		for d in [Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1)]:
			_pblend(x + d.x * i, y + d.y * i, c, k)

func _circle(cx: int, cy: int, r: int, c: Color) -> void:
	var x := r
	var y := 0
	var err := 1 - r
	while x >= y:
		for p in [Vector2i(x, y), Vector2i(y, x), Vector2i(-y, x), Vector2i(-x, y), Vector2i(-x, -y), Vector2i(-y, -x), Vector2i(y, -x), Vector2i(x, -y)]:
			Px.pset(self, cx + p.x, cy + p.y, c)
		y += 1
		if err < 0:
			err += 2 * y + 1
		else:
			x -= 1
			err += 2 * (y - x) + 1

func _line(x0: float, y0: float, x1: float, y1: float, c: Color, a: float) -> void:
	if a <= 0.0:
		return
	draw_line(Vector2(x0, y0) + Vector2(0.5, 0.5), Vector2(x1, y1) + Vector2(0.5, 0.5), Color(c, clampf(a, 0.0, 1.0)), 1.0)

static func _ease(x: float) -> float:
	return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x * x * (3.0 - 2.0 * x))

func _draw() -> void:
	if scene == null:
		return
	var t: int = scene.t
	if t < scene.PRESENTS:
		_draw_presents(t)
	else:
		_draw_battle(t - scene.PRESENTS)

func _hint(col: Color, bt: int) -> void:
	var tx := ""
	if not scene.sound_asked:
		tx = "PRESS ANY KEY FOR SOUND"
	elif bt >= 0 and bt < 200:
		tx = "PRESS ANY KEY TO SKIP"
		col = Color("#5a6078")
	if tx != "":
		Px.small(self, tx, 320 - Px.measure_small(tx) - 6, 8, col)

func _draw_presents(t: int) -> void:
	var land := 62
	var fade_out := maxf(0.0, (t - (scene.PRESENTS - 24)) / 24.0)
	var bg_k := _ease((t - land) / 30.0)
	Px.rect(self, 0, 0, Px.W, Px.H, Px.mix(Color.BLACK, NAVY, bg_k))
	for i in 46:
		var x := int(SfxSynth.hash2(i, 1, 3) * 320.0)
		var y := int(SfxSynth.hash2(i, 2, 3) * 180.0)
		var tw := (t + i * 13) % 80
		if bg_k > 0.0 and tw < 60:
			_pblend(x, y, IVORY, 0.25 * bg_k + (0.3 if tw < 6 else 0.0))
	var k := clampf((t - 12) / float(land - 12), 0.0, 1.0)
	var sx := lerpf(360.0, 160.0, _ease(k))
	var sy := lerpf(-20.0, 58.0, _ease(k))
	if t >= 12 and t < land:
		for i in 26:
			var kk := maxf(0.0, k - i * 0.012)
			var col := Color.WHITE if i < 4 else (IVORY if i % 3 != 0 else ORANGE)
			_pblend(lerpf(360.0, 160.0, _ease(kk)), lerpf(-20.0, 58.0, _ease(kk)), col, 1.0 - i / 26.0)
		_sparkle(sx, sy, 3, Color.WHITE)
	for p in scene.parts:
		if not p.battle and p.life > 0:
			_pblend(p.x, p.y, p.c, minf(1.0, p.life / 14.0))
	if t >= land and t < land + 18:
		_circle(160, 58, (t - land) * 3, Px.mix(NAVY, Color.WHITE, 1.0 - (t - land) / 18.0))
	if t >= land:
		var g := _ease((t - land) / 14.0)
		var mw := maxf(1.0, roundf(LEVY_MARK.get_width() * g))
		var mh := maxf(1.0, roundf(LEVY_MARK.get_height() * g))
		Px.blit(self, LEVY_MARK, 160 - (int(mw) >> 1), 58 - (int(mh) >> 1), mw, mh)
		var ww := LEVY_WORD.get_width()
		var wipe := roundf(ww * _ease((t - land - 16) / 26.0))
		if wipe > 0.0:
			draw_texture_rect_region(LEVY_WORD, Rect2(160 - (ww >> 1), 84, wipe, LEVY_WORD.get_height()), Rect2(0, 0, wipe, LEVY_WORD.get_height()))
		var spaced := "G  A  M  E  S"
		var gk := _ease((t - land - 44) / 18.0)
		if gk > 0.0:
			Px.small(self, spaced, 160 - (Px.measure_small(spaced) >> 1), 117, Px.mix(NAVY, IVORY, gk * 0.85))
		var pk := _ease((t - land - 70) / 20.0)
		if pk > 0.0:
			Px.text(self, "presents", 160 - (Px.measure("presents") >> 1), 128, Px.mix(NAVY, IVORY, pk), Color(0, 0, 0, 0))
		var vk := _ease((t - land - 110) / 24.0)
		var vibe := "VIBE CODED WITH CLAUDE OPUS 5.5"
		if vk > 0.0:
			var vw := Px.measure_small(vibe)
			var vx := 160 - (vw >> 1) + 5
			Px.small(self, vibe, vx, 164, Px.mix(NAVY, ORANGE, vk))
			if _spark_icon == null:
				_spark_icon = IntroCreatures.claude_sprite(4.0, 0, "eyes")
			Px.blit(self, _spark_icon, vx - 12, 161, -1, -1, Color(1, 1, 1, vk))
		for i in 3:
			var ph := (t + i * 37) % 90
			if ph < 16:
				_sparkle(160 + [-26, 24, 18][i], 58 + [-16, -12, 18][i], 2 if ph < 8 else 1, IVORY)
	_hint(Color("#5a6280"), -1)
	if fade_out > 0.0:
		Px.rect(self, 0, 0, Px.W, Px.H, Color(0, 0, 0, minf(1.0, fade_out)))

func _draw_battle(bt: int) -> void:
	var gx: float = scene.gx
	# steam from every fourth tower (screen-space puffs above the 3D roofs)
	for tw in scene.towers:
		if tw.b % 4 == 1:
			var tcx: float = roundf(tw.x0 + 20 - scene.pan * 0.45 + scene.shx) - 20 + (tw.w >> 1)
			for k in 4:
				_pblend(tcx + sin((bt + k * 20) / 14.0) * 3.0, tw.y0 - 4 - ((bt + k * 12) % 26), Color("#9aa4c8"), 0.35)
	# energy-shot twinkles
	if bt >= 160 and bt < 240:
		for i in 5:
			var k := (bt - 160 - i * 9) / 30.0
			if k < 0.0 or k > 1.0:
				continue
			var px := lerpf(gx + 20.0, 238.0, k)
			var py := lerpf(110.0, 124.0, k) - sin(k * PI) * 18.0
			_sparkle(scene.X(px), roundf(py), 2, Color("#b8ffe8") if i % 2 == 1 else Color.WHITE)
	# the lunge's slash where CLAUDE stood
	if bt >= 262 and bt < 276:
		for i in 3:
			_line(scene.X(226 + i * 6), 104, scene.X(246 + i * 6), 134, Color.WHITE, 1.0 - (bt - 262) / 14.0)
	for p in scene.parts:
		if p.battle:
			_sparkle(scene.X(p.x), p.y, 2 if p.life > 8 else 1, p.c)
	# the clash: rays, then white
	if bt >= 352:
		var k2 := (bt - 352) / 24.0
		for i in 16:
			var a := i * PI / 8.0 + 0.2
			var r0 := 10.0 + k2 * 60.0
			var r1 := 30.0 + k2 * 170.0
			var ox: float = scene.X(gx)
			_line(ox + cos(a) * r0, 110 + sin(a) * r0, ox + cos(a) * r1, 110 + sin(a) * r1, ORANGE if i % 2 == 1 else IVORY, maxf(0.0, 1.0 - k2 * 0.6))
		var w := 1.0 if bt < 364 else maxf(0.0, 1.0 - (bt - 364) / 50.0)
		if bt >= 356:
			Px.rect(self, 0, 0, Px.W, Px.H, Color(1, 1, 1, (bt - 356) / 8.0 if bt < 364 else w))
	Px.rect(self, 0, 0, Px.W, scene.TOP, Color.BLACK)
	Px.rect(self, 0, scene.BOT, Px.W, Px.H - scene.BOT, Color.BLACK)
	_hint(Color("#8a90a8"), bt)
	if bt < 16:
		Px.rect(self, 0, 0, Px.W, Px.H, Color(0, 0, 0, 1.0 - bt / 16.0))
