// Inverted-hull outline for the 3D trees: upstream outlines every foliage sprite with its ramp's darkest colour.
shader_type spatial;
render_mode unshaded, cull_front, depth_draw_opaque;
#include "res://scripts/overworld/shaders/_common.gdshaderinc"

uniform vec3 outline_srgb = vec3(0.047, 0.137, 0.133);
uniform float width = 0.035;
varying vec2 p2d;

void vertex() {
	VERTEX += NORMAL * width;
	p2d = p2d_of((MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz);
}

void fragment() {
	ALBEDO = to_output(clamp(night_light(outline_srgb, p2d), 0.0, 1.0));
}
