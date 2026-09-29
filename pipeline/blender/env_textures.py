"""Procedural, seamless textures for the environment kit (numpy + Pillow only, no bpy).

  python3 pipeline/blender/env_textures.py

Writes
  pipeline/data/env_tex/<name>.png          128x128 (or 256) seamless colour textures painted from upstream's palette
                                            ramps (grass turf, dirt, sand, cobble, plaster, brick, shingles, wood, bark,
                                            stone, cave rock, metal...). gen_tiles / gen_world / gen_battlebg embed them
                                            in the generated .glb materials.
  godot/assets/models/tiles/env_detail.png  the *detail atlas* the overworld ground shader lays over upstream's baked
                                            pixel ground (grass blades + clover, dirt pebbles, sand ripples, pavement
                                            chips, rock, floor speckle, carpet weave, wood grain, water caustics).
                                            Each 64x64 tile is 0.5 grey ("no change") modulation with a faint tint; the
                                            shader multiplies it over the baked colours so the palette survives.
Everything here is generated from noise + hand-rolled strokes; nothing is downloaded.
"""
import json
import math
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
TEX_DIR = os.path.join(ROOT, 'pipeline', 'data', 'env_tex')
DETAIL_PATH = os.path.join(ROOT, 'godot', 'assets', 'models', 'tiles', 'env_detail.png')

# ---------------------------------------------------------------- palettes (src/art/palette.js ramps)
PAL = {
    'grass': ['#173d2f', '#1f5634', '#2f7a3a', '#48a043', '#6cbf4c', '#9dd95f', '#cdef82'],
    'path': ['#6b4d3a', '#8f6a48', '#b58c5c', '#cfa874', '#e2c28e', '#f1dbae', '#fbf0d2'],
    'sand': ['#a8895a', '#c9a872', '#e2c78e', '#f0dca8', '#fff0c8'],
    'pave': ['#4d5068', '#6a6d86', '#81849c', '#a3a6bb', '#c2c4d3', '#dcdde8'],
    'water': ['#122056', '#1b3582', '#2552ad', '#3176d0', '#4d9be6', '#7fc3f3', '#bde6ff', '#ffffff'],
    'leaf': ['#0c2322', '#143a2c', '#1d5433', '#2a723a', '#3c9142', '#5bb04d', '#8bcf5f', '#bfe882'],
    'trunk': ['#3b2418', '#54331f', '#6a3f2e', '#8e5a3a', '#b0774c'],
    'stone': ['#3c3e54', '#5a5c74', '#7b7e95', '#9da0b4', '#c0c3d2'],
    'cream': ['#b8a98e', '#ded0b8', '#f0e6d2', '#fbf6ea'],
    'brick': ['#5e2c28', '#7c3a30', '#94463a', '#b35f47', '#cf8060'],
    'roof_red': ['#5c1c22', '#8f2a2c', '#bb4034', '#dc6244'],
    'roof_blue': ['#1c2c58', '#2c4a90', '#3e6cc0', '#6a98de'],
    'roof_brown': ['#3c2418', '#5c3a26', '#7c5236', '#a0724a'],
    'wood': ['#3e2418', '#5a3524', '#744630', '#9a6340', '#bd8554', '#d8a878'],
    'cave': ['#2a2230', '#3a2e30', '#54443a', '#6a5848', '#8a7660'],
    'metal': ['#1c2029', '#343c48', '#4c5664', '#7a8494', '#a8b2c0'],
    'tower': ['#2c2440', '#4a3e5a', '#6a5a80', '#8e80a6', '#b4a8c8'],
}


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


def ramp(name):
    return np.stack([hexrgb(h) for h in PAL[name]])


def sample_ramp(r, t):
    """t in 0..1 (array) -> RGB by linear interpolation along the ramp r (N,3)."""
    t = np.clip(t, 0, 1) * (len(r) - 1)
    i = np.minimum(t.astype(int), len(r) - 2)
    f = (t - i)[..., None]
    return r[i] * (1 - f) + r[i + 1] * f


