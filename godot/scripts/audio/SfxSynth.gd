class_name SfxSynth
extends RefCounted
## Offline port of upstream's procedural SFX voices (src/core/audio.js tone() /
## noise() and the SFX table, plus per-species cries): each effect is rendered
## once into an AudioStreamWAV and cached.

const RATE := 22050

## name -> list of voice commands; ["t", start, hz, dur, opts] / ["n", start, dur, opts] / ["j", song]
const SFX := {
	"blip": [["t", 0.0, 1760.0, 0.03, {"duty": 0.25, "vol": 0.12}]],
	"cursor": [["t", 0.0, 1320.0, 0.025, {"duty": 0.25, "vol": 0.1}]],
	"select": [["t", 0.0, 1046.0, 0.04, {"duty": 0.5, "vol": 0.14}], ["t", 0.04, 1568.0, 0.05, {"duty": 0.5, "vol": 0.14}]],
	"menu": [["t", 0.0, 880.0, 0.05, {"duty": 0.25, "vol": 0.12, "slide": 1.5}]],
	"bump": [["t", 0.0, 90.0, 0.08, {"duty": 0.5, "vol": 0.2}]],
	"door": [["n", 0.0, 0.12, {"freq": 900.0, "type": "lowpass", "vol": 0.3}], ["t", 0.0, 220.0, 0.1, {"duty": 0.25, "vol": 0.1, "slide": 0.6}]],
	"exit": [["t", 0.0, 330.0, 0.06, {"duty": 0.25, "vol": 0.12}], ["t", 0.06, 220.0, 0.08, {"duty": 0.25, "vol": 0.12}]],
	"jump": [["t", 0.0, 300.0, 0.18, {"duty": 0.25, "vol": 0.16, "slide": 2.2}]],
	"exclaim": [["t", 0.0, 1175.0, 0.06, {"duty": 0.5, "vol": 0.18}], ["t", 0.07, 1568.0, 0.12, {"duty": 0.5, "vol": 0.18}]],
	"hit": [["n", 0.0, 0.12, {"freq": 800.0, "type": "lowpass", "vol": 0.5}], ["t", 0.0, 180.0, 0.08, {"duty": 0.5, "vol": 0.2, "slide": 0.5}]],
	"hit_super": [["n", 0.0, 0.2, {"freq": 1200.0, "type": "lowpass", "vol": 0.6}], ["t", 0.0, 260.0, 0.14, {"duty": 0.5, "vol": 0.25, "slide": 0.4}]],
	"hit_weak": [["n", 0.0, 0.08, {"freq": 500.0, "type": "lowpass", "vol": 0.35}]],
	"ballthrow": [["t", 0.0, 400.0, 0.25, {"duty": 0.125, "vol": 0.12, "slide": 2.0}]],
	"ballpop": [["n", 0.0, 0.15, {"freq": 3000.0, "vol": 0.25}], ["t", 0.0, 900.0, 0.12, {"duty": 0.25, "vol": 0.12, "slide": 0.5}]],
	"shake": [["t", 0.0, 220.0, 0.05, {"duty": 0.5, "vol": 0.15}], ["n", 0.0, 0.05, {"freq": 600.0, "type": "lowpass", "vol": 0.2}]],
	"caught": [["j", "SFX_Caught_Mon"]],
	"run": [["n", 0.0, 0.05, {"freq": 1500.0, "vol": 0.12}], ["n", 0.06, 0.05, {"freq": 1500.0, "vol": 0.12}], ["n", 0.12, 0.05, {"freq": 1500.0, "vol": 0.12}]],
	"levelup": [["j", "SFX_Level_Up"]],
	"lowhp": [["t", 0.0, 1480.0, 0.06, {"duty": 0.5, "vol": 0.08}], ["t", 0.12, 1480.0, 0.06, {"duty": 0.5, "vol": 0.08}]],
	"heal": [["t", 0.0, 880.0, 0.08, {"duty": 0.25, "vol": 0.12}], ["t", 0.08, 1320.0, 0.14, {"duty": 0.25, "vol": 0.12}]],
	"get_item": [["j", "SFX_Get_Item1_1"]], "get_key": [["j", "SFX_Get_Key_Item_1"]], "get_tm": [["j", "SFX_Get_Item1_1"]],
	"get_mon": [["j", "SFX_Get_Item1_1"]], "get_badge": [["j", "SFX_Get_Item1_1"]], "hidden_item": [["j", "SFX_Get_Item2_1"]],
	"dex": [["j", "SFX_Dex_Page_Added"]], "save": [["j", "SFX_Save_1"]], "learn": [["j", "SFX_Level_Up"]], "item": [["j", "SFX_Get_Item1_1"]],
	"buy": [["t", 0.0, 1568.0, 0.05, {"duty": 0.5, "vol": 0.14}], ["t", 0.06, 2093.0, 0.08, {"duty": 0.5, "vol": 0.14}]],
	"pc_on": [["t", 0.0, 660.0, 0.05, {"duty": 0.25, "vol": 0.1}], ["t", 0.05, 990.0, 0.08, {"duty": 0.25, "vol": 0.1}]],
	"pc_off": [["t", 0.0, 990.0, 0.05, {"duty": 0.25, "vol": 0.1}], ["t", 0.05, 660.0, 0.08, {"duty": 0.25, "vol": 0.1}]],
	"pc_access": [["t", 0.0, 1175.0, 0.08, {"duty": 0.25, "vol": 0.1}]],
	"ballplace": [["t", 0.0, 1320.0, 0.05, {"duty": 0.25, "vol": 0.12}]],
	"cut": [["n", 0.0, 0.2, {"freq": 2500.0, "vol": 0.3}]],
	"boulder": [["n", 0.0, 0.25, {"freq": 300.0, "type": "lowpass", "vol": 0.5}]],
	"elevator": [["t", 0.0, 110.0, 1.0, {"duty": 0.5, "vol": 0.08}]],
	"horn": [["t", 0.0, 110.0, 1.0, {"duty": 0.5, "vol": 0.08}]],
	"ding": [["t", 0.0, 1760.0, 0.4, {"wave": "sine", "vol": 0.2}]],
	"shrink": [["t", 0.0, 880.0, 0.5, {"duty": 0.25, "vol": 0.12, "slide": 0.25}]],
}

