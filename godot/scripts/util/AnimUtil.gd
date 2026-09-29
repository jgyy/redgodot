class_name AnimUtil
extends RefCounted
## The Blender pipeline bakes Idle/Walk (meant to loop) and one-shot clips
## (Attack, Hurt, Faint, Special) into every generated glb, but glTF import doesn't
## set the Animation resource's loop mode on its own - do it here once per loaded
## model instead of per call site.

const LOOPING := ["Idle", "Walk", "Run", "Fly", "Sleep", "Charge", "Taunt", "Hover", "Talk"]
## Crossfade between any two clips (s). A play() with no explicit blend eases from the pose the model is in
## into the new clip instead of snapping to it.
const DEFAULT_BLEND := 0.12

static func fix_looping(anim_player: AnimationPlayer) -> void:
	if anim_player == null:
		return
	anim_player.playback_default_blend_time = DEFAULT_BLEND
	for anim_name in LOOPING:
		if anim_player.has_animation(anim_name):
			var anim := anim_player.get_animation(anim_name)
			anim.loop_mode = Animation.LOOP_LINEAR
	# one-shots hand back to Idle with a slightly longer ease than they are entered with
	for anim_name in ["Attack", "Hurt", "Special"]:
		if anim_player.has_animation(anim_name) and anim_player.has_animation("Idle"):
			anim_player.set_blend_time(anim_name, "Idle", 0.2)

## Length of a clip in seconds (0 if the player or clip is missing).
static func clip_length(anim_player: AnimationPlayer, anim_name: String) -> float:
	if anim_player == null or not anim_player.has_animation(anim_name):
		return 0.0
	return anim_player.get_animation(anim_name).length

## Crossfade to a clip without restarting it if it is already the current one. Returns false when the clip
## does not exist, so callers can fall back.
static func play_smooth(anim_player: AnimationPlayer, anim_name: String, blend: float = -1.0, speed: float = 1.0) -> bool:
	if anim_player == null or not anim_player.has_animation(anim_name):
		return false
	if anim_player.current_animation != anim_name or not anim_player.is_playing():
		anim_player.play(anim_name, blend, speed)
	return true

## First AnimationPlayer under `node` (or null).
static func find_player(node: Node) -> AnimationPlayer:
	if node == null:
		return null
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var found := find_player(c)
		if found:
			return found
	return null
