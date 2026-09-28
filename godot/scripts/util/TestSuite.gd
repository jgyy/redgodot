class_name TestSuite
extends RefCounted
## Minimal in-engine test suite (no external addons). Run via the normal project
## boot so autoloads (GameData/GameState/SceneRouter) are guaranteed initialized:
##   godot4 --headless --rendering-driver opengl3 --path godot -- --run-tests
## See Main.gd for the entry point. Exits process code 0 on pass, 1 on failure.

var passed := 0
var failures: Array = []

func check(cond: bool, label: String) -> void:
	if cond:
		passed += 1
	else:
		failures.append(label)

func run_all(tree: SceneTree) -> void:
	check(GameData != null, "GameData autoload present")
	check(GameData.species.size() == 151, "151 species loaded (got %d)" % GameData.species.size())
	check(GameData.moves.size() > 0, "moves loaded (%d)" % GameData.moves.size())
	check(GameData.maps.size() == 223, "223 maps loaded (got %d)" % GameData.maps.size())
	check(GameData.mon_art.has("PIKACHU"), "PIKACHU vector art present")
	check(GameData.cast.has("red"), "cast has 'red'")

	_test_type_chart()
	_test_damage_formula()
	_test_height_scaling()
	_test_map_classification(tree)
	_test_encounter_table()
	_test_party_mon()
	_test_lighting_and_clock()
	_test_dialogue_text()
	_test_save_load()
	_test_new_game_defaults()
	AudioTests.run(self)

func _test_type_chart() -> void:
	check(GameData.type_multiplier("WATER", ["FIRE"]) == 2.0, "WATER is super effective vs FIRE")
	check(GameData.type_multiplier("FIRE", ["WATER"]) == 0.5, "FIRE is not very effective vs WATER")
	check(GameData.type_multiplier("NORMAL", ["GHOST"]) == 0.0, "NORMAL has no effect on GHOST")
	check(GameData.type_multiplier("NORMAL", ["NORMAL"]) == 1.0, "NORMAL vs NORMAL is neutral")

func _test_damage_formula() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	var dmg := BattleMath.calc_damage(10, 35, 15, 15, "NORMAL", ["NORMAL"], ["GRASS"], false, rng)
	check(dmg > 0, "non-zero damage for a valid attack (got %d)" % dmg)
	check(dmg < 50, "damage is sane for a low-level Tackle (got %d)" % dmg)

	var zero_power := BattleMath.calc_damage(10, 0, 15, 15, "NORMAL", [], [], false, rng)
	check(zero_power == 0, "zero-power move deals zero damage")

	# Compare crit vs non-crit with identically-seeded RNGs (so the final
	# 217-255/255 random factor draw matches) and identical types, isolating
	# the level-doubling effect the formula gives critical hits.
	var rng_a := RandomNumberGenerator.new(); rng_a.seed = 7
	var rng_b := RandomNumberGenerator.new(); rng_b.seed = 7
	var normal_dmg := BattleMath.calc_damage(10, 35, 15, 15, "NORMAL", ["NORMAL"], ["GRASS"], false, rng_a)
	var crit_dmg := BattleMath.calc_damage(10, 35, 15, 15, "NORMAL", ["NORMAL"], ["GRASS"], true, rng_b)
	check(crit_dmg >= normal_dmg, "critical hit deals at least as much damage (%d vs %d)" % [crit_dmg, normal_dmg])

	var stab_dmg := BattleMath.calc_damage(10, 35, 15, 15, "FIRE", ["FIRE"], ["NORMAL"], false, rng)
	var no_stab_dmg := BattleMath.calc_damage(10, 35, 15, 15, "FIRE", ["WATER"], ["NORMAL"], false, rng)
	check(stab_dmg >= no_stab_dmg, "same-type attack bonus increases damage")

func _test_height_scaling() -> void:
	var h := GameData.species_height_m("PIKACHU")
	check(h > 0.1 and h < 3.0, "Pikachu height is sane (got %.2fm)" % h)

