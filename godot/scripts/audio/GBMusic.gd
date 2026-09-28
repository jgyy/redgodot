class_name GBMusic
extends RefCounted
## Port of upstream pokemon-claude-red's music engine (src/core/audio.js): a
## sequencer that reproduces the Game Boy sound engine's timing exactly (frame
## counters at 59.7275 Hz, tempo, fractional note delays, loops/calls) over the
## original pokered note data (godot/data/music.json), and upstream's re-voiced
## instruments: chorused band-limited pulse leads with GB volume envelopes and
## vibrato, the GB wave-channel samples (with a sub layer under bass lines) and
## LFSR noise drums with a tonal body. Rendered sample-by-sample into stereo
## frames for an AudioStreamGenerator; reverb/compression live on the bus.

const FPS := 59.7275
const PERIOD0 := [0x10000 - 0xF82C, 0x10000 - 0xF89D, 0x10000 - 0xF907, 0x10000 - 0xF96B,
	0x10000 - 0xF9CA, 0x10000 - 0xFA23, 0x10000 - 0xFA77, 0x10000 - 0xFAC7,
	0x10000 - 0xFB12, 0x10000 - 0xFB58, 0x10000 - 0xFB9B, 0x10000 - 0xFBDA]
const DUTY := [0.125, 0.25, 0.5, 0.25]
const WAVE_VOL := [0.0, 0.34, 0.17, 0.085]
const DRUM_BODY := {1: 190, 2: 190, 3: 190, 4: 190, 9: 150, 10: 170, 11: 180, 5: -1}
## per-channel mix: pan, lowpass cutoff (audio.js initBus chan())
const CH_PAN := [-0.3, 0.3, 0.0, 0.12]
const CH_LP := [7000.0, 7000.0, 3800.0, 10500.0]
const TABLE_N := 256

static var _data: Dictionary = {}
static var _wave_tables: Dictionary = {}   # wave idx -> PackedFloat32Array (band-limited, normalised)
static var _noise_bufs: Dictionary = {}    # nr43 -> PackedFloat32Array

var sr: float
var id: String = ""
var prog: Array = []
var tempo: int = 256
var fixed_tempo: int = 0
var frame: int = 0
var tower := false
var chans: Array[Chan] = []
var voices: Array[Voice] = []
var finished := false
var _frame_acc := 0.0
var _lp_state := PackedFloat32Array([0, 0, 0, 0])
var _lp_a := PackedFloat32Array([0, 0, 0, 0])
var _pan_l := PackedFloat32Array([0, 0, 0, 0])
var _pan_r := PackedFloat32Array([0, 0, 0, 0])
var _t := 0.0  # seconds since start


class Chan:
	var n := 0
	var pc := 0
	var stack: Array[int] = []
	var loops := {}
	var oct := 4
	var speed := 12
	var vol := 12
	var fade := 0
	var duty := 2
	var vib: Array = []
	var pp := false
	var delay := 1
	var frac := 0
	var done := false
	var wave := 0
	var slide: Array = []
	var last_drum: Voice = null


class Voice:
	var kind := 0          # 0 pulse, 1 wave, 2 drum
	var ch := 0
	var t := 0.0           # seconds since note start
	var dur := 0.0
	var hz := 0.0
	var slide_hz := 0.0
	var per := 1.0
	var v := 0
	var fade := 0
	var duty := 0.5
	var vib_delay := 0.0
	var vib_rate := 0.0
	var vib_cents := 0.0
	var ph1 := 0.0
	var ph2 := 0.0
	var ph_sub := 0.0
	var level := 0.0       # wave-channel level
	var table: PackedFloat32Array
	var segs: Array = []   # drum segments [len, v, fade, nr43]
	var seg_i := 0
	var seg_t := 0.0
	var seg_dur := 0.0
	var seg_buf: PackedFloat32Array
	var seg_pos := 0
	var body_f0 := 0.0
	var body_f1 := 0.0
	var body_d := 0.0
	var body_ph := 0.0
	var kill_at := -1.0    # drum choke (seconds since start)
	var total := 0.0       # lifetime incl. release


static func data() -> Dictionary:
	if _data.is_empty():
		var f := FileAccess.open("res://data/music.json", FileAccess.READ)
		if f:
			var parsed: Variant = JSON.parse_string(f.get_as_text())
			if parsed is Dictionary:
				_data = parsed
	return _data


static func has_song(song_id: String) -> bool:
	var songs: Dictionary = data().get("songs", {})
	return songs.has(song_id.split("@")[0])


