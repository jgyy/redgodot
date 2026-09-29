// 3D trees and props (pipeline/blender/gen_world.py, env_props.py): faces carry upstream's ramp colours as vertex
// colours (authored sRGB, stored linear by the glTF exporter). Vertex alpha < 1 selects a tile of the shared detail
// atlas (wood grain, stone, grass ...) that is laid over the flat colour in the 2D-art pixel space, like the ground.
// Per-instance data (MultiMesh custom): r = brightness variation, g = wind phase, b = wind strength scale.
// `sway` bends the upper part of a mesh in the wind (canopies, grass, flags); 0 = static prop.
shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;
#include "res://scripts/overworld/shaders/_common.gdshaderinc"
#include "res://scripts/overworld/shaders/_detail.gdshaderinc"

uniform bool detail_on = false;
uniform float sway = 0.0;        // horizontal amplitude in cells at the top
uniform float sway_from = 0.6;   // local height where bending starts
uniform float sway_range = 1.0;  // ... and reaches full strength

varying vec2 p2d;
varying vec4 inst;

void vertex() {
	inst = INSTANCE_CUSTOM;
	vec3 v = VERTEX;
	if (sway > 0.0) {
		float w = clamp((v.y - sway_from) / sway_range, 0.0, 1.0);
		w *= w;
		float amp = sway * (1.0 + inst.b);
		float t = TIME * 1.3 + inst.g;
		v.x += (sin(t + v.y * 1.7) * 0.75 + sin(t * 2.3 + v.x * 3.1) * 0.25) * amp * w;
		v.z += cos(t * 0.8 + v.x * 1.3) * amp * 0.5 * w;
	}
	VERTEX = v;
	p2d = p2d_of((MODEL_MATRIX * vec4(v, 1.0)).xyz);
}

void fragment() {
	vec3 col = linear_to_srgb(COLOR.rgb);
	if (detail_on && COLOR.a < 0.99) {
		int tile = int(floor(COLOR.a * 16.0));
		if (tile < 11) {
			vec3 d = detail_mod(tile, p2d);
			col *= 1.0 + (d - 0.5) * 2.0 * DAMT[tile] * detail_amt;
		}
	}
	col *= 1.0 + inst.r;
	ALBEDO = to_output(clamp(night_light(col, p2d), 0.0, 1.0));
}
