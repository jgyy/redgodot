// Tall grass cards (mode 0) and flower ground cards (mode 1), textured from upstream's own sprites
// (res://assets/maps/decor_atlas.png: 16 tiles of 16x16 = grass v0f0,v0f1..v3f1, flowers red,yellow,white,pink
// x f0,f1) with upstream's frame timing: grass tips sway one frame in five every 40 frames and while
// rustling, flowers flip every 24 frames.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;
#include "res://scripts/overworld/shaders/_common.gdshaderinc"

uniform sampler2D tex : filter_nearest, repeat_disable;
uniform int mode = 0;
varying vec2 p2d;
varying vec4 custom;

void vertex() {
	p2d = p2d_of((MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz);
	custom = INSTANCE_CUSTOM;
}

void fragment() {
	float t = TIME * 60.0;
	float tile;
	if (mode == 0) {
		float f = custom.g > 0.5 ? 1.0 : (mod(floor(t / 40.0 + custom.b), 5.0) < 0.5 ? 1.0 : 0.0);
		tile = floor(custom.r + 0.5) * 2.0 + f;
	} else {
		float f = mod(floor(t / 24.0) + custom.b, 2.0);
		tile = 8.0 + floor(custom.r + 0.5) * 2.0 + f;
	}
	vec2 uv = vec2((tile + clamp(UV.x, 0.0, 0.999)) / 16.0, clamp(UV.y, 0.0, 0.999));
	vec4 c = texture(tex, uv);
	if (c.a < 0.5) discard;
	ALBEDO = to_output(clamp(night_light(c.rgb, p2d), 0.0, 1.0));
}
