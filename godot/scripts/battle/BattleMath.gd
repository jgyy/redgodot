class_name BattleMath
extends RefCounted
## Faithful port of the Gen-1 damage formula from the original game's src/game/battle.js
## (calcDamage). Kept as a small, dependency-free, unit-testable static utility.

## Base critical-hit chance (0..1) before the 256-roll: floor(spd/2), x8 for high-crit moves.
static func crit_chance(speed: int, high_crit: bool) -> float:
	var base: int = int(floor(speed / 2.0))
	if high_crit:
		base *= 8
	return min(255, base) / 256.0

static func roll_crit(speed: int, high_crit: bool, rng: RandomNumberGenerator = null) -> bool:
	var chance := crit_chance(speed, high_crit)
	var roll := (rng.randf() if rng else randf())
	return roll < chance

## atk/def are the *effective* (stage-modified) stats already selected for physical/special.
## attacker_types / defender_types: Array[String] of type ids (e.g. "FIRE", "PSYCHIC_TYPE").
## Returns the final damage (int, >= 0) using the same integer-truncation steps as the original.
static func calc_damage(level: int, power: int, atk: int, def: int, move_type: String,
		attacker_types: Array, defender_types: Array, is_crit: bool, rng: RandomNumberGenerator = null) -> int:
	if power <= 0:
		return 0
	var l: int = level * 2 if is_crit else level
	var stage1: int = int(floor(2.0 * l / 5.0 + 2.0))
	var dmg: int = int(floor(floor(float(stage1) * power * atk / def) / 50.0))
	dmg = min(997, dmg) + 2

	if attacker_types.has(move_type):
		dmg = int(floor(dmg * 1.5))

	var mult := GameData.type_multiplier(move_type, defender_types)
	dmg = int(floor(dmg * mult))

	if dmg > 1:
		var r: int = (rng.randi_range(0, 38) if rng else randi() % 39)
		dmg = int(floor(dmg * (217.0 + r) / 255.0))

	return max(0, dmg)

## Accuracy check, 0..255 style roll ported from accuracyCheck (stat stages simplified out for MVP:
## no accuracy/evasion stage support yet, that's future work like status effects).
static func accuracy_check(move_acc: int, rng: RandomNumberGenerator = null) -> bool:
	var acc: int = int(floor(move_acc * 255.0 / 100.0))
	var roll: int = (rng.randi_range(0, 255) if rng else randi() % 256)
	return roll < min(255, acc)

static func xp_yield(base_exp: int, level: int, is_trainer: bool) -> int:
	var xp: int = int(floor(float(base_exp * level) / 7.0))
	if is_trainer:
		xp = int(floor(xp * 1.5))
	return xp
