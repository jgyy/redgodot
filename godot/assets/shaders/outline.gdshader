// Inverted-hull outline in upstream's outline colour: mix(shade(c, -0.8), #141220, 0.55),
// where c is the albedo under the outline (pokesprite.js "outer outline: tinted dark of
// neighbour").  Used as the toon material's next_pass.  The hull is pushed out in view
// space by an amount that keeps the line ~width_px screen pixels wide at any distance.  Where two art
// groups intersect, the hull of the rear one pokes through and draws upstream's inner line.
shader_type spatial;
render_mode unshaded, cull_front, depth_draw_opaque, skip_vertex_transform;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform bool use_texture = true;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform float width_px = 2.4;          // line width in pixels of a viewport_h-tall view (scales with resolution)
uniform float viewport_h = 540.0;      // reference screen height for width_px (VIEWPORT_SIZE is
                                       // not reliable in the Compatibility renderer's vertex stage)
uniform float max_world = 0.04;        // clamp: never thicker than this many metres
uniform vec4 tint : source_color = vec4(1.0);
uniform float fade = 0.0;

vec3 rgb2hsl(vec3 c) {
	float mx = max(c.r, max(c.g, c.b));
	float mn = min(c.r, min(c.g, c.b));
	float l = (mx + mn) * 0.5;
	float h = 0.0;
	float s = 0.0;
	float d = mx - mn;
	if (d > 1e-5) {
		s = l > 0.5 ? d / (2.0 - mx - mn) : d / (mx + mn);
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

vec3 to_srgb(vec3 c) {
	return mix(pow(c, vec3(1.0 / 2.4)) * 1.055 - 0.055, c * 12.92, lessThan(c, vec3(0.0031308)));
}

vec3 to_linear(vec3 c) {
	return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, lessThan(c, vec3(0.04045)));
}

void vertex() {
	// view-space hull push sized so the line is ~width_px screen pixels wide
	VERTEX = (MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 nv = normalize((MODELVIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	float persp = PROJECTION_MATRIX[3][3] < 0.5 ? -VERTEX.z : 1.0;   // ortho: constant
	float world_per_px = 2.0 * persp / (max(abs(PROJECTION_MATRIX[1][1]), 1e-4)  /* y may be flipped for render targets */ * max(viewport_h, 1.0));
	float w = min(width_px * world_per_px, max_world);
	VERTEX += nv * w;
	NORMAL = nv;
}

void fragment() {
	vec3 base = albedo_color.rgb;
	if (use_texture) {
		base *= texture(albedo_tex, UV).rgb;
	}
	vec3 c = to_srgb(base);
	vec3 hsl = rgb2hsl(c);
	float dh = mod(250.0 - hsl.x + 540.0, 360.0) - 180.0;
	vec3 dark = hsl2rgb(vec3(hsl.x + dh * 0.8 * 0.35, min(1.0, hsl.y * 1.12), max(0.0, hsl.z - 0.4)));
	vec3 o = mix(dark, vec3(0.0784, 0.0706, 0.1255), 0.55);
	ALBEDO = mix(to_linear(o) * tint.rgb, vec3(0.02, 0.02, 0.04), fade);
}
