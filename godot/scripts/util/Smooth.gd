class_name Smooth
extends RefCounted
## Frame-rate independent smoothing helpers. Everything takes the frame delta `dt`, so an effect looks the
## same at 30, 60 or 144 fps (unlike `lerp(a, b, 0.2)` per frame).

## Fraction of the remaining distance to cover this frame for an exponential ease with the given rate (1/s):
## `x = lerp(x, target, Smooth.decay(dt, 12.0))`.
static func decay(dt: float, rate: float) -> float:
	return 1.0 - exp(-rate * dt)

## Critically damped spring (no overshoot toward a fixed target, exact for any dt). Returns [new_pos, new_vel].
## omega (1/s) is the stiffness: the settling time is roughly 4 / omega.
static func damp(cur: float, vel: float, target: float, omega: float, dt: float) -> Array:
	var ex := exp(-omega * dt)
	var d := cur - target
	var tmp := (vel + omega * d) * dt
	return [target + (d + tmp) * ex, (vel - omega * tmp) * ex]

## Vector3 version of damp().
static func damp3(cur: Vector3, vel: Vector3, target: Vector3, omega: float, dt: float) -> Array:
	var ex := exp(-omega * dt)
	var d := cur - target
	var tmp := (vel + d * omega) * dt
	return [target + (d + tmp) * ex, (vel - tmp * omega) * ex]

## Smooth 0..1 ease in/out (smootherstep).
static func ease_io(k: float) -> float:
	var t := clampf(k, 0.0, 1.0)
	return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)

## Ease-out (fast start, gentle stop) of a 0..1 fraction; `power` 2 = quadratic, 3 = cubic.
static func ease_out(k: float, power: float = 2.0) -> float:
	return 1.0 - pow(1.0 - clampf(k, 0.0, 1.0), power)

## Ease-in (gentle start, fast finish) of a 0..1 fraction.
static func ease_in(k: float, power: float = 2.0) -> float:
	return pow(clampf(k, 0.0, 1.0), power)

## Overshooting ease-out (a small back-swing): 0 -> 1 with `s` about 1.7 giving ~10% overshoot.
static func ease_out_back(k: float, s: float = 1.70158) -> float:
	var t := clampf(k, 0.0, 1.0) - 1.0
	return 1.0 + t * t * ((s + 1.0) * t + s)
