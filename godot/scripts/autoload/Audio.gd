extends Node
## Game audio (port of upstream src/core/audio.js): the original Red music
## through GBMusic's sequencer/synth streamed into an AudioStreamGenerator,
## jingles that duck the music, procedural SFX and per-species cries.
##
##   Audio.music("title") / Audio.music("PalletTown") / Audio.music("heal", true)
##   Audio.sfx("select") ; Audio.cry("PIKACHU") ; Audio.stop_music()
##
## Upstream's track names (title, wild, trainer, center, ...) and pokered song
## ids both work. With no explicit calls, the autoload follows the active scene
## (title / overworld map song / wild or trainer battle) on its own.
## Disabled in headless runs, --run-tests and --screenshot captures.

const MIX_RATE := 22050.0
const BUFFER_SEC := 0.25

## game track names -> pokered songs (audio.js NAME)
const NAME := {
	"title": "TitleScreen", "oak_intro": "Routes2", "pallet": "PalletTown", "oak": "MeetProfOak",
	"oak_lab": "OaksLab", "rival": "MeetRival", "rival_leave": "MeetRival", "surf": "Surfing",
	"bike": "BikeRiding", "evolution": "SafariZone", "hall_of_fame": "HallOfFame", "credits": "Credits",
	"wild": "WildBattle", "legendary": "WildBattle", "trainer": "TrainerBattle", "gym_leader": "GymLeaderBattle",
	"final_battle": "FinalBattle", "champion": "FinalBattle", "elite_four": "TrainerBattle",
	"victory": "DefeatedTrainer", "victory_wild": "DefeatedWildMon", "victory_leader": "DefeatedGymLeader",
	"center": "Pokecenter", "gym": "Gym", "cave": "Dungeon2", "forest": "Dungeon2", "tower": "PokemonTower",
	"lavender": "Lavender", "ss_anne": "SSAnne", "game_corner": "GameCorner", "silph": "SilphCo",
	"hideout": "Dungeon1", "mansion": "CinnabarMansion", "safari": "SafariZone", "indigo": "IndigoPlateau",
	"city": "Cities1", "route": "Routes1", "jigglypuff": "JigglypuffSong", "museum": "MuseumGuy",
}
const JINGLE := {
	"heal": "PkmnHealed", "item": "SFX_Get_Item1_1", "badge": "SFX_Get_Item1_1", "key": "SFX_Get_Key_Item_1",
	"mon": "SFX_Get_Item1_1", "levelup": "SFX_Level_Up", "caught": "SFX_Caught_Mon", "jigglypuff": "JigglypuffSong",
}
const GYM_LEADERS := ["BROCK", "MISTY", "LT_SURGE", "ERIKA", "KOGA", "SABRINA", "BLAINE", "GIOVANNI"]

var enabled := true
var muted := false
var auto_follow := true

var _player: AudioStreamPlayer
var _playback: AudioStreamGeneratorPlayback
var _seq: GBMusic = null
var _jseq: GBMusic = null
var _music_gain := 1.0
var _music_target := 1.0
var _sfx_players: Array[AudioStreamPlayer] = []
var _auto_key := ""
var _buf := PackedVector2Array()


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if DisplayServer.get_name() == "headless" or args.has("--run-tests") or _has_prefix(args, "--screenshot="):
		enabled = false
		set_process(false)
		return
	_setup_buses()
	_player = AudioStreamPlayer.new()
	_player.bus = "Music"
	var gen := AudioStreamGenerator.new()
	gen.mix_rate = MIX_RATE
	gen.buffer_length = BUFFER_SEC
	_player.stream = gen
	add_child(_player)
	_player.play()
	_playback = _player.get_stream_playback()
	for i in 6:
		var p := AudioStreamPlayer.new()
		p.bus = "SFX"
		add_child(p)
		_sfx_players.append(p)


func _has_prefix(args: PackedStringArray, prefix: String) -> bool:
	for a in args:
		if a.begins_with(prefix):
			return true
	return false


## Music / SFX buses with upstream's mix chain: compressor + makeup, small reverb.
func _setup_buses() -> void:
	for bus_name in ["Music", "SFX"]:
		if AudioServer.get_bus_index(bus_name) >= 0:
			continue
		AudioServer.add_bus()
		var idx := AudioServer.bus_count - 1
		AudioServer.set_bus_name(idx, bus_name)
		AudioServer.set_bus_send(idx, "Master")
		if bus_name == "Music":
			var rev := AudioEffectReverb.new()
			rev.room_size = 0.55
			rev.damping = 0.6
			rev.wet = 0.18
			rev.dry = 1.0
			AudioServer.add_bus_effect(idx, rev)
			var comp := AudioEffectCompressor.new()
			comp.threshold = -14.0
			comp.ratio = 3.0
			comp.attack_us = 5000.0
			comp.release_ms = 180.0
			comp.gain = 2.0
			AudioServer.add_bus_effect(idx, comp)


