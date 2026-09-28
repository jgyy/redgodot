class_name BattleNullUI
extends RefCounted
## Instant, scripted implementation of the battle UI protocol (the same
## methods BattleScene.gd implements) for headless engine tests and
## simulations. `actions` is a queue of choose_action() results; when empty it
## picks FIGHT with the first move that has PP. Every message is logged.

var log: Array = []
var actions: Array = []
var yes_no: Array = []   # queued ask_yes_no answers (default true)
var anims: Array = []

func intro(b: BattleEngine) -> void:
	if b.wild:
		log.append("Wild " + b.mon(b.e).display_name() + " appeared!")
	else:
		log.append(b.trainer_name() + " wants to fight!")

func msg(text: String, _opts: Dictionary = {}) -> void:
	log.append(text)

func choose_action(b: BattleEngine) -> Dictionary:
	if not actions.is_empty():
		return actions.pop_front()
	var ml := b.move_list(b.p)
	for i in ml.size():
		if int(ml[i]["pp"]) > 0:
			return {"type": "fight", "slot": i}
	return {"type": "fight", "slot": 0}

func ask_yes_no(_q: String) -> bool:
	return yes_no.pop_front() if not yes_no.is_empty() else true

func choose_index(_items: Array, _prompt: String) -> int:
	return 0

func party_menu(_forced: bool) -> int:
	for i in GameState.party.size():
		if not GameState.party[i].is_fainted():
			return i
	return 0

func refresh() -> void:
	pass

func sync_hp(_side: Variant) -> void:
	pass

func hit_flash(_side: Variant, _eff: float) -> void:
	pass

func faint(_side: Variant) -> void:
	pass

func withdraw(_side: Variant) -> void:
	pass

func send_out(_side: Variant) -> void:
	pass

func exp_bar(_m: Variant, _from: int, _to: int) -> void:
	pass

func level_stats(_m: Variant, _old: Dictionary) -> void:
	pass

func status_anim(_side: Variant, _st: String) -> void:
	pass

func stat_anim(_side: Variant, _up: bool) -> void:
	pass

func anim(move: String, _side: Variant, _hit: int) -> void:
	anims.append(move)

func hide_side(_side: Variant, _h: bool) -> void:
	pass

func substitute(_side: Variant, _on: bool) -> void:
	pass

func transform_to(_side: Variant, _sp: String) -> void:
	pass

func flee(_side: Variant) -> void:
	pass

func trainer_says(text: String) -> void:
	log.append(text)

func dex_entry(_sp: String) -> void:
	pass

func trainer_defeated(b: BattleEngine) -> void:
	log.append(GameState.player_name + " defeated " + b.trainer_name() + "!")
	var money := b.prize_money()
	if money > 0:
		GameState.money += money
		log.append(GameState.player_name + " got $%d for winning!" % money)

func ball_throw(_item: String, _shakes: int, _caught: bool) -> void:
	pass
