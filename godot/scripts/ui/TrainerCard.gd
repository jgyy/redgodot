class_name TrainerCard
extends PxScreen
## Port of menus.js trainerCard(): gold stripes, the red-framed cream card
## (NAME / ID No. / MONEY / POKéDEX / TIME), the player's real 3D model where
## upstream blits Red's 64px portrait, and the grey badge case with the eight
## pixel badges (lit when earned) numbered 1-8.

const BADGES := ["BOULDERBADGE", "CASCADEBADGE", "THUNDERBADGE", "RAINBOWBADGE", "SOULBADGE", "MARSHBADGE", "VOLCANOBADGE", "EARTHBADGE"]
const SHAPES := [
	["..#..", ".###.", "#####", "#####", ".###."], ["..#..", ".###.", "#####", ".###.", "..#.."], ["#.#.#", ".###.", "##.##", ".###.", "#.#.#"],
	[".#.#.", "#####", "#####", ".###.", "..#.."], [".###.", "#...#", "#.#.#", "#...#", ".###."], ["#####", "#...#", "#.#.#", "#...#", "#####"],
	["..#..", ".#.#.", "#.#.#", ".#.#.", "..#.."], [".###.", "#####", "##.##", "#####", ".###."],
]
const BADGE_COLS := ["#a0a0a8", "#58a8f0", "#f8b830", "#78d078", "#e060a8", "#e8c848", "#f06038", "#58c098"]

var _view: PxView3D

func _ready() -> void:
	super()
	_view = PxView3D.new(64, 64)
	_view.anchor = "bottom"
	_view.yaw = -18.0
	_view.fill = 0.98
	add_child(_view)
	_view.show_character("red")

func _input_event(e: InputEvent) -> bool:
	if pressed(e, "confirm") or pressed(e, "cancel"):
		exit()
		return true
	return false

## menus.js drawBadge(): 5x5 cells of 3x3 px; top two rows get a dark fleck.
static func draw_badge(ci: CanvasItem, i: int, x: int, y: int, has: bool) -> void:
	var rows: Array = SHAPES[i]
	var c := Color(BADGE_COLS[i]) if has else Color("#6a6a7a")
	for j in 5:
		var r: String = rows[j]
		for k in 5:
			if r[k] == "#":
				Px.rect(ci, x + k * 3, y + j * 3, 3, 3, c)
				if has and j < 2:
					Px.pset(ci, x + k * 3, y + j * 3, Px.shade(c, 0.4))

func _draw() -> void:
	Px.menu_bg(self, Color("#d8b060"), Color("#cca050"), t)
	Px.frame(self, 12, 8, 296, 164, "red", Color("#fff8e8"))
	Px.text(self, "TRAINER CARD", 26, 18, Color("#c04040"))
	Px.text_r(self, GameState.version, 296, 18, GameState.version_color(GameState.version).darkened(0.1))   # RED / BLUE / YELLOW
	var rows := [["NAME", GameState.player_name], ["ID No.", "%05d" % GameState.trainer_id],
		["MONEY", "$%d" % GameState.money], ["POKéDEX", str(GameState.caught_species.size())],
		["TIME", GameState.play_time_text()]]
	for i in rows.size():
		Px.text(self, rows[i][0], 26, 38 + i * 15, Color("#8a7a60"))
		Px.text_r(self, rows[i][1], 180, 38 + i * 15)
	_view.draw_at(self, 238 - 32, 104 - 64)
	Px.frame(self, 20, 118, 280, 48, "gray")
	for i in 8:
		var x := 34 + i * 33
		draw_badge(self, i, x, 130, GameState.badges.has(BADGES[i]))
		Px.small(self, str(i + 1), x + 6, 150, Px.INK)
