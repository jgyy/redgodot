"""Albedo rasteriser for upstream Pokemon sprite definitions (pure numpy, no bpy).

A port of the colour/coverage half of upstream src/art/pokesprite.js (render(),
rasterPart(), drawFeature()) WITHOUT its lighting ramp, dithering, inner lines or
outline: every primitive is painted in its flat palette colour at S texels per sprite
pixel, in continuous (vector) coordinates so eyes, mouths, spots and stripes stay
crisp at high resolution.  Lighting/outline are re-done in 3D by the toon shader.

Coordinates: sprite space (64x64, y down).  A Region maps texel (i, j) to the sprite
point (x0 + (i + 0.5) / S, y0 + (j + 0.5) / S).
"""
import math

import numpy as np

DARK = '#1b1a2e'
WHITE = '#ffffff'
MOUTH_IN = '#8a2838'
TONGUE = '#e8687a'


def hex_rgb(h):
    h = (h or '#ff00ff').strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    except ValueError:
        return np.array([1.0, 0.0, 1.0])


def col(c, pal):
    if isinstance(c, (int, float)):
        v = int(c)
        return '#%06x' % (v & 0xffffff)
    if pal and c in pal and isinstance(pal[c], str):
        return pal[c]
    return c if isinstance(c, str) and c.startswith('#') else '#ff00ff'


class Region:
    def __init__(self, x0, y0, x1, y1, S, mult=1):
        self.S = S
        self.x0, self.y0 = x0, y0
        self.x1, self.y1 = x1, y1
        self.w = max(1, int(math.ceil((x1 - x0) * S)))
        self.h = max(1, int(math.ceil((y1 - y0) * S)))
        self.w = -(-self.w // mult) * mult      # multiples of the supersampling factor
        self.h = -(-self.h // mult) * mult
        xs = x0 + (np.arange(self.w) + 0.5) / S
        ys = y0 + (np.arange(self.h) + 0.5) / S
        self.X, self.Y = np.meshgrid(xs, ys)   # [h, w]


# ----------------------------------------------------------------------------- coverage masks
def _seg(X, Y, ax, ay, bx, by):
    ex, ey = bx - ax, by - ay
    l2 = ex * ex + ey * ey
    t = np.zeros_like(X) if l2 < 1e-12 else np.clip(((X - ax) * ex + (Y - ay) * ey) / l2, 0, 1)
    return np.hypot(X - (ax + ex * t), Y - (ay + ey * t)), t


def mask_ellipse(R, x, y, rx, ry, rot_deg=0.0):
    rot = math.radians(rot_deg or 0.0)
    c, s = math.cos(rot), math.sin(rot)
    dx, dy = R.X - x, R.Y - y
    u = (dx * c + dy * s) / rx
    v = (-dx * s + dy * c) / ry
    return u * u + v * v <= 1.0


def mask_capsule(R, x1, y1, x2, y2, r1, r2):
    d, t = _seg(R.X, R.Y, x1, y1, x2, y2)
    return d <= r1 + (r2 - r1) * t


def mask_poly(R, pts):
    X, Y = R.X, R.Y
    inside = np.zeros(X.shape, dtype=bool)
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if yi != yj:
            inside ^= ((yi > Y) != (yj > Y)) & (X < (xj - xi) * (Y - yi) / (yj - yi) + xi)
        j = i
    return inside


def stroke_segments(pts, w1, w2):
    lens = [math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]) for k in range(len(pts) - 1)]
    total = sum(lens) or 1.0
    out, acc = [], 0.0
    for k, l in enumerate(lens):
        t0, t1 = acc / total, (acc + l) / total
        acc += l
        out.append((pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1],
                    (w1 + (w2 - w1) * t0) * 0.5, (w1 + (w2 - w1) * t1) * 0.5))
    return out


def mask_stroke(R, pts, w1, w2):
    m = np.zeros(R.X.shape, dtype=bool)
    for ax, ay, bx, by, ra, rb in stroke_segments(pts, w1, w2):
        m |= mask_capsule(R, ax, ay, bx, by, ra, rb)
    return m


def pairs(flat):
    return [(float(flat[i]), float(flat[i + 1])) for i in range(0, len(flat) - 1, 2)]