# ---------------------------------------------------------------- tileable noise
def pnoise(n, cells, seed, smooth=True):
    """Periodic value noise on an n x n grid, `cells` lattice cells per side -> 0..1."""
    rs = np.random.RandomState(seed)
    lat = rs.rand(cells, cells).astype(np.float32)
    xs = (np.arange(n, dtype=np.float32) + 0.5) * cells / n
    xi = np.floor(xs).astype(int)
    f = xs - xi
    if smooth:
        f = f * f * f * (f * (f * 6 - 15) + 10)
    x0, x1 = xi % cells, (xi + 1) % cells
    fx = f[None, :]
    fy = f[:, None]
    a = lat[np.ix_(x0, x0)]
    b = lat[np.ix_(x0, x1)]
    c = lat[np.ix_(x1, x0)]
    d = lat[np.ix_(x1, x1)]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, base, octaves, seed, gain=0.5):
    out = np.zeros((n, n), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out += pnoise(n, base * (2 ** o), seed + 31 * o) * amp
        tot += amp
        amp *= gain
    out /= tot
    lo, hi = out.min(), out.max()
    return (out - lo) / max(1e-6, hi - lo)


def warp(img, n, amt, seed, cells=4):
    """Domain-warp a (n,n[,c]) image with periodic noise."""
    dx = (pnoise(n, cells, seed) - 0.5) * 2 * amt
    dy = (pnoise(n, cells, seed + 7) - 0.5) * 2 * amt
    ys, xs = np.mgrid[0:n, 0:n]
    xi = ((xs + dx).astype(int)) % n
    yi = ((ys + dy).astype(int)) % n
    return img[yi, xi]


def stamp(img, x, y, patch, mode='add', k=1.0):
    """Blit a small 2D patch at (x, y) with wrap-around."""
    n = img.shape[0]
    ph, pw = patch.shape[:2]
    ys = (np.arange(ph) + y) % n
    xs = (np.arange(pw) + x) % n
    sub = img[np.ix_(ys, xs)]
    if mode == 'add':
        sub = sub + patch * k
    elif mode == 'max':
        sub = np.maximum(sub, patch * k)
    elif mode == 'set':
        m = patch != 0
        sub = np.where(m, patch * k, sub)
    img[np.ix_(ys, xs)] = sub


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def shade_lum(rgb, lum, k=1.0):
    """Multiply an RGB image by (0.5 + lum-0.5)*... i.e. lum centred at 0.5 -> 1 +- k."""
    return rgb * (1.0 + (lum[..., None] - 0.5) * 2.0 * k)


# ---------------------------------------------------------------- detail modulation tiles (0.5 = neutral), 64x64
DN = 64


def d_grass(seed=1):
    rs = np.random.RandomState(seed)
    h = 0.5 + (fbm(DN, 3, 3, seed) - 0.5) * 0.09
    h += (pnoise(DN, 32, seed + 3) - 0.5) * 0.06
    # blades: short vertical strokes, light (lit tips) and dark (gaps)
    for _ in range(46):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        ln = rs.randint(2, 5)
        lean = rs.choice([-1, 0, 0, 1])
        light = rs.rand() < 0.62
        for i in range(ln):
            t = i / max(1, ln - 1)
            v = (0.16 * (0.4 + t) if light else -0.15 * (1.1 - t))
            stamp(h, x + int(lean * t * 1.5), y - i, np.array([[v]], np.float32))
    # clover: 3 tiny lobes
    for _ in range(9):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        for dx, dy in ((0, 0), (1, 0), (0, 1)):
            stamp(h, x + dx, y + dy, np.array([[-0.13]], np.float32))
        stamp(h, x, y - 1, np.array([[0.10]], np.float32))
    # tiny flowers/seed heads
    for _ in range(3):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        stamp(h, x, y, np.array([[0.34]], np.float32))
    rgb = np.stack([h, h * 1.01, h * 0.99], -1)
    return rgb


def d_path(seed=2):
    rs = np.random.RandomState(seed)
    h = 0.5 + (fbm(DN, 4, 3, seed) - 0.5) * 0.08 + (pnoise(DN, 32, seed + 1) - 0.5) * 0.07
    # scuffs / footprints streaks
    streak = warp(pnoise(DN, 6, seed + 9)[:, :], DN, 3, seed + 5)
    h += (streak - 0.5) * 0.04
    # pebbles with highlight upper-left, shadow lower-right
    for _ in range(11):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        w, hh = rs.randint(2, 5), rs.randint(2, 4)
        yy, xx = np.mgrid[0:hh + 2, 0:w + 2]
        e = ((xx - (w + 1) / 2) / (w / 2 + 0.3)) ** 2 + ((yy - (hh + 1) / 2) / (hh / 2 + 0.3)) ** 2
        body = (e < 1).astype(np.float32)
        shade = np.where(xx + yy < (w + hh) / 2 + 0.4, 0.10, -0.12)
        stamp(h, x, y, body * (0.02 + shade))
        # contact shadow underneath
        sh = np.roll(np.roll(body, 1, 0), 1, 1)
        stamp(h, x, y, (sh > 0) * (body == 0) * -0.10)
    for _ in range(40):  # grit
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[rs.choice([-0.10, 0.09])]], np.float32))
    # hairline crack
    x, y = rs.randint(0, DN), rs.randint(0, DN)
    for i in range(14):
        stamp(h, x, y, np.array([[-0.16]], np.float32))
        x += rs.choice([-1, 0, 1]) + 1
        y += rs.choice([0, 1])
    return np.stack([h * 1.01, h, h * 0.98], -1)


