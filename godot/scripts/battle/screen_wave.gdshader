// upstream vfx.js wave(): horizontal sine displacement of the battle area's rows
// (PSYCHIC, CONFUSION, PSYBEAM). Only the top 132/180 of the screen is affected.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform float amp = 0.0;      // in UV units
uniform float phase = 0.0;

void fragment() {
	vec2 uv = SCREEN_UV;
	float row = floor(uv.y * 180.0);
	float sh = 0.0;
	if (row < 132.0) {
		sh = round(sin(row * 0.18 + phase) * amp * 320.0) / 320.0;
	}
	COLOR = texture(screen_tex, vec2(clamp(uv.x - sh, 0.0, 1.0), uv.y));
}