def part_mask(R, p):
    t = p['t']
    if t in ('e', 'spot'):
        rx = float(p.get('rx', 2) or 2)
        ry = float(p.get('ry', rx) or rx)
        return mask_ellipse(R, float(p['x']), float(p['y']), rx, ry, float(p.get('rot', 0) or 0))
    if t == 'c':
        r1 = float(p.get('r1', 2) or 2)
        r2 = float(p['r2']) if p.get('r2') is not None else r1
        return mask_capsule(R, float(p['x1']), float(p['y1']), float(p['x2']), float(p['y2']), r1, r2)
    if t == 'p':
        return mask_poly(R, pairs(p['pts']))
    if t in ('l', 'stripe'):
        w1 = float(p.get('w', 2) or 2)
        w2 = float(p['w2']) if p.get('w2') is not None else w1
        return mask_stroke(R, pairs(p['pts']), w1, w2)
    return np.zeros(R.X.shape, dtype=bool)


def part_bbox(p):
    """(x0, y0, x1, y1) sprite-space bounds of a primitive."""
    t = p['t']
    if t in ('e', 'spot'):
        rx = float(p.get('rx', 2) or 2)
        ry = float(p.get('ry', rx) or rx)
        r = max(rx, ry)
        return (p['x'] - r, p['y'] - r, p['x'] + r, p['y'] + r)
    if t == 'c':
        r1 = float(p.get('r1', 2) or 2)
        r2 = float(p['r2']) if p.get('r2') is not None else r1
        return (min(p['x1'] - r1, p['x2'] - r2), min(p['y1'] - r1, p['y2'] - r2),
                max(p['x1'] + r1, p['x2'] + r2), max(p['y1'] + r1, p['y2'] + r2))
    if 'pts' in p:
        P = pairs(p['pts'])
        w = max(float(p.get('w', 0) or 0), float(p.get('w2', 0) or 0)) * 0.5 if t in ('l', 'stripe') else 0.0
        return (min(q[0] for q in P) - w, min(q[1] for q in P) - w, max(q[0] for q in P) + w, max(q[1] for q in P) + w)
    if t == 'eye':
        s = float(p.get('s', 3) or 3) * 1.6 + 1
        return (p['x'] - s, p['y'] - s, p['x'] + s, p['y'] + s)
    if t == 'mouth':
        w = float(p.get('w', 4) or 4) + 1.5
        return (p['x'] - w, p['y'] - w, p['x'] + w + 1, p['y'] + w * 1.2 + 1)
    return (p.get('x', 32) - 1, p.get('y', 32) - 1, p.get('x', 32) + 2, p.get('y', 32) + 2)