func _test_map_classification(tree: SceneTree) -> void:
	# MapLoader.load_map() only needs to be a valid Node (its GridMap child is
	# parented to it directly); it doesn't need to be inside the live tree for
	# this check, which avoids "parent busy" issues while Main is still in _ready().
	var ml := MapLoader.new()
	var ok := ml.load_map("PalletTown")
	check(ok, "PalletTown loads")
	check(ml.width == 20 and ml.height == 18, "PalletTown dimensions match source data (20x18)")
	check(not ml.warp_at(Vector2i(5, 5)).is_empty(), "PalletTown has a warp at (5,5) -> Red's house")
	ml.free()

func _test_encounter_table() -> void:
	var table := EncounterSystem.wild_table_for_map("Route1")
	check(table.get("rate", 0) == 25, "Route1 grass encounter rate matches source data (25)")
	check(table.get("mons", []).size() == 10, "Route1 has the classic 10-slot wild table")

func _test_party_mon() -> void:
	var m := GameState.PartyMon.new("PIKACHU", 10)
	check(m.max_hp > 0, "PartyMon computes positive max HP")
	check(m.hp == m.max_hp, "new PartyMon starts at full HP")
	check(not m.moves.is_empty(), "new PartyMon has starting moves")
	check(not m.is_fainted(), "fresh PartyMon is not fainted")
	m.hp = 0
	check(m.is_fainted(), "0 HP PartyMon is fainted")

func _test_lighting_and_clock() -> void:
	check(GameState.time_period(12.0 * 60.0) == "day", "noon is day")
	check(GameState.time_period(19.0 * 60.0) == "dusk", "7 PM is dusk")
	check(GameState.time_period(23.0 * 60.0) == "night", "11 PM is night")
	check(GameState.time_period(0.0) == "night", "midnight is night")
	for period in LightingRig.periods():
		check(LightingRig.PRESETS.has(period), "LightingRig has a preset for %s" % period)
	var env := Environment.new()
	LightingRig.apply(null, env, "night")
	var night_bg := env.background_color
	LightingRig.apply(null, env, "day")
	check(env.background_color != night_bg, "day/night presets produce different sky colors")

func _test_dialogue_text() -> void:
	check(DialogueText.is_humanoid_sprite("oak"), "oak is a talkable NPC sprite")
	check(not DialogueText.is_humanoid_sprite("poke_ball"), "poke_ball is a non-humanoid prop sprite")
	check(not DialogueText.for_obj({"sprite": "oak"}).is_empty(), "oak has curated dialogue lines")
	check(not DialogueText.for_obj({"sprite": "totally_unknown_sprite_xyz"}).is_empty(),
		"unknown NPC sprites still get a fallback line")
	var sign_lines := DialogueText.for_sign({"textLabel": "PalletTownOaksLabSignText"}, "PalletTown")
	check(sign_lines[0].findn("OAKS LAB") >= 0, "sign text humanizes its label (got: %s)" % sign_lines[0])

func _test_save_load() -> void:
	var saved_party := GameState.party
	var saved_map := GameState.current_map
	GameState.new_game("BULBASAUR")
	GameState.current_map = "Route1"
	GameState.player_cell = Vector2i(3, 4)
	var ok := GameState.save()
	check(ok, "GameState.save() succeeds")
	GameState.current_map = "PewterCity"
	var loaded := GameState.load_save()
	check(loaded, "GameState.load_save() succeeds")
	check(GameState.current_map == "Route1", "load_save() restores current_map")
	check(GameState.player_cell == Vector2i(3, 4), "load_save() restores player_cell")
	check(not GameState.party.is_empty() and GameState.party[0].species_id == "BULBASAUR",
		"load_save() restores the party")
	GameState.party = saved_party
	GameState.current_map = saved_map

func _test_new_game_defaults() -> void:
	GameState.new_game("SQUIRTLE")
	check(GameState.bag.get("POKE_BALL", 0) > 0, "new_game() starts with POKE_BALLs")
	check(GameState.bag.has("TOWN_MAP"), "new_game() starts with a TOWN MAP")
	check(GameState.seen_species.has("SQUIRTLE"), "picking a starter marks it seen")
	check(GameState.caught_species.has("SQUIRTLE"), "picking a starter marks it caught")