def d_sand(seed=3):
    rs = np.random.RandomState(seed)
    ys, xs = np.mgrid[0:DN, 0:DN].astype(np.float32)
    w = warp(np.sin((xs * 0.55 + ys * 0.35) * 2 * math.pi / DN * 4)[..., None].repeat(1, 2)[..., 0], DN, 6, seed)
    h = 0.5 + w * 0.05 + (fbm(DN, 4, 3, seed) - 0.5) * 0.12
    for _ in range(80):
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[rs.choice([-0.08, 0.08])]], np.float32))
    for _ in range(4):  # shell flecks
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[0.22, 0.14]], np.float32))
    return np.stack([h * 1.02, h, h * 0.95], -1)


def d_pave(seed=4):
    rs = np.random.RandomState(seed)
    h = 0.5 + (fbm(DN, 6, 3, seed) - 0.5) * 0.14 + (pnoise(DN, 32, seed + 1) - 0.5) * 0.09
    for _ in range(60):
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[rs.choice([-0.10, 0.11])]], np.float32))
    # chips: 2px notch with light lower edge
    for _ in range(6):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        stamp(h, x, y, np.array([[-0.16, -0.16], [0.0, 0.10]], np.float32))
    # cracks: random walks
    for c in range(2):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        d = [(1, 0), (0, 1), (1, 1)][rs.randint(0, 3)]
        for i in range(rs.randint(10, 22)):
            stamp(h, x, y, np.array([[-0.20]], np.float32))
            x += d[0] + (rs.randint(-1, 2) if d[0] == 0 else 0)
            y += d[1] + (rs.randint(-1, 2) if d[1] == 0 else 0)
    rgb = np.stack([h, h, h * 1.03], -1)
    # moss in places
    mo = np.clip((fbm(DN, 4, 2, seed + 40) - 0.72) * 5, 0, 1) * 0.5
    rgb[..., 0] -= mo * 0.08
    rgb[..., 1] += mo * 0.05
    rgb[..., 2] -= mo * 0.10
    return rgb


def d_rock(seed=5):
    rs = np.random.RandomState(seed)
    n1 = fbm(DN, 3, 4, seed)
    h = 0.5 + (n1 - 0.5) * 0.30
    # strata: warped horizontal banding
    ys = np.arange(DN, dtype=np.float32)[:, None].repeat(DN, 1)
    band = np.sin((ys + warp(n1 * 8, DN, 5, seed + 2)) * 2 * math.pi / DN * 5)
    h += band * 0.045
    for _ in range(50):
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[rs.choice([-0.12, 0.10])]], np.float32))
    for c in range(3):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        for i in range(rs.randint(6, 16)):
            stamp(h, x, y, np.array([[-0.20]], np.float32))
            x += rs.randint(-1, 2)
            y += 1
    return np.stack([h * 1.02, h, h * 0.97], -1)


