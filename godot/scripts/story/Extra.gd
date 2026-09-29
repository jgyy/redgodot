extends RefCounted
## Port of upstream src/scripts/extra.js: the Route 5 Day Care (Gen I: the stored
## Pokémon gains 1 EXP per step; Story.on_step counts GameState.daycare.steps).

func register() -> void:
	Story.def_map("Daycare", {"talk": {"DAYCARE_GENTLEMAN": _gentleman}})

func _growth(sp: String) -> String:
	return str(GameData.get_species(sp).get("growth", "MEDIUM_FAST"))

func _gentleman(_o: Dictionary) -> void:
	var dc: Dictionary = GameState.daycare
	if not dc.is_empty():
		var m: GameState.PartyMon = GameState.PartyMon.from_dict(dc["mon"])
		var start_lv := m.level
		m.xp += int(dc.get("steps", 0))
		while m.level < 100 and m.xp >= GameState.exp_for_level(_growth(m.species_id), m.level + 1):
			m.level += 1
		var old_moves: Array = m.moves.duplicate()
		var nick := m.nickname
		var xp := m.xp
		var status := m.status
		m = GameState.PartyMon.new(m.species_id, m.level)  # recalc stats at the new level, full HP
		m.nickname = nick
		m.xp = xp
		m.status = status
		m.moves = old_moves
		for mv in m.moves:
			m.pp[mv] = int(GameData.get_move(mv).get("pp", 0))
		Story.setvar("wNameBuffer", m.nickname)
		Story.setvar("wDayCareMonName", m.nickname)
		var grown := m.level - start_lv
		if int(dc.get("steps", 0)) == 0:
			await Story.say("DaycareGentlemanMonNeedsMoreTimeText")
			return
		if grown > 0:
			Story.setvar("wDayCareNumLevelsGrown", grown)
			await Story.say("DaycareGentlemanMonHasGrownText")
		var cost := 100 + 100 * grown
		Story.setvar("wDayCareTotalCost", cost)
		if not await Story.ask(Story.fmt(Story.t("DaycareGentlemanOweMoneyText")) + "\fWant it back?"):
			await Story.say("DaycareGentlemanAllRightThenText")
			await Story.say("DaycareGentlemanComeAgainText")
			return
		if GameState.party.size() >= 6:
			await Story.say("DaycareGentlemanNoRoomForMonText")
			return
		if GameState.money < cost:
			await Story.say("DaycareGentlemanNotEnoughMoneyText")
			return
		GameState.money -= cost
		# learn level-up moves it would have learned
		var learn: Array = GameData.get_species(m.species_id).get("learn", [])
		for lv in range(start_lv + 1, m.level + 1):
			for e in learn:
				if int(e[0]) == lv and not m.moves.has(e[1]):
					if m.moves.size() >= 4:
						m.moves.pop_front()
					m.moves.append(e[1])
					m.pp[e[1]] = int(GameData.get_move(e[1]).get("pp", 0))
		GameState.party.append(m)
		GameState.party_changed.emit()
		GameState.daycare = {}
		await Story.say("DaycareGentlemanHeresYourMonText")
		Story.sfx("get_mon")
		await Story.say("DaycareGentlemanGotMonBackText")
		return
	if not await Story.ask("DaycareGentlemanIntroText"):
		await Story.say("DaycareGentlemanAllRightThenText")
		await Story.say("DaycareGentlemanComeAgainText")
		return
	if GameState.party.size() <= 1:
		await Story.say("DaycareGentlemanOnlyHaveOneMonText")
		return
	await Story.say("DaycareGentlemanWhichMonText")
	var i := await Story.party_screen("Leave which POKéMON?")
	if i < 0:
		await Story.say("DaycareGentlemanAllRightThenText")
		await Story.say("DaycareGentlemanComeAgainText")
		return
	var pm: GameState.PartyMon = GameState.party[i]
	for mv in pm.moves:
		if GameData.hm_moves.has(mv):
			await Story.say("DaycareGentlemanCantAcceptMonWithHMText")
			return
	GameState.party.remove_at(i)
	GameState.party_changed.emit()
	GameState.daycare = {"mon": pm.to_dict(), "steps": 0}
	Story.setvar("wNameBuffer", pm.nickname)
	await Story.say("DaycareGentlemanWillLookAfterMonText")
	await Story.say("DaycareGentlemanComeSeeMeInAWhileText")
