class_name Px
extends RefCounted
## Pixel-UI drawing kit mirroring upstream pokemon-claude-red's Surface / ui.js
## API (rect, pset, text with its 3-pixel drop shadow, frame(), cursor, small
## digits) so every 2D overlay can be ported with upstream's exact 320x180
## coordinates. Draw from a PxCanvas's _draw() (logical 320x180, scaled 3x).
##
## Fonts are upstream's own hand-drawn glyphs, baked by
## pipeline/scripts/bake_font.js into BMFont files Godot imports natively.

const W := 320
const H := 180

const FONT: FontFile = preload("res://assets/ui/pxfont.fnt")
const FONT_SMALL: FontFile = preload("res://assets/ui/pxfont_small.fnt")
const FONT_SIZE := 10
const FONT_SMALL_SIZE := 6
const LINE := 14

const INK := Color("#3a3a4c")
const INK_SH := Color("#d6d4cc")
const PAPER := Color("#fbfaf4")
const PAPER2 := Color("#f1efe4")
const RED := Color("#d04a4a")
const OUTLINE := Color("#1b1a2e")

## ui.js THEMES: [outline, dark band, mid band, light bevel, rivet]
const THEMES := {
	"blue": [Color("#1b1a2e"), Color("#3b4f96"), Color("#5c7fd0"), Color("#9fbff0"), Color("#dfeaff")],
	"red": [Color("#1b1a2e"), Color("#8a2a3a"), Color("#d04a4a"), Color("#f09a8a"), Color("#ffe4dc")],
	"green": [Color("#1b1a2e"), Color("#2a6a4a"), Color("#4aa06a"), Color("#9ad8a0"), Color("#e0f8e0")],
	"gray": [Color("#1b1a2e"), Color("#4a4e62"), Color("#7a7f96"), Color("#b8bccc"), Color("#eceef4")],
	"dark": [Color("#0d0c16"), Color("#2a2a40"), Color("#3a3a58"), Color("#5a5a80"), Color("#8a8ab0")],
}

## Type colors used by upstream's summary/move screens (menus.js TYPE_COL).
const TYPE_COLORS := {
	"NORMAL": Color("#a8a878"), "FIRE": Color("#f08030"), "WATER": Color("#6890f0"),
	"ELECTRIC": Color("#f8d030"), "GRASS": Color("#78c850"), "ICE": Color("#98d8d8"),
	"FIGHTING": Color("#c03028"), "POISON": Color("#a040a0"), "GROUND": Color("#e0c068"),
	"FLYING": Color("#a890f0"), "PSYCHIC": Color("#f85888"), "BUG": Color("#a8b820"),
	"ROCK": Color("#b8a038"), "GHOST": Color("#705898"), "DRAGON": Color("#7038f8"),
}

static var theme_name := "blue"

static func _static_init() -> void:
	# Never let the text server substitute a system/emoji glyph (e.g. for ▶).
	for f: FontFile in [FONT, FONT_SMALL]:
		f.allow_system_fallback = false

# ---------------------------------------------------------------- primitives
static func rect(ci: CanvasItem, x: float, y: float, w: float, h: float, c: Color) -> void:
	if w <= 0 or h <= 0:
		return
	ci.draw_rect(Rect2(floorf(x), floorf(y), floorf(w), floorf(h)), c)

static func pset(ci: CanvasItem, x: float, y: float, c: Color) -> void:
	ci.draw_rect(Rect2(floorf(x), floorf(y), 1, 1), c)

static func hline(ci: CanvasItem, x: float, y: float, w: float, c: Color) -> void:
	rect(ci, x, y, w, 1, c)

static func vline(ci: CanvasItem, x: float, y: float, h: float, c: Color) -> void:
	rect(ci, x, y, 1, h, c)

## Outline-only rectangle.
static func box(ci: CanvasItem, x: float, y: float, w: float, h: float, c: Color) -> void:
	hline(ci, x, y, w, c)
	hline(ci, x, y + h - 1, w, c)
	vline(ci, x, y, h, c)
	vline(ci, x + w - 1, y, h, c)

# ---------------------------------------------------------------- text
## Width in pixels, same as font.measure() (no trailing gap). Multi-line aware.
static func measure(s: String) -> int:
	var best := 0
	for line in s.split("\n"):
		var w := 0
		for i in line.length():
			w += int(FONT.get_char_size(line.unicode_at(i), FONT_SIZE).x)
		best = maxi(best, w - 1)
	return maxi(best, 0)

