class_name BattleSide
extends RefCounted
## One side of a battle (upstream Battle's `p` / `e` objects): the party,
## the active index and the active mon's volatile battle state.

var party: Array = []
var idx := 0
var v: Dictionary = {}
var is_player := false
var fainted := false