# ----------------------------------------------------------------------------- a paintable layer
class Layer:
    def __init__(self, region):
        self.R = region
        self.rgb = np.zeros((region.h, region.w, 3))
        self.cov = np.zeros((region.h, region.w), dtype=bool)     # the group's own coverage
        self.z = np.full((region.h, region.w), -1e18)

    def put(self, m, color):
        self.rgb[m] = hex_rgb(color)

    # --- facial features (drawFeature port, continuous coords) -------------------
    def draw_feature(self, p, pal):
        R = self.R
        X, Y = R.X, R.Y
        t = p['t']
        dark, white = hex_rgb(DARK), hex_rgb(WHITE)
        x, y = float(p['x']), float(p['y'])
        if t == 'shine':
            m = np.hypot(X - (round(x) + 0.5), Y - (round(y) + 0.5)) <= 0.62
            self.rgb[m] = white
            return
        if t == 'eye':
            sz = max(1.0, float(p.get('s', 3) or 3))
            style = p.get('style') or 'round'
            lk = p.get('look') or [0, 0]
            if style in ('closed', 'happy'):
                w = max(2, round(sz * 1.2))
                pts = []
                for k in range(-w * 4, w * 4 + 1):
                    i = k / 4.0
                    if style == 'happy':
                        yy = -(1 - (i * i) / (w * w)) * sz * 0.5
                    else:
                        yy = (i * i) / (w * w) * sz * 0.4
                    pts.append((x + i + 0.5, y + yy + 0.5))
                self.rgb[mask_stroke(R, pts, 1.15, 1.15)] = dark
                return
            if style == 'dot':
                if sz > 1.5:
                    m = np.hypot(X - (x + 1), Y - (y + 1)) <= 1.05
                else:
                    m = np.hypot(X - (x + 0.5), Y - (y + 0.5)) <= 0.62
                self.rgb[m] = dark
                return
            rx = max(1.0, sz * float(p.get('wide', 0.75) or 0.75))
            ry = max(1.2, sz)
            u = (X - x) / (rx + 0.5)
            v = (Y - y) / (ry + 0.5)
            d = u * u + v * v
            inside = d <= 1.15
            rim = d > 0.72
            scl = white if p.get('sclera', True) is not False else dark
            flip = bool(p.get('flip'))
            drawn = inside.copy()
            fill_dark = inside & rim
            fill_scl = inside & ~rim
            if style == 'angry':
                cut = v < -0.2 + (-u if flip else u) * 0.6
                fill_scl &= ~cut
                drawn = fill_dark | fill_scl
            elif style == 'sleepy':
                cut = v < -0.1
                fill_dark &= ~cut
                fill_scl &= ~cut
                drawn = fill_dark | fill_scl
            elif style == 'sad':
                cut = v < -0.25 + (u if flip else -u) * 0.5
                fill_dark &= ~cut
                fill_scl &= ~cut
                drawn = fill_dark | fill_scl
            self.rgb[fill_dark] = dark
            self.rgb[fill_scl] = scl
            if style == 'sleepy':
                m = (Y >= y) & (Y < y + 1) & (X >= x - rx) & (X < x + rx + 1)
                self.rgb[m] = dark
                drawn |= m
            pr = max(0.8, min(rx, ry) * 0.62)
            px = x + lk[0] * rx * 0.35
            py = y + lk[1] * ry * 0.3 + (ry * 0.4 if style == 'sleepy' else 0)
            dd = ((X - px) ** 2 + (Y - py) ** 2) / ((pr + 0.4) ** 2)
            pm = (dd <= 1) & drawn
            iris = p.get('iris')
            if iris:
                ic = hex_rgb(col(iris, pal))
                # iris: darker at the top, lighter toward the lower rim (a glassy look), black pupil
                g = np.clip((Y - (py - pr)) / (2.0 * pr + 1e-6), 0.0, 1.0)[..., None]
                ig = np.clip(ic[None, None, :] * (0.72 + 0.55 * g), 0.0, 1.0)
                ring = pm & (dd > 0.33)
                self.rgb[ring] = ig[ring]
                self.rgb[pm & (dd <= 0.33)] = dark
            else:
                self.rgb[pm] = dark
            # continuous (not pixel-snapped) glints: a big one up-left, a tiny one low-right
            gr = max(0.5, pr * 0.34)
            hm = np.hypot(X - (px - pr * 0.42), Y - (py - pr * 0.5)) <= gr
            self.rgb[hm & drawn] = white
            if sz >= 2.4:
                hm2 = np.hypot(X - (px + pr * 0.5), Y - (py + pr * 0.5)) <= gr * 0.45
                self.rgb[hm2 & drawn] = white
            return
        if t == 'mouth':
            w = max(1, round(float(p.get('w', 4) or 4)))
            st = p.get('style') or 'smile'
            mc = hex_rgb(col(p['c'], pal)) if p.get('c') else dark
            if st == 'line':
                self.rgb[mask_stroke(R, [(x - w + 0.5, y + 0.5), (x + w + 0.5, y + 0.5)], 1.1, 1.1)] = mc
                return
            if st in ('smile', 'frown'):
                pts = []
                for k in range(-w * 4, w * 4 + 1):
                    i = k / 4.0
                    kk = (i * i) / (w * w) * (w * 0.5)
                    yy = y - kk if st == 'smile' else y + kk - round(w * 0.5)
                    pts.append((x + i + 0.5, yy + 0.5))
                self.rgb[mask_stroke(R, pts, 1.1, 1.1)] = mc
                return
            if st in ('open', 'fang', 'tongue') or True:
                h = max(2, round(w * 0.9))
                i = X - x - 0.5
                j = Y - y - 0.5
                uu = i / (w + 0.5)
                vv = j / (h + 0.5)
                q = uu * uu + (vv - 0.1) ** 2 * 1.2
                m = (q <= 1) & (j >= -0.5) & (np.abs(i) <= w + 0.5) & (j <= h + 0.5)
                edge = (q > 0.6) | (j < 0.5)
                self.rgb[m & edge] = dark
                inner = m & ~edge
                if st == 'tongue':
                    self.rgb[inner] = hex_rgb(TONGUE)
                else:
                    self.rgb[inner & (j > h * 0.55)] = hex_rgb(TONGUE)
                    self.rgb[inner & (j <= h * 0.55)] = hex_rgb(MOUTH_IN)
                if st == 'fang':
                    for fx in (x - w + 1, x + w - 1):
                        fm = (X >= fx) & (X < fx + 1) & (Y >= y + 1) & (Y < y + 3)
                        self.rgb[fm] = white
                return

    def finish(self, fill_color, iters=None):
        """Bleed colours outward from covered texels, then fill the rest."""
        rgb = self.rgb.copy()
        known = self.cov.copy()
        if not known.any():
            rgb[:] = hex_rgb(fill_color)
            return rgb
        iters = iters if iters is not None else int(max(4, self.R.S * 2.5))
        for _ in range(iters):
            acc = np.zeros_like(rgb)
            cnt = np.zeros(known.shape)
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                k = np.roll(known, (dy, dx), axis=(0, 1))
                c = np.roll(rgb, (dy, dx), axis=(0, 1))
                acc += c * k[..., None]
                cnt += k
            new = (~known) & (cnt > 0)
            if not new.any():
                break
            rgb[new] = acc[new] / cnt[new][:, None]
            known = known | new
        if (~known).any():
            # fill the remainder with the mean covered colour
            rgb[~known] = rgb[self.cov].mean(axis=0) if self.cov.any() else hex_rgb(fill_color)
        return rgb