def d_floor(seed=6):
    rs = np.random.RandomState(seed)
    h = 0.5 + (pnoise(DN, 16, seed) - 0.5) * 0.07 + (pnoise(DN, 32, seed + 1) - 0.5) * 0.06
    # terrazzo / polished-tile flecks
    for _ in range(26):
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[rs.choice([-0.16, 0.14])]], np.float32))
    # faint gloss streak
    ys, xs = np.mgrid[0:DN, 0:DN].astype(np.float32)
    h += np.clip(1 - np.abs(((xs + ys) % DN) - DN * 0.5) / 7.0, 0, 1) * 0.045
    return np.stack([h, h, h], -1)


def d_carpet(seed=7):
    rs = np.random.RandomState(seed)
    ys, xs = np.mgrid[0:DN, 0:DN]
    weave = (((xs // 1) + (ys // 1)) % 2).astype(np.float32) * 0.07 + (((xs // 2) % 2) ^ ((ys // 2) % 2)) * 0.05
    h = 0.5 + weave - 0.06 + (pnoise(DN, 8, seed) - 0.5) * 0.10
    for _ in range(40):
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[rs.choice([-0.09, 0.09])]], np.float32))
    return np.stack([h, h, h], -1)


def d_wood(seed=8):
    rs = np.random.RandomState(seed)
    ys, xs = np.mgrid[0:DN, 0:DN].astype(np.float32)
    g = pnoise(DN, 2, seed)  # coarse along x, stretched along y for grain
    rows = np.zeros((DN, DN), np.float32)
    lat = rs.rand(DN // 2).astype(np.float32)
    grain = np.repeat(lat, 2)[None, :].repeat(DN, 0)
    grain = warp(grain, DN, 2.2, seed + 3, cells=3)
    h = 0.5 + (grain - 0.5) * 0.18 + (pnoise(DN, 32, seed + 1) - 0.5) * 0.05
    h += (fbm(DN, 3, 2, seed + 5) - 0.5) * 0.10
    # plank seams every 16 px, offset butt joints
    for k in range(4):
        h[k * 16, :] -= 0.14
        h[k * 16 + 1, :] += 0.05
    for k in range(4):
        x = (k * 23 + 9) % DN
        h[k * 16:(k + 1) * 16, x] -= 0.13
    # knots
    for _ in range(2):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        for r, v in ((3, 0.07), (2, -0.14), (1, -0.20)):
            yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
            stamp(h, x - r, y - r, ((xx / (r * 1.6)) ** 2 + (yy / r) ** 2 < 1) * v)
    return np.stack([h * 1.04, h, h * 0.94], -1)


def d_tower(seed=9):
    rs = np.random.RandomState(seed)
    h = 0.5 + (fbm(DN, 5, 3, seed) - 0.5) * 0.18 + (pnoise(DN, 32, seed + 1) - 0.5) * 0.08
    for _ in range(50):
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[rs.choice([-0.11, 0.10])]], np.float32))
    for c in range(2):
        x, y = rs.randint(0, DN), rs.randint(0, DN)
        for i in range(rs.randint(8, 18)):
            stamp(h, x, y, np.array([[-0.2]], np.float32))
            x += rs.randint(-1, 2)
            y += 1
    return np.stack([h * 0.98, h * 0.97, h * 1.05], -1)


def d_water(seed=10):
    """Caustic net: interference of two warped ridged noises -> bright web on 0.5."""
    a = np.abs(fbm(DN, 3, 3, seed) - 0.5) * 2
    b = np.abs(fbm(DN, 4, 3, seed + 11) - 0.5) * 2
    web = np.clip(1 - np.minimum(a, b) * 9, 0, 1)
    h = 0.5 + web * 0.34 - 0.06 + (pnoise(DN, 16, seed + 2) - 0.5) * 0.06
    return np.stack([h * 0.97, h * 1.0, h * 1.05], -1)


def d_cliff(seed=11):
    rs = np.random.RandomState(seed)
    n1 = fbm(DN, 3, 4, seed)
    h = 0.5 + (n1 - 0.5) * 0.26
    ys = np.arange(DN, dtype=np.float32)[:, None].repeat(DN, 1)
    h += np.sin((ys + warp(n1 * 10, DN, 6, seed + 2)) * 2 * math.pi / DN * 4) * 0.06
    for _ in range(40):
        stamp(h, rs.randint(0, DN), rs.randint(0, DN), np.array([[rs.choice([-0.12, 0.11])]], np.float32))
    return np.stack([h, h * 0.98, h * 0.95], -1)


