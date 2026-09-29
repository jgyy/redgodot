// Battle set dressing (pipeline/blender/env_bgprops.py): flat ramp-lit vertex colours (authored sRGB, stored linear
// by the glTF exporter), unshaded like upstream's painted backdrop, with an optional sun-side wind sway for foliage
// and a candle-like flicker for glowing parts. Tinted with the stage (night / elite rooms) unless it is a glow.
shader_type spatial;
render_mode unshaded, cull_disabled;

uniform vec3 tint = vec3(1.0);     // sRGB multiplier
uniform float sway = 0.0;
uniform float flicker = 0.0;

vec3 srgb_to_linear(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

vec3 linear_to_srgb(vec3 c) {
	return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
}

// the Compatibility renderer writes sRGB straight to the screen; Forward+/Mobile expect linear
#define to_output(c) (OUTPUT_IS_SRGB ? (c) : srgb_to_linear(c))

void vertex() {
	if (sway > 0.0 && COLOR.a < 0.07) {   // vertex alpha = detail id; id 0 = foliage
		float w = clamp(VERTEX.y * 0.9, 0.0, 1.0);
		vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
		VERTEX.x += sin(TIME * 1.6 + wp.x * 1.7 + wp.z * 0.9) * sway * w * w;
		VERTEX.z += cos(TIME * 1.3 + wp.x * 0.8) * sway * 0.5 * w * w;
	}
}

void fragment() {
	vec3 c = linear_to_srgb(COLOR.rgb);
	if (flicker > 0.0) {
		c *= 1.0 + sin(TIME * 17.0 + UV.x * 3.0) * flicker * 0.07 + sin(TIME * 29.0) * flicker * 0.05;
	}
	ALBEDO = to_output(clamp(c * tint, 0.0, 1.0));
}
