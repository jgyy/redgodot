// World material for everything baked from the 2D game: the ground plane and every extruded object
// (buildings, walls, furniture, fences, signs...). Colours come straight from upstream's painters, so it is
// unshaded; 3D form comes from a per-face shade (light from the top-left, like the 2D art), and day/dusk/night
// is upstream ambient.js's multiplicative grade plus its dithered light pools, sampled in "2D screen space"
// (the oblique projection of each fragment back onto the map), exactly where the 2D game would draw them.
// All colour maths happens in sRGB like the 2D game; the result is converted to linear at the end.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;
#include "res://scripts/overworld/shaders/_common.gdshaderinc"
#include "res://scripts/overworld/shaders/_detail.gdshaderinc"

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

// --- procedural richness (pipeline/blender/env_textures.py + GroundDetail.gd) ---
uniform sampler2D class_tex : filter_nearest, repeat_disable;         // per cell: detail tile (255 none, 254 pick from the baked colour)
uniform sampler2D ao_tex : hint_default_black, filter_linear, repeat_disable;  // contact-shadow mask, 4 px per texel
uniform bool detail_on = false;
uniform float ao_amt = 0.20;
uniform float obj_ao = 0.16;
uniform float grain_amt = 0.05;
uniform float obj_grain = 0.0;       // fine material grain over baked objects (walls, roofs, furniture)

varying vec2 p2d;
varying vec3 wnrm;
varying float hpx;      // height above the ground in px of 2D art

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	p2d = p2d_of(wp);
	hpx = wp.y / k_vert * 16.0;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

int auto_tile(vec3 c) {
	if (c.g > c.r + 0.02 && c.g > c.b) return 0;      // grass
	if (c.b >= c.r - 0.01) return 3;                  // cool greys: pavement
	if (c.r - c.b > 0.22) return 1;                   // packed dirt
	return 4;                                         // brown-grey rock
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
	bool solid = !is_ground && COLOR.a < 0.99;     // procedural trim (WorldBuilder._solid): vertex colour, no atlas
	if (!solid && c.a < 0.5) discard;
	vec3 col = c.rgb;
	vec2 pix = floor(p2d);
	bool in_water = false;
	if (!is_ground) {
		if (COLOR.a < 0.99) col = COLOR.rgb;                 // procedural trim geometry: vertex colour instead of the atlas
		else col *= COLOR.rgb * 1.25;                      // baked ambient occlusion (0.8 = unchanged)
	}
	if (is_ground && has_water) {
		vec4 wv = texture(water_tex, (pix + 0.5) / map_px);
		if (wv.r > 0.5 && wv.a > 0.5) {
			float t = floor(TIME * 60.0 / 4.0) * 4.0;
			col = water_color(pix, floor(wv.g * 255.0 / 25.0 + 0.5), wv.b > 0.5, t);
			in_water = true;
		}
	}
	if (is_ground) {
		if (detail_on) {
			ivec2 cell = ivec2(clamp(floor(p2d / 16.0), vec2(0.0), map_px / 16.0 - 1.0));
			int cls = int(texelFetch(class_tex, cell, 0).r * 255.0 + 0.5);
			if (cls == 254) cls = auto_tile(col);
			if (in_water) cls = 9; else if (cls == 9) cls = 255;
			if (cls < 11) {
				vec2 dp = p2d;
				if (cls == 9) dp += vec2(sin(TIME * 0.6 + p2d.y * 0.11), cos(TIME * 0.5 + p2d.x * 0.09)) * 2.0 + TIME * vec2(1.5, 0.7);
				vec3 d = detail_mod(cls, dp);
				float k = DAMT[cls] * detail_amt;
				if (cls == 9) {
					col += (d.r - 0.5) * 0.30 * detail_amt;
				} else {
					col *= 1.0 + (d - 0.5) * 2.0 * k;
				}
			}
			// gentle large-scale tone drift so big fields never look stamped
			float macro = sin(p2d.x * 0.031 + sin(p2d.y * 0.047) * 1.7) * sin(p2d.y * 0.029 + cos(p2d.x * 0.041) * 1.3);
			col *= 1.0 + macro * grain_amt;
			// contact shadow around anything standing on the ground
			vec2 au = p2d / map_px;
			vec2 st = vec2(5.0) / map_px;
			float ao = texture(ao_tex, au).r * 0.36 + (texture(ao_tex, au + vec2(st.x, 0.0)).r + texture(ao_tex, au - vec2(st.x, 0.0)).r
				+ texture(ao_tex, au + vec2(0.0, st.y)).r + texture(ao_tex, au - vec2(0.0, st.y)).r) * 0.16;
			col *= 1.0 - ao_amt * ao;
		}
	}
	if (!is_ground) {
		// light from the top-left, as the 2D art is lit: tops full, faces toward the camera slightly darker,
		// right-facing sides darkest
		vec3 n = normalize(wnrm);
		float sh = 1.0;
		sh -= 0.10 * clamp(n.z, 0.0, 1.0) * (1.0 - clamp(n.y, 0.0, 1.0));
		sh -= 0.28 * clamp(n.x, 0.0, 1.0);
		sh -= 0.16 * clamp(-n.x, 0.0, 1.0);
		col *= mix(1.0, sh, face_shading);
		if (obj_grain > 0.0 && COLOR.a > 0.99) {
			vec3 d = detail_mod(3, p2d * 1.0);
			col *= 1.0 + (d.r - 0.5) * 2.0 * obj_grain;
		}
		// ambient occlusion: walls and furniture darken toward their foot, soft rise toward the top edge
		float vert = 1.0 - clamp(abs(n.y), 0.0, 1.0);
		col *= 1.0 - obj_ao * vert * (1.0 - smoothstep(0.0, 7.0, hpx));
	}
	col = night_light(col, p2d);
	if (light_amt > 0.001) {
		float gl = texture(glow_tex, (pix + 0.5) / map_px).r;
		col = mix(col, vec3(1.0, 0.91, 0.66), gl * 0.75 * light_amt);
	}
	ALBEDO = to_output(clamp(col, 0.0, 1.0));
}
