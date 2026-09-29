// Small procedural sprites for overworld effects (footstep dust, landing puffs, water rings, grass blades,
// sparkles). Everything is drawn from UV in the fragment shader: no textures. Colours follow the day/night grade.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0);
uniform float alpha = 1.0;
uniform int kind = 0;            // 0 soft puff, 1 ground ring, 2 leaf blade, 3 four-point sparkle, 4 hard drop
uniform vec3 grade = vec3(1.0);
uniform float seed = 0.0;
uniform float spin = 0.0;        // radians, rotates the sprite in its own plane

#define to_output(c) (OUTPUT_IS_SRGB ? (c) : mix((c) / 12.92, pow(((c) + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), (c))))

void vertex() {
	if (kind != 1) {
		// camera-facing quad, keeping the node's scale
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
		MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
			vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0), vec4(0.0, 0.0, 0.0, 1.0));
	}
}

void fragment() {
	vec2 p = (UV - 0.5) * 2.0;
	float c = cos(spin), s = sin(spin);
	vec2 q = vec2(c * p.x - s * p.y, s * p.x + c * p.y);
	float a = 0.0;
	if (kind == 0) {
		// lumpy soft cloud: radius wobbles with the angle
		float ang = atan(p.y, p.x);
		float wob = 0.78 + 0.16 * sin(ang * 3.0 + seed * 6.0) + 0.08 * sin(ang * 5.0 + seed * 11.0);
		float d = length(p) / wob;
		a = smoothstep(1.0, 0.25, d);
		a = a * a * (3.0 - 2.0 * a) * 0.9;
	} else if (kind == 1) {
		float d = length(p);
		a = smoothstep(0.55, 0.85, d) * smoothstep(1.0, 0.9, d);
	} else if (kind == 2) {
		// pointed leaf: |x| < (1-|y|^1.7)*0.5
		float w = pow(max(0.0, 1.0 - pow(abs(q.y), 1.7)), 0.9) * 0.5;
		a = 1.0 - smoothstep(w * 0.85, w, abs(q.x));
		a *= step(abs(q.y), 1.0);
	} else if (kind == 3) {
		float r = sqrt(abs(q.x)) + sqrt(abs(q.y));
		float glow = smoothstep(1.0, 0.0, length(p));
		a = max(smoothstep(1.0, 0.55, r), glow * glow * 0.6);
	} else {
		float d = length(p);
		a = 1.0 - smoothstep(0.8, 1.0, d);
	}
	ALBEDO = to_output(color.rgb * grade);
	ALPHA = a * alpha * color.a;
}