DETAIL_TILES = ['grass', 'path', 'sand', 'pave', 'rock', 'floor', 'carpet', 'wood', 'tower', 'water', 'cliff']
DETAIL_FN = {'grass': d_grass, 'path': d_path, 'sand': d_sand, 'pave': d_pave, 'rock': d_rock, 'floor': d_floor,
             'carpet': d_carpet, 'wood': d_wood, 'tower': d_tower, 'water': d_water, 'cliff': d_cliff}
CELL = DN + 4   # 2 px gutter of wrapped content on each side so linear filtering never bleeds


def build_detail_atlas():
    cols = 6
    rows = (len(DETAIL_TILES) + cols - 1) // cols
    W, H = cols * CELL, rows * CELL
    atlas = np.full((H, W, 3), 0.5, np.float32)
    for i, name in enumerate(DETAIL_TILES):
        t = np.clip(DETAIL_FN[name](), 0, 1)
        pad = np.pad(t, ((2, 2), (2, 2), (0, 0)), mode='wrap')
        cx, cy = (i % cols) * CELL, (i // cols) * CELL
        atlas[cy:cy + CELL, cx:cx + CELL] = pad
    os.makedirs(os.path.dirname(DETAIL_PATH), exist_ok=True)
    to_img(atlas).save(DETAIL_PATH, optimize=True)
    meta = {'tile': DN, 'cell': CELL, 'cols': cols, 'rows': rows, 'names': DETAIL_TILES}
    with open(os.path.join(os.path.dirname(DETAIL_PATH), 'env_detail.json'), 'w') as fh:
        json.dump(meta, fh)
    print('detail atlas', W, H, DETAIL_PATH)


# ---------------------------------------------------------------- colour textures for models (N x N, seamless)
TN = 128


def t_turf(seed=21, n=TN):
    rs = np.random.RandomState(seed)
    r = ramp('grass')
    base = 0.34 + fbm(n, 3, 3, seed) * 0.30 + (pnoise(n, 32, seed + 1) - 0.5) * 0.10
    img = sample_ramp(r, base)
    for _ in range(int(n * n / 40)):
        x, y = rs.randint(0, n), rs.randint(0, n)
        ln = rs.randint(3, 7)
        lean = rs.choice([-1, 0, 1])
        light = rs.rand() < 0.5
        col = r[5 if light else 1] * (0.9 + rs.rand() * 0.2)
        for i in range(ln):
            yy, xx = (y - i) % n, (x + int(lean * i * 0.4)) % n
            img[yy, xx] = img[yy, xx] * 0.35 + col * 0.65
    for _ in range(6):   # clover patch
        x, y = rs.randint(0, n), rs.randint(0, n)
        for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 1), (1, 1)):
            img[(y + dy) % n, (x + dx) % n] = r[2] * 0.85
    return img


def t_dirt(seed=22, n=TN):
    rs = np.random.RandomState(seed)
    r = ramp('path')
    base = 0.40 + fbm(n, 4, 3, seed) * 0.30 + (pnoise(n, 32, seed + 1) - 0.5) * 0.10
    img = sample_ramp(r, base)
    for _ in range(24):
        x, y = rs.randint(0, n), rs.randint(0, n)
        w, hh = rs.randint(3, 7), rs.randint(2, 5)
        yy, xx = np.mgrid[0:hh + 2, 0:w + 2]
        e = ((xx - (w + 1) / 2) / (w / 2 + 0.3)) ** 2 + ((yy - (hh + 1) / 2) / (hh / 2 + 0.3)) ** 2
        body = e < 1
        lit = xx + yy < (w + hh) / 2 + 0.4
        col = np.where(lit[..., None], r[4], r[2]) * (0.92 + rs.rand() * 0.14)
        sub = img[np.ix_((np.arange(hh + 2) + y) % n, (np.arange(w + 2) + x) % n)]
        img[np.ix_((np.arange(hh + 2) + y) % n, (np.arange(w + 2) + x) % n)] = np.where(body[..., None], col, sub)
    return img


