// Full-screen environment grading from upstream src/art/ambient.js, applied over the 3D view (under the UI):
// Lavender Town / Pokémon Tower purple tint + drifting fog, the soft vignette of caves / the tower / the mansion /
// Seafoam, and Seafoam's icy haze. Coordinates follow upstream's 320x180 screen.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform sampler2D big_tex : filter_nearest, repeat_enable;   // upstream N.big
uniform vec3 tint = vec3(1.0);          // multiplicative (0..1), 1 = off
uniform bool fog = false;
uniform float vignette = 0.0;           // strength, 0 = off
uniform vec3 vignette_col = vec3(0.051, 0.039, 0.071);
uniform float ice = 0.0;                // mix toward #dceeff
uniform vec2 cam_px = vec2(0.0);        // map-local px of the screen's top-left (upstream cx, cy)
uniform bool dark = false;              // fieldmoves.js ambientDark: caves needing FLASH

const float BAYER[16] = float[16](0.03125, 0.53125, 0.15625, 0.65625, 0.78125, 0.28125, 0.90625, 0.40625,
	0.21875, 0.71875, 0.09375, 0.59375, 0.96875, 0.46875, 0.84375, 0.34375);

void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	vec2 s = floor(SCREEN_UV * vec2(320.0, 180.0));
	if (tint != vec3(1.0) || fog) {
		c *= tint;
		if (fog) {
			float t = TIME * 60.0;
			vec2 n = mod(floor((cam_px + s) / 2.0) + vec2(floor(t / 4.0), floor(t / 8.0)), 256.0);
			float f = texture(big_tex, (n + 0.5) / 256.0).r;
			if (f > 0.55) {
				float k = min(0.35, (f - 0.55) * 1.4);
				c = mix(c, vec3(0.722, 0.659, 0.816), k);
			}
		}
	}
	if (vignette > 0.0) {
		float xx = (s.x - 160.0) / 190.0, yy = (s.y - 90.0) / 120.0;
		float r2 = xx * xx + yy * yy;
		if (r2 >= 0.3844) {
			float k = min(1.0, (sqrt(r2) - 0.62) * 1.6) * vignette;
			c = mix(c, vignette_col, k);
		}
	}
	if (ice > 0.0) c = mix(c, vec3(0.863, 0.933, 1.0), ice);
	if (dark) {
		float r = length(vec2(s.x - 160.0, (s.y - 86.0) * 1.1));
		if (r >= 18.0) {
			float k = min(1.0, (r - 18.0) / 14.0);
			vec3 black = vec3(0.051, 0.047, 0.086);
			int bi = int(mod(s.y, 4.0)) * 4 + int(mod(s.x, 4.0));
			c = BAYER[bi] < k ? black : mix(c, black, 0.45);
		}
	}
	COLOR = vec4(c, 1.0);
}
