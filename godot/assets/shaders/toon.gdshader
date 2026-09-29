// Cel shader reproducing upstream pokesprite.js's lighting in 3D.
//
// Upstream shades every sprite pixel with a 6-entry hue-shifted ramp of its base colour
// (gfx.js shade(): darker steps lean toward a cool blue/violet hue, lighter steps toward a
// warm yellow) picked by thresholds on N.L with a fixed screen-space light from the upper
// left.  Here N is the real 3D view-space normal and L the same screen-space light, so a
// model reads like its sprite from any camera (front for the foe, back for the player's
// Pokemon).  Works in the Compatibility (opengl3) renderer: unshaded, no light() pass.
shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform bool use_texture = true;
uniform vec4 albedo_color : source_color = vec4(1.0);
// light direction in VIEW space (x right, y up, z toward the camera) = upstream's L mirrored to y-up
uniform vec3 light_view = vec3(-0.466, 0.671, 0.577);
uniform bool gloss = false;           // allow the brightest (+0.42) step everywhere
uniform float band_soft = 0.03;       // anti-aliasing width of band edges (in N.L units)
uniform vec4 tint : source_color = vec4(1.0);          // multiply (time of day, status tints)
uniform vec4 flash : source_color = vec4(1.0, 1.0, 1.0, 0.0); // mix toward flash.rgb by flash.a (hit flash)
uniform float fade = 0.0;             // 0..1 dissolve toward transparent-dark (faint)
uniform float rim = 0.12;             // subtle back-rim so silhouettes pop against dark backgrounds
uniform float ramp_bias = 0.0;        // added to N.L (e.g. +0.2 keeps faces out of the shadow bands)
uniform float ramp_strength = 1.0;    // scales the ramp's shade amounts (softer look for characters)
// Baked ambient occlusion (COLOR.r of the vertex colour; the Pokemon glbs carry it -- PokemonActor turns it on).
// 0 = off (default, so every other model is unchanged).  Occluded areas take the darkest ramp step (cool hue).
uniform float use_vertex_ao : hint_range(0.0, 1.0) = 0.0;

vec3 rgb2hsl(vec3 c) {
	float mx = max(c.r, max(c.g, c.b));
	float mn = min(c.r, min(c.g, c.b));
	float l = (mx + mn) * 0.5;
	float h = 0.0;
	float s = 0.0;
	float d = mx - mn;
	if (d > 1e-5) {
		s = clamp(l > 0.5 ? d / max(2.0 - mx - mn, 1e-4) : d / max(mx + mn, 1e-4), 0.0, 1.0);
		if (mx == c.r) {
			h = (c.g - c.b) / d + (c.g < c.b ? 6.0 : 0.0);
		} else if (mx == c.g) {
			h = (c.b - c.r) / d + 2.0;
		} else {
			h = (c.r - c.g) / d + 4.0;
		}
		h *= 60.0;
	}
	return vec3(h, s, l);
}

float hue2rgb(float p, float q, float t) {
	t = fract(t);
	if (t < 1.0 / 6.0) return p + (q - p) * 6.0 * t;
	if (t < 0.5) return q;
	if (t < 2.0 / 3.0) return p + (q - p) * (2.0 / 3.0 - t) * 6.0;
	return p;
}

vec3 hsl2rgb(vec3 hsl) {
	float h = hsl.x / 360.0;
	float s = hsl.y;
	float l = hsl.z;
	if (s <= 1e-5) return vec3(l);
	float q = l < 0.5 ? l * (1.0 + s) : l + s - l * s;
	float p = 2.0 * l - q;
	return vec3(hue2rgb(p, q, h + 1.0 / 3.0), hue2rgb(p, q, h), hue2rgb(p, q, h - 1.0 / 3.0));
}

// gfx.js shade(c, amt) -- operates on sRGB values like the original
vec3 shade(vec3 c, float amt) {
	vec3 hsl = rgb2hsl(c);
	if (amt < 0.0) {
		float dh = mod(250.0 - hsl.x + 540.0, 360.0) - 180.0;
		return hsl2rgb(vec3(hsl.x + dh * min(1.0, -amt) * 0.35, min(1.0, hsl.y * (1.0 - amt * 0.15)), max(0.0, hsl.z + amt * 0.5)));
	}
	float dh = mod(55.0 - hsl.x + 540.0, 360.0) - 180.0;
	return hsl2rgb(vec3(hsl.x + dh * min(1.0, amt) * 0.3, max(0.0, hsl.y * (1.0 - amt * 0.1)), min(1.0, hsl.z + amt * 0.5)));
}

vec3 to_srgb(vec3 c) {
	return mix(pow(c, vec3(1.0 / 2.4)) * 1.055 - 0.055, c * 12.92, lessThan(c, vec3(0.0031308)));
}

vec3 to_linear(vec3 c) {
	return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, lessThan(c, vec3(0.04045)));
}

void fragment() {
	vec3 base = albedo_color.rgb;
	if (use_texture) {
		base *= texture(albedo_tex, UV).rgb;
	}
	vec3 c = to_srgb(base);  // ramp math in sRGB, like upstream
	vec3 n = normalize(NORMAL);  // view space
	float I = dot(n, normalize(light_view)) + ramp_bias;
	// upstream thresholds: >0.86 (gloss) +0.42 | >0.62 +0.2 | >0.32 base | >0.08 -0.17 | else -0.38
	float s = band_soft;
	float amt = -0.38;
	amt = mix(amt, -0.17, smoothstep(0.08 - s, 0.08 + s, I));
	amt = mix(amt, 0.0, smoothstep(0.32 - s, 0.32 + s, I));
	amt = mix(amt, 0.2, smoothstep(0.62 - s, 0.62 + s, I));
	float top = gloss ? 0.86 : 0.94;
	amt = mix(amt, 0.42, smoothstep(top - s, top + s, I));
	amt *= ramp_strength;
	vec3 col;
	if (amt < 0.0) {
		col = shade(c, amt);
	} else {
		col = mix(c, shade(c, max(amt, 0.001)), step(0.001, amt));
	}
	// soft rim on the silhouette facing away from the light (keeps dark sides readable)
	float fres = pow(1.0 - clamp(n.z, 0.0, 1.0), 3.0);
	col = mix(col, shade(c, 0.1), fres * rim * step(I, 0.32));
	// baked AO: soft toward the darkest cel step so creases / armpits / under-chins read
	float occ = (1.0 - clamp(COLOR.r, 0.0, 1.0)) * use_vertex_ao;
	col = mix(col, shade(c, -0.36 * ramp_strength), clamp(occ * 0.85, 0.0, 0.85) * (0.5 + 0.5 * smoothstep(0.0, 0.35, occ)));
	col = to_linear(col);
	col *= tint.rgb;
	col = mix(col, flash.rgb, flash.a);
	col = mix(col, vec3(0.02, 0.02, 0.04), fade);
	ALBEDO = col;
}