# ---------------------------------------------------------------- API
func resolve_song(song_name: String) -> String:
	if GBMusic.has_song(song_name):
		return song_name
	if NAME.has(song_name):
		return NAME[song_name]
	if song_name.begins_with("encounter_"):
		var cls := song_name.substr(10)
		var enc: Dictionary = GBMusic.data().get("encounter", {})
		if (enc.get("evil", []) as Array).has(cls):
			return "MeetEvilTrainer"
		if (enc.get("female", []) as Array).has(cls):
			return "MeetFemaleTrainer"
		return "MeetMaleTrainer"
	return song_name


## Plays a looping song (or a one-shot jingle that ducks the music when is_jingle).
func music(song_name: String, is_jingle: bool = false) -> void:
	if not enabled or song_name == "":
		return
	if is_jingle:
		_play_jingle(JINGLE.get(song_name, resolve_song(song_name)))
		return
	var sid := resolve_song(song_name)
	if _seq and _seq.id == sid and not _seq.finished:
		return
	if not GBMusic.has_song(sid):
		return
	_seq = GBMusic.new(sid, MIX_RATE)


func stop_music() -> void:
	_seq = null


func current_song() -> String:
	return _seq.id if _seq else ""


func _play_jingle(sid: String) -> void:
	if not enabled or muted or not GBMusic.has_song(sid):
		return
	_jseq = GBMusic.new(sid, MIX_RATE)
	_music_target = 0.0


func sfx(sfx_name: String) -> void:
	if not enabled or muted:
		return
	var j := SfxSynth.jingle_of(sfx_name)
	if j != "":
		_play_jingle(j)
		return
	var s := SfxSynth.stream(sfx_name)
	if s:
		_play_stream(s)


## Procedural cry for a species (mode "faint" = slowed, falling).
func cry(species: String, mode: String = "") -> void:
	if not enabled or muted:
		return
	var sp: Dictionary = GameData.get_species(species)
	var dex := int(sp.get("dex", 1))
	_play_stream(SfxSynth.cry(dex, mode))


func _play_stream(s: AudioStream) -> void:
	for p in _sfx_players:
		if not p.playing:
			p.stream = s
			p.play()
			return
	_sfx_players[0].stream = s
	_sfx_players[0].play()


func set_muted(m: bool) -> void:
	muted = m
	AudioServer.set_bus_mute(AudioServer.get_bus_index("Master"), m)


## pokered's per-map song (mapSongs keyed by the map constant).
func map_song(map_name: String) -> String:
	var md: Dictionary = GameData.get_map(map_name)
	var songs: Dictionary = GBMusic.data().get("mapSongs", {})
	return songs.get(md.get("cnst", ""), "PalletTown")


# ---------------------------------------------------------------- streaming
func _process(dt: float) -> void:
	if auto_follow:
		_follow_scene()
	if _playback == null:
		return
	var n := _playback.get_frames_available()
	if n <= 0:
		return
	if _buf.size() != n:
		_buf.resize(n)
	_buf.fill(Vector2.ZERO)
	# ~50 ms duck/unduck ramps (audio.js duck())
	_music_gain = move_toward(_music_gain, _music_target, dt / 0.05)
	if _seq and not muted and _music_gain > 0.001:
		if not _seq.render(_buf, 0, n, 0.56 * _music_gain):
			_seq = null
	if _jseq and not muted:
		if not _jseq.render(_buf, 0, n, 0.56):
			_jseq = null
			_music_target = 1.0
	elif _jseq == null:
		_music_target = 1.0
	_playback.push_buffer(_buf)


## Follows the active scene like upstream's G.music() call sites: title theme,
## the map's song in the overworld, wild/trainer battle themes.
func _follow_scene() -> void:
	var active: Node = SceneRouter.get("_active")
	if active == null:
		return
	var key := String(active.name)
	var song := ""
	match key:
		"Title":
			song = "title"
		"Intro":
			song = "oak_intro"
		"Overworld":
			key += ":" + GameState.current_map
			song = map_song(GameState.current_map)
		"Battle":
			var enc: Dictionary = active.get("encounter") if active.get("encounter") is Dictionary else {}
			var trainer_cls := str(enc.get("trainer_class", enc.get("trainer_key", "")))
			key += ":" + trainer_cls
			if enc.get("kind", "wild") == "trainer":
				song = "gym_leader" if GYM_LEADERS.has(trainer_cls) else "trainer"
			else:
				song = "wild"
	if key == _auto_key:
		return
	_auto_key = key
	if song != "":
		music(song)