static func measure_small(s: String) -> int:
	var w := 0
	for i in s.length():
		w += int(FONT_SMALL.get_char_size(s.unicode_at(i), FONT_SMALL_SIZE).x)
	return maxi(w - 1, 0)

## font.draw(): (x, y) is the glyph box's top-left. Returns the end x.
## Pass shadow = Color(0,0,0,0) for no shadow.
static func text(ci: CanvasItem, s: String, x: float, y: float, color: Color = INK, shadow: Color = INK_SH) -> int:
	var ix := floorf(x)
	var iy := floorf(y)
	var lines := s.split("\n")
	var end_x := int(ix)
	for li in lines.size():
		var ly := iy + li * LINE
		var pos := Vector2(ix, ly + 8)  # BMFont base = 8
		if shadow.a > 0.0:
			ci.draw_string(FONT, pos + Vector2(1, 0), lines[li], HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, shadow)
			ci.draw_string(FONT, pos + Vector2(0, 1), lines[li], HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, shadow)
			ci.draw_string(FONT, pos + Vector2(1, 1), lines[li], HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, shadow)
		ci.draw_string(FONT, pos, lines[li], HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, color)
		end_x = int(ix) + measure(lines[li]) + 1
	return end_x

## Right-aligned text ending at x_right (exclusive).
static func text_r(ci: CanvasItem, s: String, x_right: float, y: float, color: Color = INK, shadow: Color = INK_SH) -> int:
	return text(ci, s, x_right - measure(s), y, color, shadow)

## Centered text around cx.
static func text_c(ci: CanvasItem, s: String, cx: float, y: float, color: Color = INK, shadow: Color = INK_SH) -> int:
	return text(ci, s, cx - floorf(measure(s) / 2.0), y, color, shadow)

## font.drawOutlined(): 8-neighbour outline then the text.
static func text_outlined(ci: CanvasItem, s: String, x: float, y: float, color: Color, outline: Color) -> void:
	for oy in [-1, 0, 1]:
		for ox in [-1, 0, 1]:
			if ox != 0 or oy != 0:
				text(ci, s, x + ox, y + oy, outline, Color(0, 0, 0, 0))
	text(ci, s, x, y, color, Color(0, 0, 0, 0))