func _init(song_id: String, sample_rate: float) -> void:
	sr = sample_rate
	id = song_id
	var parts := song_id.split("@")
	var songs: Dictionary = data().get("songs", {})
	var sd: Dictionary = songs.get(parts[0], {})
	if sd.is_empty():
		finished = true
		return
	if parts.size() > 1:
		fixed_tempo = int(parts[1])
	prog = data().get("progs", {}).get(sd.get("f", ""), [])
	tower = song_id.contains("Tower")
	var ch_pcs: Array = sd.get("ch", [])
	var ch_ns: Array = sd.get("n", [])
	for i in ch_pcs.size():
		var c := Chan.new()
		c.pc = int(ch_pcs[i])
		c.n = int(ch_ns[i])
		chans.append(c)
	for k in 4:
		_lp_a[k] = 1.0 - exp(-TAU * minf(CH_LP[k], sr * 0.45) / sr)
		var x: float = (CH_PAN[k] + 1.0) * 0.5
		_pan_l[k] = cos(x * PI * 0.5)
		_pan_r[k] = sin(x * PI * 0.5)


# ---------------------------------------------------------------- sequencer
static func _period_of(p: int, oct: int) -> int:
	return ceili(PERIOD0[p] / pow(2.0, oct - 1))


func _note_frames(c: Chan, length: int) -> int:
	var tot: int = ((length * c.speed) & 0xff) * tempo + c.frac
	c.frac = tot & 0xff
	return maxi(1, tot >> 8)


func _step(c: Chan) -> void:
	for _guard in 500:
		if c.pc < 0 or c.pc >= prog.size():
			c.done = true
			return
		var op: Array = prog[c.pc]
		c.pc += 1
		match int(op[0]):
			0:  # note
				var fr := _note_frames(c, int(op[2]))
				c.delay = fr
				var per: int = maxi(1, _period_of(int(op[1]), c.oct) - (1 if c.pp else 0))
				var dur := fr / FPS
				var sl := 0
				if not c.slide.is_empty():
					sl = _period_of(int(c.slide[2]), int(c.slide[1]))
				if c.n == 2:
					var wv := 6 if (tower and c.wave == 5) else c.wave
					_wave_voice(c.n, dur, 65536.0 / per, c.vol, wv, (65536.0 / sl) if sl > 0 else 0.0)
				elif c.n < 2:
					_pulse_voice(c.n, dur, 131072.0 / per, per, c.vol, c.fade, c.duty, c.vib, (131072.0 / sl) if sl > 0 else 0.0)
				c.slide = []
				return
			1:  # rest
				c.delay = _note_frames(c, int(op[1]))
				c.slide = []
				return
			2:
				c.oct = int(op[1])
			3:
				c.speed = int(op[1])
				c.vol = int(op[2])
				c.fade = int(op[3])
				if c.n == 2:
					c.wave = int(op[3])
			4:
				c.speed = int(op[1])
			5:  # drum note
				var frd := _note_frames(c, int(op[2]))
				c.delay = frd
				var drums: Array = data().get("drums", [])
				var inst := int(op[1])
				if inst < drums.size() and drums[inst] != null:
					_drum_voice(c, drums[inst], inst)
				return
			6:
				tempo = fixed_tempo if fixed_tempo > 0 else int(op[1])
				for k in chans:
					k.frac = 0
			7:
				c.duty = int(op[1])
			8:
				c.vib = [int(op[1]), int(op[2]), int(op[3])]
			9:
				c.slide = [int(op[1]), int(op[2]), int(op[3])]
			10:
				c.pp = not c.pp
			11:
				c.stack.append(c.pc)
				c.pc = int(op[1])
			12:
				if not c.stack.is_empty():
					c.pc = c.stack.pop_back()
				else:
					c.done = true
					return
			13:  # sound_loop count (0 = forever), target
				if int(op[1]) == 0:
					c.pc = int(op[2])
				else:
					var key := c.pc - 1
					var n: int = c.loops.get(key, int(op[1]))
					if n <= 1:
						c.loops.erase(key)
					else:
						c.loops[key] = n - 1
						c.pc = int(op[2])
			16:
				c.duty = (int(op[1]) >> 6) & 3
			17:  # raw square note: length, volume, fade, frequency register
				var fr17 := int(op[1]) + 1
				c.delay = fr17
				var per17 := 2048 - int(op[4])
				if int(op[2]) > 0 and per17 > 0:
					_pulse_voice(c.n, fr17 / FPS, 131072.0 / per17, per17, int(op[2]), int(op[3]), c.duty, [], 0.0)
				return
			18:
				c.delay = int(op[1]) + 1
				_drum_voice(c, [[int(op[1]), int(op[2]), int(op[3]), int(op[4])]], 0)
				return
			_:
				pass  # master volume, panning, pitch sweep: handled by the mix
	c.done = true