# ----------------------------------------------------------------------------- anti-aliasing + micro detail
def box_down(rgb, painted, ss):
    """Average an (H, W) supersampled layer down by `ss`, un-premultiplying colour by coverage.
    Returns (rgb[h, w, 3], alpha[h, w])."""
    H, W = painted.shape
    h, w = H // ss, W // ss
    a = painted.astype(np.float64)
    prem = rgb * a[..., None]
    A = a.reshape(h, ss, w, ss).sum(axis=(1, 3))
    C = prem.reshape(h, ss, w, ss, 3).sum(axis=(1, 3))
    out = C / np.maximum(A, 1e-9)[..., None]
    return out, A / float(ss * ss)


def value_noise(shape, cell, seed):
    """Smooth 2D value noise in [0, 1]; `cell` is the lattice spacing in texels."""
    rng = np.random.RandomState(seed & 0x7fffffff)
    h, w = shape
    gh, gw = int(h / cell) + 3, int(w / cell) + 3
    g = rng.rand(gh, gw)
    ys = np.arange(h) / cell
    xs = np.arange(w) / cell
    yi, xi = ys.astype(int), xs.astype(int)
    ty, tx = ys - yi, xs - xi
    ty = ty * ty * (3 - 2 * ty)
    tx = tx * tx * (3 - 2 * tx)
    a = g[yi][:, xi] * (1 - tx)[None, :] + g[yi][:, xi + 1] * tx[None, :]
    b = g[yi + 1][:, xi] * (1 - tx)[None, :] + g[yi + 1][:, xi + 1] * tx[None, :]
    return a * (1 - ty)[:, None] + b * ty[:, None]


def micro_detail(rgb, weight, kind, S, seed):
    """Subtle surface texture multiplied into the albedo: fur, scales, rock, skin.
    `weight` (0..1) masks where it applies (0 on eyes / mouths)."""
    if kind in (None, '', 'smooth', 'none'):
        return rgb
    h, w = weight.shape
    if kind == 'fur':
        n = 0.55 * value_noise((h, w), 0.55 * S, seed) + 0.45 * value_noise((h, w), 1.6 * S, seed + 1)
        amp = 0.05
    elif kind == 'scale':
        # hex-ish scale cells: distance to the nearest of jittered lattice points
        cell = 1.5 * S
        rng = np.random.RandomState(seed & 0x7fffffff)
        gy, gx = int(h / cell) + 3, int(w / cell) + 3
        jy = rng.rand(gy, gx)
        jx = rng.rand(gy, gx)
        yy, xx = np.mgrid[0:h, 0:w]
        cy, cx = (yy / cell).astype(int), (xx / cell).astype(int)
        best = np.full((h, w), 9.0)
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                py = np.clip(cy + oy, 0, gy - 1)
                px = np.clip(cx + ox, 0, gx - 1)
                dy = (py + jy[py, px]) - yy / cell
                dx = (px + jx[py, px]) - xx / cell
                best = np.minimum(best, np.sqrt(dx * dx + dy * dy))
        n = np.clip(best * 1.25, 0, 1)
        n = 1.0 - n
        amp = 0.06
    elif kind == 'rock':
        n = 0.5 * value_noise((h, w), 1.2 * S, seed) + 0.3 * value_noise((h, w), 3.0 * S, seed + 1) + \
            0.2 * value_noise((h, w), 0.5 * S, seed + 2)
        amp = 0.10
    elif kind == 'plant':
        n = 0.6 * value_noise((h, w), 1.0 * S, seed) + 0.4 * value_noise((h, w), 0.4 * S, seed + 1)
        amp = 0.06
    elif kind == 'skin':
        n = value_noise((h, w), 1.5 * S, seed)
        amp = 0.04
    else:
        return rgb
    n = (n - n.mean()) / (n.std() + 1e-6) * 0.35
    f = 1.0 + amp * n * weight
    return np.clip(rgb * f[..., None], 0.0, 1.0)
