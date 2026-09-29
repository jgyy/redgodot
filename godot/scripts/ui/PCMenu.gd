class_name PCMenu
extends PxScreen
## Port of pc.js usePC(): "<name> turned on the PC." then BILL's PC (POKéMON
## storage: WITHDRAW / DEPOSIT / RELEASE / CHANGE BOX over 12 boxes of 20) and
## <name>'s PC (item storage: WITHDRAW / DEPOSIT / TOSS with a ×NN quantity
## picker), all as upstream's menus/text boxes over the overworld.
## Call `await pc_menu.use_pc()` (e.g. from the overworld when facing a PC);
## `party_menu` must be set for DEPOSIT.

var party_menu: PartyMenu
var _qty := 0
var _qty_max := 0

func use_pc() -> void:
	visible = true
	busy = true
	UI.sfx("pc_on")
	await say(GameState.player_name + " turned on the PC.")
	while true:
		# pc.js usePC(): SOMEONE's PC until BILL is met, PROF.OAK's PC only with the POKéDEX
		var opts := ["BILL's PC" if Story.flag("EVENT_MET_BILL") else "SOMEONE's PC", GameState.player_name + "'s PC"]
		if Story.flag("EVENT_GOT_POKEDEX"):
			opts.append("PROF.OAK's PC")
		opts.append("LOG OFF")
		var r := await choose(opts, {"x": 150, "y": 20, "w": 164})
		if r < 0 or opts[r] == "LOG OFF":
			UI.sfx("pc_off")
			break
		if r == 0:
			await _bills_pc()
		elif r == 1:
			await _players_pc()
		else:
			await _oak_rating()
	busy = false
	close()
	closed.emit()

func _mon_rows(b: Array) -> Array:
	return b.map(func(m): return "%s  Lv%d" % [m.nickname, m.level])

func _bills_pc() -> void:
	UI.sfx("pc_access")
	await say(("Accessed BILL's PC." if Story.flag("EVENT_MET_BILL") else "Accessed someone's PC.") + "\fAccessed POKéMON Storage System.")
	while true:
		var b := GameState.box()
		var r := await choose(["WITHDRAW PKMN", "DEPOSIT PKMN", "RELEASE PKMN", "CHANGE BOX", "SEE YA!"], {"x": 150, "y": 20, "w": 164})
		if r < 0 or r == 4:
			return
		if r == 0:
			if b.is_empty():
				await say("What? There are no POKéMON here!")
				continue
			if GameState.party.size() >= 6:
				await say("You can't take any more POKéMON.\fDeposit POKéMON first.")
				continue
			var i := await choose(_mon_rows(b), {"x": 100, "y": 4, "w": 214})
			if i < 0:
				continue
			var m: GameState.PartyMon = b[i]
			b.remove_at(i)
			GameState.party.append(m)
			GameState.party_changed.emit()
			await say(m.nickname + " is taken out.\fGot " + m.nickname + ".")
		elif r == 1:
			if GameState.party.size() <= 1:
				await say("You can't deposit the last POKéMON!")
				continue
			if b.size() >= 20:
				await say("Oops! This box is full of POKéMON.")
				continue
			var i2 := await _pick_party("Deposit which POKéMON?")
			if i2 < 0:
				continue
			var m2: GameState.PartyMon = GameState.party[i2]
			GameState.party.remove_at(i2)
			b.append(m2)
			GameState.party_changed.emit()
			await say(m2.nickname + " was stored in Box %d." % (GameState.current_box + 1))
		elif r == 2:
			if b.is_empty():
				await say("What? There are no POKéMON here!")
				continue
			var i3 := await choose(_mon_rows(b), {"x": 100, "y": 4, "w": 214})
			if i3 < 0:
				continue
			var nm: String = b[i3].nickname
			if await ask("Once released, " + nm + " is gone forever. OK?"):
				b.remove_at(i3)
				await say(nm + " was released outside.\fBye " + nm + "!")
		elif r == 3:
			var boxes: Array = []
			for k in 12:
				var c := GameState.box(k).size()
				boxes.append("BOX %d%s" % [k + 1, (" (%d)" % c) if c > 0 else ""])
			var i4 := await choose(boxes, {"x": 180, "y": 2, "w": 134})
			if i4 >= 0:
				GameState.current_box = i4
				await say("Switched to BOX %d." % (i4 + 1))

