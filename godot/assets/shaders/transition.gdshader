// Screen-transition mask. The ColorRect's own alpha is the progress (0 = clear .. 1 = fully covered), so the same
// tween that used to fade to black now drives one of several wipes.
//   mode 0 fade | 1 iris (circle closing on `center`) | 2 blinds | 3 diagonal wipe | 4 pixel dissolve
//   mode 5 ball split (red/white halves slide together, black band) | 6 radial clock wipe
shader_type canvas_item;

uniform int mode = 0;
uniform vec2 center = vec2(0.5, 0.5);   // uv, iris centre
uniform float aspect = 1.7778;
uniform vec4 cover : source_color = vec4(0.0, 0.0, 0.0, 1.0);

float bayer4(vec2 p) {
	int x = int(mod(p.x, 4.0));
	int y = int(mod(p.y, 4.0));
	int i = x + y * 4;
	float m[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return (m[i] + 0.5) / 16.0;
}

void fragment() {
	float p = COLOR.a;
	vec2 uv = UV;
	float a = 0.0;
	vec4 col = cover;
	if (mode == 0) {
		a = p;
	} else if (mode == 1) {
		vec2 d = (uv - center) * vec2(aspect, 1.0);
		float maxr = length(max(center, 1.0 - center) * vec2(aspect, 1.0)) + 0.02;
		float r = maxr * (1.0 - p);
		a = smoothstep(r - 0.012, r, length(d));
		a = p >= 0.999 ? 1.0 : a;
	} else if (mode == 2) {
		float band = fract(uv.y * 9.0);
		a = band < clamp(p * 1.15, 0.0, 1.0) ? 1.0 : 0.0;
		a = p >= 0.999 ? 1.0 : a;
	} else if (mode == 3) {
		float d = (uv.x + uv.y * 0.6) / 1.6;
		a = smoothstep(d - 0.06, d, p * 1.12);
		a = p >= 0.999 ? 1.0 : a;
	} else if (mode == 4) {
		vec2 cell = floor(uv * vec2(80.0, 45.0));
		a = (bayer4(cell) + fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453) * 0.35) < p * 1.3 ? 1.0 : 0.0;
		a = p >= 0.999 ? 1.0 : a;
	} else if (mode == 5) {
		float h = 0.5 * p;
		bool top = uv.y < h;
		bool bot = uv.y > 1.0 - h;
		bool mid = abs(uv.y - 0.5) < 0.03 * p && p > 0.4;
		if (top) { col = vec4(0.86, 0.15, 0.15, 1.0); a = 1.0; }
		else if (bot) { col = vec4(0.96, 0.96, 0.96, 1.0); a = 1.0; }
		if (mid) { col = vec4(0.05, 0.05, 0.07, 1.0); a = 1.0; }
		if (p >= 0.999) { col = cover; a = 1.0; }
	} else {
		vec2 d = uv - center;
		float ang = atan(d.x, -d.y) / 6.2831853 + 0.5;
		a = ang < p ? 1.0 : 0.0;
		a = p >= 0.999 ? 1.0 : a;
	}
	COLOR = vec4(col.rgb, a * col.a);
}
