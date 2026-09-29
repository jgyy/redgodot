// Battle actor tint overlay (upstream BattleScene tint[k] = [colour, amount]):
// drawn as GeometryInstance3D.material_overlay on every mesh of a battler.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_back, shadows_disabled;

uniform vec4 tint : source_color = vec4(1.0);
uniform float amt = 0.0;

void fragment() {
	ALBEDO = tint.rgb;
	ALPHA = amt;
}
