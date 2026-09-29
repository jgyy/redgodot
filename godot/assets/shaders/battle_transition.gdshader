// Battle intro wipes over a snapshot of the overworld (upstream battleflow.js transition(), in screen space so it
// scales to any resolution).  t counts 60 fps frames.
//   kind 0 wild : white flashes, then a dithered black spiral       (62 frames)
//   kind 1 trainer : alternating bands sweep in from both sides    (52 frames)
//   kind 2 boss : a spinning Poke Ball grows from the centre       (48 frames)
shader_type canvas_item;

uniform sampler2D snap : source_color, filter_nearest;
uniform int kind = 0;
uniform float t = 0.0;



float bayer4(vec2 p) {
	int x = int(mod(p.x, 4.0));
	int y = int(mod(p.y, 4.0));
	float m[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return (m[x + y * 4] + 0.5) / 16.0;
}

void fragment() {
	vec3 c = texture(snap, UV).rgb;
	vec2 px = UV * vec2(320.0, 180.0);
	if (kind == 0) {
		if (t < 24.0) {
			if (mod(floor(t / 4.0), 2.0) < 0.5) c = mix(c, vec3(1.0), 0.7);
		} else {
			float k = (t - 24.0) / 36.0;
			vec2 cell = floor(px / 2.0) * 2.0 + 1.0;
			float a = atan(cell.y - 90.0, cell.x - 160.0) / 6.28318530718 + 0.5;
			float r = length(cell - vec2(160.0, 90.0)) / 184.0;
			float v = fract(a + r * 0.6) + (bayer4(floor(px / 2.0)) - 0.5) * 0.18;
			if (v < k * 1.4) c = vec3(0.0);
		}
	} else if (kind == 1) {
		float k2 = max(0.0, t - 8.0) / 40.0;
		float band = floor(px.y / 12.0);
		float cover = min(1.0, k2 * 1.3 - band * 0.012) * 320.0;
		if (cover > 0.0) {
			bool from_left = mod(band, 2.0) > 0.5;
			if (from_left ? px.x < cover : px.x > 320.0 - cover) c = vec3(0.0);
		}
		if (t < 8.0 && mod(t, 4.0) < 2.0) c = mix(c, vec3(1.0), 0.6);
	} else {
		float k = clamp(t / 44.0, 0.0, 1.0);
		float dark = smoothstep(0.0, 1.0, k);
		c *= 1.0 - dark * 0.85;
		if (t < 10.0 && mod(t, 4.0) < 2.0) c = mix(c, vec3(1.0), 0.6);   // upstream's opening white flicker
		float R = 0.04 + k * k * 1.35;                 // in screen-height units
		vec2 d = (UV - vec2(0.5)) * vec2(320.0 / 180.0, 1.0);
		float ang = t * 0.18;
		vec2 q = vec2(cos(ang) * d.x + sin(ang) * d.y, -sin(ang) * d.x + cos(ang) * d.y);
		float l = length(q);
		if (l < R) {
			vec3 ball = q.y < 0.0 ? vec3(0.86, 0.13, 0.13) : vec3(0.97, 0.97, 0.97);
			float shine = smoothstep(0.55 * R, 0.35 * R, length(q - vec2(-0.45, -0.45) * R));
			if (q.y < 0.0) ball = mix(ball, vec3(1.0, 0.55, 0.55), shine * 0.7);
			if (abs(q.y) < 0.09 * R) ball = vec3(0.04);
			float bl = length(q);
			if (bl < 0.24 * R) ball = vec3(0.04);
			if (bl < 0.16 * R) ball = vec3(0.98);
			if (bl > 0.94 * R) ball = vec3(0.04);
			c = ball;
		}
		if (k >= 0.98) c = mix(c, vec3(0.0), (k - 0.98) / 0.02);
	}
	COLOR = vec4(c, 1.0);
}