## One sequencer frame (1/59.7275 s). Returns false once every channel ended.
func _advance_frame() -> bool:
	var alive := false
	for c in chans:
		if c.done:
			continue
		alive = true
		if c.delay > 1:
			c.delay -= 1
			continue
		_step(c)
	frame += 1
	return alive


# ---------------------------------------------------------------- voices
func _pulse_voice(ch: int, dur: float, hz: float, per: int, v: int, fade: int, duty: int, vib: Array, slide_hz: float) -> void:
	var vo := Voice.new()
	vo.kind = 0
	vo.ch = ch
	vo.dur = dur
	vo.hz = hz
	vo.slide_hz = slide_hz
	vo.per = per
	vo.v = v
	vo.fade = fade
	vo.duty = DUTY[duty & 3]
	vo.total = dur + 0.03
	if vib.size() == 3 and int(vib[1]) > 0 and dur > int(vib[0]) / FPS + 0.03:
		vo.vib_delay = int(vib[0]) / FPS
		vo.vib_rate = FPS / (2.0 * ((int(vib[2]) & 15) + 1))
		vo.vib_cents = 1200.0 * log(per / maxf(1.0, per - int(vib[1]) / 2.0)) / log(2.0)
	voices.append(vo)


func _wave_voice(ch: int, dur: float, hz: float, vol: int, wave: int, slide_hz: float) -> void:
	var lvl: float = WAVE_VOL[vol & 3]
	if lvl <= 0.0:
		return
	var vo := Voice.new()
	vo.kind = 1
	vo.ch = ch
	vo.dur = dur
	vo.hz = hz
	vo.slide_hz = slide_hz
	vo.level = lvl
	vo.table = _wave_table(wave)
	vo.total = dur + 0.03
	voices.append(vo)


func _drum_voice(c: Chan, segs: Array, inst: int) -> void:
	if c.last_drum != null and c.last_drum.kill_at < 0.0:
		c.last_drum.kill_at = c.last_drum.t
	var vo := Voice.new()
	vo.kind = 2
	vo.ch = c.n
	vo.segs = segs
	vo.seg_i = -1
	var tot := 0.0
	for i in segs.size():
		tot += (int(segs[i][0]) + 1) / FPS
	var last: Array = segs[segs.size() - 1]
	var tail := maxf((int(last[0]) + 1) / FPS, int(last[1]) * maxf(1.0, int(last[2])) / 64.0)
	vo.total = tot - (int(last[0]) + 1) / FPS + tail + 0.05
	var body: int = DRUM_BODY.get(inst, 0)
	if body != 0:
		vo.body_f0 = body if body > 0 else 170.0
		vo.body_f1 = body * 0.7 if body > 0 else 80.0
		vo.body_d = 0.09 if body > 0 else tot + 0.08
		vo.total = maxf(vo.total, vo.body_d + 0.03)
	_next_drum_seg(vo)
	c.last_drum = vo
	voices.append(vo)


func _next_drum_seg(vo: Voice) -> void:
	vo.seg_i += 1
	if vo.seg_i >= vo.segs.size():
		vo.seg_buf = PackedFloat32Array()
		return
	var s: Array = vo.segs[vo.seg_i]
	vo.seg_t = 0.0
	var seg_len := (int(s[0]) + 1) / FPS
	if vo.seg_i < vo.segs.size() - 1:
		vo.seg_dur = seg_len
	else:
		vo.seg_dur = maxf(seg_len, int(s[1]) * maxf(1.0, int(s[2])) / 64.0)
	vo.seg_buf = _noise_buf(int(s[3]), sr)
	vo.seg_pos = randi() % maxi(1, int(sr * 0.3))


## GB volume envelope (audio.js envelope()) evaluated at time t.
static func env(t: float, dur: float, v: int, fade: int, peak: float) -> float:
	var g0 := peak * v / 15.0
	var g := 0.0
	var te := minf(t, dur)
	if te < 0.004:
		g = g0 * te / 0.004
	elif fade > 0 and v > 0:
		var tt := v * fade / 64.0
		if tt < dur:
			g = g0 * (1.0 - (te - 0.004) / maxf(0.0001, tt - 0.004)) if te < tt else 0.0
		else:
			g = g0 + (g0 * (1.0 - dur / tt) - g0) * (te - 0.004) / maxf(0.0001, dur - 0.004)
	elif fade < 0:
		var tr := maxf(0.001, (15 - v) * -fade / 64.0)
		if tr < dur:
			g = g0 + (peak - g0) * clampf((te - 0.004) / maxf(0.0001, tr - 0.004), 0.0, 1.0)
		else:
			g = g0 + ((g0 + (peak - g0) * dur / tr) - g0) * (te - 0.004) / maxf(0.0001, dur - 0.004)
	else:
		g = g0
	if t > dur:
		g *= maxf(0.0, 1.0 - (t - dur) / 0.015)
	return maxf(g, 0.0)


