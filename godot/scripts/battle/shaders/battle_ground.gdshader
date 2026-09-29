// Battle floors / seas: upstream's painted 320x180 "screen" texture (pipeline/blender/gen_battlebg.py + env_bg.py),
// projected onto the ground plane *per fragment* from the resting camera, so the perspective-correct tiles, planks and
// wave crests painted in world space land exactly where they were painted (a mesh only interpolates the UV
// approximately). The plane is still a lit 3D surface, so it receives the Pokemon's shadows.
// Water variants add a slow swell (the painted crests drift) and twinkling glints.
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_disabled;

uniform sampler2D albedo_tex : source_color, filter_nearest, repeat_disable;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec3 cam_pos = vec3(0.0, 1.6, 0.0);
uniform float cam_pitch_deg = -11.5;
uniform float cam_fov_deg = 34.0;
uniform float water_rows = 0.0;       // > 0: rows of the 320x180 art above this are animated water
uniform float glint_col = 1.0;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float h21(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float vnoise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(h21(i), h21(i + vec2(1, 0)), f.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), f.x), f.y);
}

vec2 project(vec3 wp) {
	float p = radians(cam_pitch_deg);
	vec3 f = vec3(0.0, sin(p), -cos(p));
	vec3 up = vec3(0.0, cos(p), sin(p));
	vec3 r = vec3(1.0, 0.0, 0.0);
	float th = tan(radians(cam_fov_deg) * 0.5);
	vec3 v = wp - cam_pos;
	float z = dot(v, f);
	vec2 s = vec2(dot(v, r), dot(v, up)) / (z * th);
	return vec2(s.x * 270.0 + 480.0, 270.0 - s.y * 270.0) / 3.0;   // px of the 320x180 art
}

void fragment() {
	vec2 px = project(wpos);
	bool water = water_rows > 0.0 && px.y < water_rows;
	vec2 uv_px = px;
	if (water) {
		uv_px.x += sin(wpos.z * 0.9 + TIME * 0.8) * 0.7 + sin(wpos.z * 2.3 - TIME * 1.3 + wpos.x * 0.2) * 0.3;
	}
	vec3 c = texture(albedo_tex, uv_px / vec2(320.0, 180.0)).rgb;
	if (water) {
		vec2 g = wpos.xz;
		float cell = floor(g.x * 5.0) * 7.0 + floor(g.y * 5.0) * 13.0;
		float ph = TIME * 1.1 + h21(vec2(cell, 3.0)) * 6.283;
		float sp = step(0.955, h21(vec2(floor(g.x * 5.0), floor(g.y * 5.0)))) * smoothstep(0.55, 1.0, sin(ph));
		float caus = smoothstep(0.62, 0.95, vnoise(g * vec2(1.3, 2.2) + vec2(TIME * 0.25, TIME * 0.12)) * vnoise(g * vec2(2.7, 4.1) - vec2(TIME * 0.18, 0.0)) * 1.9);
		c += vec3(0.05, 0.09, 0.13) * caus * 0.55;
		c = mix(c, vec3(1.0), sp * 0.85 * glint_col);
	}
	ALBEDO = c * tint.rgb;
	ROUGHNESS = 1.0;
}
