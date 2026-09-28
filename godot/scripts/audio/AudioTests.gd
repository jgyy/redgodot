class_name AudioTests
extends RefCounted
## Audio checks for TestSuite: music data, sequencer output, SFX/cry synthesis
## and the JS-exact hash2 port that seeds per-species cries.

static func run(suite: TestSuite) -> void:
	var M := GBMusic.data()
	suite.check((M.get("songs", {}) as Dictionary).size() == 52, "music.json has 52 songs")
	suite.check(M.get("mapSongs", {}).get("PALLET_TOWN", "") == "PalletTown", "Pallet Town plays PalletTown")
	suite.check(Audio.map_song("ViridianForest") == "Dungeon2", "Viridian Forest plays Dungeon2 (got %s)" % Audio.map_song("ViridianForest"))
	suite.check(Audio.resolve_song("wild") == "WildBattle", "track alias wild -> WildBattle")
	suite.check(Audio.resolve_song("encounter_LASS") == "MeetFemaleTrainer", "lass encounter theme")
	# values from upstream gfx.js hash2() evaluated in Node
	suite.check(is_equal_approx(SfxSynth.hash2(25, 1, 91), 0.13119850074872375), "hash2 matches upstream JS")
	var seq := GBMusic.new("PalletTown", 22050.0)
	var buf := PackedVector2Array()
	buf.resize(22050)
	buf.fill(Vector2.ZERO)
	seq.render(buf, 0, buf.size(), 0.56)
	var peak := 0.0
	for v in buf:
		peak = maxf(peak, absf(v.x))
	suite.check(peak > 0.02 and peak < 1.0, "sequencer renders audible, unclipped music (peak %.3f)" % peak)
	var jingle := GBMusic.new("SFX_Level_Up", 22050.0)
	var jb := PackedVector2Array()
	jb.resize(2048)
	var ends := false
	for i in 200:
		jb.fill(Vector2.ZERO)
		if not jingle.render(jb, 0, jb.size(), 0.56):
			ends = true
			break
	suite.check(ends, "jingles end on their own")
	suite.check(SfxSynth.stream("select") != null and SfxSynth.stream("select").data.size() > 1000, "select sfx synthesizes")
	suite.check(SfxSynth.jingle_of("levelup") == "SFX_Level_Up", "levelup sfx is the pokered jingle")
	suite.check(SfxSynth.cry(25).data.size() > 1000, "PIKACHU cry synthesizes")
