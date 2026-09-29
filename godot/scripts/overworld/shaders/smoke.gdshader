// Chimney smoke: a few pixel-art puffs per chimney rise, drift with the wind, grow and fade out through upstream's
// Bayer dither (so they stay crisp 2D-art pixels on the 320x180 grid). Camera-facing quads from one MultiMesh; the
// instance origin is the chimney top, INSTANCE_CUSTOM.r a per-puff phase.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque, shadows_disabled;
#include "res://scripts/overworld/shaders/_common.gdshaderinc"

uniform float wind = 1.0;
varying vec2 p2d;
varying float age;

void vertex() {
	float ph = INSTANCE_CUSTOM.r;
	age = fract(TIME * 0.2 + ph);
	vec3 base = MODEL_MATRIX[3].xyz;
	vec3 off = vec3(age * 0.32 * wind + sin(age * 6.0 + ph * 9.0) * 0.06 * age, age * 1.25 * k_vert, 0.0);
	float size = mix(0.2, 0.55, sqrt(age));
	vec4 c = VIEW_MATRIX * vec4(base + off, 1.0);
	c.xy += VERTEX.xy * size;
	POSITION = PROJECTION_MATRIX * c;
	p2d = p2d_of(base + off);
}

void fragment() {
	vec2 u = UV * 2.0 - 1.0;
	float r = length(u);
	if (r > 1.0) discard;
	float a = (1.0 - age * age) * 0.95;
	ivec2 sp = ivec2(FRAGCOORD.xy / 3.0);
	int bi = (sp.y % 4) * 4 + (sp.x % 4);
	if (BAYER[bi] > a) discard;
	vec3 col = mix(vec3(0.96, 0.96, 0.98), vec3(0.66, 0.68, 0.76), smoothstep(0.35, 1.0, r + (u.x + u.y) * 0.18));
	ALBEDO = to_output(clamp(night_light(col, p2d), 0.0, 1.0));
}
