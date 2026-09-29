"""Python ports of upstream pokemon-claude-red's pixel-art primitives (src/core/gfx.js
hash2/bayer/mix/shade, src/art/palette.js NoiseTex) and battle-background painters
(src/art/battlebg.js), so the Blender battle-stage generator can paint textures and
place 3D props from the *same* procedural recipes the 2D game draws with.

Pure Python + numpy; no bpy dependency (usable standalone for tests).
"""
import math
import numpy as np


# ---------------------------------------------------------------- JS integer semantics
def _i32(v):
    v = int(v) & 0xffffffff
    return v - (1 << 32) if v >= (1 << 31) else v


def _u32(v):
    return int(v) & 0xffffffff


def hash2(x, y, s):
    """gfx.js hash2 with JS double/int32 semantics reproduced exactly."""
    h = float(_i32(math.trunc(x))) * 374761393.0 + float(_i32(math.trunc(y))) * 668265263.0 \
        + float(_i32(float(_i32(math.trunc(s))) * 2147483647.0))
    a = _i32(_i32(h) ^ (_u32(h) >> 13))
    h = float(a) * 1274126177.0
    b = _i32(h) ^ (_u32(h) >> 16)
    return _u32(b) / 4294967296.0


BAYER4 = [(v + 0.5) / 16 for v in [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]]


def bayer(x, y):
    return BAYER4[(int(y) & 3) * 4 + (int(x) & 3)]


class NoiseTex:
    """palette.js NoiseTex: tileable value-noise fbm normalised to 0..1, sampled at ints."""

    def __init__(self, size, period, octaves, seed):
        self.size = size
        self.mask = size - 1
        d = np.zeros((size, size), dtype=np.float64)
        xs = np.arange(size)
        for o in range(octaves):
            p = period << o
            amp = 0.5 ** o
            step = size / p
            fx = xs / step
            xi = np.floor(fx).astype(int)
            tx = fx - xi
            u = tx * tx * (3 - 2 * tx)
            table = np.array([[hash2(i, j, seed + o) for i in range(p)] for j in range(p)])
            # table[j][i] = hash(i, j)
            X0, Y0 = np.meshgrid(xi, xi)  # X0[y][x] = xi[x], Y0[y][x] = xi[y]
            U, V = np.meshgrid(u, u)
            a = table[Y0 % p, X0 % p]
            b = table[Y0 % p, (X0 + 1) % p]
            c = table[(Y0 + 1) % p, X0 % p]
            e = table[(Y0 + 1) % p, (X0 + 1) % p]
            d += (a + (b - a) * U + (c - a) * V + (a - b - c + e) * U * V) * amp
        d = (d - d.min()) / (d.max() - d.min())
        self.data = d

    def at(self, x, y):
        return float(self.data[int(y) & self.mask, int(x) & self.mask])


_N = {}


def N(name):
    if name not in _N:
        spec = {'big': (256, 4, 4, 11), 'mid': (256, 16, 3, 23), 'fine': (128, 32, 2, 37), 'water': (128, 8, 3, 83)}[name]
        _N[name] = NoiseTex(*spec)
    return _N[name]


# ---------------------------------------------------------------- colours (0..255 tuples)
def hexc(s):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def mix(a, b, t):
    if t <= 0:
        return a
    if t >= 1:
        return b
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _to_hsl(c):
    r, g, b = c[0] / 255, c[1] / 255, c[2] / 255
    mx, mn = max(r, g, b), min(r, g, b)
    h = s = 0.0
    l = (mx + mn) / 2
    if mx != mn:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif mx == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h *= 60
    return h, s, l


