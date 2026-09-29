// Soft contact shadow under overworld characters (upstream draws a 5.5x2px multiplied ellipse).
shader_type spatial;
render_mode unshaded, blend_mul, depth_draw_never, cull_disabled, shadows_disabled;

void fragment() {
	vec2 d = (UV - 0.5) * 2.0;
	float r = dot(d, d);
	float a = r < 1.0 ? 0.5 : 0.0;
	// multiply toward upstream's shadow tint rgb(150,150,190)
	ALBEDO = mix(vec3(1.0), vec3(0.30, 0.30, 0.52), a);
}
