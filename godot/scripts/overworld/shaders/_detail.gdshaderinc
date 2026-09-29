// Detail atlas shared by the ground/object shader and the prop shader (pipeline/blender/env_textures.py):
// 6x2 tiles of 64 px (+2 px wrapped gutter) holding 0.5-grey modulation textures. Tile ids:
// 0 grass, 1 path, 2 sand, 3 pave, 4 rock, 5 floor, 6 carpet, 7 wood, 8 tower, 9 water, 10 cliff.
uniform sampler2D detail_tex : filter_linear, repeat_disable;
uniform float detail_amt = 0.6;

const float DT = 64.0;    // tile texels
const float DC = 68.0;    // + gutter
const float DAMT[11] = float[11](0.95, 0.95, 0.70, 0.85, 0.85, 0.60, 0.60, 0.50, 0.85, 0.55, 0.85);

vec3 detail_tile(int tile, vec2 p) {
	vec2 f = fract(p);
	vec2 org = vec2(float(tile % 6), float(tile / 6)) * DC + 2.0 + f * DT;
	return texture(detail_tex, org / vec2(6.0 * DC, 2.0 * DC)).rgb;
}

// two differently scaled/offset samples so the 32 px tile never reads as a repeat
vec3 detail_mod(int tile, vec2 px) {
	vec3 a = detail_tile(tile, px / 32.0);
	vec3 b = detail_tile(tile, px / 45.0 + vec2(0.37, 0.61));
	return (a + b - 1.0) * 0.82 + 0.5;
}
