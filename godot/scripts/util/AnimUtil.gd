class_name AnimUtil
extends RefCounted
## The Blender pipeline bakes Idle/Walk (meant to loop) and Attack (a one-shot
## lunge) into every generated glb, but glTF import doesn't set the Animation
## resource's loop mode on its own - do it here once per loaded model instead
## of per call site.

const LOOPING := ["Idle", "Walk"]

static func fix_looping(anim_player: AnimationPlayer) -> void:
	if anim_player == null:
		return
	for anim_name in LOOPING:
		if anim_player.has_animation(anim_name):
			var anim := anim_player.get_animation(anim_name)
			anim.loop_mode = Animation.LOOP_LINEAR
