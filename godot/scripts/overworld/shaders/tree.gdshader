// 3D trees (pipeline/blender/gen_world.py): faces carry upstream's foliage ramp colours as vertex colours.
shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;
#include "res://scripts/overworld/shaders/_common.gdshaderinc"

varying vec2 p2d;

void vertex() {
	p2d = p2d_of((MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz);
}

void fragment() {
	ALBEDO = to_output(clamp(night_light(linear_to_srgb(COLOR.rgb), p2d), 0.0, 1.0));
}