def _hsl(h, s, l):
    h = ((h % 360) + 360) % 360 / 360

    def f(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p
    if s == 0:
        v = int(l * 255)
        return (v, v, v)
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return (int(f(p, q, h + 1 / 3) * 255), int(f(p, q, h) * 255), int(f(p, q, h - 1 / 3) * 255))


def shade(c, amt):
    """gfx.js shade(): hue-shifted darken (toward blue) / lighten (toward warm yellow)."""
    h, s, l = _to_hsl(c)
    if amt < 0:
        dh = ((250 - h + 540) % 360) - 180
        return _hsl(h + dh * min(1, -amt) * 0.35, min(1, s * (1 - amt * 0.15)), max(0, l + amt * 0.5))
    dh = ((55 - h + 540) % 360) - 180
    return _hsl(h + dh * min(1, amt) * 0.3, max(0, s * (1 - amt * 0.1)), min(1, l + amt * 0.5))


# ---------------------------------------------------------------- surface
class Surf:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), dtype=np.uint8)

    def pset(self, x, y, c):
        x, y = int(math.floor(x)), int(math.floor(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x, 0:3] = c
            self.a[y, x, 3] = 255

    def get(self, x, y):
        return tuple(int(v) for v in self.a[y, x, 0:3])


# ---------------------------------------------------------------- battlebg.js painters
def vgrad(s, y0, y1, c0, c1, steps):
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        for x in range(s.w):
            q = math.floor(t * steps + bayer(x, y) * 0.999) / steps
            s.pset(x, y, mix(c0, c1, min(1, q)))


def cloud_blobs(y0, y1, seed):
    """clouds(): 6 clouds x 5 round blobs -> [(bx, by, r)] in 320x132 px."""
    out = []
    for k in range(6):
        cx = hash2(k, 1, seed) * 360 - 20
        cy = y0 + hash2(k, 2, seed) * (y1 - y0)
        w = 22 + hash2(k, 3, seed) * 30
        blobs = []
        for b in range(5):
            bx = cx + (b - 2) * w * 0.28
            by = cy - math.sin(b / 4 * math.pi) * w * 0.18
            r = w * (0.22 + 0.1 * math.sin(b / 4 * math.pi))
            blobs.append((bx, by, r))
        out.append(blobs)
    return out


def hill_heights(w, base, amp, freq, seed):
    return [base - amp * (0.5 + 0.5 * math.sin(x * freq + seed) * 0.6 + 0.4 * (N('big').at(x * 0.7 + seed * 10, seed) - 0.5))
            for x in range(w)]


def paint_hills(s, base, amp, freq, seed, col, col_hi):
    hs = hill_heights(s.w, base, amp, freq, seed)
    for x in range(s.w):
        h = hs[x]
        for y in range(int(math.floor(h)), s.h):
            s.pset(x, y, col_hi if y < h + 2 else col)
    return hs


def tree_specs(base, seed):
    """treeLine(): [(cx, cy, r)]"""
    out = []
    for k in range(-2, 26):
        cx = k * 14 + hash2(k, 0, seed) * 8
        r = 8 + hash2(k, 1, seed) * 5
        cy = base - r * 0.6 - hash2(k, 2, seed) * 6
        out.append((cx, cy, r))
    return out


def paint_trees(s, base, seed, cols):
    for cx, cy, r in tree_specs(base, seed):
        for y in range(int(math.floor(cy - r)), s.h):
            for x in range(int(math.floor(cx - r)), int(cx + r) + 1):
                if y < cy:
                    d = ((x - cx) ** 2 + (y - cy) ** 2) / (r * r)
                    if d > 1:
                        continue
                elif abs(x - cx) > r:
                    continue
                lit = (x - cx) / r * -0.6 + (y - cy) / r * -0.8
                s.pset(x, y, cols[2] if lit > 0.35 else (cols[1] if lit > -0.2 else cols[0]))


def paint_ground(s, y0, cA, cB, cC, stripe, h_ref=132):
    for y in range(y0, s.h):
        t = (y - y0) / (h_ref - y0)
        for x in range(s.w):
            band = math.floor(math.pow(max(t, 0), 0.7) * stripe + (N('mid').at(x, y * 2) - 0.5) * 0.8)
            c = cA if band % 2 else cB
            if N('fine').at(x * 2, y * 3) > 0.83 and bayer(x, y) > 0.5:
                c = cC
            s.pset(x, y, c)


def paint_platform_top(size, cols, kind):
    """platform(): the ellipse top in local disc space (u, v in -1..1, v>0 = front)."""
    s = Surf(size, size)
    for y in range(size):
        for x in range(size):
            dx = (x + 0.5) / (size / 2) - 1
            dy = (y + 0.5) / (size / 2) - 1
            d = dx * dx + dy * dy
            c = cols[2]
            if d > 0.82:
                c = cols[0] if dy > 0 else cols[3]
            elif d > 0.6:
                c = cols[1] if dy > 0 else cols[2]
            else:
                if kind == 'grass':
                    if hash2(x, y, 5) < 0.12:
                        c = cols[3]
                    elif hash2(x, y, 6) < 0.1:
                        c = cols[1]
                elif kind == 'rock':
                    if N('mid').at(x * 3, y * 5) > 0.65:
                        c = cols[1]
                    elif hash2(x, y, 7) < 0.06:
                        c = cols[3]
                elif kind == 'water':
                    if abs(math.sin(d * 18)) < 0.25:
                        c = cols[3]
                elif kind == 'floor':
                    if (x + y * 2) % 12 == 0:
                        c = cols[1]
                elif kind == 'ice':
                    if (x - y * 2) % 17 == 0:
                        c = cols[3]
                    elif hash2(x, y, 10) < 0.05:
                        c = cols[1]
                elif kind == 'sand':
                    if hash2(x, y, 8) < 0.08:
                        c = cols[3]
                    elif hash2(x, y, 9) < 0.08:
                        c = cols[1]
            s.pset(x, y, c)
    return s


PLATFORM_COLS = {
    'grass': ['#3a7a3a', '#4c9a44', '#62b452', '#8ad466'],
    'forest': ['#28502c', '#346a36', '#468a44', '#62a852'],
    'rock': ['#3a2e2a', '#54443a', '#6a5848', '#88745e'],
    'water': ['#2858a8', '#3a78c8', '#5a98e0', '#a8dcff'],
    'floor': ['#6a7888', '#8898a8', '#a8b8c8', '#d0dce8'],
    'tower': ['#2e2440', '#403456', '#54486a', '#7a6c94'],
    'sand': ['#b89860', '#d0b078', '#e8cc90', '#fbeec0'],
    'mountain': ['#7a6450', '#96806a', '#b09a80', '#d4c0a0'],
    'ice': ['#4e86b0', '#7eb4d8', '#aad8f0', '#eaf8ff'],
    'metal': ['#262c34', '#3c4450', '#56606e', '#8a96a6'],
    'wood': ['#3a2a1e', '#56402c', '#6e5438', '#94744e'],
}
PLATFORM_KIND = {'grass': 'grass', 'forest': 'grass', 'rock': 'rock', 'water': 'water', 'floor': 'floor', 'tower': 'floor',
                 'sand': 'sand', 'mountain': 'sand', 'ice': 'ice', 'metal': 'floor', 'wood': 'floor'}
