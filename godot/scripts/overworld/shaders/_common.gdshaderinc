// Shared by the world / tree / decor shaders: 2D-screen-space position of a fragment (the oblique projection
// back onto the map, in baked px), upstream's night grade and dithered light pools, sRGB output.
uniform sampler2D light_tex : filter_linear, repeat_disable;
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

vec3 night_light(vec3 col, vec2 p2d) {
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