def t_sand(seed=23, n=TN):
    r = ramp('sand')
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    rip = warp(np.sin((xs * 0.6 + ys * 0.4) * 2 * math.pi / n * 6), n, 8, seed)
    base = 0.5 + rip * 0.08 + (fbm(n, 4, 3, seed) - 0.5) * 0.25
    img = sample_ramp(r, base)
    rs = np.random.RandomState(seed)
    for _ in range(int(n * n * 0.03)):
        img[rs.randint(0, n), rs.randint(0, n)] *= rs.choice([0.9, 1.06])
    return np.clip(img, 0, 1)


def t_cobble(seed=24, n=TN):
    """Irregular cobble / paving stones with grout."""
    rs = np.random.RandomState(seed)
    r = ramp('pave')
    pts = rs.rand(28, 2) * n
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    best = np.full((n, n), 1e9, np.float32)
    second = np.full((n, n), 1e9, np.float32)
    idx = np.zeros((n, n), int)
    for k, (px, py) in enumerate(pts):
        best_d = None
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                d = (xs - px - ox) ** 2 + (ys - py - oy) ** 2
                upd = d < best
                second = np.where(upd, best, np.minimum(second, d))
                idx = np.where(upd, k, idx)
                best = np.where(upd, d, best)
    edge = (np.sqrt(second) - np.sqrt(best))
    tone = rs.rand(28) * 0.5 + 0.35
    base = tone[idx] + (fbm(n, 6, 3, seed) - 0.5) * 0.18
    img = sample_ramp(r, base)
    grout = np.clip(1 - edge / 2.6, 0, 1)[..., None]
    img = img * (1 - grout * 0.6) + r[0] * grout * 0.6
    hi = np.clip((edge - 2.6) / 2.0, 0, 1)
    img = np.where((hi < 1)[..., None] & (edge > 2.6)[..., None], img * 1.06, img)
    return np.clip(img, 0, 1)


