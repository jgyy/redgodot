// World material for everything baked from the 2D game: the ground plane and every extruded object
// (buildings, walls, furniture, fences, signs...). Colours come straight from upstream's painters, so it is
// unshaded; 3D form comes from a per-face shade (light from the top-left, like the 2D art), and day/dusk/night
// is upstream ambient.js's multiplicative grade plus its dithered light pools, sampled in "2D screen space"
// (the oblique projection of each fragment back onto the map), exactly where the 2D game would draw them.
// All colour maths happens in sRGB like the 2D game; the result is converted to linear at the end.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;
#include "res://scripts/overworld/shaders/_common.gdshaderinc"

uniform sampler2D albedo_tex : filter_nearest, repeat_disable;
uniform sampler2D glow_tex : hint_default_black, filter_nearest, repeat_disable;   // r = lit-window rectangles (night)
uniform float face_shading = 1.0;
uniform bool is_ground = false;

// water (ground only)
uniform bool has_water = false;
uniform sampler2D water_tex : filter_nearest, repeat_disable;   // r mask, g dist*25, b deep patch
uniform sampler2D noise_tex : filter_nearest, repeat_enable;    // upstream N.water (128x128)
uniform vec2 world_px0 = vec2(0.0);  // upstream world pixel of baked px (0,0)
uniform vec3 water_pal[8];

varying vec2 p2d;
varying vec3 wnrm;

void vertex() {
	p2d = p2d_of((MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz);
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

float wnoise(vec2 p) {
	return texture(noise_tex, (mod(floor(p), 128.0) + 0.5) / 128.0).r;
}

// upstream terrain.js waterColor()
vec3 water_color(vec2 px, float d, bool deep, float t) {
	vec2 g = world_px0 + px;
	int idx;
	if (d <= 1.0) idx = 7; else if (d < 2.5) idx = 5; else if (d <= 4.0) idx = 4; else idx = deep ? 2 : 3;
	float tt = t * 0.25;
	float w = wnoise(vec2(g.x + tt, g.y * 2.0 + sin((g.x + tt) * 0.12) * 2.0));
	if (d > 2.0) {
		if (w > 0.8) idx = min(6, idx + 2); else if (w > 0.7) idx = min(6, idx + 1); else if (w < 0.14) idx = max(1, idx - 1);
	}
	if (d <= 1.0) {
		float f = sin(t * 0.06 + g.x * 0.4 + g.y * 0.3);
		if (f < -0.35) idx = 6;
	}
	return water_pal[idx];
}

void fragment() {
	vec4 c = texture(albedo_tex, UV);
	if (c.a < 0.5) discard;
	vec3 col = c.rgb;
	vec2 pix = floor(p2d);
	if (is_ground && has_water) {
		vec4 wv = texture(water_tex, (pix + 0.5) / map_px);
		if (wv.r > 0.5 && wv.a > 0.5) {
			float t = floor(TIME * 60.0 / 4.0) * 4.0;
			col = water_color(pix, floor(wv.g * 255.0 / 25.0 + 0.5), wv.b > 0.5, t);
		}
	}
	if (!is_ground) {
		// light from the top-left, as the 2D art is lit: tops full, faces toward the camera slightly darker,
		// right-facing sides darkest
		vec3 n = normalize(wnrm);
		float sh = 1.0;
		sh -= 0.10 * clamp(n.z, 0.0, 1.0) * (1.0 - clamp(n.y, 0.0, 1.0));
		sh -= 0.28 * clamp(n.x, 0.0, 1.0);
		sh -= 0.06 * clamp(-n.x, 0.0, 1.0);
		col *= mix(1.0, sh, face_shading);
	}
	col = night_light(col, p2d);
	if (light_amt > 0.001) {
		float gl = texture(glow_tex, (pix + 0.5) / map_px).r;
		col = mix(col, vec3(1.0, 0.91, 0.66), gl * 0.75 * light_amt);
	}
	ALBEDO = to_output(clamp(col, 0.0, 1.0));
}