static var _cache: Dictionary = {}


## Returns the jingle song id for a jingle-backed effect, or "".
static func jingle_of(sfx_name: String) -> String:
	var cmds: Array = SFX.get(sfx_name, [])
	if cmds.size() == 1 and cmds[0][0] == "j":
		return cmds[0][1]
	return ""


static func stream(sfx_name: String) -> AudioStreamWAV:
	if _cache.has(sfx_name):
		return _cache[sfx_name]
	var cmds: Array = _commands(sfx_name)
	if cmds.is_empty():
		return null
	var wav := _render(cmds)
	_cache[sfx_name] = wav
	return wav


static func _commands(sfx_name: String) -> Array:
	var cmds: Array = SFX.get(sfx_name, []).duplicate()
	match sfx_name:
		"battle_start":
			for i in 8:
				cmds.append(["t", i * 0.05, 440.0 + (i % 2) * 220.0, 0.04, {"duty": 0.5, "vol": 0.12}])
		"exp":
			for i in 10:
				cmds.append(["t", i * 0.04, 880.0 + i * 60.0, 0.03, {"duty": 0.125, "vol": 0.06}])
		"fly":
			for i in 6:
				cmds.append(["n", i * 0.08, 0.06, {"freq": 900.0 + i * 200.0, "vol": 0.2}])
		"teleport":
			for i in 8:
				cmds.append(["t", i * 0.04, 400.0 + i * 150.0, 0.04, {"duty": 0.25, "vol": 0.1}])
	return cmds.filter(func(c: Array) -> bool: return c[0] != "j")


## Procedural cry, unique per species (audio.js G.cry()).
static func cry(dex: int, mode: String = "") -> AudioStreamWAV:
	var key := "cry_%d_%s" % [dex, mode]
	if _cache.has(key):
		return _cache[key]
	var base := 200.0 + hash2(dex, 1, 91) * 600.0
	var length := 0.25 + hash2(dex, 2, 91) * 0.35
	var slow := 0.6 if mode == "faint" else 1.0
	var duties := [0.125, 0.25, 0.5]
	var cmds: Array = [
		["t", 0.0, base * slow, length * 0.5 / slow, {"duty": duties[int(hash2(dex, 3, 91) * 3)], "vol": 0.18, "slide": 0.6 + hash2(dex, 4, 91) * 1.2}],
		["t", length * 0.45 / slow, base * (0.7 + hash2(dex, 5, 91)) * slow, length * 0.55 / slow,
			{"duty": 0.25, "vol": 0.14, "slide": 0.4 if mode == "faint" else 0.8 + hash2(dex, 6, 91), "vib": 8.0 + hash2(dex, 7, 91) * 10.0}],
	]
	if hash2(dex, 8, 91) > 0.5:
		cmds.append(["n", 0.0, length * 0.4, {"freq": 1500.0 + hash2(dex, 9, 91) * 3000.0, "vol": 0.08}])
	var wav := _render(cmds)
	_cache[key] = wav
	return wav


## gfx.js hash2(), reproducing JS double/int32 semantics exactly.
static func hash2(x: int, y: int, s: int) -> float:
	var h: float = float(x) * 374761393.0 + float(y) * 668265263.0 + float(_to_i32(float(s) * 2147483647.0))
	var a := _to_i32(h)
	var b := _to_u32(h) >> 13
	h = float(a ^ b)
	if h >= 2147483648.0:
		h -= 4294967296.0
	h = h * 1274126177.0
	var c := _to_i32(h)
	var d := _to_u32(h) >> 16
	var r := (c ^ d) & 0xffffffff
	return float(r) / 4294967296.0