def t_brick(seed=25, n=TN):
    rs = np.random.RandomState(seed)
    r = ramp('brick')
    img = np.zeros((n, n, 3), np.float32)
    rh, rw = 16, 32
    for row in range(n // rh):
        off = (rw // 2) if row % 2 else 0
        for col in range(n // rw + 1):
            x0 = (col * rw + off) % n
            tone = 0.30 + rs.rand() * 0.55
            ys = np.arange(row * rh + 1, row * rh + rh - 1) % n
            xs = (np.arange(x0 + 1, x0 + rw - 1)) % n
            block = sample_ramp(r, np.full((len(ys), len(xs)), tone) + (pnoise(n, 24, seed + row)[np.ix_(ys, xs)] - 0.5) * 0.25)
            block[0] *= 1.10
            block[-1] *= 0.82
            img[np.ix_(ys, xs)] = block
    mortar = ramp('cream')[0] * 0.85
    mask = np.zeros((n, n), bool)
    for row in range(n // rh):
        mask[row * rh, :] = True
        mask[(row * rh + rh - 1) % n, :] = True
        off = (rw // 2) if row % 2 else 0
        for col in range(n // rw + 1):
            mask[row * rh:(row + 1) * rh, (col * rw + off) % n] = True
            mask[row * rh:(row + 1) * rh, (col * rw + off + rw - 1) % n] = True
    img[mask] = mortar * (0.92 + (pnoise(n, 32, seed)[mask] - 0.5)[:, None] * 0.2)
    return np.clip(img, 0, 1)


def t_plaster(seed=26, n=TN):
    r = ramp('cream')
    base = 0.55 + (fbm(n, 3, 4, seed) - 0.5) * 0.30 + (pnoise(n, 64, seed + 1) - 0.5) * 0.12
    img = sample_ramp(r, base)
    rs = np.random.RandomState(seed)
    for _ in range(3):   # hairline crack
        x, y = rs.randint(0, n), rs.randint(0, n)
        for i in range(rs.randint(10, 24)):
            img[y % n, x % n] *= 0.72
            x += rs.randint(-1, 2)
            y += 1
    return np.clip(img, 0, 1)


def _shingle(name, seed, n=TN):
    rs = np.random.RandomState(seed)
    r = ramp(name)
    img = np.zeros((n, n, 3), np.float32)
    rh, rw = 16, 16
    for row in range(n // rh):
        off = (rw // 2) if row % 2 else 0
        for col in range(n // rw + 1):
            x0 = (col * rw + off) % n
            tone = 0.35 + rs.rand() * 0.5
            ys = np.arange(row * rh, row * rh + rh) % n
            xs = np.arange(x0, x0 + rw) % n
            t = np.full((rh, rw), tone, np.float32)
            yy = np.arange(rh)[:, None].repeat(rw, 1)
            t += (yy / rh - 0.5) * -0.30          # darker toward the exposed lower edge
            blk = sample_ramp(r, t + (pnoise(n, 32, seed + row)[np.ix_(ys, xs)] - 0.5) * 0.15)
            blk[-2:] *= 0.62                      # shadow line under each row
            blk[:, 0] *= 0.7
            blk[0] *= 1.12
            # rounded tab corners
            blk[-1, 0] = blk[-1, -1] = r[0]
            img[np.ix_(ys, xs)] = blk
    return np.clip(img, 0, 1)


def t_shingle_red(seed=27, n=TN):
    return _shingle('roof_red', seed, n)


def t_shingle_blue(seed=28, n=TN):
    return _shingle('roof_blue', seed, n)


def t_shingle_brown(seed=29, n=TN):
    return _shingle('roof_brown', seed, n)


def t_wood(seed=30, n=TN):
    rs = np.random.RandomState(seed)
    r = ramp('wood')
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    lat = rs.rand(n // 2).astype(np.float32)
    grain = np.repeat(lat, 2)[None, :].repeat(n, 0)
    grain = warp(grain, n, 3.0, seed + 2, cells=3)
    base = 0.45 + (grain - 0.5) * 0.35 + (fbm(n, 3, 2, seed) - 0.5) * 0.15
    img = sample_ramp(r, base)
    for k in range(n // 32):
        img[k * 32, :] *= 0.62
        img[k * 32 + 1, :] *= 1.10
        x = (k * 47 + 13) % n
        img[k * 32:(k + 1) * 32, x] *= 0.68
    for _ in range(2):
        x, y = rs.randint(0, n), rs.randint(0, n)
        for rr, v in ((5, 0.9), (3, 0.72), (1, 0.55)):
            yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]
            m = (xx / (rr * 1.6)) ** 2 + (yy / rr) ** 2 < 1
            sub = img[np.ix_((np.arange(2 * rr + 1) + y - rr) % n, (np.arange(2 * rr + 1) + x - rr) % n)]
            img[np.ix_((np.arange(2 * rr + 1) + y - rr) % n, (np.arange(2 * rr + 1) + x - rr) % n)] = np.where(m[..., None], sub * v, sub)
    return np.clip(img, 0, 1)


def t_bark(seed=31, n=TN):
    rs = np.random.RandomState(seed)
    r = ramp('trunk')
    lat = rs.rand(n // 4).astype(np.float32)
    strip = np.repeat(lat, 4)[None, :].repeat(n, 0)
    strip = warp(strip, n, 4.0, seed + 2, cells=3)
    ys = np.arange(n, dtype=np.float32)[:, None].repeat(n, 1)
    base = 0.38 + (strip - 0.5) * 0.32 + (pnoise(n, 6, seed) - 0.5) * 0.25
    img = sample_ramp(r, base)
    # vertical furrows
    for _ in range(n // 4):
        x = rs.randint(0, n)
        y0, ln = rs.randint(0, n), rs.randint(14, 44)
        for i in range(ln):
            img[(y0 + i) % n, (x + int(math.sin(i * 0.2 + x) * 1.2)) % n] *= 0.62
    return np.clip(img, 0, 1)


def t_stone(seed=32, n=TN):
    """Cut stone blocks with chiselled edges (walls, statues, gym floor)."""
    rs = np.random.RandomState(seed)
    r = ramp('stone')
    img = np.zeros((n, n, 3), np.float32)
    rh = 32
    for row in range(n // rh):
        off = 32 if row % 2 else 0
        for col in range(2):
            x0 = (col * 64 + off) % n
            tone = 0.35 + rs.rand() * 0.4
            ys = np.arange(row * rh, row * rh + rh) % n
            xs = np.arange(x0, x0 + 64) % n
            blk = sample_ramp(r, np.full((rh, 64), tone) + (fbm(n, 6, 3, seed + row * 2 + col)[np.ix_(ys, xs)] - 0.5) * 0.35)
            blk[0] *= 1.16
            blk[-1] *= 0.62
            blk[:, 0] *= 1.08
            blk[:, -1] *= 0.66
            img[np.ix_(ys, xs)] = blk
    return np.clip(img, 0, 1)


def t_cave(seed=33, n=TN):
    r = ramp('cave')
    n1 = fbm(n, 3, 4, seed)
    ys = np.arange(n, dtype=np.float32)[:, None].repeat(n, 1)
    base = 0.30 + n1 * 0.5 + np.sin((ys + warp(n1 * 10, n, 6, seed + 3)) * 2 * math.pi / n * 6) * 0.05
    img = sample_ramp(r, base)
    rs = np.random.RandomState(seed)
    for c in range(4):
        x, y = rs.randint(0, n), rs.randint(0, n)
        for i in range(rs.randint(10, 30)):
            img[y % n, x % n] *= 0.6
            x += rs.randint(-1, 2)
            y += 1
    return np.clip(img, 0, 1)


def t_metal(seed=34, n=TN):
    r = ramp('metal')
    rs = np.random.RandomState(seed)
    base = 0.45 + (pnoise(n, 64, seed) - 0.5) * 0.15 + (fbm(n, 2, 2, seed + 4) - 0.5) * 0.15
    img = sample_ramp(r, base)
    img[0:2] *= 0.6
    img[:, 0:2] *= 0.6
    img[2:3] *= 1.25
    for (x, y) in ((6, 6), (n - 8, 6), (6, n - 8), (n - 8, n - 8)):   # rivets
        img[y:y + 3, x:x + 3] = r[4]
        img[y + 2, x:x + 3] *= 0.6
    for _ in range(30):
        img[rs.randint(0, n), rs.randint(0, n)] *= 0.8
    return np.clip(img, 0, 1)


def t_water(seed=35, n=TN):
    r = ramp('water')
    a = np.abs(fbm(n, 3, 3, seed) - 0.5) * 2
    b = np.abs(fbm(n, 4, 3, seed + 11) - 0.5) * 2
    web = np.clip(1 - np.minimum(a, b) * 8, 0, 1)
    base = 0.36 + fbm(n, 3, 3, seed + 3) * 0.22 + web * 0.36
    return sample_ramp(r, base)


def t_tile(seed=36, n=TN):
    """Indoor floor tile."""
    r = ramp('cream')
    img = np.zeros((n, n, 3), np.float32)
    rs = np.random.RandomState(seed)
    for i in range(2):
        for j in range(2):
            t = 0.55 + rs.rand() * 0.25
            blk = sample_ramp(r, np.full((64, 64), t) + (pnoise(n, 64, seed + i * 2 + j)[:64, :64] - 0.5) * 0.15)
            blk[0] *= 0.66
            blk[:, 0] *= 0.8
            blk[1] *= 1.1
            img[i * 64:(i + 1) * 64, j * 64:(j + 1) * 64] = blk
    return np.clip(img, 0, 1)


TEXTURES = {
    'turf': t_turf, 'dirt': t_dirt, 'sand': t_sand, 'cobble': t_cobble, 'brick': t_brick, 'plaster': t_plaster,
    'shingle_red': t_shingle_red, 'shingle_blue': t_shingle_blue, 'shingle_brown': t_shingle_brown,
    'wood': t_wood, 'bark': t_bark, 'stone': t_stone, 'cave': t_cave, 'metal': t_metal, 'water': t_water,
    'tile': t_tile,
}


def build_textures():
    os.makedirs(TEX_DIR, exist_ok=True)
    for name, fn in TEXTURES.items():
        img = np.clip(fn(), 0, 1)
        to_img(img).save(os.path.join(TEX_DIR, name + '.png'), optimize=True)
    print('textures:', ', '.join(TEXTURES))


def tex_path(name):
    return os.path.join(TEX_DIR, name + '.png')


if __name__ == '__main__':
    build_textures()
    build_detail_atlas()