static func _poly_blep(t: float, dt: float) -> float:
	if t < dt:
		var x := t / dt
		return x + x - x * x - 1.0
	elif t > 1.0 - dt:
		var y := (t - 1.0) / dt
		return y * y + y + y + 1.0
	return 0.0


static func pulse(ph: float, duty: float, dt: float) -> float:
	var s := 1.0 if ph < duty else -1.0
	s += _poly_blep(ph, dt)
	s -= _poly_blep(fposmod(ph + 1.0 - duty, 1.0), dt)
	return s


## GB channel-3 instrument -> band-limited single-cycle table (16 harmonics,
## top end softened, normalised like a Web Audio PeriodicWave).
static func _wave_table(idx: int) -> PackedFloat32Array:
	if _wave_tables.has(idx):
		return _wave_tables[idx]
	var waves: Array = data().get("waves", [])
	var src: Array = waves[idx] if idx < waves.size() else (waves[0] if not waves.is_empty() else [])
	var n := src.size()
	var tab := PackedFloat32Array()
	tab.resize(TABLE_N)
	if n > 0:
		var re := PackedFloat32Array()
		var im := PackedFloat32Array()
		re.resize(17)
		im.resize(17)
		for k in range(1, 17):
			var a := 0.0
			var b := 0.0
			for i in n:
				var smp := (float(src[i]) - 7.5) / 7.5
				var ph := TAU * k * (i + 0.5) / n
				a += smp * cos(ph)
				b += smp * sin(ph)
			var soft := 0.55 if k > 8 else 1.0
			re[k] = a * 2.0 / n * soft
			im[k] = b * 2.0 / n * soft
		var mx := 0.0001
		for j in TABLE_N:
			var x := 0.0
			for k in range(1, 17):
				var p := TAU * k * j / TABLE_N
				x += re[k] * cos(p) + im[k] * sin(p)
			tab[j] = x
			mx = maxf(mx, absf(x))
		for j in TABLE_N:
			tab[j] /= mx
	_wave_tables[idx] = tab
	return tab


## GB noise channel: LFSR clocked from the NR43 byte (shift, 7-bit width, divisor).
static func _noise_buf(nr43: int, rate: float) -> PackedFloat32Array:
	if _noise_bufs.has(nr43):
		return _noise_bufs[nr43]
	var sh := nr43 >> 4
	var w7 := (nr43 >> 3) & 1
	var r := nr43 & 7
	var clk: float = 524288.0 / (float(r) if r > 0 else 0.5) / pow(2.0, sh + 1)
	var n := int(rate * 0.7)
	var buf := PackedFloat32Array()
	buf.resize(n)
	var step: float = clk / rate
	var lfsr := 0x7fff
	var acc := 0.0
	var out := 1.0
	for i in n:
		acc += step
		while acc >= 1.0:
			acc -= 1.0
			var bit := (lfsr ^ (lfsr >> 1)) & 1
			lfsr = (lfsr >> 1) | (bit << 14)
			if w7 == 1:
				lfsr = (lfsr & ~0x40) | (bit << 6)
			out = -1.0 if (lfsr & 1) == 1 else 1.0
		buf[i] = out
	_noise_bufs[nr43] = buf
	return buf


# ---------------------------------------------------------------- render
## Renders `count` stereo frames, mixing into `out` (added, scaled by gain).
## Returns false once the song has fully ended (jingles).
func render(out: PackedVector2Array, offset: int, count: int, gain: float) -> bool:
	if finished:
		return false
	var spf := sr / FPS
	var inv_sr := 1.0 / sr
	var i := 0
	while i < count:
		if _frame_acc <= 0.0:
			if not _advance_frame() and voices.is_empty():
				finished = true
				return false
			_frame_acc += spf
		var n := mini(count - i, ceili(_frame_acc))
		_render_block(out, offset + i, n, gain, inv_sr)
		_frame_acc -= n
		i += n
	return true


