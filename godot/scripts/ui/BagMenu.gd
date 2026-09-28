class_name BagMenu
extends Control
## Item bag (Start Menu's ITEM entry): lists GameState.bag with counts and a
## description for the selected item. Confirming the TOWN MAP item opens the
## Town Map screen — the same real mechanic the original game uses (Town Map
## isn't its own start-menu row; it's a held Key Item).

signal closed
signal item_selected(item_id: String)

const DESCRIPTIONS := {
	"POTION": "Restores 20 HP to one POKéMON.",
	"SUPER_POTION": "Restores 50 HP to one POKéMON.",
	"MAX_POTION": "Fully restores a POKéMON's HP.",
	"POKE_BALL": "A device for catching wild POKéMON.",
	"GREAT_BALL": "A good, high-performance BALL.",
	"ULTRA_BALL": "An ultra-high-performance BALL.",
	"MASTER_BALL": "The best BALL that catches any wild POKéMON without fail.",
	"REVIVE": "Revives a fainted POKéMON with half HP.",
	"ESCAPE_ROPE": "Use to escape instantly from a cave or dungeon.",
	"ANTIDOTE": "Heals a poisoned POKéMON.",
	"BURN_HEAL": "Heals a POKéMON of a burn.",
	"ICE_HEAL": "Defrosts a frozen POKéMON.",
	"AWAKENING": "Awakens a sleeping POKéMON.",
	"FULL_HEAL": "Heals all status problems.",
	"TOWN_MAP": "Can be viewed anytime. Shows the whole KANTO region.",
}
const DEFAULT_DESCRIPTION := "A useful item."

var _list: VBoxContainer
var _desc_label: Label
var _rows: Array = []
var _index := 0
var _item_ids: Array = []

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(380, 320)
	panel.position = Vector2(-190, -160)
	add_child(panel)

	var root := VBoxContainer.new()
	panel.add_child(root)
	var title := Label.new()
	title.text = "ITEMS"
	title.add_theme_font_size_override("font_size", 20)
	root.add_child(title)
	_list = VBoxContainer.new()
	root.add_child(_list)

	var desc_panel := PanelContainer.new()
	root.add_child(desc_panel)
	_desc_label = Label.new()
	_desc_label.autowrap_mode = TextServer.AUTOWRAP_WORD
	_desc_label.custom_minimum_size = Vector2(360, 48)
	desc_panel.add_child(_desc_label)

	var hint := Label.new()
	hint.text = "(confirm: use/view, cancel: back)"
	hint.add_theme_font_size_override("font_size", 13)
	root.add_child(hint)

func open() -> void:
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_index = 0
	_refresh()

func close() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _refresh() -> void:
	for c in _list.get_children():
		c.queue_free()
	_rows.clear()
	_item_ids = GameState.bag.keys()
	for i in range(_item_ids.size()):
		var iid: String = _item_ids[i]
		var item: Dictionary = GameData.items.get(iid, {})
		var l := Label.new()
		var prefix := "▶ " if i == _index else "   "
		l.text = "%s%-16s x%d" % [prefix, item.get("name", iid), GameState.bag[iid]]
		_list.add_child(l)
		_rows.append(l)
	_desc_label.text = DESCRIPTIONS.get(_item_ids[_index], DEFAULT_DESCRIPTION) if not _item_ids.is_empty() else "(bag is empty)"

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if _item_ids.is_empty():
		if event.is_action_pressed("cancel"):
			close(); closed.emit(); get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("move_up"):
		_index = (_index - 1 + _item_ids.size()) % _item_ids.size()
		_refresh()
	elif event.is_action_pressed("move_down"):
		_index = (_index + 1) % _item_ids.size()
		_refresh()
	elif event.is_action_pressed("confirm"):
		item_selected.emit(_item_ids[_index])
	elif event.is_action_pressed("cancel"):
		close()
		closed.emit()
	else:
		return
	get_viewport().set_input_as_handled()
