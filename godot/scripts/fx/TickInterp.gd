class_name TickInterp
extends RefCounted
## Render-rate interpolation for things simulated in fixed 60 Hz ticks (the battle scene and its effects).
## Each tick the simulation writes a node's transform through put() / capture(); every rendered frame apply()
## shows the pose between the last two ticks, so motion stays smooth on 30/90/144 Hz displays and on frames where
## the tick loop runs zero or two ticks (a 60 Hz display would otherwise stutter every few seconds).

var tick := 0
# node instance id -> {node, prev, cur, tick, world, dirty}
var _e: Dictionary = {}

func begin_tick() -> void:
	tick += 1

## Set a node's transform for this tick (world space by default) and remember it for interpolation.
func put(n: Node3D, t: Transform3D, world: bool = true) -> void:
	if world:
		n.global_transform = t
	else:
		n.transform = t
	_record(n, t, world)

## Remember a node's current transform (already set by the caller) as this tick's value.
func capture(n: Node3D, world: bool = false) -> void:
	if n == null or not is_instance_valid(n):
		return
	_record(n, n.global_transform if world else n.transform, world)

func _record(n: Node3D, t: Transform3D, world: bool) -> void:
	var id := n.get_instance_id()
	var e: Variant = _e.get(id)
	if e == null:
		_e[id] = {"node": n, "prev": t, "cur": t, "tick": tick, "world": world, "dirty": false}
		return
	var d: Dictionary = e
	if int(d["tick"]) == tick:
		d["cur"] = t
	else:
		# a node that skipped ticks (hidden, idle) restarts from its own last value
		d["prev"] = d["cur"] if int(d["tick"]) == tick - 1 else t
		d["cur"] = t
		d["tick"] = tick

## Show every tracked node `alpha` (0..1) of the way from its previous tick pose to the current one.
func apply(alpha: float) -> void:
	var dead: Array = []
	for id in _e:
		var d: Dictionary = _e[id]
		var nv: Variant = d["node"]
		if not is_instance_valid(nv):
			dead.append(id)
			continue
		var n: Node3D = nv
		if int(d["tick"]) == tick:
			var t: Transform3D = _blend(d["prev"], d["cur"], alpha) if alpha < 1.0 else d["cur"]
			if d["world"]:
				n.global_transform = t
			else:
				n.transform = t
			d["dirty"] = alpha < 1.0
		elif d["dirty"]:
			if d["world"]:
				n.global_transform = d["cur"]
			else:
				n.transform = d["cur"]
			d["dirty"] = false
	for id in dead:
		_e.erase(id)

## Transform3D.interpolate_with needs invertible bases; a zero-scale pose (an effect that has not popped in yet) just
## snaps to the nearer end instead of spamming "Basis must be normalized" errors.
static func _blend(a: Transform3D, b: Transform3D, alpha: float) -> Transform3D:
	if absf(a.basis.determinant()) < 1e-9 or absf(b.basis.determinant()) < 1e-9:
		return b if alpha >= 0.5 else a
	return a.interpolate_with(b, alpha)

## Show the latest tick pose exactly (screenshots, tests).
func settle() -> void:
	apply(1.0)

func clear() -> void:
	_e.clear()
