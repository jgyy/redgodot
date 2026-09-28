class_name TownMap
extends PxScreen
## Port of townmap.js townMapScreen(): navy stripes, the Kanto minimap baked by
## pipeline/scripts/bake_ui.js from upstream's own build() (every outdoor map's
## real terrain placed by walking the map connections), town squares (light
## when visited), the blinking red player marker, and the TOWN MAP / location
## / help panels. open_fly(options) turns it into the FLY picker and emits
## `fly_chosen(map_name)` ("" if cancelled).

signal fly_chosen(map_name: String)

const TEX: Texture2D = preload("res://assets/ui/townmap.png")
static var _info: Dictionary = {}

var fly_options: Array = []
var fly_sel := 0

static func info() -> Dictionary:
	if _info.is_empty():
		var f := FileAccess.open("res://assets/ui/townmap.json", FileAccess.READ)
		if f:
			_info = JSON.parse_string(f.get_as_text())
	return _info

## The outdoor map the player is on (or last left).
static func current_outdoor() -> String:
	var wh: Dictionary = info().get("where", {})
	if wh.has(GameState.current_map):
		GameState.last_outdoor = GameState.current_map
	return GameState.last_outdoor if wh.has(GameState.last_outdoor) else "PalletTown"

func open() -> void:
	fly_options = []
	super()

func open_fly(options: Array) -> void:
	fly_options = options
	super.open()
	fly_sel = maxi(0, options.find(current_outdoor()))

func _input_event(e: InputEvent) -> bool:
	var fly := not fly_options.is_empty()
	if fly:
		var n := fly_options.size()
		if pressed(e, "move_up", true) or pressed(e, "move_left", true):
			fly_sel = (fly_sel + n - 1) % n
			return true
		if pressed(e, "move_down", true) or pressed(e, "move_right", true):
			fly_sel = (fly_sel + 1) % n
			return true
		if pressed(e, "confirm"):
			close()
			fly_chosen.emit(fly_options[fly_sel])
			return true
		if pressed(e, "cancel"):
			close()
			fly_chosen.emit("")
			return true
		return false
	if pressed(e, "confirm") or pressed(e, "cancel"):
		exit()
		return true
	return false

func _draw() -> void:
	var fly := not fly_options.is_empty()
	var inf := info()
	var wh: Dictionary = inf.get("where", {})
	Px.menu_bg(self, Color("#3a5a8a"), Color("#34527e"), t)
	var mw := TEX.get_width()
	var mh := TEX.get_height()
	var mx := 8
	var my := int(roundf((180 - mh) / 2.0))
	Px.frame(self, mx - 6, my - 6, mw + 12, mh + 12, "gray", null)
	Px.blit(self, TEX, mx, my)
	var cur := current_outdoor()
	GameState.visited[cur] = true
	for n in inf.get("towns", []):
		if not wh.has(n):
			continue
		var x: int = mx + int(wh[n]["x"])
		var y: int = my + int(wh[n]["y"])
		Px.rect(self, x - 2, y - 2, 5, 5, Px.OUTLINE)
		Px.rect(self, x - 1, y - 1, 3, 3, Color("#f8f0d0") if GameState.visited.has(n) else Color("#b0a890"))
	var target: String = fly_options[fly_sel] if fly else cur
	if wh.has(target):
		var px: int = mx + int(wh[target]["x"])
		var py: int = my + int(wh[target]["y"])
		if (t / 12) % 2 == 0 or fly:
			if fly:
				_circle(px, py, 5 + (t >> 3) % 2, Color("#f8d048"))
				_circle(px, py, 4, Px.OUTLINE)
			else:
				_disc(px, py - 1, 3, Color("#e04848"))
				Px.pset(self, px, py - 2, Px.WHITE)
	var ppx := mx + mw + 14
	var pw := 320 - ppx - 6
	Px.frame(self, ppx, 8, pw, 40)
	Px.text(self, "FLY to where?" if fly else "TOWN MAP", ppx + 10, 14)
	var nm: String = wh[target]["name"] if wh.has(target) else ""
	Px.text(self, nm, ppx + 10, 30, Color("#c04040"))
	Px.frame(self, ppx, 52, pw, 120)
	var lines := Px.wrap_text("Choose a town you have visited. A: fly  B: cancel" if fly else "KANTO region. Your location blinks in red.", pw - 20)
	for i in lines.size():
		Px.text(self, lines[i], ppx + 10, 60 + i * 14)

## gfx.disc() / ellipse scanlines.
func _disc(cx: float, cy: float, r: float, c: Color) -> void:
	for y in range(int(floorf(cy - r)), int(ceilf(cy + r)) + 1):
		var dy := (y + 0.5 - cy) / r
		if absf(dy) > 1.0:
			continue
		var hw := r * sqrt(1.0 - dy * dy)
		var x0 := roundf(cx - hw)
		var x1 := roundf(cx + hw)
		if x1 > x0:
			Px.rect(self, x0, y, x1 - x0, 1, c)

## gfx.circle(): midpoint ring.
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
