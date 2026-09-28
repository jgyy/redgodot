// Animated map effects, drawn procedurally at upstream's pixel scale:
//  mode 0: brazier flame (terrain.js drawFlame), on a card standing on the brazier bowl (12x17 px)
//  mode 1: electric barrier lines (interior.js drawOverlay 'barrier'), on the cell's ground (16x16 px)
//  mode 2: teleport pad pulse (interior.js drawOverlay 'teleport'), on the cell's ground (16x16 px)
shader_type spatial;
render_mode unshaded, cull_disabled, blend_mix, depth_draw_opaque, shadows_disabled;

uniform int mode = 0;
varying vec4 custom;

#define to_output(c) (OUTPUT_IS_SRGB ? (c) : mix((c) / 12.92, pow(((c) + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), (c))))

void vertex() {
	custom = INSTANCE_CUSTOM;
}

float h3(float a, float b, float c) {
	uint h = uint(int(a)) * 374761393u + uint(int(b)) * 668265263u + uint(int(c)) * 2147483647u;
	h = (h ^ (h >> 13u)) * 1274126177u;
	h = h ^ (h >> 16u);
	return float(h) / 4294967296.0;
}

const vec3 FLAME[5] = vec3[5](vec3(1.0, 0.984, 0.878), vec3(1.0, 0.894, 0.463), vec3(1.0, 0.671, 0.204), vec3(0.949, 0.4, 0.110), vec3(0.722, 0.204, 0.102));

void fragment() {
	float t = floor(TIME * 60.0);
	vec3 col = vec3(1.0);
	float a = 1.0;
	if (mode == 0) {
		vec2 p = floor(clamp(UV, 0.0, 0.999) * vec2(12.0, 17.0));
		float seed = custom.r;
		float f = floor(t / 5.0) + seed * 13.0;
		float r = 16.0 - p.y;
		float hf = 10.0 + floor(h3(f, seed, 31.0) * 3.0);
		if (r < 0.0 || r >= hf) discard;
		float k = r / hf;
		float w = 4.4 * pow(1.0 - k, 0.7) + (h3(f, r, 32.0) - 0.5) * 1.1;
		if (w < 0.4) discard;
		float cxo = sin(f * 0.9 + r * 0.55 + seed) * k * 1.7;
		float x = p.x - 6.0;
		float d = abs(x + 0.5 - cxo) / w;
		if (d > 1.0) discard;
		float v = d * 0.7 + k * 0.62 + (h3(x + f, r, 33.0) - 0.5) * 0.22;
		col = FLAME[int(clamp(floor(v * 4.0), 0.0, 4.0))];
	} else if (mode == 1) {
		vec2 p = floor(clamp(UV, 0.0, 0.999) * 16.0);
		bool hit = false;
		for (int k = 0; k < 3; k++) {
			float yy = 2.0 + mod(t * 2.0 + float(k) * 5.0, 14.0);
			float i = floor(p.x / 2.0);
			float j = h3(i + custom.r * 17.0, float(k), t) < 0.5 ? -1.0 : 1.0;
			float y = yy + ((p.x - i * 2.0) >= 1.0 ? j : 0.0);
			if (abs(p.y - y) < 0.5) hit = true;
		}
		if (!hit) discard;
		col = vec3(0.973, 0.941, 0.502);
	} else {
		vec2 p = floor(clamp(UV, 0.0, 0.999) * 16.0) + 0.5;
		float ph = mod(t, 30.0);
		float r = 3.0 + ph / 5.0;
		vec2 d = (p - vec2(8.0, 7.0)) / vec2(r * 1.3, r);
		if (dot(d, d) > 1.0) discard;
		col = vec3(0.753, 0.910, 1.0);
		a = 0.25 * (1.0 - ph / 30.0);
	}
	ALBEDO = to_output(col);
	ALPHA = a;
}