func _pick_party(msg: String) -> int:
	if party_menu == null:
		return await choose(GameState.party.map(func(m): return m.nickname), {"x": 150, "y": 20})
	busy = true
	party_menu.open_with({"msg": msg, "pick": func(_m, _i, _ps): return true})
	var i: int = await party_menu.picked
	busy = false
	return i

func _item_rows(d: Dictionary) -> Array:
	return d.keys().map(func(id): return "%s ×%d" % [BagMenu.item_name(id), int(d[id])])

func _players_pc() -> void:
	UI.sfx("pc_access")
	await say("Accessed my PC.\fAccessed Item Storage System.")
	while true:
		var r := await choose(["WITHDRAW ITEM", "DEPOSIT ITEM", "TOSS ITEM", "LOG OFF"], {"x": 150, "y": 20, "w": 164})
		if r < 0 or r == 3:
			return
		var pc := GameState.pc_items
		if r == 0 or r == 2:
			if pc.is_empty():
				await say("There is nothing stored.")
				continue
			var i := await choose(_item_rows(pc), {"x": 110, "y": 4, "w": 204})
			if i < 0:
				continue
			var id: String = pc.keys()[i]
			if r == 2:
				if BagMenu.is_key(id):
					await say("That's too important to toss!")
				elif await ask("Is it OK to toss " + BagMenu.item_name(id) + "?"):
					pc.erase(id)
				continue
			var q := await quantity(int(pc[id]))
			if q <= 0:
				continue
			if not Story.bag_add(id, q):
				await say("You can't carry any more items.")
				continue
			pc[id] = int(pc[id]) - q
			if int(pc[id]) <= 0:
				pc.erase(id)
			await say("Withdrew " + BagMenu.item_name(id) + ".")
		else:
			if GameState.bag.is_empty():
				await say("You have nothing to deposit.")
				continue
			var i2 := await choose(_item_rows(GameState.bag), {"x": 110, "y": 4, "w": 204})
			if i2 < 0:
				continue
			var id2: String = GameState.bag.keys()[i2]
			var q2 := await quantity(int(GameState.bag[id2]))
			if q2 <= 0:
				continue
			pc[id2] = int(pc.get(id2, 0)) + q2
			GameState.bag[id2] = int(GameState.bag[id2]) - q2
			if int(GameState.bag[id2]) <= 0:
				GameState.bag.erase(id2)
			await say(BagMenu.item_name(id2) + " was stored via PC.")

## pc.js quantity(): ×NN picker at (254, 104); returns 0 when cancelled.
func quantity(mx: int) -> int:
	_qty = 1
	_qty_max = mx
	busy = true
	queue_redraw()
	var result := 0
	await get_tree().process_frame   # skip the frame of the A press that chose the item (it would confirm ×1 at once)
	while true:
		await get_tree().process_frame
		if Input.is_action_just_pressed("move_up"):
			_qty = 1 if _qty >= _qty_max else _qty + 1
		elif Input.is_action_just_pressed("move_down"):
			_qty = _qty_max if _qty <= 1 else _qty - 1
		elif Input.is_action_just_pressed("move_right"):
			_qty = mini(_qty_max, _qty + 10)
		elif Input.is_action_just_pressed("move_left"):
			_qty = maxi(1, _qty - 10)
		elif Input.is_action_just_pressed("confirm"):
			result = _qty
			break
		elif Input.is_action_just_pressed("cancel"):
			break
	_qty_max = 0
	busy = false
	return result

func _oak_rating() -> void:
	var seen := GameState.seen_species.size()
	var own := GameState.caught_species.size()
	await say("POKéDEX completion is:\f%d POKéMON seen\f%d POKéMON owned\fPROF.OAK's rating:" % [seen, own])
	var lo := mini(150, (own / 10) * 10)
	var label := "DexRatingText_Own150To151" if lo >= 150 else "DexRatingText_Own%dTo%d" % [lo, lo + 9]
	await say(GameText.get_text(label, "Keep it up!"))

func _draw() -> void:
	if _qty_max > 0:
		var w := 60
		Px.frame(self, 314 - w, 104, w, 22)
		Px.text(self, "×%02d" % _qty, 324 - w, 111)
