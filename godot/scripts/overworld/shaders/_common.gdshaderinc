// Shared by the world / tree / decor shaders: 2D-screen-space position of a fragment (the oblique projection
// back onto the map, in baked px), upstream's night grade and dithered light pools, sRGB output.
uniform sampler2D light_tex : hint_default_black, filter_linear, repeat_disable;
uniform vec2 map_px = vec2(512.0);
uniform vec2 margin = vec2(0.0);
uniform float k_vert = 1.428;
uniform vec3 grade = vec3(1.0);
uniform float light_amt = 0.0;

const float BAYER[16] = float[16](0.03125, 0.53125, 0.15625, 0.65625, 0.78125, 0.28125, 0.90625, 0.40625,
	0.21875, 0.71875, 0.09375, 0.59375, 0.96875, 0.46875, 0.84375, 0.34375);

vec2 p2d_of(vec3 wp) {
	return vec2(wp.x + margin.x, wp.z + margin.y - wp.y / k_vert) * 16.0;
}

vec3 srgb_to_linear(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

vec3 linear_to_srgb(vec3 c) {
	return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
}

// our colour maths is in sRGB like the 2D game; the Compatibility renderer also outputs sRGB directly,
// Forward+/Mobile expect linear
#define to_output(c) (OUTPUT_IS_SRGB ? (c) : srgb_to_linear(c))

// ambient.js cloud shadows: upstream N.big noise drifting over the map (outdoors, by day)
uniform bool clouds = false;
uniform float cloud_t = 0.0;     // frames
uniform sampler2D big_tex : hint_default_black, filter_nearest, repeat_enable;

vec3 cloud_shadow(vec3 col, vec2 p2d) {
	if (!clouds) return col;
	vec2 lp = floor(p2d - margin * 16.0);   // map-local px (upstream camera space)
	float ct = cloud_t + TIME * 60.0;
	vec2 o = floor(vec2(ct * 0.18, ct * 0.07));
	vec2 cell = mod(floor(lp / 4.0) + o, 256.0);
	float v = texture(big_tex, (cell + 0.5) / 256.0).r;
	if (v > 0.68 || (v > 0.665 && mod(lp.x + lp.y, 2.0) > 0.5)) col *= vec3(196.0, 204.0, 232.0) / 256.0;
	return col;
}

vec3 night_light(vec3 col, vec2 p2d) {
	col = cloud_shadow(col, p2d);
	col *= grade;
	if (light_amt > 0.001) {
		vec2 pix = floor(p2d);
		vec4 L = texture(light_tex, (pix + 0.5) / map_px);
		int bi = int(mod(pix.y, 4.0)) * 4 + int(mod(pix.x, 4.0));
		float q = clamp(floor(L.a * 4.0 + BAYER[bi]), 0.0, 4.0);
		float tb = q * 0.62 * light_amt / 4.0;
		vec3 scr = 1.0 - (1.0 - col) * (1.0 - L.rgb);
		col = mix(col, scr, tb);
	}
	return col;
}