static func _to_u32(d: float) -> int:
	var t := fmod(float(int(d)) if absf(d) < 9.0e18 else d - fmod(d, 1.0), 4294967296.0)
	if t < 0.0:
		t += 4294967296.0
	return int(t)


static func _to_i32(d: float) -> int:
	var u := _to_u32(d)
	return u - 0x100000000 if u >= 0x80000000 else u


static func _render(cmds: Array) -> AudioStreamWAV:
	var end_t := 0.0
	for c in cmds:
		if c[0] == "t":
			var o: Dictionary = c[4]
			end_t = maxf(end_t, float(c[1]) + float(c[3]) + float(o.get("rel", 0.04)) + 0.03)
		elif c[0] == "n":
			end_t = maxf(end_t, float(c[1]) + float(c[2]) + 0.03)
	var n := int(end_t * RATE) + 1
	var buf := PackedFloat32Array()
	buf.resize(n)
	for c in cmds:
		if c[0] == "t":
			_tone(buf, float(c[1]), float(c[2]), float(c[3]), c[4])
		elif c[0] == "n":
			_noise(buf, float(c[1]), float(c[2]), c[3])
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	for i in n:
		# sfxGain 1.5 x master 0.55
		bytes.encode_s16(i * 2, int(clampf(buf[i] * 0.825, -1.0, 1.0) * 32767.0))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = RATE
	wav.stereo = false
	wav.data = bytes
	return wav


static func _tone(buf: PackedFloat32Array, t0: float, hz: float, dur: float, o: Dictionary) -> void:
	var v: float = o.get("vol", 0.3)
	var a: float = o.get("a", 0.005)
	var rel: float = o.get("rel", 0.04)
	var sus: float = o.get("sus", 0.75)
	var wave: String = o.get("wave", "pulse")
	var duty: float = o.get("duty", 0.5)
	var slide: float = o.get("slide", 0.0)
	var vib: float = o.get("vib", 0.0)
	var start := int(t0 * RATE)
	var count := int((dur + rel + 0.02) * RATE)
	var ph := 0.0
	var hold_t := maxf(a, dur * 0.3)
	for i in count:
		var idx := start + i
		if idx >= buf.size():
			break
		var t := float(i) / RATE
		var f := hz
		if slide > 0.0:
			f = hz * pow(maxf(20.0, hz * slide) / hz, minf(1.0, t / dur))
		if vib > 0.0 and t > 0.08:
			f += sin(TAU * vib * (t - 0.08)) * hz * 0.012
		var dt := f / RATE
		ph = fposmod(ph + dt, 1.0)
		var s := 0.0
		match wave:
			"sine": s = sin(TAU * ph)
			"tri": s = 1.0 - 4.0 * absf(ph - 0.5)
			"saw": s = 2.0 * ph - 1.0
			_: s = GBMusic.pulse(ph, duty, dt)
		var g := 0.0
		if t < a:
			g = v * t / a
		elif t < hold_t:
			g = v
		elif t < dur + rel:
			var g1 := v * sus
			g = g1 * (1.0 - (t - hold_t) / maxf(0.0001, dur + rel - hold_t))
		buf[idx] += s * g


static var _rng := RandomNumberGenerator.new()

static func _noise(buf: PackedFloat32Array, t0: float, dur: float, o: Dictionary) -> void:
	var v: float = o.get("vol", 0.2)
	var fc: float = o.get("freq", 4000.0)
	var hp: bool = o.get("type", "highpass") == "highpass"
	# RBJ biquad, Q = 1 (Web Audio default)
	var w0 := TAU * minf(fc, RATE * 0.49) / RATE
	var alpha := sin(w0) / 2.0
	var cw := cos(w0)
	var b0 := (1.0 + cw) / 2.0 if hp else (1.0 - cw) / 2.0
	var b1 := -(1.0 + cw) if hp else 1.0 - cw
	var b2 := b0
	var a0 := 1.0 + alpha
	var a1 := -2.0 * cw
	var a2 := 1.0 - alpha
	var x1 := 0.0
	var x2 := 0.0
	var y1 := 0.0
	var y2 := 0.0
	var start := int(t0 * RATE)
	var count := int((dur + 0.02) * RATE)
	_rng.seed = 12345
	for i in count:
		var idx := start + i
		if idx >= buf.size():
			break
		var t := float(i) / RATE
		var x := _rng.randf() * 2.0 - 1.0
		var y := (b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0
		x2 = x1
		x1 = x
		y2 = y1
		y1 = y
		var g := v * pow(0.001 / v, minf(1.0, t / dur)) if t <= dur else 0.0
		buf[idx] += y * g