## font.drawSmall(): compact 3x5 digits/caps (levels, HP numbers). Shadow is 1px diagonal.
static func small(ci: CanvasItem, s: String, x: float, y: float, color: Color = INK, shadow: Color = Color(0, 0, 0, 0)) -> int:
	var pos := Vector2(floorf(x), floorf(y) + 5)
	if shadow.a > 0.0:
		ci.draw_string(FONT_SMALL, pos + Vector2(1, 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SMALL_SIZE, shadow)
	ci.draw_string(FONT_SMALL, pos, s, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SMALL_SIZE, color)
	return int(floorf(x)) + measure_small(s) + 1

## font.wrap(): greedy word wrap to max_w pixels, '\n' = hard break.
static func wrap_text(s: String, max_w: int) -> PackedStringArray:
	var out := PackedStringArray()
	for para in s.split("\n"):
		var line := ""
		for wd in para.split(" "):
			var t := wd if line == "" else line + " " + wd
			if measure(t) > max_w and line != "":
				out.append(line)
				line = wd
			else:
				line = t
		out.append(line)
	return out

# ---------------------------------------------------------------- ui.js
## ui.js frame(): rounded outline, 3px themed bevel band, paper fill with a
## PAPER2 inner top/left edge, corner rivets. fill = null -> hollow.
static func frame(ci: CanvasItem, x: int, y: int, w: int, h: int, theme: String = "", fill: Variant = PAPER) -> void:
	var T: Array = THEMES.get(theme if theme != "" else theme_name, THEMES["blue"])
	# outer outline (corners rounded by one pixel)
	hline(ci, x + 2, y, w - 4, T[0])
	hline(ci, x + 2, y + h - 1, w - 4, T[0])
	vline(ci, x, y + 2, h - 4, T[0])
	vline(ci, x + w - 1, y + 2, h - 4, T[0])
	for p in [Vector2i(1, 1), Vector2i(w - 2, 1), Vector2i(1, h - 2), Vector2i(w - 2, h - 2)]:
		pset(ci, x + p.x, y + p.y, T[0])
	# band ring 0: light top/left, dark bottom/right (ring corners are the outline pixels above)
	hline(ci, x + 2, y + 1, w - 4, T[3])
	vline(ci, x + 1, y + 2, h - 4, T[3])
	hline(ci, x + 2, y + h - 2, w - 4, T[1])
	vline(ci, x + w - 2, y + 2, h - 4, T[1])
	# ring 1 (mid) and ring 2 (dark)
	box(ci, x + 2, y + 2, w - 4, h - 4, T[2])
	box(ci, x + 3, y + 3, w - 6, h - 6, T[1])
	if fill != null:
		var f: Color = fill
		rect(ci, x + 4, y + 4, w - 8, h - 8, f)
		hline(ci, x + 4, y + 4, w - 8, PAPER2)
		vline(ci, x + 4, y + 4, h - 8, PAPER2)
	pset(ci, x + 2, y + 2, T[4])
	pset(ci, x + w - 3, y + 2, T[3])
	pset(ci, x + 2, y + h - 3, T[3])
	pset(ci, x + w - 3, y + h - 3, T[1])

## Blinking ▶ selection cursor (ui.js cursor()); t = frame counter (60 fps).
static func cursor(ci: CanvasItem, x: float, y: float, t: int) -> void:
	text(ci, "▶", x + (1 if (t / 16) % 2 == 1 else 0), y, INK, INK_SH)

## Frame counter at upstream's 60 fps, for blink/bob timing.
static func frame_count() -> int:
	return int(Time.get_ticks_msec() * 60 / 1000)

## Upstream's standard dialogue box geometry (ui.js BOX).
const BOX := Rect2i(6, 128, 308, 48)
const BOX_LINE_H := 15
const BOX_TEXT_W := 308 - 24

## ui.js paginate(): '\f' forces a page break, 2 lines per page.
static func paginate(s: String) -> Array:
	var pages: Array = []
	for chunk in s.split("\f"):
		var lines := wrap_text(chunk, BOX_TEXT_W)
		var i := 0
		while i < lines.size():
			var page: Array = [lines[i]]
			if i + 1 < lines.size():
				page.append(lines[i + 1])
			pages.append(page)
			i += 2
	return pages

## Draws a TextBox page with `chars` characters revealed and the red ▼ prompt
## when `prompt` is true (TextBox.draw()).
static func text_box(ci: CanvasItem, page: Array, chars: int, prompt: bool, t: int, theme: String = "") -> void:
	frame(ci, BOX.position.x, BOX.position.y, BOX.size.x, BOX.size.y, theme)
	var left := chars
	var y := BOX.position.y + 10
	for ln in page:
		var line: String = ln
		text(ci, line.substr(0, maxi(0, left)), BOX.position.x + 12, y)
		left -= line.length() + 1
		y += BOX_LINE_H
	if prompt and (t / 20) % 2 == 0:
		text(ci, "▼", BOX.position.x + BOX.size.x - 18, BOX.position.y + BOX.size.y - 13 + ((t / 10) % 2), RED, INK_SH)

## ui.js Menu.draw(): framed list with ▶ cursor; returns the frame rect.
static func menu(ci: CanvasItem, items: Array, sel: int, x: int, y: int, w: int = -1, rows: int = -1, top: int = 0, t: int = 0, theme: String = "") -> Rect2i:
	if w < 0:
		var mw := 0
		for it in items:
			mw = maxi(mw, measure(str(it)))
		w = mw + 30
	if rows < 0:
		rows = items.size()
	var h := rows * 15 + 12
	frame(ci, x, y, w, h, theme)
	for k in rows:
		var i := top + k
		if i >= items.size():
			break
		text(ci, str(items[i]), x + 18, y + 8 + k * 15)
		if i == sel:
			cursor(ci, x + 8, y + 8 + k * 15, t)
	var blink := (t / 20) % 2
	if top > 0:
		text(ci, "▲", x + w - 14, y + 3 + blink, RED, Color(0, 0, 0, 0))
	if top + rows < items.size():
		text(ci, "▼", x + w - 14, y + h - 13 - blink, RED, Color(0, 0, 0, 0))
	return Rect2i(x, y, w, h)