func _render_block(out: PackedVector2Array, offset: int, n: int, gain: float, inv_sr: float) -> void:
	var mix := PackedFloat32Array()
	mix.resize(n * 4)
	var keep: Array[Voice] = []
	for vo in voices:
		var base := vo.ch * n
		match vo.kind:
			0:
				for j in n:
					var t := vo.t
					var e := env(t, vo.dur, vo.v, vo.fade, 0.2)
					var hz := vo.hz
					if vo.slide_hz > 0.0:
						hz = vo.hz * pow(vo.slide_hz / vo.hz, minf(1.0, t / maxf(0.0001, vo.dur)))
					if vo.vib_rate > 0.0 and t >= vo.vib_delay:
						var lfo := 4.0 * absf(fposmod(t * vo.vib_rate, 1.0) - 0.5) - 1.0
						hz *= pow(2.0, vo.vib_cents * lfo / 1200.0)
					var dt1 := hz * inv_sr
					var hz2 := hz * 1.0040514  # +7 cents chorus voice
					var dt2 := hz2 * inv_sr
					vo.ph1 = fposmod(vo.ph1 + dt1, 1.0)
					vo.ph2 = fposmod(vo.ph2 + dt2, 1.0)
					var s := pulse(vo.ph1, vo.duty, dt1) + 0.45 * pulse(vo.ph2, vo.duty, dt2)
					mix[base + j] += s * e * 0.5
					vo.t += inv_sr
			1:
				for j in n:
					var t := vo.t
					var g := 0.0
					if t < 0.004:
						g = vo.level * t / 0.004
					elif t <= vo.dur:
						g = vo.level * (1.0 - 0.18 * (t - 0.004) / maxf(0.001, maxf(0.005, vo.dur) - 0.004))
					else:
						g = vo.level * 0.82 * maxf(0.0, 1.0 - (t - vo.dur) / 0.015)
					var hz := vo.hz
					if vo.slide_hz > 0.0:
						hz = vo.hz * pow(vo.slide_hz / vo.hz, minf(1.0, t / maxf(0.0001, vo.dur)))
					vo.ph1 = fposmod(vo.ph1 + hz * inv_sr, 1.0)
					var tf := vo.ph1 * TABLE_N
					var k0 := int(tf)
					var fr := tf - k0
					var s := lerpf(vo.table[k0 % TABLE_N], vo.table[(k0 + 1) % TABLE_N], fr)
					if hz < 220.0:
						vo.ph_sub = fposmod(vo.ph_sub + hz * 0.5 * inv_sr, 1.0)
						s += 0.55 * sin(TAU * vo.ph_sub)
					mix[base + j] += s * g
					vo.t += inv_sr
			2:
				for j in n:
					var s := 0.0
					if vo.seg_buf.size() > 0:
						var ss: Array = vo.segs[vo.seg_i]
						var e := env(vo.seg_t, vo.seg_dur, int(ss[1]), int(ss[2]), 0.3)
						s = vo.seg_buf[vo.seg_pos % vo.seg_buf.size()] * e
						vo.seg_pos += 1
						vo.seg_t += inv_sr
						if vo.seg_i < vo.segs.size() - 1 and vo.seg_t >= (int(ss[0]) + 1) / FPS:
							_next_drum_seg(vo)
						elif vo.seg_i == vo.segs.size() - 1 and vo.seg_t >= vo.seg_dur + 0.015:
							vo.seg_buf = PackedFloat32Array()
					if vo.body_d > 0.0 and vo.t < vo.body_d:
						var f := vo.body_f0 * pow(vo.body_f1 / vo.body_f0, vo.t / vo.body_d)
						vo.body_ph = fposmod(vo.body_ph + f * inv_sr, 1.0)
						s += sin(TAU * vo.body_ph) * 0.16 * pow(0.001 / 0.16, vo.t / vo.body_d)
					if vo.kill_at >= 0.0:
						s *= maxf(0.0, 1.0 - (vo.t - vo.kill_at) / 0.004)
					mix[base + j] += s
					vo.t += inv_sr
		var dead := vo.t >= vo.total or (vo.kill_at >= 0.0 and vo.t > vo.kill_at + 0.004)
		if not dead:
			keep.append(vo)
	voices = keep
	# per-channel lowpass + pan into the stereo output
	for k in 4:
		var a := _lp_a[k]
		var st := _lp_state[k]
		var pl := _pan_l[k] * gain
		var pr := _pan_r[k] * gain
		var base := k * n
		for j in n:
			st += a * (mix[base + j] - st)
			out[offset + j] += Vector2(st * pl, st * pr)
		_lp_state[k] = st
