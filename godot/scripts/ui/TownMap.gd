class_name TownMap
extends Control
## The Town Map (reached from the bag's TOWN MAP item, the real mechanic):
## lays out Kanto's 36 outdoor maps by BFS-walking their real `conns` graph
## from mapdata.json (no hardcoded geometry), marking the player's current
## location.

signal closed

const CELL := 30

var _grid_root: Control
var _location_label: Label
var _desc_label: Label
var _nodes: Dictionary = {}   # map name -> Panel

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(620, 420)
	panel.position = Vector2(-310, -210)
	add_child(panel)

	var root := HBoxContainer.new()
	panel.add_child(root)

	_grid_root = Control.new()
	_grid_root.custom_minimum_size = Vector2(420, 400)
	root.add_child(_grid_root)

	var right := VBoxContainer.new()
	root.add_child(right)
	var title := Label.new()
	title.text = "TOWN MAP"
	title.add_theme_font_size_override("font_size", 20)
	right.add_child(title)
	_location_label = Label.new()
	_location_label.add_theme_font_size_override("font_size", 18)
	right.add_child(_location_label)
	_desc_label = Label.new()
	_desc_label.text = "KANTO region.\nYour location blinks in red."
	_desc_label.autowrap_mode = TextServer.AUTOWRAP_WORD
	_desc_label.custom_minimum_size = Vector2(160, 100)
	right.add_child(_desc_label)
	var hint := Label.new()
	hint.text = "(cancel: back)"
	hint.add_theme_font_size_override("font_size", 13)
	right.add_child(hint)

	_build_layout()

func open() -> void:
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_refresh()

func close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE

## BFS over the real route-connection graph (mapdata.json `conns`), starting
## from PalletTown, so layout reflects Kanto's actual adjacency data.
func _build_layout() -> void:
	var coords := {"PalletTown": Vector2i.ZERO}
	var queue := ["PalletTown"]
	var dir_offset := {"north": Vector2i(0, -1), "south": Vector2i(0, 1), "west": Vector2i(-1, 0), "east": Vector2i(1, 0)}
	while not queue.is_empty():
		var name: String = queue.pop_front()
		var here: Vector2i = coords[name]
		var md := GameData.get_map(name)
		for dir in md.get("conns", {}).keys():
			var c: Dictionary = md["conns"][dir]
			var neighbor: String = c.get("map", "")
			if neighbor == "" or coords.has(neighbor):
				continue
			coords[neighbor] = here + dir_offset.get(dir, Vector2i.ZERO)
			queue.append(neighbor)

	var min_x := 0
	var min_y := 0
	for p in coords.values():
		min_x = min(min_x, p.x)
		min_y = min(min_y, p.y)

	for name in coords.keys():
		var p: Vector2i = coords[name]
		var n := PanelContainer.new()
		n.custom_minimum_size = Vector2(CELL - 4, CELL - 4)
		n.position = Vector2((p.x - min_x) * CELL, (p.y - min_y) * CELL)
		var style := StyleBoxFlat.new()
		style.bg_color = Color(0.35, 0.6, 0.35)
		style.set_corner_radius_all(3)
		n.add_theme_stylebox_override("panel", style)
		_grid_root.add_child(n)
		_nodes[name] = n

func _refresh() -> void:
	var current := GameState.current_map
	_location_label.text = _display_name(current)
	for name in _nodes.keys():
		var n: PanelContainer = _nodes[name]
		var style: StyleBoxFlat = n.get_theme_stylebox("panel")
		style = style.duplicate()
		style.bg_color = Color(0.85, 0.2, 0.2) if name == current else Color(0.35, 0.6, 0.35)
		n.add_theme_stylebox_override("panel", style)

static func _display_name(map_name: String) -> String:
	var words := []
	var cur := ""
	for i in range(map_name.length()):
		var ch := map_name[i]
		if ch == ch.to_upper() and ch != ch.to_lower() and cur != "":
			words.append(cur)
			cur = ch
		else:
			cur += ch
	if cur != "":
		words.append(cur)
	return " ".join(words).to_upper()

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("cancel") or event.is_action_pressed("confirm"):
		close()
		closed.emit()
		get_viewport().set_input_as_handled()
